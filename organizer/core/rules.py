"""Pure destination-decision logic. Zero Django/Qt imports so this can be
unit-tested and reasoned about in isolation. Ported 1:1 from Get-Destination
/ Get-ContentCategory / Is-Ebook / Find-CourseByTopic in OrganizeDownloads.ps1.
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


def load_config():
    if not paths.CONFIG_PATH.exists():
        return None
    try:
        return json.loads(paths.CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_curriculum():
    if not paths.CURRICULUM_PATH.exists():
        return None
    try:
        data = json.loads(paths.CURRICULUM_PATH.read_text(encoding="utf-8"))
        return data.get("courses", [])
    except (OSError, json.JSONDecodeError):
        return None


def find_course_by_topic(name, curriculum):
    """Matches by TOPIC, not just course code in the filename -- e.g. "Data
    Structures Notes.pdf" matches CSC2100 via its keyword list even with no
    course code anywhere in the name. Searches the whole degree, not just the
    current semester."""
    if not curriculum:
        return None
    n = name.lower()
    for course in curriculum:
        for keyword in course.get("keywords", []):
            if re.search(re.escape(keyword.lower()), n):
                return course
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


def get_destination(file_path, ai_classify=None):
    """Decides where a file belongs. Re-reads config/curriculum fresh every
    call (not cached) so editing those files takes effect on the very next
    download, no restart needed.

    ai_classify: optional callable(name, curriculum) -> course dict or None,
    used as the last-resort fallback before giving up to _Unsorted/_NeedsSorting.
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

    # Ebooks win over course/topic matching.
    if is_ebook(name, ext):
        return Destination(paths.LIBRARY_INBOX, "ebook")

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
        config = load_config()
        curriculum = load_curriculum()
        category = get_content_category(name)

        # 1. Explicit course code in the filename (current semester's list).
        if config:
            for course in config.get("courses", []):
                if re.search(re.escape(course.lower()), lname):
                    dest = paths.SCHOOL_ROOT / config["current_year"] / config["current_semester"] / course / category
                    return Destination(dest, "course_code", course)

        # 2. No code -- try matching the TOPIC against the whole curriculum map.
        topic_match = find_course_by_topic(name, curriculum)
        if topic_match:
            prefix = (paths.SCHOOL_ROOT / "_Archive") if topic_match.get("archived") else paths.SCHOOL_ROOT
            dest = prefix / topic_match["year"] / topic_match["semester"] / topic_match["code"] / category
            return Destination(dest, "topic", topic_match["code"])

        # 3. No code, no topic match -- optional AI fallback.
        if ai_classify:
            ai_match = ai_classify(name, curriculum)
            if ai_match:
                prefix = (paths.SCHOOL_ROOT / "_Archive") if ai_match.get("archived") else paths.SCHOOL_ROOT
                dest = prefix / ai_match["year"] / ai_match["semester"] / ai_match["code"] / category
                return Destination(dest, "ai", ai_match["code"])

        # 4. Nothing matched -- current semester's _Unsorted, or _NeedsSorting
        #    if there's no config at all.
        if config:
            dest = paths.SCHOOL_ROOT / config["current_year"] / config["current_semester"] / "_Unsorted" / category
            return Destination(dest, "unsorted")
        return Destination(paths.PERSONAL_ROOT / "Documents" / "_NeedsSorting" / category, "needs_sorting")

    # Loose code/project files belong in a real project folder, not a
    # generic documents pile -- routed to Work for manual relocation.
    if ext in paths.CODE_EXT:
        return Destination(paths.WORK_UNSORTED, "work_unsorted")

    return Destination(paths.PERSONAL_ROOT / "Documents" / "_NeedsSorting", "needs_sorting")
