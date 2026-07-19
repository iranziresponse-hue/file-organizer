"""System tray icon and menu."""

import os
import webbrowser

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMenu, QMessageBox, QSystemTrayIcon

from organizer.core import paths

from . import autostart
from .assets import ORCH_ICON_PATH
from .server import dashboard_url
from .watcher_controller import WatcherController


class OrganizerTray(QSystemTrayIcon):
    def __init__(self, app):
        icon = QIcon(str(ORCH_ICON_PATH))
        super().__init__(icon, app)

        self.app = app
        self.watcher = WatcherController()

        self.setToolTip("Orch")

        self.menu = QMenu()
        self.toggle_action = self.menu.addAction("Start watching")
        self.toggle_action.triggered.connect(self._toggle_watcher)

        self.menu.addAction("Open dashboard", self._open_dashboard)
        self.menu.addAction("Open log", self._open_log)
        self.menu.addSeparator()

        self.autostart_action = self.menu.addAction("Start with Windows")
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(autostart.is_enabled())
        self.autostart_action.triggered.connect(self._toggle_autostart)

        self.menu.addSeparator()
        self.menu.addAction("Quit", self._quit)
        self.setContextMenu(self.menu)

        self.activated.connect(self._on_activated)

        self.watcher.start()
        self._refresh_toggle_label()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._open_dashboard()

    def _toggle_watcher(self):
        if self.watcher.running:
            self.watcher.stop()
        else:
            self.watcher.start()
        self._refresh_toggle_label()

    def _refresh_toggle_label(self):
        self.toggle_action.setText("Stop watching" if self.watcher.running else "Start watching")

    def _toggle_autostart(self, checked):
        autostart.set_enabled(checked)

    def _open_dashboard(self):
        webbrowser.open(dashboard_url())

    def _open_log(self):
        if not paths.LOG_PATH.exists():
            QMessageBox.information(None, "Orch", "No log file yet -- nothing has been sorted.")
            return
        os.startfile(paths.LOG_PATH)

    def _quit(self):
        self.watcher.stop()
        self.app.quit()
