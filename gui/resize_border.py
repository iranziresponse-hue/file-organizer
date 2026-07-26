"""Restores OS-native mouse handling to the frameless main window.

pywebview's frameless mode drops the resize grips and native titlebar drag
area that a normal bordered window gets for free. Without this hook, dragging
the top strip can look like webpage text selection instead of moving the
window. The hook intercepts WM_NCHITTEST and tells Windows which edge, corner,
or caption area the cursor is over, then Windows performs the real move/resize.
"""

import ctypes
from ctypes import wintypes

_user32 = ctypes.windll.user32

_GWLP_WNDPROC = -4
_GWL_STYLE = -16
_WM_NCHITTEST = 0x0084
_BORDER = 7  # px margin around the window edge that counts as a resize grip
_TITLEBAR_HEIGHT = 30
_TITLEBAR_CONTROLS_WIDTH = 168  # 4 titlebar buttons x 42px each (base.css's desktop pass)

_WS_THICKFRAME = 0x00040000
_WS_MINIMIZEBOX = 0x00020000
_WS_MAXIMIZEBOX = 0x00010000
_WS_SYSMENU = 0x00080000

_SWP_NOMOVE = 0x0002
_SWP_NOSIZE = 0x0001
_SWP_NOZORDER = 0x0004
_SWP_FRAMECHANGED = 0x0020

_HTCAPTION = 2
_HTLEFT, _HTRIGHT, _HTTOP, _HTBOTTOM = 10, 11, 12, 15
_HTTOPLEFT, _HTTOPRIGHT, _HTBOTTOMLEFT, _HTBOTTOMRIGHT = 13, 14, 16, 17

_WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM
)

_user32.SetWindowLongPtrW.restype = ctypes.c_void_p
_user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
_user32.GetWindowLongPtrW.restype = ctypes.c_void_p
_user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.CallWindowProcW.restype = ctypes.c_ssize_t
_user32.CallWindowProcW.argtypes = [
    ctypes.c_void_p, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM,
]
_user32.DefWindowProcW.restype = ctypes.c_ssize_t
_user32.DefWindowProcW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
_user32.SetWindowPos.restype = wintypes.BOOL
_user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint,
]

# Keeps the trampoline (and the hook holding it) alive for the process's
# whole life. If this were garbage collected, Windows would call into
# freed memory the next time it delivered a message to the window and
# take the whole app down with it -- so this list is never popped.
_active_hooks = []


def install(hwnd):
    """Subclasses the given window handle to add edge-resize hit-testing.
    Safe to call once per window; the caller (main_window.py) guards
    against calling it twice for the same window."""
    _enable_native_window_styles(hwnd)
    _active_hooks.append(_ResizeHook(hwnd))


def _enable_native_window_styles(hwnd):
    style = int(_user32.GetWindowLongPtrW(hwnd, _GWL_STYLE) or 0)
    style |= _WS_THICKFRAME | _WS_MINIMIZEBOX | _WS_MAXIMIZEBOX | _WS_SYSMENU
    _user32.SetWindowLongPtrW(hwnd, _GWL_STYLE, ctypes.c_void_p(style))
    _user32.SetWindowPos(
        hwnd,
        None,
        0,
        0,
        0,
        0,
        _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOZORDER | _SWP_FRAMECHANGED,
    )


class _ResizeHook:
    def __init__(self, hwnd):
        self.hwnd = hwnd
        # Set before SetWindowLongPtrW below, not after: Windows can (and
        # does, in practice) call straight into _new_proc synchronously as
        # part of that same call, before it has returned the previous
        # window proc for us to store. Without this placeholder, that
        # reentrant call would hit _wnd_proc with no _old_proc attribute
        # yet and crash as an unraisable exception in the ctypes callback --
        # exactly the "AttributeError: '_ResizeHook' object has no
        # attribute '_old_proc'" crash this was fixed for.
        self._old_proc = None
        self._new_proc = _WNDPROC(self._wnd_proc)
        self._old_proc = _user32.SetWindowLongPtrW(hwnd, _GWLP_WNDPROC, self._new_proc)

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == _WM_NCHITTEST:
            try:
                hit = self._hit_test(lparam)
            except Exception:
                hit = None
            if hit is not None:
                return hit
        if self._old_proc is None:
            # Reentrant call during installation itself (see __init__) --
            # the real previous window proc isn't known yet, so fall back
            # to the OS default rather than crash. Only ever hit for the
            # handful of messages Windows sends synchronously while
            # SetWindowLongPtrW is still executing.
            return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        return _user32.CallWindowProcW(self._old_proc, hwnd, msg, wparam, lparam)

    def _hit_test(self, lparam):
        # lParam's low/high words are the cursor's SCREEN coordinates, each
        # a signed 16-bit value (a second monitor to the left of the
        # primary one has genuinely negative coordinates).
        x = ctypes.c_short(lparam & 0xFFFF).value
        y = ctypes.c_short((lparam >> 16) & 0xFFFF).value

        rect = wintypes.RECT()
        _user32.GetWindowRect(self.hwnd, ctypes.byref(rect))

        near_left = x - rect.left <= _BORDER
        near_right = rect.right - x <= _BORDER
        near_top = y - rect.top <= _BORDER
        near_bottom = rect.bottom - y <= _BORDER

        if near_top and near_left:
            return _HTTOPLEFT
        if near_top and near_right:
            return _HTTOPRIGHT
        if near_bottom and near_left:
            return _HTBOTTOMLEFT
        if near_bottom and near_right:
            return _HTBOTTOMRIGHT
        if near_left:
            return _HTLEFT
        if near_right:
            return _HTRIGHT
        if near_top:
            return _HTTOP
        if near_bottom:
            return _HTBOTTOM
        if self._in_caption_area(x, y, rect):
            return _HTCAPTION
        return None

    def _in_caption_area(self, x, y, rect):
        in_titlebar_y = rect.top + _BORDER < y < rect.top + _TITLEBAR_HEIGHT
        before_buttons = x < rect.right - _TITLEBAR_CONTROLS_WIDTH
        return in_titlebar_y and before_buttons
