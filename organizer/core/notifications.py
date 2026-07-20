"""Notification bus for Orch. Sends desktop notifications via the
system tray icon when events happen (new files sorted, deadlines
approaching, MUELE sync complete, etc.).

Uses PyQt6's QSystemTrayIcon.showMessage() for desktop notifications.
All notification functions are safe to call from any thread.
"""

import logging
from datetime import datetime, timedelta
from typing import Callable

from django.utils import timezone

logger = logging.getLogger("organizer.notifications")

# Queue of pending notifications (thread-safe via QTimer)
_pending_notifications: list[dict] = []


# ---------------------------------------------------------------------------
# Notification data
# ---------------------------------------------------------------------------


class Notification:
    """A notification to be shown via the system tray."""

    def __init__(self, title: str, message: str, icon: int = 0, urgency: str = "normal"):
        self.title = title
        self.message = message
        self.icon = icon  # QSystemTrayIcon.MessageIcon value
        self.urgency = urgency  # "low", "normal", "critical"
        self.timestamp = datetime.now()

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "message": self.message,
            "urgency": self.urgency,
            "timestamp": self.timestamp.isoformat(),
        }


# ---------------------------------------------------------------------------
# Enqueue notifications
# ---------------------------------------------------------------------------


def notify(title: str, message: str, urgency: str = "normal", profile=None) -> None:
    """Queue a live tray toast, and persist it so it's still visible in the
    web UI later even if the toast was missed or the tray wasn't running."""
    _pending_notifications.append({
        "title": title,
        "message": message,
        "urgency": urgency,
        "timestamp": datetime.now().isoformat(),
    })

    from organizer.models import Notification

    Notification.objects.create(profile=profile, title=title, message=message, urgency=urgency)


def pop_pending() -> list[dict]:
    """Retrieve and clear all pending notifications. Called by the tray."""
    global _pending_notifications
    batch = _pending_notifications
    _pending_notifications = []
    return batch


def has_pending() -> bool:
    return len(_pending_notifications) > 0


# ---------------------------------------------------------------------------
# Notification generators
# ---------------------------------------------------------------------------


def check_deadlines(profile, log: Callable | None = None) -> int:
    """Check for upcoming/missed assignment deadlines and notify.

    Cheap enough to call on every dashboard/study page load: each
    assignment only ever triggers one notification per stage
    (warning/urgent/missed), tracked on deadline_notified_stage, so
    repeated page loads never re-notify about the same deadline.

    Returns the number of notifications sent.
    """
    from organizer.models import AssignmentItem

    now = timezone.now()
    count = 0

    # Urgent: due within 24 hours
    urgent = AssignmentItem.objects.filter(
        profile=profile,
        status="open",
        due_at__gte=now,
        due_at__lte=now + timedelta(hours=24),
    ).exclude(deadline_notified_stage="urgent")
    for assign in urgent:
        hours_left = int((assign.due_at - now).total_seconds() / 3600)
        notify(
            f"Due soon: {assign.title}",
            f"{hours_left}h remaining, {assign.subject_code or 'No subject'}",
            urgency="critical",
            profile=profile,
        )
        assign.deadline_notified_stage = "urgent"
        assign.save(update_fields=["deadline_notified_stage"])
        count += 1

    # Warning: due within 48 hours
    warning = AssignmentItem.objects.filter(
        profile=profile,
        status="open",
        due_at__gte=now + timedelta(hours=24),
        due_at__lte=now + timedelta(hours=48),
    ).exclude(deadline_notified_stage__in=["warning", "urgent"])
    for assign in warning:
        notify(
            f"Due tomorrow: {assign.title}",
            f"Due in {(assign.due_at - now).total_seconds() / 3600:.0f}h",
            urgency="normal",
            profile=profile,
        )
        assign.deadline_notified_stage = "warning"
        assign.save(update_fields=["deadline_notified_stage"])
        count += 1

    # Missed
    missed = AssignmentItem.objects.filter(
        profile=profile,
        status="open",
        due_at__lt=now,
    ).exclude(deadline_notified_stage="missed")
    for assign in missed:
        notify(
            f"Missed: {assign.title}",
            f"Was due {assign.due_at.strftime('%Y-%m-%d %H:%M') if assign.due_at else 'unknown'}",
            urgency="critical",
            profile=profile,
        )
        assign.deadline_notified_stage = "missed"
        assign.save(update_fields=["deadline_notified_stage"])
        count += 1

    return count


def notify_muele_sync(result: dict, profile=None) -> None:
    """Send a notification after a MUELE sync completes."""
    if result.get("downloaded", 0) > 0:
        notify(
            "MUELE sync complete",
            f"{result['downloaded']} new files downloaded, "
            f"{result['skipped']} skipped, "
            f"{result['errors']} errors",
            profile=profile,
        )


def notify_file_sorted(filename: str, method: str, destination: str, profile=None) -> None:
    """Notify that a file was sorted."""
    method_labels = {
        "course_code": "Subject match",
        "topic": "Topic match",
        "muele_sync": "MUELE download",
        "ebook": "Ebook",
        "sensitive": "Sensitive file",
        "media": "Media",
        "installer": "Installer",
        "unsorted": "Unsorted",
        "needs_sorting": "Needs sorting",
    }
    label = method_labels.get(method, method)
    notify(label, f"{filename} → {Path(destination).parent.name}", urgency="low", profile=profile)


# Import Path here to avoid circular imports at module level
from pathlib import Path  # noqa: E402