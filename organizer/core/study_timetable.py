"""Smart Study Timetable -- a priority engine, not a calendar. Generates a
short list of suggested study blocks for the days ahead, computed fresh
every time from assignments, exams, classes, weak areas, and past-paper
questions already tracked elsewhere. Nothing here is persisted: reloading
the page regenerates it, the same read-only aggregation pattern as Exam
Countdown / Weakness Radar / the War Room.
"""

from datetime import date, timedelta

from django.db.models import Q
from django.utils import timezone

DAYS_AHEAD = 7
ASSIGNMENT_LOOKAHEAD_DAYS = 4
CLASS_PREP_LOOKAHEAD_DAYS = 3
MAX_BLOCKS = 12

_WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

_PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}


def _day_label(day: date, today: date) -> str:
    delta = (day - today).days
    if delta == 0:
        return "Today"
    if delta == 1:
        return "Tomorrow"
    return _WEEKDAY_NAMES[day.weekday()]


def _assignment_blocks(profile, today: date) -> list[dict]:
    from organizer.models import AssignmentItem

    blocks = []
    items = AssignmentItem.objects.filter(profile=profile, status="open", due_at__isnull=False)
    for item in items:
        due_date = timezone.localtime(item.due_at).date()
        days_left = (due_date - today).days
        if days_left < 0 or days_left > ASSIGNMENT_LOOKAHEAD_DAYS:
            continue
        block_day = max(today, due_date - timedelta(days=1))
        blocks.append({
            "day": block_day,
            "day_label": _day_label(block_day, today),
            "subject_code": item.subject_code,
            "action": f"Work on '{item.title}'",
            "reason": "due today" if days_left == 0 else f"due in {days_left} day(s)",
            "priority": "high" if days_left <= 1 else "normal",
        })
    return blocks


def _exam_blocks(profile, today: date) -> list[dict]:
    from organizer.models import TimetableEntry

    blocks = []
    entries = TimetableEntry.objects.filter(
        profile=profile, kind__in=["test", "examination"],
        specific_date__gte=today, specific_date__lte=today + timedelta(days=DAYS_AHEAD),
    ).order_by("specific_date")
    for entry in entries:
        days_left = (entry.specific_date - today).days
        block_day = max(today, entry.specific_date - timedelta(days=1))
        blocks.append({
            "day": block_day,
            "day_label": _day_label(block_day, today),
            "subject_code": entry.course_code,
            "action": "Revise for the exam",
            "reason": "exam today" if days_left == 0 else f"exam in {days_left} day(s)",
            "priority": "high" if days_left <= 2 else "normal",
        })
    return blocks


def _class_prep_blocks(profile, today: date) -> list[dict]:
    """"Revise X before Friday's class" -- for each upcoming teaching class
    in the next few days, if that subject has a weak area (preferred) or
    an existing focus theme, suggest revising it the day before. One block
    per subject, even if it has several class sessions in the window."""
    from organizer.models import SubjectMemory, SubjectTheme, TimetableEntry

    blocks = []
    seen_subjects = set()
    for offset in range(1, CLASS_PREP_LOOKAHEAD_DAYS + 1):
        day = today + timedelta(days=offset)
        entries = TimetableEntry.objects.filter(profile=profile, kind="teaching").filter(
            Q(specific_date=day) | Q(specific_date__isnull=True, weekday=day.weekday())
        )
        for entry in entries:
            code = entry.course_code
            if not code or code in seen_subjects:
                continue
            seen_subjects.add(code)

            topic = None
            memory = SubjectMemory.objects.filter(profile=profile, code=code).first()
            if memory and memory.weak_areas:
                topic = memory.weak_areas[0]
            else:
                theme = SubjectTheme.objects.filter(profile=profile, subject_code=code).order_by("-weight").first()
                if theme:
                    topic = theme.name
            if not topic:
                continue

            block_day = max(today, day - timedelta(days=1))
            day_label = _day_label(day, today)
            blocks.append({
                "day": block_day,
                "day_label": _day_label(block_day, today),
                "subject_code": code,
                "action": f"Revise {topic}",
                "reason": f"before {day_label.lower()}'s class",
                "priority": "normal",
            })
    return blocks


def _past_paper_filler_blocks(profile, today: date, covered_subjects_today: set) -> list[dict]:
    """"Do one past paper question from X" -- a light filler suggestion for
    a subject with real past-paper questions available that doesn't
    already have a block today."""
    from organizer.models import PastPaperAnalysis

    blocks = []
    for analysis in PastPaperAnalysis.objects.filter(profile=profile).exclude(questions=[]):
        if analysis.subject_code in covered_subjects_today:
            continue
        blocks.append({
            "day": today,
            "day_label": _day_label(today, today),
            "subject_code": analysis.subject_code,
            "action": "Do one past paper question",
            "reason": "keep exam practice warm",
            "priority": "low",
        })
    return blocks


def generate_study_blocks(profile, limit: int = MAX_BLOCKS) -> list[dict]:
    today = timezone.localdate()

    blocks = []
    blocks.extend(_assignment_blocks(profile, today))
    blocks.extend(_exam_blocks(profile, today))
    blocks.extend(_class_prep_blocks(profile, today))

    covered_subjects_today = {b["subject_code"] for b in blocks if b["day"] == today and b["subject_code"]}
    blocks.extend(_past_paper_filler_blocks(profile, today, covered_subjects_today))

    blocks.sort(key=lambda b: (b["day"], _PRIORITY_RANK.get(b["priority"], 1)))
    return blocks[:limit]


def group_by_day(blocks: list[dict]) -> dict:
    """Blocks are already day-sorted -- this is a straight grouping, no
    re-sort needed."""
    grouped: dict = {}
    for block in blocks:
        grouped.setdefault(block["day"], []).append(block)
    return grouped
