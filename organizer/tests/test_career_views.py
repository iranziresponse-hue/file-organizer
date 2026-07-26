from unittest import mock

from django.urls import reverse

from organizer.models import CareerDigest, CareerProfile, ContentDraft, Project, ProjectUpdate

from .helpers import SandboxedPathsTestCase


class CareerHomeTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_requires_active_profile(self):
        self.profile.is_active = False
        self.profile.save()

        response = self.client.get(reverse("career_home"))

        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_no_projects_suggests_logging_the_first_one(self):
        response = self.client.get(reverse("career_home"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("Add your first project", response.context["next_action"])

    def test_stale_project_is_flagged_as_next_action(self):
        Project.objects.create(profile=self.profile, title="Orch", status="building")

        response = self.client.get(reverse("career_home"))

        self.assertIn("Orch", response.context["next_action"])
        self.assertIn("quiet", response.context["next_action"])

    def test_career_profile_update_saves_track_and_goal(self):
        response = self.client.post(reverse("career_profile_update"), {
            "career_track": "backend_engineer",
            "weekly_goal": "Ship the login flow",
        })

        self.assertRedirects(response, reverse("career_home"))
        cp = CareerProfile.objects.get(profile=self.profile)
        self.assertEqual(cp.career_track, "backend_engineer")
        self.assertEqual(cp.weekly_goal, "Ship the login flow")


class ProjectStudioTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_creates_a_project_with_parsed_tech_stack(self):
        response = self.client.post(reverse("project_studio"), {
            "title": "Orch",
            "status": "building",
            "problem_statement": "Students lose files.",
            "tech_stack": "Django, SQLite",
            "github_url": "https://github.com/x/orch",
        })

        self.assertRedirects(response, reverse("project_studio"))
        project = Project.objects.get(profile=self.profile)
        self.assertEqual(project.tech_stack, ["Django", "SQLite"])

    def test_blank_title_is_rejected(self):
        response = self.client.post(reverse("project_studio"), {"title": ""})

        self.assertRedirects(response, reverse("project_studio"))
        self.assertEqual(Project.objects.count(), 0)

    def test_grouped_by_status(self):
        Project.objects.create(profile=self.profile, title="Idea one", status="idea")
        Project.objects.create(profile=self.profile, title="Shipped one", status="shipped")

        response = self.client.get(reverse("project_studio"))

        self.assertContains(response, "Idea one")
        self.assertContains(response, "Shipped one")


class ProjectDetailTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.project = Project.objects.create(profile=self.profile, title="Orch", status="building")

    def test_add_update_logs_progress(self):
        response = self.client.post(reverse("project_detail", args=[self.project.pk]), {
            "action": "add_update", "update_content": "Shipped the trust layer.",
        })

        self.assertRedirects(response, reverse("project_detail", args=[self.project.pk]))
        self.assertTrue(ProjectUpdate.objects.filter(project=self.project, content="Shipped the trust layer.").exists())

    def test_update_saves_fields(self):
        response = self.client.post(reverse("project_detail", args=[self.project.pk]), {
            "action": "update", "title": "Orch v2", "status": "shipped",
            "problem_statement": "", "tech_stack": "Django", "github_url": "",
            "folder_path": "", "lessons_learned": "", "portfolio_description": "",
        })

        self.assertRedirects(response, reverse("project_detail", args=[self.project.pk]))
        self.project.refresh_from_db()
        self.assertEqual(self.project.title, "Orch v2")
        self.assertEqual(self.project.status, "shipped")

    def test_generate_draft_creates_content_draft_and_redirects_to_it(self):
        response = self.client.post(reverse("project_generate_draft", args=[self.project.pk]), {
            "post_type": "project_update",
        })

        draft = ContentDraft.objects.get(project=self.project)
        self.assertRedirects(response, reverse("content_draft_detail", args=[draft.pk]))
        self.assertIn("Orch", draft.raw_text)

    def test_delete_removes_the_project(self):
        response = self.client.post(reverse("project_delete", args=[self.project.pk]))

        self.assertRedirects(response, reverse("project_studio"))
        self.assertFalse(Project.objects.filter(pk=self.project.pk).exists())

    def test_refresh_github_without_a_url_shows_a_clear_message(self):
        response = self.client.post(
            reverse("project_detail", args=[self.project.pk]), {"action": "refresh_github"}, follow=True,
        )

        self.assertContains(response, "valid github.com")
        self.project.refresh_from_db()
        self.assertIsNone(self.project.github_synced_at)

    def test_refresh_github_saves_stars_on_success(self):
        self.project.github_url = "https://github.com/octocat/hello-world"
        self.project.save()

        with mock.patch("organizer.core.github_api.get_repo_info", return_value={"stars": 42, "forks": 3, "updated_at": ""}):
            response = self.client.post(
                reverse("project_detail", args=[self.project.pk]), {"action": "refresh_github"}, follow=True,
            )

        self.assertContains(response, "42 stars")
        self.project.refresh_from_db()
        self.assertEqual(self.project.github_stars, 42)
        self.assertIsNotNone(self.project.github_synced_at)

    def test_refresh_github_unreachable_repo_shows_a_clear_message_and_saves_nothing(self):
        self.project.github_url = "https://github.com/octocat/does-not-exist"
        self.project.save()

        with mock.patch("organizer.core.github_api.get_repo_info", return_value=None):
            response = self.client.post(
                reverse("project_detail", args=[self.project.pk]), {"action": "refresh_github"}, follow=True,
            )

        self.assertContains(response, "Couldn")
        self.project.refresh_from_db()
        self.assertIsNone(self.project.github_stars)


class CareerDigestViewTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_empty_state(self):
        response = self.client.get(reverse("career_digest"))

        self.assertContains(response, "No digest yet")

    def test_generate_creates_a_digest(self):
        response = self.client.post(reverse("career_digest_generate"))

        self.assertRedirects(response, reverse("career_digest"))
        self.assertEqual(CareerDigest.objects.filter(profile=self.profile).count(), 1)


class ContentDraftsViewTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_manual_create(self):
        response = self.client.post(reverse("content_drafts"), {
            "topic": "New portfolio piece",
            "post_type": "portfolio_launch",
            "raw_text": "Just shipped a new feature.",
        })

        self.assertRedirects(response, reverse("content_drafts"))
        draft = ContentDraft.objects.get(profile=self.profile)
        self.assertEqual(draft.topic, "New portfolio piece")
        self.assertIn("Makerere", draft.hashtags)

    def test_blank_raw_text_is_rejected(self):
        response = self.client.post(reverse("content_drafts"), {"raw_text": ""})

        self.assertRedirects(response, reverse("content_drafts"))
        self.assertEqual(ContentDraft.objects.count(), 0)


class ContentDraftDetailTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.draft = ContentDraft.objects.create(profile=self.profile, raw_text="Raw draft text.", topic="Test")

    def test_edit_saves_fields(self):
        response = self.client.post(reverse("content_draft_detail", args=[self.draft.pk]), {
            "topic": "Updated topic", "post_type": "lesson_learned",
            "raw_text": "Updated text.", "hashtags": "Django, Python",
        })

        self.assertRedirects(response, reverse("content_draft_detail", args=[self.draft.pk]))
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.topic, "Updated topic")
        self.assertEqual(self.draft.hashtags, ["Django", "Python"])

    def test_polish_without_ai_configured_shows_an_honest_error(self):
        response = self.client.post(
            reverse("content_draft_polish", args=[self.draft.pk]), {"style": "polished"}, follow=True,
        )

        self.assertContains(response, "Writing help isn")
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.polished_text, "")

    def test_approve_then_mark_posted(self):
        self.client.post(reverse("content_draft_approve", args=[self.draft.pk]))
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "approved")

        self.client.post(reverse("content_draft_mark_posted", args=[self.draft.pk]))
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "posted")

    def test_delete_removes_the_draft(self):
        response = self.client.post(reverse("content_draft_delete", args=[self.draft.pk]))

        self.assertRedirects(response, reverse("content_drafts"))
        self.assertFalse(ContentDraft.objects.filter(pk=self.draft.pk).exists())

    def test_variants_context_reflects_model_fields(self):
        response = self.client.get(reverse("content_draft_detail", args=[self.draft.pk]))

        styles = [v[0] for v in response.context["variants"]]
        self.assertEqual(styles, ["polished", "professional", "short", "website"])
