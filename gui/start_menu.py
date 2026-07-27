"""Creates a Start Menu shortcut so Orch shows up when searching or
browsing the Windows Start Menu. The installer (installer/Orch.iss)
already creates one of these at install time; this is a fallback safety
net for a copy that was moved or run without going through the installer,
so a missing shortcut fixes itself on the next launch either way.
"""

import os
import sys
from pathlib import Path

from .assets import ORCH_ICON_PATH

SHORTCUT_NAME = "Orch.lnk"


def _start_menu_shortcut_path():
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / SHORTCUT_NAME


def ensure_shortcut():
    """Idempotent: does nothing once the shortcut already exists, so this
    is safe and cheap to call on every launch rather than needing its own
    first-run marker, unlike gui/autostart.py's toggle (which reflects a
    user choice that must not be silently reapplied after they turn it
    off). A missing app just means "reinstalled to a new folder," in
    which case re-creating it here is exactly the right behavior anyway.
    """
    if sys.platform != "win32":
        return

    shortcut_path = _start_menu_shortcut_path()
    if shortcut_path.exists():
        return

    try:
        import win32com.client

        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(shortcut_path))
        if getattr(sys, "frozen", False):
            target = Path(sys.executable)
            shortcut.TargetPath = str(target)
        else:
            # Dev mode: relaunch through the same interpreter and this
            # project's main.py, matching gui/autostart.py's _command().
            target = Path(__file__).resolve().parent.parent / "main.py"
            shortcut.TargetPath = sys.executable
            shortcut.Arguments = f'"{target}"'
        shortcut.WorkingDirectory = str(target.parent)
        shortcut.IconLocation = str(ORCH_ICON_PATH)
        shortcut.Description = "Orch"
        shortcut.save()
    except Exception:
        # A missing Start Menu entry is a cosmetic gap, never worth
        # crashing startup over.
        pass
