"""Smart review queue with spaced repetition scheduling.

Uses a simplified SM-2 algorithm to schedule reviews: new items start
at 1 day, then 3 days, 7 days, 14 days, 30 days, and eventually 90 days
if consistently marked as "done". Items marked "skip" are rescheduled
at half the interval.
"""

from datetime import timedelta
from pathlib import Path
from typing import Callable

from django.db.models import Count
from django.utils import timezone

# Spaced repetition intervals (in days) for progressive scheduling
_INTERVALS = [1, 3, 7, 14, 30, 60, 90]


def _next_interval(current_index: int, success: bool) -> int:
    """Calculate the next review interval based on spaced repetition.

    On success: advance to the next interval level.
    On failure/skip: drop back one level (minimum 1 day).
    """
    if success:
        next_idx = min(current_index + 1, len(_INTERVALS) - 1)
    else:
        next_idx = max(current_index - 1, 0)
    return _INTERVALS[next_idx]


def _determine_review_index(review_item) -> int:
    """Determine which interval index a review item is currently at
    based on how many times it's been reviewed."""
    from organizer.models import LearningActivity

    past_reviews = LearningActivity.objects.filter(
        profile=review_item.profile,
        move_event=review_item.move_event,
        activity_type__in=["review_scheduled", "review_completed"],
    ).count()
    return min(past_reviews, len(_INTERVALS) - 1)


def auto_schedule_reviews(
    profile,
    limit: int = 20,
    log: Callable | None = None,
) -> int:
    """Automatically create review items from recently sorted study files.

    Scans the most recent MoveEvents for the profile that have a course_code
    and are summarizable documents. Creates a ReviewItem for each one if
    one doesn't already exist, scheduled at the appropriate interval.

    Returns the number of new review items created.
    """
    from organizer.models import LearningActivity, MoveEvent, ReviewItem

    events = (
        MoveEvent.objects.filter(profile=profile, success=True)
        .exclude(course_code__isnull=True)
        .exclude(course_code="")
        .order_by("-timestamp")[:limit]
    )

    now = timezone.now()
    created = 0

    for event in events:
        # Skip if already has a review item
        if ReviewItem.objects.filter(profile=profile, move_event=event).exists():
            continue

        # Schedule at 1 day after the file was sorted (spaced repetition start)
        due_at = event.timestamp + timedelta(days=1)
        if due_at < now:
            due_at = now + timedelta(hours=4)  # Due in 4 hours if already overdue

        title = f"Review: {Path(event.filename).stem}"
        try:
            item = ReviewItem.objects.create(
                profile=profile,
                move_event=event,
                subject_code=event.course_code or "",
                title=title[:180],
                reason="Learning material to review",
                due_at=due_at,
                priority="normal",
                metadata={
                    "source": "auto_schedule",
                    "interval_index": 0,
                    "filename": event.filename,
                },
            )
            LearningActivity.objects.create(
                profile=profile,
                move_event=event,
                activity_type="review_scheduled",
                subject_code=event.course_code or "",
                title=f"Review scheduled: {title}",
                details=f"Due: {due_at.strftime('%Y-%m-%d %H:%M')}",
            )
            created += 1
        except Exception as exc:
            if log:
                log(f"Review scheduling failed for '{event.filename}': {exc}")

    return created


def mark_review_done(review_item) -> None:
    """Mark a review item as completed and create the next queued review
    item with a later due date based on spaced repetition."""
    from organizer.models import LearningActivity, ReviewItem

    current_idx = int(review_item.metadata.get("interval_index", 0))
    next_days = _next_interval(current_idx, success=True)

    review_item.status = "done"
    review_item.completed_at = timezone.now()
    review_item.save()

    LearningActivity.objects.create(
        profile=review_item.profile,
        move_event=review_item.move_event,
        activity_type="review_scheduled",
        subject_code=review_item.subject_code,
        title=f"Review completed: {review_item.title}",
        details=f"Next review in {next_days} day(s)",
    )

    # Create the next review item at the next interval
    next_due = timezone.now() + timedelta(days=next_days)
    ReviewItem.objects.create(
        profile=review_item.profile,
        move_event=review_item.move_event,
        subject_code=review_item.subject_code,
        title=review_item.title,
        reason=f"Spaced repetition (interval: {next_days} day(s))",
        due_at=next_due,
        priority=review_item.priority,
        metadata={
            "interval_index": current_idx + 1,
            "source": "spaced_repetition",
            "previous_review": review_item.pk,
        },
    )


def skip_review(review_item) -> None:
    """Skip a review item. Creates a new queued item at a shorter interval."""
    from organizer.models import LearningActivity, ReviewItem

    current_idx = int(review_item.metadata.get("interval_index", 0))
    next_days = _next_interval(current_idx, success=False)

    review_item.status = "skipped"
    review_item.completed_at = timezone.now()
    review_item.save()

    LearningActivity.objects.create(
        profile=review_item.profile,
        move_event=review_item.move_event,
        activity_type="review_scheduled",
        subject_code=review_item.subject_code,
        title=f"Review skipped: {review_item.title}",
        details=f"Will be rescheduled in {next_days} day(s)",
    )

    # Create a new review item at the shorter interval
    next_due = timezone.now() + timedelta(days=next_days)
    ReviewItem.objects.create(
        profile=review_item.profile,
        move_event=review_item.move_event,
        subject_code=review_item.subject_code,
        title=review_item.title,
        reason=f"Rescheduled after skip (interval: {next_days} day(s))",
        due_at=next_due,
        priority=review_item.priority,
        metadata={
            "interval_index": max(current_idx - 1, 0),
            "source": "rescheduled_after_skip",
            "previous_review": review_item.pk,
        },
    )


def reschedule_overdue(profile, batch_size: int = 10) -> int:
    """Find overdue review items and reschedule them with higher priority.

    Returns the number of items rescheduled.
    """
    from organizer.models import ReviewItem

    now = timezone.now()
    overdue = ReviewItem.objects.filter(
        profile=profile,
        status="queued",
        due_at__lt=now,
    )[:batch_size]

    count = 0
    for item in overdue:
        # Boost priority for overdue items
        if item.priority == "low":
            item.priority = "normal"
        elif item.priority == "normal":
            item.priority = "high"

        # Reschedule to 4 hours from now
        item.due_at = now + timedelta(hours=4)
        # Drop interval index to reschedule sooner
        current_idx = int(item.metadata.get("interval_index", 0))
        item.metadata["interval_index"] = max(current_idx - 1, 0)
        item.metadata["rescheduled"] = True
        item.save()
        count += 1

    return count


def get_due_reviews(profile, limit: int = 20):
    """Get all queued review items for a profile, prioritized by due date
    and priority level."""
    from organizer.models import ReviewItem

    return ReviewItem.objects.filter(
        profile=profile,
        status="queued",
    ).order_by("due_at", "-priority")[:limit]


def get_overdue_count(profile) -> int:
    """Get the count of overdue review items."""
    from organizer.models import ReviewItem

    return ReviewItem.objects.filter(
        profile=profile,
        status="queued",
        due_at__lt=timezone.now(),
    ).count()


def get_stats(profile) -> dict:
    """Get review queue statistics for a profile."""
    from organizer.models import ReviewItem

    now = timezone.now()
    all_items = ReviewItem.objects.filter(profile=profile)
    return {
        "total": all_items.count(),
        "queued": all_items.filter(status="queued").count(),
        "done": all_items.filter(status="done").count(),
        "skipped": all_items.filter(status="skipped").count(),
        "overdue": all_items.filter(status="queued", due_at__lt=now).count(),
        "due_today": all_items.filter(
            status="queued",
            due_at__gte=now - timedelta(days=1),
            due_at__lte=now + timedelta(days=1),
        ).count(),
        "by_priority": {
            "high": all_items.filter(status="queued", priority="high").count(),
            "normal": all_items.filter(status="queued", priority="normal").count(),
            "low": all_items.filter(status="queued", priority="low").count(),
        },
        "by_subject": list(
            all_items.filter(status="queued")
            .exclude(subject_code="")
            .values("subject_code")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        ),
    }