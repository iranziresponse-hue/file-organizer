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


def main():
    _silence_none_streams()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    import django

    django.setup()

    from django.core.management import call_command

    call_command("migrate", run_syncdb=True, verbosity=0)

    from PyQt6.QtWidgets import QApplication

    from .server import start_dashboard_server
    from .tray import OrganizerTray

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    start_dashboard_server()

    tray = OrganizerTray(app)
    tray.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
