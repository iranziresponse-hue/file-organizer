from unittest import mock

from organizer.core import publishing
from organizer.models import ContentDraft, IntegrationConnection, PublishedPost

from .helpers import SandboxedPathsTestCase


class KeyringFallbackTests(SandboxedPathsTestCase):
    """`sys.modules["keyring"] = None` forces `import keyring` to raise
    ImportError within the block -- same hermetic trick test_drive_api.py
    already uses, so these tests exercise the graceful fallback path
    without ever touching this machine's real OS credential store."""

    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.channel = IntegrationConnection.objects.create(
            profile=self.profile, provider="custom_website", display_name="My Blog",
            base_url="https://example.com/api/posts",
        )

    def test_store_returns_false_and_a_message_without_keyring(self):
        with mock.patch.dict("sys.modules", {"keyring": None}):
            ok, message = publishing.store_channel_api_key(self.channel, "secret-key")

        self.assertFalse(ok)
        self.assertIsNotNone(message)

    def test_load_returns_none_without_keyring(self):
        with mock.patch.dict("sys.modules", {"keyring": None}):
            self.assertIsNone(publishing.load_channel_api_key(self.channel))

    def test_clear_never_raises_without_keyring(self):
        with mock.patch.dict("sys.modules", {"keyring": None}):
            publishing.clear_channel_api_key(self.channel)  # should not raise


class KeyringRoundTripTests(SandboxedPathsTestCase):
    """When a real keyring backend IS available (as it is on this Windows
    dev machine -- WinVaultKeyring), store/load/clear should actually
    round-trip through it. Every credential written here is deleted in
    tearDown so no test secret is ever left behind in the real OS store."""

    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.channel = IntegrationConnection.objects.create(
            profile=self.profile, provider="custom_website", display_name="My Blog",
            base_url="https://example.com/api/posts",
        )
        self.addCleanup(publishing.clear_channel_api_key, self.channel)

    def test_store_then_load_round_trips(self):
        try:
            import keyring  # noqa: F401
        except ImportError:
            self.skipTest("keyring package not installed in this environment")

        ok, message = publishing.store_channel_api_key(self.channel, "a-test-secret")
        self.assertTrue(ok, msg=message)
        self.assertEqual(publishing.load_channel_api_key(self.channel), "a-test-secret")

    def test_clear_removes_it(self):
        try:
            import keyring  # noqa: F401
        except ImportError:
            self.skipTest("keyring package not installed in this environment")

        publishing.store_channel_api_key(self.channel, "a-test-secret")
        publishing.clear_channel_api_key(self.channel)
        self.assertIsNone(publishing.load_channel_api_key(self.channel))


class BuildPayloadTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_uses_topic_as_title_and_includes_tags(self):
        draft = ContentDraft.objects.create(
            profile=self.profile, topic="Weekly update", raw_text="Body text.", hashtags=["Django", "Makerere"],
        )

        payload = publishing.build_payload(draft)

        self.assertEqual(payload["title"], "Weekly update")
        self.assertEqual(payload["body"], "Body text.")
        self.assertEqual(payload["tags"], ["Django", "Makerere"])
        self.assertEqual(payload["status"], "draft")

    def test_falls_back_to_raw_text_when_variant_is_blank(self):
        draft = ContentDraft.objects.create(profile=self.profile, raw_text="Raw only.", polished_text="")

        payload = publishing.build_payload(draft, variant="polished")

        self.assertEqual(payload["body"], "Raw only.")

    def test_uses_polished_text_when_present(self):
        draft = ContentDraft.objects.create(profile=self.profile, raw_text="Raw.", polished_text="Polished version.")

        payload = publishing.build_payload(draft, variant="polished")

        self.assertEqual(payload["body"], "Polished version.")

    def test_blank_topic_falls_back_to_post_type_label(self):
        draft = ContentDraft.objects.create(profile=self.profile, raw_text="x", post_type="lesson_learned", topic="")

        payload = publishing.build_payload(draft)

        self.assertEqual(payload["title"], "Lesson learned")


class PublishToCustomWebsiteTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.channel = IntegrationConnection.objects.create(
            profile=self.profile, provider="custom_website", display_name="My Blog",
            base_url="https://example.com/api/posts",
        )

    def test_unapproved_draft_raises_and_creates_nothing(self):
        draft = ContentDraft.objects.create(profile=self.profile, raw_text="x", status="draft")

        with self.assertRaises(ValueError):
            publishing.publish_to_custom_website(self.channel, draft)

        self.assertEqual(PublishedPost.objects.count(), 0)

    def test_successful_publish_marks_sent_and_flips_draft_to_posted(self):
        draft = ContentDraft.objects.create(profile=self.profile, raw_text="x", status="approved")

        mock_response = mock.Mock(status_code=200, text='{"url": "https://example.com/posts/1"}')
        mock_response.json.return_value = {"url": "https://example.com/posts/1"}
        with mock.patch("requests.post", return_value=mock_response):
            post = publishing.publish_to_custom_website(self.channel, draft)

        self.assertEqual(post.status, "sent")
        self.assertEqual(post.external_url, "https://example.com/posts/1")
        draft.refresh_from_db()
        self.assertEqual(draft.status, "posted")
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.status, "connected")

    def test_non_2xx_response_marks_failed_and_leaves_draft_approved(self):
        draft = ContentDraft.objects.create(profile=self.profile, raw_text="x", status="approved")

        mock_response = mock.Mock(status_code=500, text="Internal Server Error")
        with mock.patch("requests.post", return_value=mock_response):
            post = publishing.publish_to_custom_website(self.channel, draft)

        self.assertEqual(post.status, "failed")
        self.assertIn("500", post.error_message)
        draft.refresh_from_db()
        self.assertEqual(draft.status, "approved")

    def test_network_exception_marks_failed_without_crashing(self):
        draft = ContentDraft.objects.create(profile=self.profile, raw_text="x", status="approved")

        with mock.patch("requests.post", side_effect=Exception("connection refused")):
            post = publishing.publish_to_custom_website(self.channel, draft)

        self.assertEqual(post.status, "failed")
        self.assertIn("connection refused", post.error_message)
        draft.refresh_from_db()
        self.assertEqual(draft.status, "approved")


class ExportTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_export_markdown_includes_title_body_and_tags(self):
        draft = ContentDraft.objects.create(
            profile=self.profile, topic="My Post", raw_text="Body content.", hashtags=["Django"],
        )

        markdown = publishing.export_markdown(draft)

        self.assertIn("My Post", markdown)
        self.assertIn("Body content.", markdown)
        self.assertIn("Django", markdown)

    def test_export_html_escapes_unsafe_content(self):
        draft = ContentDraft.objects.create(
            profile=self.profile, topic="My Post", raw_text="<script>alert(1)</script>",
        )

        html = publishing.export_html(draft)

        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)
