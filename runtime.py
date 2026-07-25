"""Where persistent app state (database, ai_config.json, first-run markers)
lives on disk. In development that's the repo root. Once PyInstaller freezes
main.py into a one-file exe, __file__ resolves inside a temporary extraction
directory that is recreated, and deleted, on every single run -- so frozen
builds must anchor persistent files somewhere stable instead, or every
restart would look like a fresh install with an empty database.

That stable place is the per-user Windows AppData folder, not the folder
the exe binary happens to sit in. Anchoring to the exe's own folder was
tried first, but it means every time the exe is moved, replaced, or
redownloaded as a new file (exactly what happens on every update, since
each release is a fresh Orch.exe) the user's whole profile and database
look like they vanished, when really they're just sitting next to a
different, now-unused copy of the exe. AppData follows the user, not the
binary, so Orch.exe can be rebuilt, redownloaded, or moved freely and the
database is still exactly where Orch left it.

This is the opposite concern from gui/assets.py's resource_path(), which
deliberately points *into* the temporary bundle for read-only assets
(templates, static files) that only ever need to be read, never persisted.
"""

import os
import sys
from pathlib import Path


def app_dir():
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        target = base / "Orch"
        target.mkdir(parents=True, exist_ok=True)
        return target
    return Path(__file__).resolve().parent
