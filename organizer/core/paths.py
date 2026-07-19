"""Central location for every path/constant this app touches on disk.

Ported 1:1 from Documents\\Scripts\\OrganizeDownloads.ps1's global variables.
If you ever change which physical drive is D:, or move where School/Personal
docs live, this is the only file that needs updating.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

USER_PROFILE = Path(os.environ["USERPROFILE"])

DOWNLOADS = USER_PROFILE / "Downloads"
DOWNLOADS2 = Path("D:/myDownloads")  # a second, real download location
SCHOOL_ROOT = Path("D:/School")
CONFIG_PATH = SCHOOL_ROOT / "_config.json"
CURRICULUM_PATH = SCHOOL_ROOT / "_curriculum_map.json"
WORK_UNSORTED = USER_PROFILE / "Documents" / "Work" / "_Unsorted"
PERSONAL_ROOT = USER_PROFILE / "Documents" / "Personal"
IMPORTANT_ROOT = PERSONAL_ROOT / "Important"
LIBRARY_INBOX = Path("D:/Library/00 New - Sort Me")

# Kept pointing at the same log file the PowerShell version used, so history
# stays in one continuous place across the switchover.
LOG_PATH = USER_PROFILE / "Documents" / "Scripts" / "organize-log.txt"

# Project-local, gitignored -- see ai_config.example.json for the template.
AI_CONFIG_PATH = BASE_DIR / "ai_config.json"

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
