"""Where persistent app state (database, ai_config.json, first-run markers)
lives on disk. In development that's the repo root. Once PyInstaller freezes
main.py into a one-file exe, __file__ resolves inside a temporary extraction
directory that is recreated, and deleted, on every single run -- so frozen
builds must anchor persistent files to the folder containing the exe itself
instead, or every restart would look like a fresh install with an empty
database.

This is the opposite concern from gui/assets.py's resource_path(), which
deliberately points *into* the temporary bundle for read-only assets
(templates, static files) that only ever need to be read, never persisted.
"""

import sys
from pathlib import Path


def app_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent
