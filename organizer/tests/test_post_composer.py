from unittest import mock

from organizer.core import post_composer
from organizer.models import CareerDigest, Project, ProjectUpdate

from .helpers import SandboxedPathsTestCase


class SuggestHashtagsTests(SandboxedPathsTestCase):
    def test_includes_tech_stack_and_subject_codes(self):
        tags = post_composer.suggest_hashtags("text", tech_stack=["Django", "Postgre SQL"], subject_codes=["CSC2100"])

        self.assertIn("Django", tags)
        self.assertIn("PostgreSQL", tags)
        self.assertIn("CSC2100", tags)
        self.assertIn("Makerere", tags)

    def test_deduplicates_case_insensitively(self):
        tags = post_composer.suggest_hashtags("text", tech_stack=["django", "Django"])

        self.assertEqual(len([t for t in tags if t.lower() == "django"]), 1)

    def test_capped_at_eight(self):
        tags = post_composer.suggest_hashtags("text", tech_stack=[f"tag{i}" for i in range(20)])

        self.assertLessEqual(len(tags), 8)


class GenerateDraftFromProjectTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.project = Project.objects.create(
            profile=self.profile, title="Orch", problem_statement="Students lose files.",
            tech_stack=["Django", "SQLite"], status="building", github_url="https://github.com/x/orch",
        )

    def test_project_update_includes_latest_update(self):
        ProjectUpdate.objects.create(project=self.project, content="Shipped the trust layer.")

        draft = post_composer.generate_draft_from_project(self.project, post_type="project_update")

        self.assertIn("Orch", draft["raw_text"])
        self.assertIn("Students lose files.", draft["raw_text"])
        self.assertIn("Shipped the trust layer.", draft["raw_text"])
        self.assertIn("Django", draft["hashtags"])

    def test_missing_fields_fall_back_to_honest_placeholders(self):
        empty_project = Project.objects.create(profile=self.profile, title="Bare project")

        draft = post_composer.generate_draft_from_project(empty_project, post_type="project_update")

        self.assertIn("no problem statement recorded yet", draft["raw_text"])
        self.assertIn("no tech stack recorded yet", draft["raw_text"])

    def test_portfolio_launch_template_includes_github_link(self):
        draft = post_composer.generate_draft_from_project(self.project, post_type="portfolio_launch")

        self.assertIn("https://github.com/x/orch", draft["raw_text"])

    def test_lesson_learned_template_uses_lessons_field(self):
        self.project.lessons_learned = "Trust layers need explainability."
        self.project.save()

        draft = post_composer.generate_draft_from_project(self.project, post_type="lesson_learned")

        self.assertIn("Trust layers need explainability.", draft["raw_text"])


class GenerateDraftFromDigestTests(SandboxedPathsTestCase):
    def test_wraps_digest_content(self):
        profile = self.make_profile()
        digest = CareerDigest.objects.create(
            profile=profile, period_start="2026-01-01T00:00:00Z", period_end="2026-01-08T00:00:00Z",
            content="This week you studied CSC2100.",
        )

        draft = post_composer.generate_draft_from_digest(digest, post_type="course_reflection")

        self.assertIn("This week you studied CSC2100.", draft["raw_text"])


class PolishTextTests(SandboxedPathsTestCase):
    def test_returns_none_without_ai_configured(self):
        self.assertIsNone(post_composer.polish_text("Some raw text.", "polished"))

    def test_returns_none_for_unrecognized_style(self):
        ai_config = {"enabled": True, "api_key": "key", "model": "m", "base_url": "https://example.com"}
        with mock.patch("organizer.core.ai_classify.load_ai_config", return_value=ai_config):
            self.assertIsNone(post_composer.polish_text("Some raw text.", "not-a-real-style"))

    def test_returns_none_on_request_failure(self):
        ai_config = {"enabled": True, "api_key": "key", "model": "m", "base_url": "https://example.com"}
        with mock.patch("organizer.core.ai_classify.load_ai_config", return_value=ai_config), \
                mock.patch("requests.post", side_effect=Exception("network down")):
            self.assertIsNone(post_composer.polish_text("Some raw text.", "polished"))
