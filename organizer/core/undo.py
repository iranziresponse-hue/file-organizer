"""Undo / restore for moved files. Every successful move creates an undo
record that allows restoring the file to its original location.

The watcher's move_downloaded_file() and the inbox approval workflow
both record undo information via MoveEvent. This module provides the
restore logic.
"""

import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable


def restore_move(event, log: Callable | None = None) -> bool:
    """Restore a file to its original location after a move.

    Args:
        event: A MoveEvent instance (must have source_path and destination_path).
        log: Optional logging function.

    Returns:
        True if the file was restored, False otherwise.
    """
    if not event.source_path or not event.destination_path:
        if log:
            log(f"Cannot restore '{event.filename}': missing source or destination path")
        return False

    source = Path(event.source_path)
    destination = Path(event.destination_path)

    if not destination.exists():
        if log:
            log(f"Cannot restore '{event.filename}': destination file no longer exists at {destination}")
        return False

    # Ensure the original directory still exists
    source.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.move(str(destination), str(source))
        if log:
            log(f"Restored '{event.filename}' from {destination} to {source}")

        # Create a "restore" record to trace the undo
        from organizer.models import MoveEvent as MoveEventModel
        MoveEventModel.objects.create(
            profile=event.profile,
            filename=event.filename,
            source_path=str(destination),
            destination_path=str(source),
            method="course_code" if event.course_code else "unsorted",
            course_code=event.course_code or "",
            success=True,
            error_message=f"Undo of move #{event.pk}",
        )
        return True
    except OSError as exc:
        if log:
            log(f"Failed to restore '{event.filename}': {exc}")
        return False


def restore_recent(profile, minutes: int = 60, limit: int = 10, log: Callable | None = None) -> int:
    """Restore all files moved within the last N minutes for a profile.

    Args:
        profile: The Profile to restore files for.
        minutes: How far back to look for moves to restore.
        limit: Maximum number of files to restore.
        log: Optional logging function.

    Returns:
        Number of files successfully restored.
    """
    from django.utils import timezone

    from organizer.models import MoveEvent

    since = timezone.now() - timedelta(minutes=minutes)
    recent = MoveEvent.objects.filter(
        profile=profile,
        success=True,
        timestamp__gte=since,
    ).order_by("-timestamp")[:limit]

    restored = 0
    for event in recent:
        if restore_move(event, log=log):
            restored += 1
    return restored


def get_restorable_moves(profile, limit: int = 20):
    """Get recent successful moves that can be undone.

    Filters out moves where the source already has a file (already restored).
    """
    from organizer.models import MoveEvent

    events = MoveEvent.objects.filter(
        profile=profile,
        success=True,
    ).order_by("-timestamp")[:limit]

    restorable = []
    for event in events:
        if event.destination_path and Path(event.destination_path).exists():
            restorable.append(event)
    return restorable


def get_undo_stats(profile) -> dict:
    """Get undo statistics for a profile."""
    from organizer.models import MoveEvent

    recent = MoveEvent.objects.filter(profile=profile, success=True).order_by("-timestamp")[:50]
    restorable = sum(1 for e in recent if e.destination_path and Path(e.destination_path).exists())

    return {
        "recent_moves": recent.count(),
        "restorable": restorable,
    }