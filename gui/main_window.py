"""Native desktop window for Orch: the real Django dashboard embedded
directly in a taskbar-visible window via QWebEngineView, not just a tray
icon plus a separate browser tab. The page has its own topbar/nav already
(organizer/templates/organizer/base.html), so this window doesn't add a
second one on top of it.
"""

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QMainWindow

from .assets import ORCH_ICON_PATH
from .server import dashboard_url

# Matches base.html's --bg-deep. QWebEngineView defaults to a white page
# background, which would flash visibly for an instant on a real reload
# since there's a brief gap between navigation starting and the page's own
# dark CSS painting.
PAGE_BACKGROUND = QColor(10, 12, 20)

# This window used to also run a QTimer every 30s that injected and ran a
# "check for new activity, show a dismissible banner" JavaScript snippet
# into the page (page().runJavaScript(...)). Every distinct flicker/freeze
# bug chased across this app's whole history traced back to that one
# mechanism in some form: a full navigate-and-reload, a DOM patch, a CSS
# specificity bug that pinned the banner permanently visible, and finally
# --disable-gpu-compositing (needed to stop a white flash tied to it)
# freezing the window outright on this machine's GPU/driver. It was cut
# entirely rather than patched a fifth time: it was solving a problem
# (missing something that happened while the window was idle) that Orch's
# native tray notifications (see gui/tray.py, notifications.py) already
# solve, via a completely separate path that never touches this webview's
# JS engine at all. No periodic runJavaScript() calls means nothing here
# can compete with the page's own rendering for the render thread.
class OrchMainWindow(QMainWindow):
    """Taskbar-visible window showing the live dashboard. Closing it hides
    the window rather than quitting the app -- the tray icon and the
    background watcher keep running either way (see gui/tray.py)."""

    def __init__(self, watcher_controller=None, parent=None):
        super().__init__(parent)
        self.watcher = watcher_controller

        self.setWindowTitle("Orch")
        self.setWindowIcon(QIcon(str(ORCH_ICON_PATH)))
        self.resize(1280, 820)
        self.setMinimumSize(860, 560)

        self.webview = QWebEngineView(self)
        self.webview.page().setBackgroundColor(PAGE_BACKGROUND)
        self.webview.setUrl(QUrl(dashboard_url()))
        self.setCentralWidget(self.webview)

    def open_path(self, path=""):
        """Navigate the embedded view to a specific dashboard path, e.g.
        "study/" or "profiles/new/" -- used by the tray menu."""
        self.webview.setUrl(QUrl(dashboard_url() + path))

    def closeEvent(self, event):
        event.ignore()
        self.hide()
