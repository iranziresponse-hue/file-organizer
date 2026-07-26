"""Snapshot for the persistent status bar shown in base.html on every page
-- what Orch is watching, what happened last, what's waiting, and whether
anything is syncing in the background right now."""

from django.utils import timezone


def _short_timesince(value):
    if not value:
        return None
    current = timezone.now()
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    seconds = max(0, int((current - value).total_seconds()))
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hr ago"
    days = hours // 24
    return f"{days} day{'s' if days != 1 else ''} ago"


def get_snapshot(profile):
    """Plain-dict snapshot, safe to call on every request (a handful of
    small indexed queries, no heavy diagnostics scan)."""
    from ..models import AppSettings, BackgroundTask, IntegrationConnection, MoveEvent, ReviewItem
    from pathlib import Path

    if not profile:
        return {
            "has_profile": False,
            "watching": None,
            "last_move": None,
            "pending_review": 0,
            "sync": None,
            "background_task": None,
        }

    settings = AppSettings.get_solo()
    watching = Path(settings.downloads_path).name if settings.downloads_path else None

    last_move = MoveEvent.objects.filter(profile=profile).order_by("-timestamp").first()
    last_move_text = (
        f"{last_move.filename} ({_short_timesince(last_move.timestamp)})" if last_move else None
    )

    pending_review = ReviewItem.objects.filter(profile=profile, status="queued").count()

    connected_count = IntegrationConnection.objects.filter(
        profile=profile, status="connected"
    ).count()
    sync = f"{connected_count} connected" if connected_count else "Local only"

    active_task = (
        BackgroundTask.objects.filter(profile=profile, status__in=["queued", "running"])
        .order_by("-created_at")
        .first()
    )
    background_task = None
    if active_task:
        background_task = {
            "label": active_task.get_kind_display(),
            "progress_current": active_task.progress_current,
            "progress_total": active_task.progress_total,
        }

    return {
        "has_profile": True,
        "watching": watching,
        "last_move": last_move_text,
        "pending_review": pending_review,
        "sync": sync,
        "background_task": background_task,
    }
