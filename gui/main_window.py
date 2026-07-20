"""Minimal native shell window for Orch.

The real dashboard/study cockpit is the Django site (opened in the system
browser today via the tray menu's "Open dashboard"). This window is NOT an
embedded browser -- it's a small native status panel with the TopBar floating
over it, and its nav buttons just open the matching dashboard page in the
system browser, same as the tray menu already does. That keeps this window
free of any new heavy dependency (no QWebEngineView / PyQt6-WebEngine).
"""

import webbrowser

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from .assets import ORCH_ICON_PATH
from .server import dashboard_url
from .topbar import BAR_HEIGHT, TopBar

# Maps a TopBar nav label to the dashboard path it should open.
NAV_ROUTES = {
    "Dashboard": "",
    "Study": "study/",
    "Profiles": "profiles/",
    "Settings": "settings/",
}

WINDOW_BG = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0A0C14, stop:0.48 #121725, stop:1 #0A0C14)"


class OrchMainWindow(QMainWindow):
    """Native window: TopBar on top, a small status panel underneath.

    watcher_controller is optional so this window can be built and tested
    without wiring it to the real file watcher.
    """

    def __init__(self, watcher_controller=None, parent=None):
        super().__init__(parent)
        self.watcher = watcher_controller

        self.setWindowTitle("Orch")
        self.setWindowIcon(QIcon(str(ORCH_ICON_PATH)))
        self.resize(720, 480)
        self.setMinimumSize(480, 360)

        self._build_content()

        # TopBar reparents itself onto this window and pins to (0, 0),
        # so it must be created after the central widget is in place.
        self.topbar = TopBar(self, icon_path=ORCH_ICON_PATH)
        self.topbar.nav_clicked.connect(self._on_nav_clicked)

    def _build_content(self):
        central = QWidget()
        central.setStyleSheet(f"background: {WINDOW_BG};")
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        # Top padding pushes content below the glass bar so it doesn't start
        # out hidden underneath it; bar height + a little breathing room.
        layout.setContentsMargins(24, BAR_HEIGHT + 24, 24, 24)
        layout.setSpacing(10)
        layout.addStretch(1)

        logo = QLabel()
        pixmap = QPixmap(str(ORCH_ICON_PATH))
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)

        title = QLabel("Orch is running")
        title.setFont(QFont("Space Grotesk", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #E8ECF2;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #AEB7C5; font-size: 13px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        self._refresh_status()

        hint = QLabel("Use Dashboard, Study, Profiles, or Settings above to open the full cockpit in your browser.")
        hint.setStyleSheet("color: #6B7280; font-size: 12px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addStretch(2)

    def _refresh_status(self):
        if self.watcher is None:
            self.status_label.setText("Watcher status unavailable")
            return
        state = "Active" if self.watcher.running else "Paused"
        self.status_label.setText(f"File watcher: {state}")

    def _on_nav_clicked(self, label):
        path = NAV_ROUTES.get(label, "")
        webbrowser.open(dashboard_url() + path)

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_status()
        # Window may not have its final size yet on first show; re-pin now
        # that geometry is real instead of waiting for the next resize.
        self.topbar._sync_geometry()
        self.topbar.raise_()
