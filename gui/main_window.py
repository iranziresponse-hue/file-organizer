"""Native desktop window for Orch.

The real Django dashboard is embedded in a taskbar-visible pywebview window.
The window stays frameless so Orch can keep its slim in-app titlebar, but all
window actions are backed by native Win32 fallbacks so resize/minimize behave
like normal desktop controls.
"""

import sys
import threading
import time

import webview

from .server import dashboard_url

# Matches base.html's light-theme --bg-deep (the app's default theme). A
# mismatched window background would flash visibly for an instant on load
# since there's a brief gap between the window appearing and the page's
# own CSS painting.
PAGE_BACKGROUND = "#F0F2F5"


class _JSApi:
    """Exposed to the page as window.pywebview.api.<name>(). Only ever
    called from the custom titlebar's own buttons and keyboard shortcuts
    (see base.html), never by arbitrary page content."""

    def __init__(self, window_holder):
        self._window_holder = window_holder

    def minimize(self):
        self._window_holder.minimize()

    def toggle_maximize(self):
        # Queries the real OS window state (IsZoomed) instead of trusting a
        # separately-maintained is_maximized flag -- a shadow copy of state
        # that lives outside the one place (Windows itself) actually
        # tracking it. Any path that changes WindowState without going
        # through this exact flag (the resize border's own drag-to-maximize
        # via Windows' native double-click-titlebar handling, Aero Snap, a
        # future feature) would desync a shadow flag silently; querying
        # reality directly can't drift.
        holder = self._window_holder
        if holder.is_maximized():
            holder.restore()
        else:
            holder.maximize()
        return holder.is_maximized()

    def toggle_fullscreen(self):
        self._window_holder.window.toggle_fullscreen()
        self._window_holder.is_fullscreen = not self._window_holder.is_fullscreen
        self._window_holder.schedule_repaint_nudge()
        return self._window_holder.is_fullscreen

    def close_to_tray(self):
        # Same behavior as clicking the OS close button on the old framed
        # window: hide, don't quit (see _on_closing below).
        self._window_holder.window.hide()


class OrchMainWindow:
    """Taskbar-visible window showing the live dashboard. Closing it hides
    the window rather than quitting the app -- the tray icon and the
    background watcher keep running either way (see gui/tray.py)."""

    def __init__(self, watcher_controller=None):
        self.watcher = watcher_controller
        self.is_fullscreen = False
        # No initial url: the dashboard server may not have finished binding
        # its socket yet when this window is created (see gui/app.py's
        # startup sequence), and loading before it's ready would show a
        # connection-refused page for an instant. app.py loads the real URL
        # once it has confirmed the server actually answers.
        self.window = webview.create_window(
            "Orch",
            width=1280,
            height=820,
            min_size=(640, 460),
            background_color=PAGE_BACKGROUND,
            hidden=True,
            frameless=True,
            resizable=True,
            easy_drag=False,
            js_api=_JSApi(self),
        )
        self.window.events.closing += self._on_closing
        self.window.events.shown += self._on_shown
        self._resize_border_installed = False

    def _on_shown(self):
        # frameless=True drops Windows' own resize grips entirely (see
        # gui/resize_border.py), so they're added back here once the real
        # native window exists. events.shown can in principle fire more
        # than once for the same window (e.g. some backends refire it after
        # a restore), so this is guarded to install at most once.
        if self._resize_border_installed or sys.platform != "win32":
            return
        self._resize_border_installed = True
        try:
            from . import resize_border

            hwnd = self._native_hwnd()
            if hwnd:
                resize_border.install(hwnd)
        except Exception:
            pass

    def show(self):
        self.window.show()
        try:
            self.restore()
        except Exception:
            pass

    def minimize(self):
        # pywebview's own minimize()/maximize()/restore() set the WinForms
        # Form's WindowState property through a proper Invoke() marshal to
        # the UI thread -- that's the SAME property toggle_fullscreen()
        # reads and writes for its own bookkeeping (old_state, is_fullscreen
        # etc). Calling raw ShowWindow() instead changes the real OS window
        # state without updating that property, so the two mechanisms drift
        # out of sync with each other -- this was the actual cause behind
        # minimize/maximize/fullscreen intermittently "doing nothing": not
        # a broken click, but a stale WindowState left over from whichever
        # of the two mechanisms touched the window last. Raw ShowWindow is
        # now only a last-resort fallback, not the primary path.
        try:
            self.window.minimize()
            return
        except Exception:
            pass
        self._show_window(6)  # SW_MINIMIZE

    def maximize(self):
        try:
            self.window.maximize()
        except Exception:
            self._show_window(3)  # SW_MAXIMIZE
        self.schedule_repaint_nudge()

    def restore(self):
        try:
            self.window.restore()
        except Exception:
            self._show_window(9)  # SW_RESTORE
        self.schedule_repaint_nudge()

    def is_maximized(self):
        if sys.platform != "win32":
            return False
        hwnd = self._native_hwnd()
        if not hwnd:
            return False
        try:
            import ctypes

            return bool(ctypes.windll.user32.IsZoomed(hwnd))
        except Exception:
            return False

    def schedule_repaint_nudge(self):
        """WebView2's compositor can lose sync with the window's actual
        size after a WindowState change (minimize/maximize/restore/
        fullscreen), leaving the page rendered as a blank frame -- this is
        a real, reproducible glitch confirmed by direct testing, not rare
        or exotic, and it takes only a handful of ordinary toggles to hit.
        A plain repaint request (InvalidateRect/UpdateWindow) does NOT
        recover it; only an actual size change does, which forces the
        swap chain to reallocate. So: wait for the state change to finish
        settling, then grow the window by 1px and immediately shrink it
        back -- imperceptible to the user, but enough to force WebView2 to
        resync, instead of leaving them staring at a blank window."""
        if sys.platform != "win32":
            return

        def _nudge():
            time.sleep(0.2)
            hwnd = self._native_hwnd()
            if not hwnd:
                return
            try:
                import ctypes
                from ctypes import wintypes

                rect = wintypes.RECT()
                ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                width = rect.right - rect.left
                height = rect.bottom - rect.top
                if width <= 0 or height <= 0:
                    return  # minimized -- nothing visible to repaint yet
                ctypes.windll.user32.MoveWindow(hwnd, rect.left, rect.top, width + 1, height, True)
                ctypes.windll.user32.MoveWindow(hwnd, rect.left, rect.top, width, height, True)
            except Exception:
                pass

        threading.Thread(target=_nudge, daemon=True).start()

    def _show_window(self, command):
        if sys.platform != "win32":
            return
        hwnd = self._native_hwnd()
        if not hwnd:
            return
        try:
            import ctypes

            ctypes.windll.user32.ShowWindow(hwnd, command)
        except Exception:
            pass

    def _native_hwnd(self):
        """Return the real Win32 HWND for pywebview's native form when present."""
        native = getattr(self.window, "native", None)
        if native is None:
            return None

        for name in ("Handle", "handle", "hwnd"):
            value = getattr(native, name, None)
            if value is None:
                continue
            if callable(value):
                try:
                    value = value()
                except Exception:
                    continue
            for converter in ("ToInt64", "ToInt32"):
                method = getattr(value, converter, None)
                if method:
                    try:
                        return int(method())
                    except Exception:
                        continue
            try:
                return int(value)
            except Exception:
                continue
        return None

    def open_path(self, path=""):
        """Navigate the embedded view to a specific dashboard path, e.g.
        "study/" or "profiles/new/" -- used by the tray menu."""
        self.window.load_url(dashboard_url() + path)

    def _on_closing(self):
        # Returning False cancels the close; hide instead so the tray icon
        # and watcher keep running, matching the old closeEvent-ignore
        # behavior.
        self.window.hide()
        return False
