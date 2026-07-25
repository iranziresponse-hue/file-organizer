"""Pure destination-decision logic. Zero Django/Qt imports so this can be
unit-tested and reasoned about in isolation. Ported originally from
Get-Destination / Get-ContentCategory / Is-Ebook / Find-CourseByTopic in
OrganizeDownloads.ps1, later generalized from a single hardcoded D:\\School
layout into per-profile routing (see organizer.models.Profile) -- profile_root
and the config/curriculum files under it are the only profile-specific
inputs, so this module still doesn't need to know Django exists.
"""

import json
import re
import time
from pathlib import Path

from . import makerere_curricula, paths


class Destination:
    def __init__(self, path: Path | str, method: str, course_code: str | None = None):
        self.path = Path(path)
        self.method = method
        self.course_code = course_code


def resolve_subject_folder(root: Path, primary_value: str, secondary_value: str, code: str) -> Path:
    """The single source of truth for where a subject/course-unit code's
    folder lives, used both when routing a file and when proactively
    scaffolding subject folders (organizer.core.sorting.ensure_subject_folders).

    Order of preference, so an existing folder is NEVER duplicated:
    1. A bare "<code>" folder that already exists -- always wins.
    2. Any "<code> - <anything>" folder that already exists -- covers a
       folder that already has a name, however it got there.
    3. Neither exists yet: "<code> - <real name>" if the name is known
       (Makerere curriculum), otherwise just "<code>".
    """
    base = Path(root) / primary_value / secondary_value
    bare = base / code
    if bare.exists():
        return bare

    if base.exists():
        for entry in base.iterdir():
            if entry.is_dir() and entry.name.startswith(f"{code} - "):
                return entry

    name = makerere_curricula.name_for_code(code)
    if name:
        return base / f"{code} - {name}"
    return bare


# ---------------------------------------------------------------------------
# TTL cache for config/curriculum reads -- re-reads from disk only when the
# file's mtime changes, so editing them takes effect on the next poll cycle
# without hammering the filesystem on every single file move.
# ---------------------------------------------------------------------------
_CACHE_TTL_SECONDS = 10
_cache: dict[str, tuple[float, object]] = {}  # path -> (mtime, data)


def _cached_read(path: Path, loader):
    """Generic TTL cache: returns cached data if the file's mtime hasn't
    changed since the last read, otherwise re-reads via `loader(path)`."""
    try:
        current_mtime = path.stat().st_mtime
    except OSError:
        return None

    cache_key = str(path)
    entry = _cache.get(cache_key)
    if entry is not None:
        cached_mtime, cached_data = entry
        if cached_mtime == current_mtime:
            return cached_data

    data = loader(path)
    _cache[cache_key] = (current_mtime, data)
    return data


def _load_config_from_disk(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _load_curriculum_from_disk(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("subjects", [])
    except (OSError, json.JSONDecodeError):
        return None


def load_config(profile_root: str | None):
    if not profile_root:
        return None
    path = paths.config_path(profile_root)
    if not path.exists():
        return None
    return _cached_read(path, _load_config_from_disk)


def load_curriculum(profile_root: str | None):
    if not profile_root:
        return None
    path = paths.curriculum_path(profile_root)
    if not path.exists():
        return None
    return _cached_read(path, _load_curriculum_from_disk)


def find_course_by_topic(name, curriculum):
    """Matches by TOPIC, not just a subject code in the filename -- e.g.
    "Data Structures Notes.pdf" matches CSC2100 via its keyword list even
    with no code anywhere in the name. Searches the whole curriculum, not
    just the current primary/secondary group."""
    if not curriculum:
        return None
    n = name.lower()
    for entry in curriculum:
        for keyword in entry.get("keywords", []):
            if re.search(re.escape(keyword.lower()), n):
                return entry
    return None


def is_ebook(name, ext):
    if ext == "epub":
        return True
    n = name.lower()
    for marker in paths.EBOOK_MARKERS:
        if re.search(re.escape(marker), n):
            return True
    if re.search(r"\b97[89]\d{10}\b", n):  # ISBN-13 in the filename
        return True
    return False


def get_content_category(name):
    """Sorts a document by what it actually IS, not just its extension.
    Checked in order -- most specific pattern wins."""
    n = name.lower()
    if re.search(r"past paper|exam|test\b|quiz|revision|cat\b", n):
        return "03 Past Papers and Tests"
    if re.search(r"assignment|takehome|take home|coursework|exercise", n):
        return "02 Assignments and Coursework"
    if re.search(r"lecture|notes|slide|week ?\d|chapter", n):
        return "01 Lecture Notes and Slides"
    if re.search(r"report|project|proposal|sdd|erd|dictionary|design", n):
        return "04 Reports and Projects"
    return "05 Reference and Extra Reading"


# The inverse of get_content_category(): a file's category is baked into
# its folder name once sorted (see get_destination's DOC_EXT branch), never
# stored as its own MoveEvent field -- this pulls it back out of a
# destination path for display, e.g. Course Unit Brain's resource buckets.
_CONTENT_CATEGORIES = (
    "01 Lecture Notes and Slides",
    "02 Assignments and Coursework",
    "03 Past Papers and Tests",
    "04 Reports and Projects",
    "05 Reference and Extra Reading",
)


def category_from_path(path):
    """Returns the get_content_category() label found in `path`'s folder
    segments, or None if the path doesn't contain one of the five known
    category folder names (e.g. it was routed by a custom FolderRule
    instead of the default document pipeline)."""
    if not path:
        return None
    parts = {part for part in re.split(r"[\\/]", str(path))}
    for category in _CONTENT_CATEGORIES:
        if category in parts:
            return category
    return None


def get_destination(file_path, profile_root=None, library_inbox=None, ai_classify=None):
    """Decides where a file belongs. Re-reads the profile's config/curriculum
    fresh every call (not cached) so editing them takes effect on the very
    next download, no restart needed.

    profile_root: the active Profile's root_path, or None if no profile is
    active yet -- document files then fall straight to _NeedsSorting, same
    as a profile with no config saved.
    library_inbox: where ebooks land -- normally organizer.models.AppSettings'
    configured value, passed in by the caller. Falls back to
    paths.DEFAULT_LIBRARY_INBOX if not given.
    ai_classify: optional callable(name, curriculum) -> curriculum entry dict
    or None, used as the last-resort fallback before giving up.
    """
    file_path = Path(file_path)
    name = file_path.name
    ext = file_path.suffix.lstrip(".").lower()
    lname = name.lower()

    if lname.endswith((".crdownload", ".part", ".tmp")):
        return None

    # Sensitive filenames/extensions win over every other rule.
    for keyword in paths.SENSITIVE_KEYWORDS:
        if re.search(re.escape(keyword), lname):
            return Destination(paths.IMPORTANT_ROOT, "sensitive")
    if ext in paths.CERT_KEY_EXT:
        return Destination(paths.IMPORTANT_ROOT, "sensitive")

    # Ebooks win over subject/topic matching.
    if is_ebook(name, ext):
        return Destination(library_inbox or paths.DEFAULT_LIBRARY_INBOX, "ebook")

    if ext in paths.IMAGE_EXT:
        return Destination(paths.PERSONAL_ROOT / "Media" / "Images", "media")
    if ext in paths.MUSIC_EXT:
        return Destination(paths.PERSONAL_ROOT / "Media" / "Music", "media")
    if ext in paths.VIDEO_EXT:
        return Destination(paths.PERSONAL_ROOT / "Media" / "Videos", "media")
    if ext in paths.ARCHIVE_EXT:
        return Destination(paths.PERSONAL_ROOT / "Archives", "archive")
    if ext in paths.INSTALLER_EXT:
        return Destination(paths.PERSONAL_ROOT / "Installers", "installer")

    if ext in paths.DOC_EXT:
        dest = route_profile_document(file_path, profile_root, ai_classify=ai_classify)
        if dest:
            return dest
        # Nothing in the profile matched -- current group's _Unsorted, or
        # _NeedsSorting if there's no active profile/config at all.
        config = load_config(profile_root)
        category = get_content_category(name)
        if config and profile_root:
            unsorted = Path(profile_root) / config["primary_value"] / config["secondary_value"] / "_Unsorted" / category
            return Destination(unsorted, "unsorted")
        return Destination(paths.PERSONAL_ROOT / "Documents" / "_NeedsSorting" / category, "needs_sorting")

    # Loose code/project files belong in a real project folder, not a
    # generic documents pile -- routed to Work for manual relocation.
    if ext in paths.CODE_EXT:
        return Destination(paths.WORK_UNSORTED, "work_unsorted")

    return Destination(paths.PERSONAL_ROOT / "Documents" / "_NeedsSorting", "needs_sorting")


def route_profile_document(file_path, profile_root=None, ai_classify=None):
    """The trusted zone: routes a document into the active profile's own
    structure by subject code, then topic keyword, then (if enabled) the
    profile's own optional AI fallback. This is the ONLY part of the old
    monolithic get_destination() the trust-layer pipeline
    (organizer.core.sorting.decide_for_file) reuses directly -- profile
    routing stays fully automatic because the user explicitly opted into
    this profile's root/structure. Returns None if nothing in the profile
    matched, leaving the caller to decide what happens to an unmatched
    document (global category suggestion, then the conservative fallback).
    """
    file_path = Path(file_path)
    name = file_path.name
    lname = name.lower()
    config = load_config(profile_root)
    curriculum = load_curriculum(profile_root)
    category = get_content_category(name)
    root = Path(profile_root) if profile_root else None

    if not root:
        return None

    # 1. Explicit subject code in the filename (current group's list).
    if config:
        for code in config.get("groups", []):
            if re.search(re.escape(code.lower()), lname):
                subject_folder = resolve_subject_folder(root, config["primary_value"], config["secondary_value"], code)
                return Destination(subject_folder / category, "course_code", code)

    # 2. No code -- try matching the TOPIC against the whole curriculum.
    topic_match = find_course_by_topic(name, curriculum)
    if topic_match:
        prefix = (root / "_Archive") if topic_match.get("archived") else root
        subject_folder = resolve_subject_folder(prefix, topic_match["primary_value"], topic_match["secondary_value"], topic_match["code"])
        return Destination(subject_folder / category, "topic", topic_match["code"])

    # 3. No code, no topic match -- optional smart fallback.
    if ai_classify:
        ai_match = ai_classify(name, curriculum)
        if ai_match:
            prefix = (root / "_Archive") if ai_match.get("archived") else root
            subject_folder = resolve_subject_folder(prefix, ai_match["primary_value"], ai_match["secondary_value"], ai_match["code"])
            return Destination(subject_folder / category, "ai", ai_match["code"])

    return None
