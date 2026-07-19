"""Central location for every path/constant this app touches on disk that
isn't specific to one profile. Profile-specific routing (root folder,
primary/secondary group, subject list) lives on the Profile model instead --
see config_path()/curriculum_path() below and organizer.core.rules.
"""

import os
from pathlib import Path

from runtime import app_dir

# Project root in development; the folder containing the exe once frozen by
# PyInstaller (see runtime.py -- this must stay a persistent, exe-adjacent
# location, not the temporary bundle extraction dir).
BASE_DIR = app_dir()

USER_PROFILE = Path(os.environ["USERPROFILE"])

DOWNLOADS = USER_PROFILE / "Downloads"
DOWNLOADS2 = Path("D:/myDownloads")  # a second, real download location
WORK_UNSORTED = USER_PROFILE / "Documents" / "Work" / "_Unsorted"
PERSONAL_ROOT = USER_PROFILE / "Documents" / "Personal"
IMPORTANT_ROOT = PERSONAL_ROOT / "Important"
LIBRARY_INBOX = Path("D:/Library/00 New - Sort Me")

# Kept pointing at the same log file the PowerShell version used, so history
# stays in one continuous place across the switchover.
LOG_PATH = USER_PROFILE / "Documents" / "Scripts" / "organize-log.txt"

# Project-local, gitignored -- see ai_config.example.json for the template.
AI_CONFIG_PATH = BASE_DIR / "ai_config.json"


def config_path(profile_root):
    """Each profile mirrors its current primary/secondary group into its own
    root folder, so multiple profiles never share one global config file."""
    return Path(profile_root) / "_config.json"


def curriculum_path(profile_root):
    return Path(profile_root) / "_curriculum_map.json"

# Filename keywords that mean "sensitive, handle with care" -- checked before
# every other rule so these never land in a generic sorting bucket.
SENSITIVE_KEYWORDS = [
    "password", "passwords", "credential", "credentials",
    "login", "logins", "recovery code", "recovery codes",
    "backup code", "backup codes", "2fa", "secret key", "private key",
]

# Certificate/key file extensions -- sensitive by nature regardless of filename.
CERT_KEY_EXT = {"pem", "key", "crt", "cer", "p12", "pfx", "ppk"}

# Markers that mean "this is an ebook", not a course note -- checked BEFORE
# course/topic matching.
EBOOK_MARKERS = [
    "z-library", "zlibrary", "1lib", "z-lib", "libgen",
    "annas-archive", "anna's archive", "oceanofpdf",
]

IMAGE_EXT = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "svg"}
MUSIC_EXT = {"mp3", "wav", "flac", "m4a"}
VIDEO_EXT = {"mp4", "mkv", "mov", "avi", "webm"}
ARCHIVE_EXT = {"zip", "rar", "7z", "tar", "gz"}
INSTALLER_EXT = {"exe", "msi", "apk"}
DOC_EXT = {"pdf", "docx", "doc", "pptx", "ppt", "xlsx", "xls", "csv"}
CODE_EXT = {"sh", "py", "js", "json", "ts", "php", "java", "sql", "ipynb"}

# Old installer cleanup thresholds -- only ever touches
# Documents\Personal\Installers, never Downloads or any other drive.
INSTALLER_STALE_DAYS = 30
INSTALLER_DELETE_DAYS = 60
