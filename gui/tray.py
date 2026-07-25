"""System tray icon and menu."""

import os
import threading
import webbrowser

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMenu, QMessageBox, QSystemTrayIcon

from organizer.core import paths, owner_access, updater

from . import autostart
from .assets import ORCH_ICON_PATH
from .desktop_window import AboutDialog, PauseDialog, StatusWindow
from .main_window import OrchMainWindow
from .server import dashboard_url
from .watcher_controller import WatcherController


class OrganizerTray(QSystemTrayIcon):
    def __init__(self, app):
        icon = QIcon(str(ORCH_ICON_PATH))
        super().__init__(icon, app)

        self.app = app
        self.watcher = WatcherController()
        self.status_window = None
        self.pause_dialog = None
        self.main_window = None
        self._notification_queue = []

        self.setToolTip("Orch")

        self.menu = QMenu()

        # Toggle watcher
        self.toggle_action = self.menu.addAction("Start watching")
        self.toggle_action.triggered.connect(self._toggle_watcher)
        self.menu.addSeparator()

        # Navigation
        self.menu.addAction("Open Orch", self._open_main_window)
        self.menu.addAction("Open in browser", self._open_dashboard)
        self.menu.addAction("Open status window", self._open_status_window)
        if owner_access.owner_mode_enabled():
            self.menu.addAction("Owner Console", self._open_owner_console)
        self.menu.addAction("Open log", self._open_log)
        self.menu.addSeparator()

        # Pause controls
        self.pause_1h = self.menu.addAction("Pause for 1 hour")
        self.pause_1h.triggered.connect(lambda: self._pause_for(60))
        self.pause_30m = self.menu.addAction("Pause for 30 minutes")
        self.pause_30m.triggered.connect(lambda: self._pause_for(30))
        self.pause_15m = self.menu.addAction("Pause for 15 minutes")
        self.pause_15m.triggered.connect(lambda: self._pause_for(15))
        self.resume_action = self.menu.addAction("Resume watching")
        self.resume_action.triggered.connect(self._resume_watcher)
        self.resume_action.setVisible(False)
        self.menu.addSeparator()

        # Autostart
        self.autostart_action = self.menu.addAction("Start with Windows")
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(autostart.is_enabled())
        self.autostart_action.triggered.connect(self._toggle_autostart)
        self.menu.addSeparator()

        # Update (hidden until a background check actually finds one)
        self.update_action = self.menu.addAction("Update available")
        self.update_action.triggered.connect(self._start_update)
        self.update_action.setVisible(False)
        self.menu.addAction("Check for updates", self._check_for_updates_now)
        self.menu.addSeparator()

        # About and Quit
        self.menu.addAction("About Orch", self._show_about)
        self.menu.addAction("Quit", self._quit)
        self.setContextMenu(self.menu)

        self.activated.connect(self._on_activated)

        # Notification timer — checks for pending notifications every 2 seconds
        self._notification_timer = QTimer()
        self._notification_timer.timeout.connect(self._show_pending_notifications)
        self._notification_timer.start(2000)

        # Update-check timer — the actual HTTP check runs on a background
        # thread (see _check_for_updates_now); this just polls the shared
        # cache result every few seconds and reacts once, the same
        # thread-to-GUI handoff the notification timer above already uses.
        self._update_announced = False
        self._update_download_error_shown = None
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._poll_update_result)
        self._update_timer.start(4000)
        self._check_for_updates_now()

        self.watcher.start()
        self._refresh_toggle_label()

    def _on_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._open_main_window()

    def _pause_for(self, minutes):
        if self.watcher.running:
            self.watcher.stop()
            self._paused_until = None
            if minutes > 0:
                from PyQt6.QtCore import QTimer
                timer = QTimer()
                timer.setSingleShot(True)
                timer.timeout.connect(self._resume_watcher)
                timer.start(minutes * 60 * 1000)
                self._paused_until = timer
            self.pause_1h.setVisible(False)
            self.pause_30m.setVisible(False)
            self.pause_15m.setVisible(False)
            self.resume_action.setVisible(True)
            self._refresh_toggle_label()

    def _resume_watcher(self):
        if not self.watcher.running:
            self.watcher.start()
        self.pause_1h.setVisible(True)
        self.pause_30m.setVisible(True)
        self.pause_15m.setVisible(True)
        self.resume_action.setVisible(False)
        self._refresh_toggle_label()

    def _open_main_window(self):
        if self.main_window is None:
            self.main_window = OrchMainWindow(watcher_controller=self.watcher)
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def _open_status_window(self):
        if self.status_window is None or not self.status_window.isVisible():
            self.status_window = StatusWindow(self.watcher)
        self.status_window.show()
        self.status_window.raise_()

    def _show_about(self):
        dialog = AboutDialog()
        dialog.exec()

    def _show_pending_notifications(self):
        from organizer.core.notifications import has_pending, pop_pending
        if has_pending():
            batch = pop_pending()
            for note in batch:
                urgency = note.get("urgency", "normal")
                icon = QSystemTrayIcon.MessageIcon.Information
                if urgency == "critical":
                    icon = QSystemTrayIcon.MessageIcon.Critical
                elif urgency == "warning":
                    icon = QSystemTrayIcon.MessageIcon.Warning
                self.showMessage(
                    note.get("title", "Orch"),
                    note.get("message", ""),
                    icon,
                    5000,
                )

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

    def _open_owner_console(self):
        webbrowser.open(dashboard_url() + "owner/")

    def _open_log(self):
        if not paths.LOG_PATH.exists():
            QMessageBox.information(None, "Orch", "No log file yet. Nothing has been sorted.")
            return
        os.startfile(paths.LOG_PATH)

    def _quit(self):
        self.watcher.stop()
        self.app.quit()

    def _check_for_updates_now(self):
        threading.Thread(target=self._run_update_check, daemon=True).start()

    def _run_update_check(self):
        updater.remember_check_result(updater.check_for_update())

    def _poll_update_result(self):
        # Runs on the GUI thread via QTimer, same as _show_pending_notifications
        # above -- the only place any of this is allowed to touch a Qt
        # widget. Background threads (below) only ever write into
        # updater's cache, never into self.update_action directly.
        result = updater.get_last_check()
        if not result:
            return

        if result.get("available") and not self._update_announced:
            self._update_announced = True
            version = result.get("latest_version", "")
            self.update_action.setText(f"Update to v{version}")
            self.update_action.setEnabled(True)
            self.update_action.setVisible(True)
            self.showMessage(
                "Orch update available",
                f"Version {version} is ready. Click \"Update to v{version}\" in the tray menu to install it.",
                QSystemTrayIcon.MessageIcon.Information,
                8000,
            )

        error = result.get("error")
        if error and result.get("available") and error != self._update_download_error_shown:
            self._update_download_error_shown = error
            version = result.get("latest_version", "")
            self.update_action.setText(f"Update to v{version}")
            self.update_action.setEnabled(True)
            self.showMessage(
                "Orch update failed",
                f"Couldn't finish updating: {error}",
                QSystemTrayIcon.MessageIcon.Warning,
                8000,
            )

    def _start_update(self):
        result = updater.get_last_check()
        if not result or not result.get("available"):
            return
        version = result.get("latest_version", "")
        confirm = QMessageBox.question(
            None,
            "Update Orch",
            f"Download and install version {version} now?\n\n"
            "Orch will close and reopen automatically once it's done.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.update_action.setEnabled(False)
        self.update_action.setText("Downloading update...")
        self.showMessage(
            "Orch update",
            "Downloading in the background — Orch will restart automatically when it's ready.",
            QSystemTrayIcon.MessageIcon.Information,
            5000,
        )
        threading.Thread(target=self._run_download_and_apply, args=(result,), daemon=True).start()

    def _run_download_and_apply(self, result):
        # On success, download_and_apply spawns the relaunch script and
        # exits this whole process -- execution never returns here. Only
        # the failure path needs to report anything back, and it does so
        # by writing into updater's cache for _poll_update_result to pick
        # up on the next tick, never by touching Qt objects from this
        # background thread directly.
        success, error = updater.download_and_apply(result)
        if not success:
            updater.remember_check_result({**result, "error": error})
