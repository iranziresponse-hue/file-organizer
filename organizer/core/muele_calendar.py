"""Makerere University academic calendar awareness.

Provides semester dates, holiday periods, exam periods, and current
academic context for the MUELE integration. This is used to:
1. Determine the current semester automatically
2. Set appropriate sync periods
3. Provide context for timetable/calendar sync
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Tuple


@dataclass
class AcademicPeriod:
    """A defined academic period at Makerere University."""
    name: str  # e.g. "Semester 1", "Semester 2", "Semester 3", "Recess"
    start: date
    end: date
    is_exam_period: bool = False
    is_holiday: bool = False


# Makerere University typical academic calendar (approximate dates)
# These are updated based on the official Makerere academic calendar.
# The calendar follows: Semester 1 (Aug-Dec), Semester 2 (Jan-May),
# Semester 3/Recess (Jun-Jul)
_ACADEMIC_YEARS: dict[int, list[AcademicPeriod]] = {
    2025: [
        AcademicPeriod("Semester 1", date(2025, 8, 18), date(2025, 12, 5)),
        AcademicPeriod("Semester 1 Exams", date(2025, 12, 8), date(2025, 12, 19), is_exam_period=True),
        AcademicPeriod("Christmas Break", date(2025, 12, 20), date(2026, 1, 12), is_holiday=True),
        AcademicPeriod("Semester 2", date(2026, 1, 13), date(2026, 5, 8)),
        AcademicPeriod("Semester 2 Exams", date(2026, 5, 11), date(2026, 5, 22), is_exam_period=True),
        AcademicPeriod("Semester 3 / Recess", date(2026, 6, 1), date(2026, 7, 31)),
    ],
    2026: [
        AcademicPeriod("Semester 1", date(2026, 8, 17), date(2026, 12, 4)),
        AcademicPeriod("Semester 1 Exams", date(2026, 12, 7), date(2026, 12, 18), is_exam_period=True),
        AcademicPeriod("Christmas Break", date(2026, 12, 19), date(2027, 1, 11), is_holiday=True),
        AcademicPeriod("Semester 2", date(2027, 1, 12), date(2027, 5, 7)),
        AcademicPeriod("Semester 2 Exams", date(2027, 5, 10), date(2027, 5, 21), is_exam_period=True),
        AcademicPeriod("Semester 3 / Recess", date(2027, 6, 1), date(2027, 7, 31)),
    ],
}


def get_current_period(today: date | None = None) -> AcademicPeriod | None:
    """Get the current academic period for Makerere University.

    Returns the AcademicPeriod that contains today's date, or None
    if no period is defined for the current date.
    """
    if today is None:
        today = date.today()

    for year, periods in _ACADEMIC_YEARS.items():
        for period in periods:
            if period.start <= today <= period.end:
                return period
    return None


def get_current_semester(today: date | None = None) -> str:
    """Get the current semester label (e.g. 'Semester 1', 'Semester 2')."""
    period = get_current_period(today)
    if period and "Semester" in period.name and not period.is_exam_period:
        return period.name
    if period and period.is_exam_period:
        return period.name.replace(" Exams", "")
    if period and period.is_holiday:
        # Return the upcoming semester
        next_periods = get_upcoming_periods(today, count=2)
        for p in next_periods:
            if "Semester" in p.name and not p.is_exam_period:
                return p.name
    return "Semester 1"  # Default


def get_current_year(today: date | None = None) -> str:
    """Get the current academic year (e.g. 'Year 1', 'Year 2')."""
    period = get_current_period(today)
    if period and "Semester 1" in period.name:
        return "Year 1"
    if period and "Semester 2" in period.name:
        return "Year 1"
    if period and "Semester 3" in period.name:
        return "Year 1"
    return "Year 1"


def get_academic_year_range(today: date | None = None) -> tuple[int, int]:
    """Get the current academic year range (e.g. (2025, 2026) for 2025/2026)."""
    if today is None:
        today = date.today()
    # Academic year starts in August
    if today.month >= 8:
        return (today.year, today.year + 1)
    else:
        return (today.year - 1, today.year)


def get_semester_weeks(today: date | None = None) -> int:
    """Get how many weeks into the current semester we are."""
    period = get_current_period(today)
    if not period or period.is_holiday:
        return 0
    now = today or date.today()
    delta = now - period.start
    return max(0, delta.days // 7)


def get_remaining_weeks(today: date | None = None) -> int:
    """Get how many weeks remain in the current period."""
    period = get_current_period(today)
    if not period:
        return 0
    now = today or date.today()
    delta = period.end - now
    return max(0, delta.days // 7)


def get_upcoming_periods(today: date | None = None, count: int = 3) -> list[AcademicPeriod]:
    """Get upcoming academic periods."""
    if today is None:
        today = date.today()

    upcoming = []
    for year, periods in _ACADEMIC_YEARS.items():
        for period in periods:
            if period.start > today:
                upcoming.append(period)
                if len(upcoming) >= count:
                    return upcoming
    return upcoming


def is_exam_period(today: date | None = None) -> bool:
    """Check if we're currently in an exam period."""
    period = get_current_period(today)
    return bool(period and period.is_exam_period)


def is_holiday(today: date | None = None) -> bool:
    """Check if we're currently in a holiday period."""
    period = get_current_period(today)
    return bool(period and period.is_holiday)


def get_semester_dates(year: int, semester: int) -> tuple[date, date] | None:
    """Get the start and end dates for a specific semester."""
    periods = _ACADEMIC_YEARS.get(year, [])
    target = f"Semester {semester}"
    for period in periods:
        if period.name == target:
            return (period.start, period.end)
    return None