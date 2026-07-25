"""Weakness Radar -- a read-only, cross-subject aggregation of signals
already produced elsewhere: SubjectMemory.weak_areas (see
organizer.core.past_papers.update_weak_areas), SubjectMemory.last_touched_at,
and which sorted files have never had a review scheduled. No new model and
no new producer here -- this only reads and ranks what already exists, the
same "local database aggregation, no paid AI" spirit as Organization DNA.

"Files never opened" from the product ask is deliberately reinterpreted as
"files with no review scheduled" -- this app has no file-access tracking,
so it can't know whether a file was ever opened, only whether Orch's own
review queue has anything recorded against it.
"""

from datetime import timedelta

from django.utils import timezone

NEGLECT_THRESHOLD_DAYS = 14
MAX_UNREVIEWED_RESOURCES = 20


def _neglect_sort_key(memory) -> float:
    """Never-touched (None) sorts as more urgent than any real timestamp."""
    return memory.last_touched_at.timestamp() if memory.last_touched_at else -1.0


def build_radar(profile) -> dict:
    from organizer.models import MoveEvent, SubjectMemory

    memories = list(SubjectMemory.objects.filter(profile=profile))
    flagged = [m for m in memories if m.weak_areas]

    subject_weak_areas = [
        {"code": m.code, "weak_areas": m.weak_areas, "last_touched_at": m.last_touched_at}
        for m in flagged
    ]

    # A topic corroborated across more than one subject's own weak-areas
    # list is a stronger "repeatedly missed" signal than any single
    # subject's own analysis on its own.
    topic_subjects: dict[str, set] = {}
    for memory in flagged:
        for area in memory.weak_areas:
            key = area.strip().lower()
            if key:
                topic_subjects.setdefault(key, set()).add(memory.code)
    repeated_topics = [
        {"topic": key, "subjects": sorted(codes)}
        for key, codes in topic_subjects.items()
        if len(codes) > 1
    ]
    repeated_topics.sort(key=lambda t: -len(t["subjects"]))

    cutoff = timezone.now() - timedelta(days=NEGLECT_THRESHOLD_DAYS)
    neglected_subjects = sorted(
        (m for m in memories if not m.last_touched_at or m.last_touched_at < cutoff),
        key=_neglect_sort_key,
    )

    unreviewed_resources = list(
        MoveEvent.objects.filter(profile=profile, success=True)
        .exclude(course_code="").exclude(course_code__isnull=True)
        .filter(review_items__isnull=True)
        .order_by("-timestamp")[:MAX_UNREVIEWED_RESOURCES]
    )

    headline = None
    if flagged:
        most_urgent = min(flagged, key=_neglect_sort_key)
        headline = {"subject_code": most_urgent.code, "topic": most_urgent.weak_areas[0]}

    return {
        "subject_weak_areas": subject_weak_areas,
        "repeated_topics": repeated_topics,
        "neglected_subjects": neglected_subjects,
        "unreviewed_resources": unreviewed_resources,
        "headline": headline,
    }
