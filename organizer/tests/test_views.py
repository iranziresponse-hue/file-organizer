import json

from django.urls import reverse

from organizer.core import paths
from organizer.models import CourseConfig, MoveEvent

from .helpers import SandboxedPathsTestCase


class DashboardViewTests(SandboxedPathsTestCase):
    def test_empty_state_renders(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_moves"], 0)

    def test_shows_recent_moves_and_stats(self):
        MoveEvent.objects.create(
            filename="notes.pdf",
            source_path="C:/Downloads/notes.pdf",
            destination_path="D:/School/notes.pdf",
            method="course_code",
            course_code="CSC2100",
            success=True,
        )

        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, "notes.pdf")
        self.assertEqual(response.context["total_moves"], 1)
        self.assertEqual(response.context["method_counts"][0]["method"], "course_code")
        self.assertEqual(response.context["course_counts"][0]["course_code"], "CSC2100")

    def test_events_without_a_course_code_are_excluded_from_course_counts(self):
        MoveEvent.objects.create(
            filename="movie.mp4",
            source_path="C:/Downloads/movie.mp4",
            destination_path="D:/Personal/Media/Videos/movie.mp4",
            method="media",
            success=True,
        )

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(list(response.context["course_counts"]), [])


class ConfigEditViewTests(SandboxedPathsTestCase):
    def test_get_renders_empty_form(self):
        response = self.client.get(reverse("config_edit"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["config"])

    def test_post_saves_to_database_and_writes_config_json(self):
        response = self.client.post(reverse("config_edit"), {
            "current_year": "Year 2",
            "current_semester": "Semester 1",
            "courses": "CSC2100, BSE2105",
        })

        self.assertRedirects(response, reverse("config_edit"))

        config = CourseConfig.objects.get()
        self.assertEqual(config.current_year, "Year 2")
        self.assertEqual(config.courses, ["CSC2100", "BSE2105"])

        self.assertTrue(paths.CONFIG_PATH.exists())
        written = json.loads(paths.CONFIG_PATH.read_text())
        self.assertEqual(written["current_year"], "Year 2")
        self.assertEqual(written["courses"], ["CSC2100", "BSE2105"])

    def test_editing_existing_config_updates_the_same_row(self):
        CourseConfig.objects.create(current_year="Year 1", current_semester="Semester 2", courses=["OLD1"])

        self.client.post(reverse("config_edit"), {
            "current_year": "Year 2",
            "current_semester": "Semester 1",
            "courses": "NEW1",
        })

        self.assertEqual(CourseConfig.objects.count(), 1)
        self.assertEqual(CourseConfig.objects.get().courses, ["NEW1"])

    def test_blank_and_whitespace_courses_are_dropped(self):
        self.client.post(reverse("config_edit"), {
            "current_year": "Year 2",
            "current_semester": "Semester 1",
            "courses": "CSC2100, , BSE2105,  ",
        })

        self.assertEqual(CourseConfig.objects.get().courses, ["CSC2100", "BSE2105"])
