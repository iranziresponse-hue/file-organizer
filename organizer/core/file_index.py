"""Per-file change-detection cache backing FileIndexEntry. Lets a repeated
folder scan (organizer.core.study.create_import_plan() today) skip files
whose size and modified time haven't changed since the last time they were
seen, instead of re-deriving everything from scratch on every pass.

size + modified time (raw stat() values) are the default, cheap check --
no file is ever opened just to decide "unchanged". compute_content_hash()
is separate and lazy: only call it when a caller needs certainty beyond
size+mtime (e.g. a cloud-synced file whose sync client can reset mtime
without actually changing content).
"""

import logging
from pathlib import Path

from .intelligence import compute_file_hash

logger = logging.getLogger("organizer.file_index")


def _key(path):
    """The same file can otherwise show up under several different
    strings -- relative vs absolute, mixed case, a trailing '..' segment
    -- each of which would look "new" to a naive str(path) key even
    though nothing about the file changed. resolve() normalizes the
    structural differences; Orch is Windows-only (see organizer/core/
    paths.py's USERPROFILE-based constants), where the filesystem is
    case-preserving but case-INsensitive, so .lower() on top of that
    treats "Notes.PDF" and "notes.pdf" as the same key, matching how
    Windows itself treats them as the same file."""
    return str(Path(path).resolve()).lower()


def check_and_record(path, profile, classification="", summary_status=""):
    """One filesystem stat() covering both the read (has this changed?)
    and the write (record what we saw) -- for a scan walking many files,
    this halves the stat() calls check()+record() used separately would
    cost. Returns True if size and modified time match what was already on
    record for this path (unchanged since last seen); False for a new,
    changed, or unreadable path.

    profile is required (not optional) -- FileIndexEntry.profile is a
    required FK precisely to avoid the NULL-uniqueness gap a None here
    would open up (see the model's docstring); this fails fast and
    clearly at the call site instead of a confusing IntegrityError.

    Never raises -- an index write failing must never break the scan it's
    piggybacking on."""
    from ..models import FileIndexEntry

    try:
        stat = path.stat()
    except OSError:
        return False

    key = _key(path)
    try:
        entry = FileIndexEntry.objects.filter(profile=profile, path=key).first()
        unchanged = bool(entry and entry.size == stat.st_size and entry.modified_at == stat.st_mtime)

        defaults = {"size": stat.st_size, "modified_at": stat.st_mtime}
        if classification:
            defaults["last_classification"] = classification
        if summary_status:
            defaults["last_summary_status"] = summary_status
        FileIndexEntry.objects.update_or_create(profile=profile, path=key, defaults=defaults)
    except Exception as exc:
        logger.warning("Could not record file-index entry for %s: %s", key, exc)
        return False

    return unchanged


def check(path, profile):
    """Read-only: True if this path is on record as unchanged, without
    writing anything. Prefer check_and_record() when a scan is going to
    record the file either way -- this and record() together cost twice
    the stat() calls."""
    from ..models import FileIndexEntry

    try:
        stat = path.stat()
    except OSError:
        return False

    entry = FileIndexEntry.objects.filter(profile=profile, path=_key(path)).first()
    return bool(entry and entry.size == stat.st_size and entry.modified_at == stat.st_mtime)


def record(path, profile, classification="", summary_status=""):
    """Write-only upsert of this path's current size/mtime (and optionally
    the classification/summary-status a caller just derived for it)."""
    from ..models import FileIndexEntry

    try:
        stat = path.stat()
    except OSError:
        return

    defaults = {"size": stat.st_size, "modified_at": stat.st_mtime}
    if classification:
        defaults["last_classification"] = classification
    if summary_status:
        defaults["last_summary_status"] = summary_status
    try:
        FileIndexEntry.objects.update_or_create(profile=profile, path=_key(path), defaults=defaults)
    except Exception as exc:
        logger.warning("Could not record file-index entry for %s: %s", path, exc)


def compute_content_hash(path):
    """Same chunked-read approach as organizer.core.intelligence.
    compute_file_hash -- exposed here under a name that matches this
    module's vocabulary. Returns None if the file can't be read."""
    return compute_file_hash(path)
