from datetime import date, time, timedelta

from django.urls import reverse
from django.utils import timezone

from organizer.core import war_room
from organizer.models import (
    AssignmentItem,
    GradeTarget,
    IntegrationConnection,
    LearningActivity,
    PastPaperAnalysis,
    SubjectMemory,
    TimetableEntry,
)

from .helpers import SandboxedPathsTestCase


class TodaysClassesAndUpcomingExamsTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.connection = IntegrationConnection.objects.create(
            profile=self.profile, provider="mak_timetable", display_name="Timetable",
        )

    def test_todays_classes_matches_weekday_recurring_entries(self):
        today = date.today()
        TimetableEntry.objects.create(
            profile=self.profile, connection=self.connection, kind="teaching",
            weekday=today.weekday(), start_time=time(9, 0), course_code="CSC2100", raw_group="SE-2",
        )
        TimetableEntry.objects.create(
            profile=self.profile, connection=self.connection, kind="teaching",
            weekday=(today.weekday() + 1) % 7, start_time=time(9, 0), course_code="BIO101", raw_group="SE-2",
        )

        classes = war_room._todays_classes(self.profile)

        codes = [c.course_code for c in classes]
        self.assertIn("CSC2100", codes)
        self.assertNotIn("BIO101", codes)

    def test_upcoming_exams_excludes_past_and_orders_by_date(self):
        TimetableEntry.objects.create(
            profile=self.profile, connection=self.connection, kind="examination",
            specific_date=date.today() - timedelta(days=1), start_time=time(9, 0),
            course_code="PAST", raw_group="SE-2",
        )
        TimetableEntry.objects.create(
            profile=self.profile, connection=self.connection, kind="test",
            specific_date=date.today() + timedelta(days=10), start_time=time(9, 0),
            course_code="LATER", raw_group="SE-2",
        )
        TimetableEntry.objects.create(
            profile=self.profile, connection=self.connection, kind="examination",
            specific_date=date.today() + timedelta(days=2), start_time=time(9, 0),
            course_code="SOON", raw_group="SE-2",
        )

        exams = war_room._upcoming_exams(self.profile)

        self.assertEqual([e["subject_code"] for e in exams], ["SOON", "LATER"])
        self.assertEqual(exams[0]["days_left"], 2)


class PastPaperRiskAreasTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_same_topic_across_subjects_dedups_and_keeps_higher_weight(self):
        PastPaperAnalysis.objects.create(
            profile=self.profile, subject_code="CSC2100",
            topics=[{"name": "Recursion", "weight": 60, "evidence": []}],
        )
        PastPaperAnalysis.objects.create(
            profile=self.profile, subject_code="BSE2106",
            topics=[{"name": "recursion", "weight": 90, "evidence": []}],
        )

        rows = war_room._past_paper_risk_areas(self.profile)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["weight"], 90)
        self.assertEqual(sorted(rows[0]["subjects"]), ["BSE2106", "CSC2100"])

    def test_sorted_by_weight_descending(self):
        PastPaperAnalysis.objects.create(
            profile=self.profile, subject_code="CSC2100",
            topics=[
                {"name": "low", "weight": 10, "evidence": []},
                {"name": "high", "weight": 90, "evidence": []},
            ],
        )

        rows = war_room._past_paper_risk_areas(self.profile)

        self.assertEqual(rows[0]["topic"], "high")


class StudyStreakTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def _activity_on(self, days_ago):
        activity = LearningActivity.objects.create(
            profile=self.profile, activity_type="manual_note", title="x",
        )
        LearningActivity.objects.filter(pk=activity.pk).update(
            happened_at=timezone.now() - timedelta(days=days_ago)
        )

    def test_no_activity_is_zero(self):
        self.assertEqual(war_room._study_streak(self.profile), 0)

    def test_three_consecutive_days_ending_today(self):
        self._activity_on(0)
        self._activity_on(1)
        self._activity_on(2)

        self.assertEqual(war_room._study_streak(self.profile), 3)

    def test_gap_breaks_the_streak(self):
        self._activity_on(0)
        self._activity_on(2)  # gap at day 1

        self.assertEqual(war_room._study_streak(self.profile), 1)

    def test_activity_only_two_days_ago_is_not_alive(self):
        self._activity_on(2)

        self.assertEqual(war_room._study_streak(self.profile), 0)

    def test_activity_yesterday_still_counts_as_alive(self):
        self._activity_on(1)

        self.assertEqual(war_room._study_streak(self.profile), 1)


class NextBestActionTests(SandboxedPathsTestCase):
    def test_near_exam_wins_over_everything(self):
        action = war_room._next_best_action(
            upcoming_exams=[{"subject_code": "CSC2100", "days_left": 2}],
            weak_radar={"headline": {"subject_code": "BIO101", "topic": "cells"}},
            due_flashcards=5,
        )
        self.assertIn("CSC2100", action)
        self.assertIn("2 day", action)

    def test_weak_radar_headline_wins_over_flashcards_and_far_exam(self):
        action = war_room._next_best_action(
            upcoming_exams=[{"subject_code": "CSC2100", "days_left": 20}],
            weak_radar={"headline": {"subject_code": "BIO101", "topic": "cells"}},
            due_flashcards=5,
        )
        self.assertIn("BIO101", action)
        self.assertIn("cells", action)

    def test_due_flashcards_wins_over_far_exam(self):
        action = war_room._next_best_action(
            upcoming_exams=[{"subject_code": "CSC2100", "days_left": 20}],
            weak_radar={"headline": None},
            due_flashcards=5,
        )
        self.assertIn("5 flashcard", action)

    def test_falls_back_to_nearest_exam(self):
        action = war_room._next_best_action(
            upcoming_exams=[{"subject_code": "CSC2100", "days_left": 20}],
            weak_radar={"headline": None},
            due_flashcards=0,
        )
        self.assertIn("CSC2100", action)

    def test_honest_fallback_when_nothing_is_flagged(self):
        action = war_room._next_best_action(upcoming_exams=[], weak_radar={"headline": None}, due_flashcards=0)
        self.assertIn("Nothing urgent flagged", action)


class WarRoomPageTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_requires_active_profile(self):
        self.profile.is_active = False
        self.profile.save()

        response = self.client.get(reverse("war_room"))

        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_empty_state_still_renders_with_honest_fallback(self):
        response = self.client.get(reverse("war_room"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nothing urgent flagged")
        self.assertContains(response, "No subjects configured")

    def test_populated_profile_renders_every_section(self):
        connection = IntegrationConnection.objects.create(
            profile=self.profile, provider="mak_timetable", display_name="Timetable",
        )
        TimetableEntry.objects.create(
            profile=self.profile, connection=connection, kind="teaching",
            weekday=date.today().weekday(), start_time=time(9, 0), course_code="CSC2100", raw_group="SE-2",
        )
        TimetableEntry.objects.create(
            profile=self.profile, connection=connection, kind="examination",
            specific_date=date.today() + timedelta(days=2), start_time=time(9, 0),
            course_code="CSC2100", raw_group="SE-2",
        )
        AssignmentItem.objects.create(
            profile=self.profile, subject_code="CSC2100", title="MUELE assignment",
            source="muele", status="open", due_at=timezone.now() + timedelta(days=3),
        )
        SubjectMemory.objects.create(profile=self.profile, code="CSC2100", weak_areas=["recursion"])
        PastPaperAnalysis.objects.create(
            profile=self.profile, subject_code="CSC2100",
            topics=[{"name": "recursion", "weight": 80, "evidence": []}],
        )
        GradeTarget.objects.create(profile=self.profile, subject_code="CSC2100", target_percent=70)

        response = self.client.get(reverse("war_room"))

        self.assertContains(response, "MUELE assignment")
        self.assertContains(response, "recursion")
        self.assertContains(response, "CSC2100")
        self.assertContains(response, "needed")
