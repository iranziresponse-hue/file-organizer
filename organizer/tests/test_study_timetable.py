from datetime import date, time, timedelta

from django.urls import reverse
from django.utils import timezone

from organizer.core import study_timetable
from organizer.models import (
    AssignmentItem,
    IntegrationConnection,
    PastPaperAnalysis,
    SubjectMemory,
    SubjectTheme,
    TimetableEntry,
)

from .helpers import SandboxedPathsTestCase


class AssignmentBlocksTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_assignment_due_in_two_days_produces_a_block_the_day_before(self):
        today = date.today()
        AssignmentItem.objects.create(
            profile=self.profile, subject_code="CSC2100", title="Assignment 2",
            status="open", due_at=timezone.now() + timedelta(days=2),
        )

        blocks = study_timetable._assignment_blocks(self.profile, today)

        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["day"], today + timedelta(days=1))
        self.assertIn("due in 2 day", blocks[0]["reason"])
        self.assertIn("Assignment 2", blocks[0]["action"])

    def test_assignment_beyond_lookahead_is_excluded(self):
        today = date.today()
        AssignmentItem.objects.create(
            profile=self.profile, subject_code="CSC2100", title="Far off",
            status="open", due_at=timezone.now() + timedelta(days=30),
        )

        self.assertEqual(study_timetable._assignment_blocks(self.profile, today), [])

    def test_closed_assignments_are_excluded(self):
        today = date.today()
        AssignmentItem.objects.create(
            profile=self.profile, subject_code="CSC2100", title="Done",
            status="submitted", due_at=timezone.now() + timedelta(days=1),
        )

        self.assertEqual(study_timetable._assignment_blocks(self.profile, today), [])

    def test_due_today_gets_high_priority_and_todays_block(self):
        today = date.today()
        AssignmentItem.objects.create(
            profile=self.profile, subject_code="CSC2100", title="Due today",
            status="open", due_at=timezone.now(),
        )

        blocks = study_timetable._assignment_blocks(self.profile, today)

        self.assertEqual(blocks[0]["day"], today)
        self.assertEqual(blocks[0]["priority"], "high")


class ExamBlocksTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.connection = IntegrationConnection.objects.create(
            profile=self.profile, provider="mak_timetable", display_name="Timetable",
        )

    def test_exam_produces_a_block_the_day_before(self):
        today = date.today()
        TimetableEntry.objects.create(
            profile=self.profile, connection=self.connection, kind="examination",
            specific_date=today + timedelta(days=5), start_time=time(9, 0),
            course_code="CSC2100", raw_group="SE-2",
        )

        blocks = study_timetable._exam_blocks(self.profile, today)

        self.assertEqual(blocks[0]["day"], today + timedelta(days=4))
        self.assertIn("exam in 5 day", blocks[0]["reason"])


class ClassPrepBlocksTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.connection = IntegrationConnection.objects.create(
            profile=self.profile, provider="mak_timetable", display_name="Timetable",
        )

    def test_prefers_weak_area_over_theme(self):
        today = date.today()
        target_day = today + timedelta(days=1)
        TimetableEntry.objects.create(
            profile=self.profile, connection=self.connection, kind="teaching",
            weekday=target_day.weekday(), start_time=time(9, 0), course_code="CSC2100", raw_group="SE-2",
        )
        SubjectMemory.objects.create(profile=self.profile, code="CSC2100", weak_areas=["recursion"])
        SubjectTheme.objects.create(profile=self.profile, subject_code="CSC2100", name="loops", weight=99)

        blocks = study_timetable._class_prep_blocks(self.profile, today)

        self.assertEqual(len(blocks), 1)
        self.assertIn("recursion", blocks[0]["action"])

    def test_falls_back_to_top_theme_without_weak_areas(self):
        today = date.today()
        target_day = today + timedelta(days=1)
        TimetableEntry.objects.create(
            profile=self.profile, connection=self.connection, kind="teaching",
            weekday=target_day.weekday(), start_time=time(9, 0), course_code="CSC2100", raw_group="SE-2",
        )
        SubjectTheme.objects.create(profile=self.profile, subject_code="CSC2100", name="loops", weight=99)

        blocks = study_timetable._class_prep_blocks(self.profile, today)

        self.assertIn("loops", blocks[0]["action"])

    def test_only_one_block_per_subject_even_with_multiple_sessions(self):
        today = date.today()
        for offset in (1, 2):
            day = today + timedelta(days=offset)
            TimetableEntry.objects.create(
                profile=self.profile, connection=self.connection, kind="teaching",
                weekday=day.weekday(), start_time=time(9, 0), course_code="CSC2100", raw_group="SE-2",
            )
        SubjectMemory.objects.create(profile=self.profile, code="CSC2100", weak_areas=["recursion"])

        blocks = study_timetable._class_prep_blocks(self.profile, today)

        self.assertEqual(len(blocks), 1)

    def test_no_topic_available_produces_no_block(self):
        today = date.today()
        target_day = today + timedelta(days=1)
        TimetableEntry.objects.create(
            profile=self.profile, connection=self.connection, kind="teaching",
            weekday=target_day.weekday(), start_time=time(9, 0), course_code="CSC2100", raw_group="SE-2",
        )

        self.assertEqual(study_timetable._class_prep_blocks(self.profile, today), [])


class PastPaperFillerBlocksTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_creates_a_low_priority_block_for_today(self):
        today = date.today()
        PastPaperAnalysis.objects.create(
            profile=self.profile, subject_code="CSC2100", questions=[{"text": "Q1"}],
        )

        blocks = study_timetable._past_paper_filler_blocks(self.profile, today, covered_subjects_today=set())

        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["priority"], "low")

    def test_skips_a_subject_already_covered_today(self):
        today = date.today()
        PastPaperAnalysis.objects.create(
            profile=self.profile, subject_code="CSC2100", questions=[{"text": "Q1"}],
        )

        blocks = study_timetable._past_paper_filler_blocks(
            self.profile, today, covered_subjects_today={"CSC2100"}
        )

        self.assertEqual(blocks, [])

    def test_analysis_with_no_questions_produces_no_block(self):
        today = date.today()
        PastPaperAnalysis.objects.create(profile=self.profile, subject_code="CSC2100", questions=[])

        blocks = study_timetable._past_paper_filler_blocks(self.profile, today, covered_subjects_today=set())

        self.assertEqual(blocks, [])


class GenerateStudyBlocksTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_sorted_by_day_then_priority(self):
        today = date.today()
        AssignmentItem.objects.create(
            profile=self.profile, subject_code="A", title="Low urgency",
            status="open", due_at=timezone.now() + timedelta(days=4),
        )
        AssignmentItem.objects.create(
            profile=self.profile, subject_code="B", title="High urgency",
            status="open", due_at=timezone.now(),
        )

        blocks = study_timetable.generate_study_blocks(self.profile)

        self.assertEqual(blocks[0]["subject_code"], "B")

    def test_empty_profile_produces_no_blocks(self):
        self.assertEqual(study_timetable.generate_study_blocks(self.profile), [])

    def test_group_by_day_preserves_order(self):
        blocks = [
            {"day": date(2026, 1, 1), "subject_code": "A"},
            {"day": date(2026, 1, 1), "subject_code": "B"},
            {"day": date(2026, 1, 2), "subject_code": "C"},
        ]

        grouped = study_timetable.group_by_day(blocks)

        self.assertEqual(list(grouped.keys()), [date(2026, 1, 1), date(2026, 1, 2)])
        self.assertEqual(len(grouped[date(2026, 1, 1)]), 2)


class StudyTimetablePageTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_requires_active_profile(self):
        self.profile.is_active = False
        self.profile.save()

        response = self.client.get(reverse("study_timetable"))

        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_empty_state(self):
        response = self.client.get(reverse("study_timetable"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nothing urgent scheduled")

    def test_populated_case_renders_a_block(self):
        AssignmentItem.objects.create(
            profile=self.profile, subject_code="CSC2100", title="Assignment 2",
            status="open", due_at=timezone.now() + timedelta(days=1),
        )

        response = self.client.get(reverse("study_timetable"))

        self.assertContains(response, "Assignment 2")
        self.assertEqual(response.context["total_blocks"], 1)
