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
from pathlib import Path

from . import paths


class Destination:
    def __init__(self, path, method, course_code=None):
        self.path = Path(path)
        self.method = method
        self.course_code = course_code


def load_config(profile_root):
    if not profile_root:
        return None
    path = paths.config_path(profile_root)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_curriculum(profile_root):
    if not profile_root:
        return None
    path = paths.curriculum_path(profile_root)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("subjects", [])
    except (OSError, json.JSONDecodeError):
        return None


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
        config = load_config(profile_root)
        curriculum = load_curriculum(profile_root)
        category = get_content_category(name)
        root = Path(profile_root) if profile_root else None

        # 1. Explicit subject code in the filename (current group's list).
        if config and root:
            for code in config.get("groups", []):
                if re.search(re.escape(code.lower()), lname):
                    dest = root / config["primary_value"] / config["secondary_value"] / code / category
                    return Destination(dest, "course_code", code)

        # 2. No code -- try matching the TOPIC against the whole curriculum.
        topic_match = find_course_by_topic(name, curriculum)
        if topic_match and root:
            prefix = (root / "_Archive") if topic_match.get("archived") else root
            dest = prefix / topic_match["primary_value"] / topic_match["secondary_value"] / topic_match["code"] / category
            return Destination(dest, "topic", topic_match["code"])

        # 3. No code, no topic match -- optional AI fallback.
        if ai_classify and root:
            ai_match = ai_classify(name, curriculum)
            if ai_match:
                prefix = (root / "_Archive") if ai_match.get("archived") else root
                dest = prefix / ai_match["primary_value"] / ai_match["secondary_value"] / ai_match["code"] / category
                return Destination(dest, "ai", ai_match["code"])

        # 4. Nothing matched -- current group's _Unsorted, or _NeedsSorting
        #    if there's no active profile/config at all.
        if config and root:
            dest = root / config["primary_value"] / config["secondary_value"] / "_Unsorted" / category
            return Destination(dest, "unsorted")
        return Destination(paths.PERSONAL_ROOT / "Documents" / "_NeedsSorting" / category, "needs_sorting")

    # Loose code/project files belong in a real project folder, not a
    # generic documents pile -- routed to Work for manual relocation.
    if ext in paths.CODE_EXT:
        return Destination(paths.WORK_UNSORTED, "work_unsorted")

    return Destination(paths.PERSONAL_ROOT / "Documents" / "_NeedsSorting", "needs_sorting")
