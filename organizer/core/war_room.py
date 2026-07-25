"""Semester War Room -- the single-screen synthesis of every study signal
Orch already tracks: today's classes, upcoming exams, MUELE deadlines,
course units, past-paper risk areas, weak topics, study streak, and grade
targets, plus one next-best-action callout. Pure aggregation over existing
data (TimetableEntry, AssignmentItem, SubjectMemory, PastPaperAnalysis,
GradeTarget, Flashcard, LearningActivity) -- no new model, no new producer,
no paid AI.
"""

from datetime import date, timedelta

from django.db.models import Q
from django.utils import timezone

UPCOMING_EXAMS_LIMIT = 5
MUELE_DEADLINES_LIMIT = 5
PAST_PAPER_RISK_LIMIT = 8
NEAR_EXAM_DAYS = 3


def _todays_classes(profile):
    from organizer.models import TimetableEntry

    today = date.today()
    return list(
        TimetableEntry.objects.filter(profile=profile, kind="teaching")
        .filter(Q(specific_date=today) | Q(specific_date__isnull=True, weekday=today.weekday()))
        .order_by("start_time")
    )


def _upcoming_exams(profile, limit: int = UPCOMING_EXAMS_LIMIT) -> list[dict]:
    from organizer.models import TimetableEntry

    today = date.today()
    entries = TimetableEntry.objects.filter(
        profile=profile, kind__in=["test", "examination"], specific_date__gte=today,
    ).order_by("specific_date")[:limit]
    return [
        {
            "subject_code": entry.course_code,
            "kind_display": entry.get_kind_display(),
            "days_left": (entry.specific_date - today).days,
        }
        for entry in entries
    ]


def _muele_deadlines(profile, limit: int = MUELE_DEADLINES_LIMIT):
    from organizer.models import AssignmentItem

    return list(
        AssignmentItem.objects.filter(profile=profile, source="muele", status="open").order_by("due_at")[:limit]
    )


def _course_units(profile):
    from organizer.models import SubjectMemory

    return list(SubjectMemory.objects.filter(profile=profile).order_by("code"))


def _past_paper_risk_areas(profile, limit: int = PAST_PAPER_RISK_LIMIT) -> list[dict]:
    from organizer.models import PastPaperAnalysis

    topic_weight: dict[str, int] = {}
    topic_display: dict[str, str] = {}
    topic_subjects: dict[str, set] = {}

    for analysis in PastPaperAnalysis.objects.filter(profile=profile):
        for topic in analysis.topics[:10]:
            name = (topic.get("name") or "").strip()
            if not name:
                continue
            key = name.lower()
            weight = topic.get("weight", 0)
            if weight > topic_weight.get(key, -1):
                topic_weight[key] = weight
                topic_display[key] = name
            topic_subjects.setdefault(key, set()).add(analysis.subject_code)

    rows = [
        {"topic": topic_display[key], "weight": weight, "subjects": sorted(topic_subjects[key])}
        for key, weight in topic_weight.items()
    ]
    rows.sort(key=lambda r: -r["weight"])
    return rows[:limit]


def _grade_targets(profile) -> list[dict]:
    from organizer.models import GradeTarget

    from . import grade_planner

    rows = []
    for target in GradeTarget.objects.filter(profile=profile):
        result = grade_planner.required_exam_score(
            coursework_weight=target.coursework_weight,
            coursework_score=target.coursework_score,
            test_weight=target.test_weight,
            test_score=target.test_score,
            exam_weight=target.exam_weight,
            target_percent=target.target_percent,
        )
        rows.append({"target": target, "result": result})
    return rows


def _study_streak(profile) -> int:
    """Consecutive days with at least one LearningActivity, ending today or
    yesterday. A streak more than a day stale is honestly reported as
    broken (0), not fudged forward."""
    from organizer.models import LearningActivity

    activity_dates = set(
        LearningActivity.objects.filter(profile=profile).values_list("happened_at__date", flat=True)
    )
    if not activity_dates:
        return 0

    today = timezone.localdate()
    anchor = today if today in activity_dates else today - timedelta(days=1)
    if anchor not in activity_dates:
        return 0

    streak = 0
    day = anchor
    while day in activity_dates:
        streak += 1
        day -= timedelta(days=1)
    return streak


def _next_best_action(upcoming_exams: list, weak_radar: dict, due_flashcards: int) -> str:
    """A small, separate priority ladder from views._next_best_action --
    that one governs the general cockpit's sorting/inbox/timetable
    priorities; this one is specifically about academic performance."""
    for exam in upcoming_exams:
        if exam["days_left"] <= NEAR_EXAM_DAYS and exam["subject_code"]:
            return f"{exam['subject_code']} exam in {exam['days_left']} day(s): prioritize revision now."

    headline = weak_radar.get("headline")
    if headline:
        return f"Focus on {headline['subject_code']}: {headline['topic']}, your weakest flagged area."

    if due_flashcards:
        return f"{due_flashcards} flashcard(s) due for review."

    if upcoming_exams:
        exam = upcoming_exams[0]
        return f"Next exam: {exam['subject_code'] or 'unlabeled'} in {exam['days_left']} day(s)."

    return "Nothing urgent flagged. Good time to get ahead on revision, or run Past Paper Intelligence for a subject."


def build_war_room(profile) -> dict:
    from organizer.models import Flashcard

    from . import weakness_radar as weakness_radar_core

    upcoming_exams = _upcoming_exams(profile)
    weak_radar = weakness_radar_core.build_radar(profile)
    due_flashcards = Flashcard.objects.filter(
        profile=profile, status="active", due_at__lte=timezone.now()
    ).count()

    return {
        "today_classes": _todays_classes(profile),
        "upcoming_exams": upcoming_exams,
        "muele_deadlines": _muele_deadlines(profile),
        "course_units": _course_units(profile),
        "past_paper_risk_areas": _past_paper_risk_areas(profile),
        "weak_radar": weak_radar,
        "study_streak": _study_streak(profile),
        "grade_targets": _grade_targets(profile),
        "due_flashcards": due_flashcards,
        "next_best_action": _next_best_action(upcoming_exams, weak_radar, due_flashcards),
    }
