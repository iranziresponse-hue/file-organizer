"""Native desktop window for Orch — About screen, build/version info,
pause controls, and notification display.

This module provides a native PyQt6 window that shows system status,
allows pausing the watcher, and displays build/version information.
"""

import os
import platform
import sys
from datetime import datetime, timedelta
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QAction, QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .assets import ORCH_ICON_PATH

try:
    from organizer import __version__ as VERSION
except (ImportError, AttributeError):
    VERSION = "1.0.0"

_BUILD_DATE = "2026-07-19"


class AboutDialog(QDialog):
    """About screen showing build/version/system information."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Orch")
        self.setFixedSize(480, 480)
        self.setWindowIcon(QIcon(str(ORCH_ICON_PATH)))

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # App icon + name
        icon_label = QLabel()
        pixmap = QPixmap(str(ORCH_ICON_PATH))
        if not pixmap.isNull():
            icon_label.setPixmap(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        # Name and version
        name_label = QLabel("Orch")
        name_font = QFont("Space Grotesk", 20, QFont.Weight.Bold)
        name_label.setFont(name_font)
        name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(name_label)

        # Version info
        info = QTextEdit()
        info.setReadOnly(True)
        info.setFrameShape(QTextEdit.Shape.NoFrame)
        info.setStyleSheet("background: transparent; color: #E8ECF2;")
        info.setHtml(f"""
        <div style='text-align:center; color:#AEB7C5; line-height:1.7;'>
            <p><strong style='color:#E8ECF2;'>Version:</strong> {VERSION}</p>
            <p><strong style='color:#E8ECF2;'>Build date:</strong> {_BUILD_DATE}</p>
            <p><strong style='color:#E8ECF2;'>Python:</strong> {platform.python_version()}</p>
            <p><strong style='color:#E8ECF2;'>Platform:</strong> {platform.platform()}</p>
            <p><strong style='color:#E8ECF2;'>Host:</strong> {platform.node()}</p>
            <hr style='border-color:rgba(255,255,255,0.1); margin:12px 0;'>
            <p>A Django + PyQt6 desktop app for Windows<br>
            that organizes learning files and tracks study flow.</p>
            <p style='font-size:0.85rem;'>Copyright &copy; 2026 Iranzi. All rights reserved.</p>
        </div>
        """)
        layout.addWidget(info)

        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.close)
        layout.addWidget(button_box)


class PauseDialog(QDialog):
    """Dialog for pausing the watcher with a timer."""

    def __init__(self, watcher_controller, parent=None):
        super().__init__(parent)
        self.watcher = watcher_controller
        self.pause_minutes = 0
        self.pause_timer = None
        self._original_running = watcher_controller.running
        self._paused = False

        self.setWindowTitle("Pause Orch")
        self.setFixedSize(360, 260)
        self.setWindowIcon(QIcon(str(ORCH_ICON_PATH)))

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Title
        title = QLabel("Pause file watching")
        title_font = QFont("Space Grotesk", 14, QFont.Weight.Bold)
        title.setFont(title_font)
        layout.addWidget(title)

        # Status
        self.status_label = QLabel("Watcher is currently active")
        self.status_label.setStyleSheet("color: #4ADE80;")
        layout.addWidget(self.status_label)

        # Slider for pause duration
        slider_layout = QVBoxLayout()
        slider_label = QLabel("Pause duration:")
        slider_layout.addWidget(slider_label)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(120)
        self.slider.setValue(0)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.setTickInterval(15)
        self.slider.valueChanged.connect(self._on_slider_changed)
        slider_layout.addWidget(self.slider)

        self.duration_label = QLabel("0 minutes (not paused)")
        self.duration_label.setAlignment(Qt.AlignCenter)
        slider_layout.addWidget(self.duration_label)
        layout.addLayout(slider_layout)

        # Battery-aware option
        self.battery_check = QPushButton("Pause while on battery")
        self.battery_check.setCheckable(True)
        self.battery_check.setStyleSheet("""
            QPushButton { padding: 8px 12px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.15);
            background: rgba(255,255,255,0.06); color: #E8ECF2; text-align: left; }
            QPushButton:checked { border-color: #6EA8FF; background: rgba(110,168,255,0.12); }
        """)
        layout.addWidget(self.battery_check)

        # Battery status display
        self.battery_status_label = QLabel()
        self._refresh_battery_status()
        layout.addWidget(self.battery_status_label)

        # Buttons
        button_layout = QHBoxLayout()
        self.pause_btn = QPushButton("Pause now")
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.pause_btn.setStyleSheet("""
            QPushButton { padding: 8px 20px; border-radius: 12px; border: 1px solid rgba(110,168,255,0.5);
            background: rgba(110,168,255,0.2); color: #E8ECF2; font-weight: 600; }
            QPushButton:hover { border-color: rgba(110,168,255,0.72); }
        """)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet("""
            QPushButton { padding: 8px 20px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.15);
            background: rgba(255,255,255,0.06); color: #E8ECF2; }
        """)

        button_layout.addWidget(self.pause_btn)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

    def _on_slider_changed(self, value):
        self.pause_minutes = value
        if value == 0:
            self.duration_label.setText("0 minutes (not paused)")
        else:
            self.duration_label.setText(f"{value} minutes")

    def _refresh_battery_status(self):
        status, percent = self._get_battery_info()
        if status == "charging":
            self.battery_status_label.setText(f"Power: Charging ({percent}%)")
            self.battery_status_label.setStyleSheet("color: #4ADE80;")
        elif status == "battery":
            self.battery_status_label.setText(f"Power: On battery ({percent}%)")
            self.battery_status_label.setStyleSheet("color: #FFD38A;")
        elif status == "full":
            self.battery_status_label.setText(f"Power: Fully charged ({percent}%)")
            self.battery_status_label.setStyleSheet("color: #4ADE80;")
        else:
            self.battery_status_label.setText("Power: AC (desktop)")
            self.battery_status_label.setStyleSheet("color: #AEB7C5;")

    @staticmethod
    def _get_battery_info():
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery is None:
                return "unknown", 100
            plugged = battery.power_plugged
            percent = int(battery.percent)
            if plugged and percent >= 99:
                return "full", percent
            if plugged:
                return "charging", percent
            return "battery", percent
        except ImportError:
            return "unknown", 100

    def _toggle_pause(self):
        if not self._paused:
            minutes = self.pause_minutes
            if minutes > 0 and self.watcher.running:
                self.watcher.stop()
                self._paused = True
                self._original_running = True
                self.status_label.setText(f"Paused for {minutes} minutes")
                self.status_label.setStyleSheet("color: #FFD38A;")
                self.pause_btn.setText("Resume now")
                # Auto-resume timer
                if self.pause_timer:
                    self.pause_timer.stop()
                self.pause_timer = QTimer()
                self.pause_timer.setSingleShot(True)
                self.pause_timer.timeout.connect(self._auto_resume)
                self.pause_timer.start(minutes * 60 * 1000)
            elif self.battery_check.isChecked():
                status, _ = self._get_battery_info()
                if status == "battery":
                    self.watcher.stop()
                    self._paused = True
                    self._original_running = True
                    self.status_label.setText("Paused: on battery power")
                    self.status_label.setStyleSheet("color: #FFD38A;")
                    self.pause_btn.setText("Resume now")
                else:
                    self.status_label.setText("Not on battery -- watcher still running")
        else:
            self._resume()

    def _auto_resume(self):
        if self._paused:
            self._resume()

    def _resume(self):
        if not self.watcher.running and self._original_running:
            self.watcher.start()
        self._paused = False
        self.status_label.setText("Watcher is active")
        self.status_label.setStyleSheet("color: #4ADE80;")
        self.pause_btn.setText("Pause now")
        if self.pause_timer:
            self.pause_timer.stop()


class StatusWindow(QDialog):
    """Desktop status window showing watcher state, recent activity, and pause controls."""

    def __init__(self, watcher_controller, parent=None):
        super().__init__(parent)
        self.watcher = watcher_controller
        self.setWindowTitle("Orch — Status")
        self.setFixedSize(520, 500)
        self.setWindowIcon(QIcon(str(ORCH_ICON_PATH)))

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Title
        title = QLabel("Orch Desktop")
        title_font = QFont("Space Grotesk", 18, QFont.Weight.Bold)
        title.setFont(title_font)
        layout.addWidget(title)

        # Tabs
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid rgba(255,255,255,0.15); border-radius: 12px;
            background: rgba(255,255,255,0.04); padding: 16px; }
            QTabBar::tab { padding: 8px 16px; border-radius: 8px; margin-right: 4px; color: #AEB7C5; }
            QTabBar::tab:selected { background: rgba(110,168,255,0.2); color: #E8ECF2; }
        """)

        # Status tab
        status_tab = QWidget()
        status_layout = QVBoxLayout(status_tab)

        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setFrameShape(QTextEdit.Shape.NoFrame)
        self.status_text.setStyleSheet("background: transparent; color: #E8ECF2;")
        status_layout.addWidget(self.status_text)

        refresh_btn = QPushButton("Refresh status")
        refresh_btn.clicked.connect(self._refresh_status)
        refresh_btn.setStyleSheet("""
            QPushButton { padding: 8px 16px; border-radius: 10px; border: 1px solid rgba(110,168,255,0.5);
            background: rgba(110,168,255,0.15); color: #E8ECF2; }
        """)
        status_layout.addWidget(refresh_btn)

        tabs.addTab(status_tab, "Status")

        # Pause tab
        pause_tab = QWidget()
        pause_layout = QVBoxLayout(pause_tab)
        self.pause_dialog = PauseDialog(watcher_controller)
        pause_layout.addWidget(self.pause_dialog.status_label)
        pause_layout.addWidget(self.pause_dialog.slider)
        pause_layout.addWidget(self.pause_dialog.duration_label)
        pause_layout.addWidget(self.pause_dialog.battery_check)

        btn_layout = QHBoxLayout()
        self.pause_btn = QPushButton("Pause / Resume")
        self.pause_btn.clicked.connect(self.pause_dialog._toggle_pause)
        self.pause_btn.setStyleSheet("""
            QPushButton { padding: 8px 20px; border-radius: 12px; border: 1px solid rgba(110,168,255,0.5);
            background: rgba(110,168,255,0.2); color: #E8ECF2; font-weight: 600; }
        """)
        btn_layout.addWidget(self.pause_btn)
        pause_layout.addLayout(btn_layout)

        tabs.addTab(pause_tab, "Pause")

        layout.addWidget(tabs)

        self._refresh_status()

    def _refresh_status(self):
        watcher_running = self.watcher.running
        status_color = "#4ADE80" if watcher_running else "#FF6B6B"
        status_text = "Active" if watcher_running else "Inactive"

        # Try to get recent log info
        from organizer.core import paths
        log_lines = []
        try:
            if paths.LOG_PATH.exists():
                lines = paths.LOG_PATH.read_text(encoding="utf-8").splitlines()
                log_lines = lines[-10:]
        except OSError:
            log_lines = ["(Could not read log)"]

        log_html = "<br>".join(f"<span style='color:#AEB7C5; font-size:0.85rem;'>{l}</span>" for l in log_lines) if log_lines else "<span style='color:#AEB7C5;'>No log entries yet.</span>"

        self.status_text.setHtml(f"""
        <div style='line-height:1.7;'>
            <p><strong style='color:#E8ECF2;'>Watcher:</strong> <span style='color:{status_color};'>{status_text}</span></p>
            <p><strong style='color:#E8ECF2;'>Version:</strong> {VERSION}</p>
            <p style='margin-top:16px;'><strong style='color:#E8ECF2;'>Recent log:</strong></p>
            {log_html}
        </div>
        """)