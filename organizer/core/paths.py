"""Central location for every path/constant this app touches on disk that
isn't specific to one profile. Profile-specific routing (root folder,
primary/secondary group, subject list) lives on the Profile model instead --
see config_path()/curriculum_path() below and organizer.core.rules.
"""

import os
import sys
from pathlib import Path
from typing import Set, List

from runtime import app_dir


def resource_path(relative_path: str) -> Path:
    """Resolve a path to a read-only asset bundled with the app itself
    (templates, static files, shipped cert bundles) -- the opposite concern
    from app_dir() above, which points at persistent, writable, exe-adjacent
    state. Once frozen by PyInstaller, bundled assets live in the temporary
    extraction dir (sys._MEIPASS), not next to the exe."""
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent))
    return base_path / relative_path

# Project root in development; the folder containing the exe once frozen by
# PyInstaller (see runtime.py -- this must stay a persistent, exe-adjacent
# location, not the temporary bundle extraction dir).
BASE_DIR: Path = app_dir()

USER_PROFILE: Path = Path(os.environ["USERPROFILE"])

WORK_UNSORTED: Path = USER_PROFILE / "Documents" / "Work" / "_Unsorted"
PERSONAL_ROOT: Path = USER_PROFILE / "Documents" / "Personal"
IMPORTANT_ROOT: Path = PERSONAL_ROOT / "Important"

# Defaults only -- used the first time AppSettings.get_solo() creates its
# row, and as rules.get_destination()'s fallback when no library_inbox is
# passed in. The actual, possibly-user-edited values always come from
# AppSettings (organizer.models), never from these constants directly, so
# nothing here assumes any drive layout beyond "this user has a profile".
DEFAULT_DOWNLOADS: Path = USER_PROFILE / "Downloads"
DEFAULT_LIBRARY_INBOX: Path = PERSONAL_ROOT / "Library" / "00 New - Sort Me"

# Kept pointing at the same log file the PowerShell version used, so history
# stays in one continuous place across the switchover.
LOG_PATH: Path = USER_PROFILE / "Documents" / "Scripts" / "organize-log.txt"

# Project-local, gitignored -- see ai_config.example.json for the template.
AI_CONFIG_PATH: Path = BASE_DIR / "ai_config.json"


def config_path(profile_root: str) -> Path:
    """Each profile mirrors its current primary/secondary group into its own
    root folder, so multiple profiles never share one global config file."""
    return Path(profile_root) / "_config.json"


def curriculum_path(profile_root: str) -> Path:
    return Path(profile_root) / "_curriculum_map.json"

# Filename keywords that mean "sensitive, handle with care" -- checked before
# every other rule so these never land in a generic sorting bucket.
SENSITIVE_KEYWORDS: List[str] = [
    "password", "passwords", "credential", "credentials",
    "login", "logins", "recovery code", "recovery codes",
    "backup code", "backup codes", "2fa", "secret key", "private key",
]

# Certificate/key file extensions -- sensitive by nature regardless of filename.
CERT_KEY_EXT: Set[str] = {"pem", "key", "crt", "cer", "p12", "pfx", "ppk"}

# Markers that mean "this is an ebook", not a course note -- checked BEFORE
# course/topic matching.
EBOOK_MARKERS: List[str] = [
    "z-library", "zlibrary", "1lib", "z-lib", "libgen",
    "annas-archive", "anna's archive", "oceanofpdf",
]

IMAGE_EXT: Set[str] = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "svg"}
MUSIC_EXT: Set[str] = {"mp3", "wav", "flac", "m4a"}
VIDEO_EXT: Set[str] = {"mp4", "mkv", "mov", "avi", "webm"}
ARCHIVE_EXT: Set[str] = {"zip", "rar", "7z", "tar", "gz"}
INSTALLER_EXT: Set[str] = {"exe", "msi", "apk"}
DOC_EXT: Set[str] = {"pdf", "docx", "doc", "pptx", "ppt", "xlsx", "xls", "csv"}
CODE_EXT: Set[str] = {"sh", "py", "js", "json", "ts", "php", "java", "sql", "ipynb"}
