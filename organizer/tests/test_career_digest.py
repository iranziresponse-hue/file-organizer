from datetime import timedelta
from unittest import mock

from django.utils import timezone

from organizer.core import career_digest
from organizer.models import CareerDigest, LearningActivity, Project, ProjectUpdate

from .helpers import SandboxedPathsTestCase


class GenerateWeeklyDigestTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_mentions_top_subject_and_activity_count(self):
        for _ in range(3):
            LearningActivity.objects.create(
                profile=self.profile, activity_type="file_sorted", subject_code="CSC2100", title="x",
            )
        LearningActivity.objects.create(
            profile=self.profile, activity_type="file_sorted", subject_code="BIO101", title="y",
        )

        digest = career_digest.generate_weekly_digest(self.profile)

        self.assertIn("CSC2100", digest.content)
        self.assertIn("4 study", digest.content)

    def test_mentions_project_updates(self):
        project = Project.objects.create(profile=self.profile, title="Orch")
        ProjectUpdate.objects.create(project=project, content="Added the trust layer.")

        digest = career_digest.generate_weekly_digest(self.profile)

        self.assertIn("Orch", digest.content)
        self.assertIn("Added the trust layer.", digest.content)

    def test_honest_when_nothing_happened(self):
        digest = career_digest.generate_weekly_digest(self.profile)

        self.assertIn("No study activity was logged this week.", digest.content)
        self.assertIn("No project updates were logged this week.", digest.content)

    def test_regenerating_within_the_same_week_updates_in_place(self):
        career_digest.generate_weekly_digest(self.profile)
        career_digest.generate_weekly_digest(self.profile)

        self.assertEqual(CareerDigest.objects.filter(profile=self.profile).count(), 1)

    def test_activity_outside_the_window_is_excluded(self):
        old = LearningActivity.objects.create(
            profile=self.profile, activity_type="file_sorted", subject_code="OLD", title="x",
        )
        LearningActivity.objects.filter(pk=old.pk).update(happened_at=timezone.now() - timedelta(days=30))

        digest = career_digest.generate_weekly_digest(self.profile)

        self.assertNotIn("OLD", digest.content)


class PolishNarrativeTests(SandboxedPathsTestCase):
    def test_returns_none_without_ai_configured(self):
        self.assertIsNone(career_digest.polish_narrative("Some content."))

    def test_returns_none_on_request_failure(self):
        ai_config = {"enabled": True, "api_key": "key", "model": "m", "base_url": "https://example.com"}
        with mock.patch("organizer.core.ai_classify.load_ai_config", return_value=ai_config), \
                mock.patch("requests.post", side_effect=Exception("network down")):
            self.assertIsNone(career_digest.polish_narrative("Some content."))
