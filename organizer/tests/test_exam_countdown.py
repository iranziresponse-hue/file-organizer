from datetime import date, time, timedelta

from django.urls import reverse

from organizer.models import AssignmentItem, IntegrationConnection, MoveEvent, ReviewItem, TimetableEntry
from django.utils import timezone

from .helpers import SandboxedPathsTestCase


class ExamCountdownPageTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.connection = IntegrationConnection.objects.create(
            profile=self.profile, provider="mak_timetable", display_name="Timetable",
        )

    def _exam(self, course_code, days_from_now, kind="examination"):
        return TimetableEntry.objects.create(
            profile=self.profile,
            connection=self.connection,
            kind=kind,
            specific_date=date.today() + timedelta(days=days_from_now),
            start_time=time(9, 0),
            course_code=course_code,
            raw_group="SE-2",
        )

    def test_requires_active_profile(self):
        self.profile.is_active = False
        self.profile.save()

        response = self.client.get(reverse("exam_countdown"))

        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_empty_state_links_to_timetable_connect(self):
        response = self.client.get(reverse("exam_countdown"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No upcoming exams tracked yet")
        self.assertContains(response, reverse("timetable_connect"))

    def test_days_left_is_computed_from_specific_date(self):
        self._exam("CSC2100", days_from_now=5)

        response = self.client.get(reverse("exam_countdown"))

        row = response.context["exams"][0]
        self.assertEqual(row["days_left"], 5)
        self.assertEqual(row["urgency"], "warning")

    def test_past_exams_are_excluded(self):
        self._exam("CSC2100", days_from_now=-3)

        response = self.client.get(reverse("exam_countdown"))

        self.assertEqual(len(response.context["exams"]), 0)

    def test_unresolved_dates_land_in_their_own_bucket(self):
        TimetableEntry.objects.create(
            profile=self.profile,
            connection=self.connection,
            kind="examination",
            specific_date=None,
            date_label="Week 15 (unconfirmed)",
            start_time=time(9, 0),
            course_code="BIO101",
            raw_group="SE-2",
        )

        response = self.client.get(reverse("exam_countdown"))

        self.assertEqual(len(response.context["exams"]), 0)
        self.assertEqual(len(response.context["undated"]), 1)
        self.assertContains(response, "Date not yet confirmed")

    def test_revision_coverage_reflects_review_item_counts(self):
        self._exam("CSC2100", days_from_now=10)
        ReviewItem.objects.create(
            profile=self.profile, subject_code="CSC2100", title="Trees",
            due_at=timezone.now(), status="done",
        )
        ReviewItem.objects.create(
            profile=self.profile, subject_code="CSC2100", title="Graphs",
            due_at=timezone.now(), status="queued",
        )

        response = self.client.get(reverse("exam_countdown"))

        row = response.context["exams"][0]
        self.assertEqual(row["reviews_done"], 1)
        self.assertEqual(row["reviews_total"], 2)
        self.assertEqual(row["coverage_percent"], 50)

    def test_past_papers_available_counts_the_past_papers_category(self):
        self._exam("CSC2100", days_from_now=10)
        MoveEvent.objects.create(
            profile=self.profile, filename="2023 exam.pdf",
            source_path="C:/Downloads/2023 exam.pdf",
            destination_path="C:/School/CSC2100/03 Past Papers and Tests/2023 exam.pdf",
            method="course_code", course_code="CSC2100", success=True,
        )
        MoveEvent.objects.create(
            profile=self.profile, filename="notes.pdf",
            source_path="C:/Downloads/notes.pdf",
            destination_path="C:/School/CSC2100/01 Lecture Notes and Slides/notes.pdf",
            method="course_code", course_code="CSC2100", success=True,
        )

        response = self.client.get(reverse("exam_countdown"))

        self.assertEqual(response.context["exams"][0]["past_papers_available"], 1)

    def test_open_assignments_count_is_scoped_to_the_subject(self):
        self._exam("CSC2100", days_from_now=10)
        AssignmentItem.objects.create(profile=self.profile, subject_code="CSC2100", title="A1", status="open")
        AssignmentItem.objects.create(profile=self.profile, subject_code="BIO101", title="A2", status="open")

        response = self.client.get(reverse("exam_countdown"))

        self.assertEqual(response.context["exams"][0]["open_assignments"], 1)

    def test_next_best_action_names_the_nearest_exams_top_review(self):
        self._exam("CSC2100", days_from_now=2)
        self._exam("BIO101", days_from_now=20)
        ReviewItem.objects.create(
            profile=self.profile, subject_code="CSC2100", title="Recursion basics",
            due_at=timezone.now(), status="queued",
        )

        response = self.client.get(reverse("exam_countdown"))

        self.assertIn("CSC2100", response.context["next_best"])
        self.assertIn("Recursion basics", response.context["next_best"])

    def test_next_best_action_without_queued_reviews_points_to_subject_memory(self):
        self._exam("CSC2100", days_from_now=2)

        response = self.client.get(reverse("exam_countdown"))

        self.assertIn("no queued reviews yet", response.context["next_best"])

    def test_urgency_bands(self):
        self._exam("A", days_from_now=1)
        self._exam("B", days_from_now=10)
        self._exam("C", days_from_now=30)

        response = self.client.get(reverse("exam_countdown"))

        urgencies = {row["entry"].course_code: row["urgency"] for row in response.context["exams"]}
        self.assertEqual(urgencies["A"], "critical")
        self.assertEqual(urgencies["B"], "warning")
        self.assertEqual(urgencies["C"], "ok")
