import json
from unittest import mock

from django.urls import reverse

from organizer.core import paths, summarize
from organizer.models import CourseGuide

from .helpers import SandboxedPathsTestCase


class GenerateCourseGuideTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.ai_config_path = self.profile_root.parent / "ai_config.json"
        self.enterContext(mock.patch.object(paths, "AI_CONFIG_PATH", self.ai_config_path))

    def _write_ai_config(self):
        self.ai_config_path.write_text(json.dumps({
            "enabled": True,
            "api_key": "test-key",
            "model": "llama-3.1-8b-instant",
            "base_url": "https://api.groq.com/openai/v1",
        }))

    def test_no_course_code_is_rejected(self):
        content, error = summarize.generate_course_guide("")
        self.assertIsNone(content)
        self.assertIn("No course code", error)

    def test_no_ai_config_is_rejected(self):
        content, error = summarize.generate_course_guide("CSC2100")
        self.assertIsNone(content)
        self.assertIn("Smart Orch isn't turned on", error)

    @mock.patch("organizer.core.summarize.requests.post")
    def test_successful_generation_includes_the_course_code_in_the_prompt(self, mock_post):
        self._write_ai_config()
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "# CSC2100 Guide\n\nAn overview paragraph.\n"}}]
        }

        content, error = summarize.generate_course_guide("CSC2100", program="BSc Computer Science", level="Year 2 Semester 1")

        self.assertIsNone(error)
        self.assertIn("CSC2100", content)
        sent_prompt = mock_post.call_args.kwargs["json"]["messages"][0]["content"]
        self.assertIn("CSC2100", sent_prompt)
        self.assertIn("BSc Computer Science", sent_prompt)
        self.assertIn("official syllabus", sent_prompt.lower())

    @mock.patch("organizer.core.summarize.requests.post", side_effect=TimeoutError("timed out"))
    def test_network_failure_never_raises(self, mock_post):
        self._write_ai_config()
        content, error = summarize.generate_course_guide("CSC2100")
        self.assertIsNone(content)
        self.assertIn("Couldn't reach", error)


class CourseGuideViewTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.ai_config_path = self.profile_root.parent / "ai_config.json"
        self.enterContext(mock.patch.object(paths, "AI_CONFIG_PATH", self.ai_config_path))

    def _write_ai_config(self):
        self.ai_config_path.write_text(json.dumps({
            "enabled": True,
            "api_key": "test-key",
            "model": "llama-3.1-8b-instant",
            "base_url": "https://api.groq.com/openai/v1",
        }))

    def test_get_is_not_allowed_for_generate(self):
        profile = self.make_profile()
        response = self.client.get(reverse("course_guide_generate", args=[profile.pk, "CSC2100"]))
        self.assertEqual(response.status_code, 405)

    def test_no_ai_config_returns_a_clear_error(self):
        profile = self.make_profile()
        response = self.client.post(reverse("course_guide_generate", args=[profile.pk, "CSC2100"]))
        self.assertEqual(response.status_code, 400)
        self.assertIn("Smart Orch isn't turned on", response.json()["error"])
        self.assertFalse(CourseGuide.objects.exists())

    @mock.patch("organizer.core.summarize.requests.post")
    def test_success_creates_and_can_regenerate_the_guide(self, mock_post):
        self._write_ai_config()
        profile = self.make_profile()

        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "# CSC2100\n\nFirst version.\n"}}]
        }
        response = self.client.post(reverse("course_guide_generate", args=[profile.pk, "CSC2100"]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(CourseGuide.objects.count(), 1)

        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "# CSC2100\n\nSecond version.\n"}}]
        }
        self.client.post(reverse("course_guide_generate", args=[profile.pk, "CSC2100"]))

        self.assertEqual(CourseGuide.objects.count(), 1)
        self.assertIn("Second version", CourseGuide.objects.get().content)

    def test_view_404_json_when_no_guide_exists_yet(self):
        profile = self.make_profile()
        response = self.client.get(reverse("course_guide_view", args=[profile.pk, "CSC2100"]))
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.json())

    def test_view_renders_escaped_html(self):
        profile = self.make_profile()
        CourseGuide.objects.create(
            profile=profile, course_code="CSC2100", content="# Title\n\nBody with <script>alert(1)</script>.\n"
        )

        response = self.client.get(reverse("course_guide_view", args=[profile.pk, "CSC2100"]))
        data = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertIn("<h1>Title</h1>", data["html"])
        self.assertIn("&lt;script&gt;", data["html"])
        self.assertNotIn("<script>", data["html"])

    def test_pdf_404_when_no_guide_exists_yet(self):
        profile = self.make_profile()
        response = self.client.get(reverse("course_guide_pdf", args=[profile.pk, "CSC2100"]))
        self.assertEqual(response.status_code, 404)

    def test_pdf_returns_a_valid_pdf(self):
        profile = self.make_profile()
        CourseGuide.objects.create(profile=profile, course_code="CSC2100", content="# Title\n\nBody.\n")

        response = self.client.get(reverse("course_guide_pdf", args=[profile.pk, "CSC2100"]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_generate_is_rejected_for_a_profile_that_is_not_active(self):
        active = self.make_profile(name="Active")
        inactive = self.make_profile(name="Inactive", is_active=False)

        response = self.client.post(reverse("course_guide_generate", args=[inactive.pk, "CSC2100"]))

        self.assertEqual(response.status_code, 404)
        self.assertFalse(CourseGuide.objects.exists())

    def test_view_is_rejected_for_a_profile_that_is_not_active(self):
        active = self.make_profile(name="Active")
        inactive = self.make_profile(name="Inactive", is_active=False)
        CourseGuide.objects.create(profile=inactive, course_code="CSC2100", content="# Title\n\nBody.\n")

        response = self.client.get(reverse("course_guide_view", args=[inactive.pk, "CSC2100"]))

        self.assertEqual(response.status_code, 404)

    def test_pdf_is_rejected_for_a_profile_that_is_not_active(self):
        active = self.make_profile(name="Active")
        inactive = self.make_profile(name="Inactive", is_active=False)
        CourseGuide.objects.create(profile=inactive, course_code="CSC2100", content="# Title\n\nBody.\n")

        response = self.client.get(reverse("course_guide_pdf", args=[inactive.pk, "CSC2100"]))

        self.assertEqual(response.status_code, 404)


class DashboardGuidedCodesTests(SandboxedPathsTestCase):
    def test_dashboard_marks_which_course_codes_already_have_a_guide(self):
        profile = self.make_profile()
        from organizer.models import CourseConfig

        CourseConfig.objects.create(
            profile=profile, primary_value="Year 2", secondary_value="Semester 1", groups=["CSC2100", "BIT2202"]
        )
        CourseGuide.objects.create(profile=profile, course_code="CSC2100", content="# Title\n\nBody.\n")

        response = self.client.get(reverse("dashboard"))

        self.assertIn("CSC2100", response.context["guided_codes"])
        self.assertNotIn("BIT2202", response.context["guided_codes"])
        self.assertContains(response, 'data-has-guide="true"')
        self.assertContains(response, 'data-has-guide="false"')
