"""Shared asset paths for development and PyInstaller builds."""

import sys
from pathlib import Path


def resource_path(relative_path):
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base_path / relative_path


ORCH_ICON_PATH = resource_path("organizer/static/organizer/img/orch-mark.ico")
