from unittest import mock

from django.urls import reverse

from organizer.core import github_api, publishing
from organizer.models import ContentDraft, IntegrationConnection, PublishedPost

from .helpers import SandboxedPathsTestCase


class PublishingChannelsViewTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_create_channel_without_key(self):
        response = self.client.post(reverse("publishing_channels"), {
            "display_name": "My Blog",
            "base_url": "https://example.com/api/posts",
            "publish_mode": "draft",
        })

        self.assertRedirects(response, reverse("publishing_channels"))
        channel = IntegrationConnection.objects.get(profile=self.profile, provider="custom_website")
        self.assertEqual(channel.display_name, "My Blog")
        self.assertEqual(channel.status, "configured")
        self.assertIsNone(publishing.load_channel_api_key(channel))

    def test_blank_fields_are_rejected(self):
        response = self.client.post(reverse("publishing_channels"), {"display_name": "", "base_url": ""})

        self.assertRedirects(response, reverse("publishing_channels"))
        self.assertEqual(IntegrationConnection.objects.count(), 0)

    def test_delete_channel_also_clears_the_keyring_reference(self):
        channel = IntegrationConnection.objects.create(
            profile=self.profile, provider="custom_website", display_name="My Blog",
            base_url="https://example.com/api/posts",
        )
        calls = []
        with mock.patch.object(publishing, "clear_channel_api_key", side_effect=lambda ch: calls.append(ch.pk)):
            response = self.client.post(reverse("publishing_channel_delete", args=[channel.pk]))

        self.assertRedirects(response, reverse("publishing_channels"))
        self.assertEqual(calls, [channel.pk])
        self.assertFalse(IntegrationConnection.objects.filter(pk=channel.pk).exists())

    def test_create_github_channel_with_token(self):
        response = self.client.post(reverse("publishing_channels"), {
            "provider": "github",
            "gh_owner": "student",
            "gh_repo": "portfolio",
            "gh_posts_path": "posts",
            "gh_token": "ghp_smoke_test_token",
        })

        self.assertRedirects(response, reverse("publishing_channels"))
        channel = IntegrationConnection.objects.get(profile=self.profile, provider="github")
        self.assertEqual(channel.config, {"owner": "student", "repo": "portfolio", "posts_path": "posts"})
        self.assertEqual(channel.status, "configured")
        self.assertEqual(github_api.load_channel_token(channel), "ghp_smoke_test_token")
        self.addCleanup(github_api.clear_channel_token, channel)

    def test_github_channel_without_a_token_is_needs_key_not_connected(self):
        response = self.client.post(reverse("publishing_channels"), {
            "provider": "github", "gh_owner": "student", "gh_repo": "portfolio",
        })

        self.assertRedirects(response, reverse("publishing_channels"))
        channel = IntegrationConnection.objects.get(profile=self.profile, provider="github")
        self.assertEqual(channel.status, "needs_key")

    def test_github_channel_stays_needs_key_when_token_storage_fails(self):
        with mock.patch.object(github_api, "store_channel_token", return_value=(False, "no keyring backend")):
            response = self.client.post(reverse("publishing_channels"), {
                "provider": "github", "gh_owner": "student", "gh_repo": "portfolio", "gh_token": "ghp_x",
            })

        self.assertRedirects(response, reverse("publishing_channels"))
        channel = IntegrationConnection.objects.get(profile=self.profile, provider="github")
        self.assertEqual(channel.status, "needs_key")

    def test_custom_website_channel_with_no_key_is_configured_not_connected(self):
        response = self.client.post(reverse("publishing_channels"), {
            "display_name": "My Blog", "base_url": "https://example.com/api/posts",
        })

        self.assertRedirects(response, reverse("publishing_channels"))
        channel = IntegrationConnection.objects.get(profile=self.profile, provider="custom_website")
        self.assertEqual(channel.status, "configured")

    def test_custom_website_channel_drops_to_needs_key_when_storage_fails(self):
        with mock.patch.object(publishing, "store_channel_api_key", return_value=(False, "no keyring backend")):
            response = self.client.post(reverse("publishing_channels"), {
                "display_name": "My Blog", "base_url": "https://example.com/api/posts", "api_key": "secret",
            })

        self.assertRedirects(response, reverse("publishing_channels"))
        channel = IntegrationConnection.objects.get(profile=self.profile, provider="custom_website")
        self.assertEqual(channel.status, "needs_key")

    def test_github_channel_missing_owner_or_repo_is_rejected(self):
        response = self.client.post(reverse("publishing_channels"), {
            "provider": "github", "gh_owner": "", "gh_repo": "",
        })

        self.assertRedirects(response, reverse("publishing_channels"))
        self.assertEqual(IntegrationConnection.objects.count(), 0)

    def test_delete_github_channel_also_clears_its_token(self):
        channel = IntegrationConnection.objects.create(
            profile=self.profile, provider="github", display_name="My Portfolio",
            config={"owner": "student", "repo": "portfolio"},
        )
        calls = []
        with mock.patch.object(github_api, "clear_channel_token", side_effect=lambda ch: calls.append(ch.pk)):
            response = self.client.post(reverse("publishing_channel_delete", args=[channel.pk]))

        self.assertRedirects(response, reverse("publishing_channels"))
        self.assertEqual(calls, [channel.pk])
        self.assertFalse(IntegrationConnection.objects.filter(pk=channel.pk).exists())


class ContentDraftPublishToGithubViewTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.channel = IntegrationConnection.objects.create(
            profile=self.profile, provider="github", display_name="My Portfolio",
            status="connected", config={"owner": "student", "repo": "portfolio", "posts_path": "posts"},
        )

    def test_publishing_dispatches_to_github_and_flips_status(self):
        draft = ContentDraft.objects.create(profile=self.profile, topic="My Post", raw_text="x", status="approved")

        get_response = mock.Mock(status_code=404)
        put_response = mock.Mock(status_code=201, text="{}")
        put_response.json.return_value = {"content": {"html_url": "https://github.com/student/portfolio/blob/main/posts/x.md"}}

        with mock.patch.object(github_api, "load_channel_token", return_value="fake-token"), \
             mock.patch("requests.get", return_value=get_response), mock.patch("requests.put", return_value=put_response):
            response = self.client.post(
                reverse("content_draft_publish", args=[draft.pk, self.channel.pk]), follow=True,
            )

        self.assertContains(response, "Published")
        draft.refresh_from_db()
        self.assertEqual(draft.status, "posted")
        self.assertEqual(PublishedPost.objects.get().channel, self.channel)


class ContentDraftPublishViewTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.channel = IntegrationConnection.objects.create(
            profile=self.profile, provider="custom_website", display_name="My Blog",
            base_url="https://example.com/api/posts", status="connected",
        )

    def test_publishing_an_unapproved_draft_shows_a_clear_message_not_a_crash(self):
        draft = ContentDraft.objects.create(profile=self.profile, raw_text="x", status="draft")

        response = self.client.post(
            reverse("content_draft_publish", args=[draft.pk, self.channel.pk]), follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "approved")
        self.assertEqual(PublishedPost.objects.count(), 0)

    def test_publishing_an_approved_draft_succeeds_and_flips_status(self):
        draft = ContentDraft.objects.create(profile=self.profile, raw_text="x", status="approved")

        mock_response = mock.Mock(status_code=200, text='{"url": "https://example.com/posts/1"}')
        mock_response.json.return_value = {"url": "https://example.com/posts/1"}
        with mock.patch("requests.post", return_value=mock_response):
            response = self.client.post(
                reverse("content_draft_publish", args=[draft.pk, self.channel.pk]), follow=True,
            )

        self.assertContains(response, "Published")
        draft.refresh_from_db()
        self.assertEqual(draft.status, "posted")
        self.assertEqual(PublishedPost.objects.count(), 1)

    def test_content_draft_detail_lists_connected_channels_and_publish_history(self):
        draft = ContentDraft.objects.create(profile=self.profile, raw_text="x", status="approved")
        PublishedPost.objects.create(content_draft=draft, channel=self.channel, status="sent")

        response = self.client.get(reverse("content_draft_detail", args=[draft.pk]))

        self.assertContains(response, "My Blog")
        self.assertEqual(list(response.context["channels"]), [self.channel])
        self.assertEqual(list(response.context["published_posts"]), [PublishedPost.objects.first()])


class ContentDraftExportViewTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.draft = ContentDraft.objects.create(profile=self.profile, topic="My Post", raw_text="Body content.")

    def test_export_markdown_returns_a_download(self):
        response = self.client.get(reverse("content_draft_export_markdown", args=[self.draft.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/markdown; charset=utf-8")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn(b"Body content.", response.content)

    def test_export_html_returns_a_download(self):
        response = self.client.get(reverse("content_draft_export_html", args=[self.draft.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn(b"Body content.", response.content)


class ContentDraftsDeletePostedViewTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_deletes_only_posted_drafts(self):
        posted = ContentDraft.objects.create(profile=self.profile, raw_text="x", status="posted")
        draft = ContentDraft.objects.create(profile=self.profile, raw_text="y", status="draft")

        response = self.client.post(reverse("content_drafts_delete_posted"))

        self.assertRedirects(response, reverse("content_drafts"))
        self.assertFalse(ContentDraft.objects.filter(pk=posted.pk).exists())
        self.assertTrue(ContentDraft.objects.filter(pk=draft.pk).exists())

    def test_get_is_not_allowed(self):
        response = self.client.get(reverse("content_drafts_delete_posted"))
        self.assertEqual(response.status_code, 405)
