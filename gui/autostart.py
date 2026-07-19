"""Launch Orch automatically at Windows login, via the per-user Run
registry key (HKCU, not HKLM) -- no admin rights needed, and it only
affects the current user's own login, never system-wide.
"""

import sys
import winreg
from pathlib import Path

from organizer.core import paths

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "Orch"

# Marks that the first-run default has already been applied, so later runs
# never fight a choice the user made from the tray menu. Lives next to the
# database/ai_config.json (BASE_DIR -- the exe's own folder once frozen),
# not inside the app package, since it's local machine state, not code.
_FIRST_RUN_MARKER = paths.BASE_DIR / ".autostart_initialized"


def _command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    # Dev mode: relaunch through the same interpreter and this project's main.py.
    main_path = Path(__file__).resolve().parent.parent / "main.py"
    return f'"{sys.executable}" "{main_path}"'


def is_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False


def set_enabled(enabled):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


def enable_on_first_run():
    """Turns auto-start on the very first time Orch ever runs on this
    machine, then gets out of the way -- every run after that defers
    entirely to whatever the user picked from the tray menu."""
    if _FIRST_RUN_MARKER.exists():
        return
    _FIRST_RUN_MARKER.parent.mkdir(parents=True, exist_ok=True)
    set_enabled(True)
    _FIRST_RUN_MARKER.write_text("")
