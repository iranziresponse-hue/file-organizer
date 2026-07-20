"""Fixed, translucent top bar for Orch's native shell ("Liquid Glass" style).

Design note on positioning
---------------------------
QMainWindow.addToolBar() reserves permanent layout space for the bar, which
pushes the central widget down by the bar's height. That's the opposite of
what's needed here (content must start at y=0, bar floats on top of it), so
the default export, TopBar, is NOT a QToolBar. It's a plain QWidget that:
  - is reparented directly onto the QMainWindow (not the central widget),
  - is pinned to (0, 0) spanning the window's full width,
  - is kept above the central widget in z-order via raise_(),
  - repaints itself as translucent, so content scrolling underneath shows
    through the glass tint.
If you'd rather have Qt's standard docked toolbar behavior (and don't mind
content being pushed down by BAR_HEIGHT), use `as_qtoolbar()` at the bottom
instead of `TopBar`.
"""

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

# ---------------------------------------------------------------------------
# Tweak these to restyle the bar without touching the layout code below.
# ---------------------------------------------------------------------------
BAR_HEIGHT = 44                    # px — hard cap per spec, keep <= 44
BAR_BG_RGBA = (30, 30, 40, 153)    # rgba(30,30,40,0.6) -> 0.6 * 255 = 153
LOGO_SIZE = 24                     # px, square
SIDE_PADDING = 8                   # px, left/right padding inside the bar
NAV_SPACING = 4                    # px, gap between nav buttons
NAV_FONT_SIZE = 12                 # px
NAV_TEXT_COLOR = "#E8ECF2"
NAV_HOVER_BG = "rgba(255, 255, 255, 0.10)"
NAV_ITEMS = ("Dashboard", "Study", "Profiles", "Settings")


class _BarContent(QWidget):
    """Logo + nav buttons + glass background. No window-pinning logic here —
    that lives in TopBar so this piece can also be embedded in a plain
    QToolBar by as_qtoolbar() without the two positioning strategies
    fighting each other.
    """

    nav_clicked = pyqtSignal(str)

    def __init__(self, icon_path=None, parent=None):
        super().__init__(parent)
        self.setFixedHeight(BAR_HEIGHT)
        # Per-pixel translucency so paintEvent's alpha fill blends with
        # whatever is drawn behind this widget instead of being opaque.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SIDE_PADDING, 0, SIDE_PADDING, 0)
        layout.setSpacing(0)

        # Left: logo only, no subtitle text.
        logo_label = QLabel()
        logo_label.setFixedSize(LOGO_SIZE, LOGO_SIZE)
        pixmap = self._load_logo_pixmap(icon_path)
        if pixmap is not None:
            logo_label.setPixmap(pixmap)
        layout.addWidget(logo_label, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addStretch(1)

        # Right: flat nav buttons.
        nav_row = QHBoxLayout()
        nav_row.setSpacing(NAV_SPACING)
        self._nav_buttons = {}
        for label in NAV_ITEMS:
            btn = QPushButton(label)
            btn.setFlat(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    color: {NAV_TEXT_COLOR};
                    background: transparent;
                    border: none;
                    padding: 6px 12px;
                    border-radius: 8px;
                    font-size: {NAV_FONT_SIZE}px;
                }}
                QPushButton:hover {{
                    background: {NAV_HOVER_BG};
                }}
            """)
            btn.clicked.connect(lambda _checked, name=label: self.nav_clicked.emit(name))
            self._nav_buttons[label] = btn
            nav_row.addWidget(btn)
        layout.addLayout(nav_row)

    @staticmethod
    def _load_logo_pixmap(icon_path):
        if icon_path is None:
            # Falls back to Orch's bundled mark if the caller doesn't pass one.
            try:
                from .assets import ORCH_ICON_PATH
                icon_path = ORCH_ICON_PATH
            except ImportError:
                return None
        icon = QIcon(str(icon_path))
        if icon.isNull():
            return None
        return icon.pixmap(LOGO_SIZE, LOGO_SIZE)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(*BAR_BG_RGBA))
        # NOTE on real backdrop blur: Qt has no built-in "blur what's behind
        # this widget" primitive — QGraphicsBlurEffect blurs the widget's own
        # contents, not the layer beneath it. A true frosted-glass look needs
        # grabbing a live snapshot of the content behind the bar and blurring
        # that pixmap, which is easy to get wrong (stale snapshot while
        # scrolling) and costs a repaint on every scroll/resize. Left out by
        # default to keep this file simple and cheap to render; the flat
        # semi-transparent fill above already reads as "glass" over most
        # content. If you want real blur later, grab a pixmap of the
        # window's central widget cropped to self.geometry(), run it through
        # a blur (e.g. QGraphicsBlurEffect via a QGraphicsScene, or a small
        # manual box-blur), and paint it here before the fillRect.
        painter.end()


class TopBar(_BarContent):
    """Floating, translucent top bar pinned over a QMainWindow's content.

    Usage in main.py:
        self.window = QMainWindow()
        self.window.setCentralWidget(your_content_widget)
        self.topbar = TopBar(self.window)
        self.topbar.nav_clicked.connect(self.on_nav_clicked)  # emits e.g. "Dashboard"
        self.window.show()

    No file/database access happens here — this widget only emits signals;
    the caller decides what "Dashboard" etc. actually does.
    """

    def __init__(self, window, icon_path=None):
        super().__init__(icon_path=icon_path, parent=window)
        self._window = window

        # Keep the bar pinned to the top and full-width whenever the window
        # resizes, and keep it above the central widget in stacking order.
        self._window.installEventFilter(self)
        self._sync_geometry()
        self.raise_()

    def eventFilter(self, obj, event):
        if obj is self._window and event.type() == QEvent.Type.Resize:
            self._sync_geometry()
        return False

    def _sync_geometry(self):
        self.setGeometry(0, 0, self._window.width(), BAR_HEIGHT)


def as_qtoolbar(window, icon_path=None):
    """Alternative: standard docked QToolBar, for callers who prefer Qt's
    normal toolbar behavior over the floating-overlay TopBar above.

    Trade-off: this DOES push the central widget down by BAR_HEIGHT, since
    QMainWindow reserves layout space for docked toolbars. Use TopBar
    instead if content must start at y=0.
    """
    from PyQt6.QtWidgets import QToolBar

    toolbar = QToolBar("Orch", window)
    toolbar.setFixedHeight(BAR_HEIGHT)
    toolbar.setMovable(False)
    toolbar.setFloatable(False)
    toolbar.setStyleSheet(f"""
        QToolBar {{
            background: rgba({BAR_BG_RGBA[0]}, {BAR_BG_RGBA[1]}, {BAR_BG_RGBA[2]}, {BAR_BG_RGBA[3] / 255});
            border: none;
            padding: 0 {SIDE_PADDING}px;
            spacing: {NAV_SPACING}px;
        }}
    """)

    content = _BarContent(icon_path=icon_path, parent=toolbar)
    toolbar.addWidget(content)
    window.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
    return toolbar, content  # content.nav_clicked is the signal to connect to
