"""Study digest generation — daily and weekly summaries with rich metrics,
subject breakdowns, review queues, assignment deadlines, and desktop
notifications.
"""

from datetime import timedelta
from typing import Callable

from django.db.models import Count
from django.utils import timezone


def _gather_metrics(profile, start, end):
    """Gather all metrics for a given time period."""
    from organizer.models import (
        AssignmentItem,
        LearningActivity,
        MoveEvent,
        ReviewItem,
        SubjectMemory,
    )

    events = MoveEvent.objects.filter(
        profile=profile, timestamp__gte=start, timestamp__lte=end
    )
    method_counts = list(
        events.values("method").annotate(total=Count("id")).order_by("-total")
    )
    subject_counts = list(
        events.exclude(course_code__isnull=True)
        .exclude(course_code="")
        .values("course_code")
        .annotate(total=Count("id"))
        .order_by("-total")[:8]
    )
    method_labels = dict(MoveEvent.METHOD_CHOICES)
    for row in method_counts:
        row["label"] = method_labels.get(row["method"], row["method"])

    subject_memories = SubjectMemory.objects.filter(profile=profile)
    active_subjects = subject_memories.filter(resource_count__gt=0).count()

    return {
        "files_sorted": events.count(),
        "summaries_ready": events.filter(summary__isnull=False).count(),
        "unsorted_items": events.filter(method__in=["unsorted", "needs_sorting"]).count(),
        "muele_downloads": events.filter(method="muele_sync").count(),
        "methods": method_counts,
        "subjects": subject_counts,
        "active_subjects": active_subjects,
        "total_subjects": subject_memories.count(),
        "reviews_due": ReviewItem.objects.filter(
            profile=profile, status="queued", due_at__lte=end
        ).count(),
        "reviews_overdue": ReviewItem.objects.filter(
            profile=profile, status="queued", due_at__lt=timezone.now()
        ).count(),
        "reviews_completed": ReviewItem.objects.filter(
            profile=profile, status="done", completed_at__gte=start, completed_at__lte=end
        ).count(),
        "open_assignments": AssignmentItem.objects.filter(
            profile=profile, status="open"
        ).count(),
        "missed_assignments": AssignmentItem.objects.filter(
            profile=profile, status="missed"
        ).count(),
        "activities": LearningActivity.objects.filter(
            profile=profile, happened_at__gte=start, happened_at__lte=end
        ).count(),
        "period_days": (end - start).days,
    }


def _build_content(metrics, profile_name, period_label) -> str:
    """Build rich digest content text with sections."""
    lines = []
    lines.append(f"# {profile_name}")
    lines.append(f"## Study Digest ({period_label})")
    lines.append("")

    # Overview
    lines.append("## Overview")
    lines.append(
        f"In the last {metrics['period_days']} day(s), Orch handled "
        f"{metrics['files_sorted']} files, created {metrics['summaries_ready']} "
        f"summaries, and logged {metrics['activities']} learning activities."
    )
    lines.append("")

    # Files breakdown
    lines.append("## Files Breakdown")
    if metrics["methods"]:
        for method in metrics["methods"]:
            lines.append(
                f"{method['total']} files by {method['label']}"
            )
    else:
        lines.append("No files were sorted in this period.")
    if metrics["muele_downloads"] > 0:
        lines.append(f"{metrics['muele_downloads']} files came from MUELE sync.")
    if metrics["unsorted_items"] > 0:
        lines.append(
            f"{metrics['unsorted_items']} file(s) need sorting attention."
        )
    lines.append("")

    # Subjects
    lines.append("## Subject Activity")
    if metrics["subjects"]:
        lines.append(f"Active subjects this period: {metrics['active_subjects']} of {metrics['total_subjects']} total.")
        for subject in metrics["subjects"]:
            lines.append(f"{subject['course_code']}: {subject['total']} file(s)")
    else:
        lines.append("No subject activity in this period.")
    lines.append("")

    # Reviews
    lines.append("## Review Queue")
    lines.append(f"{metrics['reviews_due']} review(s) due.")
    if metrics['reviews_overdue'] > 0:
        lines.append(f"{metrics['reviews_overdue']} review(s) are overdue. Check the review queue.")
    if metrics['reviews_completed'] > 0:
        lines.append(f"{metrics['reviews_completed']} review(s) completed.")
    lines.append("")

    # Assignments
    lines.append("## Assignments & Deadlines")
    lines.append(f"{metrics['open_assignments']} open assignment(s).")
    if metrics['missed_assignments'] > 0:
        lines.append(f"{metrics['missed_assignments']} assignment(s) missed.")
    lines.append("")

    # Closing
    lines.append("## Next Steps")
    next_steps = []
    if metrics["unsorted_items"] > 0:
        next_steps.append("Review unsorted files in your profile folders.")
    if metrics["reviews_due"] > 0:
        next_steps.append("Complete pending reviews in the review queue.")
    if metrics["missed_assignments"] > 0:
        next_steps.append("Check on missed assignments.")
    if metrics["muele_downloads"] > 0:
        next_steps.append("Review new MUELE course materials.")
    if not next_steps:
        next_steps.append("Keep learning. Everything is in order.")
    for step in next_steps:
        lines.append(f"- {step}")

    return "\n".join(lines)


def generate_daily_digest(
    profile,
    log: Callable | None = None,
) -> object | None:
    """Generate a daily study digest for a profile.

    Covers the last 24 hours. Returns the LearningDigest object, or None
    if there's nothing to report.
    """
    from organizer.models import LearningActivity, LearningDigest

    end = timezone.now()
    start = end - timedelta(days=1)

    metrics = _gather_metrics(profile, start, end)

    # Skip if nothing happened
    if metrics["files_sorted"] == 0 and metrics["activities"] == 0:
        return None

    period_label = start.strftime("%b %d") + " to " + end.strftime("%b %d, %Y")
    content = _build_content(metrics, profile.name, period_label)

    digest = LearningDigest.objects.create(
        profile=profile,
        period_start=start,
        period_end=end,
        title=f"{profile.name}: Daily Digest ({period_label})",
        content=content,
        metrics=metrics,
    )

    LearningActivity.objects.create(
        profile=profile,
        activity_type="digest_created",
        title=f"Daily digest: {metrics['files_sorted']} files, {metrics['reviews_due']} reviews due",
        details=f"Period: {period_label}",
        metadata={"digest_id": digest.pk, "period": "daily", "metrics": metrics},
    )

    # Notify via desktop
    if metrics["files_sorted"] > 0 or metrics["reviews_due"] > 0:
        from .notifications import notify

        notify(
            f"Daily digest: {profile.name}",
            f"{metrics['files_sorted']} files sorted, "
            f"{metrics['reviews_due']} reviews due, "
            f"{metrics['open_assignments']} assignments open",
        )

    return digest


def generate_weekly_digest(
    profile,
    log: Callable | None = None,
) -> object | None:
    """Generate a weekly study digest for a profile.

    Covers the last 7 days. Returns the LearningDigest object.
    """
    from organizer.models import LearningActivity, LearningDigest

    end = timezone.now()
    start = end - timedelta(days=7)

    metrics = _gather_metrics(profile, start, end)

    period_label = start.strftime("%b %d") + " to " + end.strftime("%b %d, %Y")
    content = _build_content(metrics, profile.name, period_label)

    digest = LearningDigest.objects.create(
        profile=profile,
        period_start=start,
        period_end=end,
        title=f"{profile.name}: Weekly Digest ({period_label})",
        content=content,
        metrics=metrics,
    )

    LearningActivity.objects.create(
        profile=profile,
        activity_type="digest_created",
        title=f"Weekly digest: {metrics['files_sorted']} files, {metrics['active_subjects']} subjects active",
        details=f"Period: {period_label}",
        metadata={"digest_id": digest.pk, "period": "weekly", "metrics": metrics},
    )

    # Notify via desktop
    from .notifications import notify

    notify(
        f"Weekly digest: {profile.name}",
        f"{metrics['files_sorted']} files, "
        f"{metrics['active_subjects']} subjects active, "
        f"{metrics['reviews_due']} reviews due, "
        f"{metrics['open_assignments']} assignments",
    )

    return digest


def generate_digests_for_all_profiles(
    period: str = "weekly",
    log: Callable | None = None,
) -> list:
    """Generate digests for all active profiles.

    period: "daily" or "weekly".
    Returns list of generated digest objects.
    """
    from organizer.models import Profile

    digests = []
    profiles = Profile.objects.all()
    generator = generate_daily_digest if period == "daily" else generate_weekly_digest

    for profile in profiles:
        try:
            digest = generator(profile, log=log)
            if digest:
                digests.append(digest)
                if log:
                    log(f"Digest generated for '{profile.name}' ({period})")
        except Exception as exc:
            if log:
                log(f"Digest failed for '{profile.name}': {exc}")

    return digests


def get_recent_digests(profile, limit: int = 5) -> list:
    """Get the most recent digests for a profile."""
    from organizer.models import LearningDigest

    return LearningDigest.objects.filter(profile=profile).order_by("-period_end")[:limit]


def get_digest_schedule_info(profile) -> dict:
    """Get information about digest generation for a profile."""
    from organizer.models import LearningDigest

    now = timezone.now()
    latest = LearningDigest.objects.filter(profile=profile).order_by("-period_end").first()

    if latest:
        hours_since = (now - latest.period_end).total_seconds() / 3600
        last_type = latest.metrics.get("period_days", 7)
        last_type_label = "daily" if last_type == 1 else "weekly"
    else:
        hours_since = None
        last_type_label = "never"

    return {
        "latest": latest,
        "hours_since_last": hours_since,
        "last_type": last_type_label,
        "total_digests": LearningDigest.objects.filter(profile=profile).count(),
    }