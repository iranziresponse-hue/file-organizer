"""Desktop entry point. Sets up Django (ORM + migrations) before touching
PyQt, then runs the dashboard server and the file watcher as background
threads under one system tray icon -- no console window, no separate
`manage.py runserver`/`manage.py migrate` steps for the packaged exe.
"""

import os
import sys


def _silence_none_streams():
    # PyInstaller's --windowed build gives frozen apps sys.stdout/stderr of
    # None. Django's runserver command writes startup banners to self.stdout,
    # which crashes on None -- redirect to a null sink instead of patching
    # every call site.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")


def _claim_windows_app_identity():
    # Without this, Windows groups the taskbar button under whatever exe
    # actually launched the process -- python.exe's own icon in dev mode,
    # since Qt's setWindowIcon only controls the window/title-bar icon, not
    # the taskbar identity Windows uses for icon + grouping. This tells
    # Windows "this process is its own distinct app," so the taskbar uses
    # the QIcon we set instead of the host exe's icon.
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Iranzi.Orch.Desktop.1")
    except Exception:
        pass


def _configure_webengine():
    # Must be set before QtWebEngineWidgets/QWebEngineView is imported
    # anywhere (gui/tray.py imports gui/main_window.py at module level,
    # which imports it), so this runs first thing in main().
    #
    # Chromium's "Native Window Occlusion" detection (Windows-only) skips
    # rendering windows it thinks are fully hidden, to save power; its
    # occlusion tracking misfires for embedded/child views like this one
    # and forces spurious repaints instead of skipping them correctly.
    #
    # --disable-gpu-compositing DID stop the white flash in A/B testing,
    # but on this machine's GPU/driver it went further than "slower" --
    # the whole window stopped responding to scroll/clicks entirely. An
    # unusable app is a worse bug than a flicker, so this stays off despite
    # fixing the flash; the CalculateNativeWinOcclusion fix and the
    # base.html blur-radius reductions stay regardless, since neither one
    # caused any harm on their own.
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-features=CalculateNativeWinOcclusion")


def main():
    _silence_none_streams()
    _claim_windows_app_identity()
    _configure_webengine()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    import django

    django.setup()

    from django.core.management import call_command

    call_command("migrate", run_syncdb=True, verbosity=0)

    from organizer.models import Profile

    needs_setup = not Profile.objects.exists()

    from PyQt6.QtCore import QTimer
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication

    from . import autostart
    from .assets import ORCH_ICON_PATH
    from .server import start_dashboard_server
    from .tray import OrganizerTray

    app = QApplication(sys.argv)
    app.setApplicationName("Orch")
    app.setWindowIcon(QIcon(str(ORCH_ICON_PATH)))
    app.setQuitOnLastWindowClosed(False)

    autostart.enable_on_first_run()
    start_dashboard_server()

    tray = OrganizerTray(app)
    tray.show()

    # The dashboard server thread needs a moment to bind its socket --
    # delay the first open instead of racing it. Orch is a real desktop
    # app now: the window opens on launch, not just the tray icon, landing
    # on the setup checklist for a brand new install or the dashboard
    # otherwise.
    def _open_at_startup():
        tray._open_main_window()
        if needs_setup:
            tray.main_window.open_path("start/")

    QTimer.singleShot(1500, _open_at_startup)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
