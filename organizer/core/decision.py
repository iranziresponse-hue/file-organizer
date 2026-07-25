"""Pure decision-scoring and classification logic for the sorting trust
layer -- zero Django imports, same "no framework, unit-testable in
isolation" design as rules.py. This module only scores and classifies; it
never touches the filesystem or the database. organizer.core.sorting is the
Django-aware orchestrator that calls into this module and turns a
DecisionResult into a SortDecision/MoveEvent.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import paths

# Sensitive-file detection extends paths.py's own lists with a couple of
# extra generic terms/extensions the profile-routing sensitivity check
# never needed to cover.
SENSITIVE_KEYWORDS = list(paths.SENSITIVE_KEYWORDS) + ["secret", "token"]
SENSITIVE_EXT = paths.CERT_KEY_EXT | {"kdbx"}

# Extension -> global category key, checked in this order. Ebooks are
# detected by rules.is_ebook (marker/ISBN based, not purely by extension)
# so they're handled separately in classify_global_category below.
GLOBAL_CATEGORY_EXTENSIONS = {
    "media": paths.IMAGE_EXT | paths.MUSIC_EXT | paths.VIDEO_EXT,
    "archives": paths.ARCHIVE_EXT,
    "installers": paths.INSTALLER_EXT,
    "code": paths.CODE_EXT,
}

AUTO_THRESHOLD = 90
SUGGEST_THRESHOLD = 60

# category_key -> MoveEvent.METHOD_CHOICES value, so every pipeline stage
# that resolves a global category can stamp a MoveEvent with the right
# label without re-deriving it later.
CATEGORY_METHOD = {
    "media": "media",
    "archives": "archive",
    "installers": "installer",
    "code": "work_unsorted",
    "ebooks": "ebook",
}


@dataclass
class DecisionResult:
    """What the pipeline decided to do with one file, and why. Every sorter
    stage returns one of these instead of moving a file directly -- see
    organizer.core.sorting.decide_for_file for how the stages are chained.
    """

    action: str  # "auto_move" | "suggest" | "hold" | "leave"
    confidence: int
    destination: Optional[Path]
    explanation: str
    decision_type: str
    method: str = "unsorted"  # MoveEvent.METHOD_CHOICES value
    category_key: Optional[str] = None
    matched_rule_name: str = ""


def detect_sensitive(name: str, ext: str) -> bool:
    """Filenames/extensions that mean "private, handle with care" -- checked
    before every other pipeline stage so these never move without the user
    seeing them first."""
    if ext in SENSITIVE_EXT:
        return True
    lname = name.lower()
    return any(re.search(re.escape(keyword), lname) for keyword in SENSITIVE_KEYWORDS)


def classify_global_category(name: str, ext: str) -> Optional[str]:
    """Which opt-in global category (if any) this file's extension/name
    belongs to. Returns None for anything that isn't media, an ebook, an
    archive, an installer, or a code/project file -- profile documents and
    everything unrecognized are the caller's problem, not this module's."""
    from . import rules

    if rules.is_ebook(name, ext):
        return "ebooks"
    for key, extensions in GLOBAL_CATEGORY_EXTENSIONS.items():
        if ext in extensions:
            return key
    return None


def score_confidence(
    explicit_rule_match: bool = False,
    exact_subject_match: bool = False,
    prior_approved_boost: int = 0,
    extension_category_match: bool = False,
    filename_keyword_match: bool = False,
    destination_exists: bool = False,
    prior_rejected: bool = False,
    unknown_source_folder: bool = False,
) -> int:
    """The confidence point table, kept deliberately simple and free (no
    ML): each signal contributes a fixed score, clamped to 0-100.
    `prior_approved_boost` takes the matched OrganizationMemoryRule's own
    editable confidence_boost (default 25) rather than a hardcoded +25, so
    a rule the user has approved many times can be worth more over time.
    """
    score = 0
    if explicit_rule_match:
        score += 50
    if exact_subject_match:
        score += 45
    score += max(0, prior_approved_boost)
    if extension_category_match:
        score += 20
    if filename_keyword_match:
        score += 15
    if destination_exists:
        score += 10
    if prior_rejected:
        score -= 40
    if unknown_source_folder:
        score -= 10
    return max(0, min(100, score))
