from unittest import mock

from organizer.core import github_api
from organizer.models import ContentDraft, IntegrationConnection, PublishedPost

from .helpers import SandboxedPathsTestCase


class KeyringFallbackTests(SandboxedPathsTestCase):
    """Same hermetic `sys.modules["keyring"] = None` trick test_publishing.py
    uses, exercising the graceful fallback path without touching this
    machine's real OS credential store."""

    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.channel = IntegrationConnection.objects.create(
            profile=self.profile, provider="github", display_name="My Portfolio",
            config={"owner": "student", "repo": "portfolio"},
        )

    def test_store_returns_false_and_a_message_without_keyring(self):
        with mock.patch.dict("sys.modules", {"keyring": None}):
            ok, message = github_api.store_channel_token(self.channel, "ghp_secret")

        self.assertFalse(ok)
        self.assertIsNotNone(message)

    def test_load_returns_none_without_keyring(self):
        with mock.patch.dict("sys.modules", {"keyring": None}):
            self.assertIsNone(github_api.load_channel_token(self.channel))

    def test_clear_never_raises_without_keyring(self):
        with mock.patch.dict("sys.modules", {"keyring": None}):
            github_api.clear_channel_token(self.channel)  # should not raise


class KeyringRoundTripTests(SandboxedPathsTestCase):
    """When a real keyring backend is available, store/load/clear should
    actually round-trip through it. Every credential written here is
    deleted via addCleanup so no test secret is ever left behind."""

    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.channel = IntegrationConnection.objects.create(
            profile=self.profile, provider="github", display_name="My Portfolio",
            config={"owner": "student", "repo": "portfolio"},
        )
        self.addCleanup(github_api.clear_channel_token, self.channel)

    def test_store_then_load_round_trips(self):
        try:
            import keyring  # noqa: F401
        except ImportError:
            self.skipTest("keyring package not installed in this environment")

        ok, message = github_api.store_channel_token(self.channel, "ghp_a_test_token")
        self.assertTrue(ok, msg=message)
        self.assertEqual(github_api.load_channel_token(self.channel), "ghp_a_test_token")

    def test_clear_removes_it(self):
        try:
            import keyring  # noqa: F401
        except ImportError:
            self.skipTest("keyring package not installed in this environment")

        github_api.store_channel_token(self.channel, "ghp_a_test_token")
        github_api.clear_channel_token(self.channel)
        self.assertIsNone(github_api.load_channel_token(self.channel))


class GetAnyTokenTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_returns_none_when_no_github_channel_connected(self):
        self.assertIsNone(github_api.get_any_token(self.profile))

    def test_returns_the_connected_channels_token(self):
        channel = IntegrationConnection.objects.create(
            profile=self.profile, provider="github", display_name="My Portfolio",
        )
        with mock.patch.object(github_api, "load_channel_token", return_value="ghp_x"):
            self.assertEqual(github_api.get_any_token(self.profile), "ghp_x")
            channel.refresh_from_db()  # keeps the fixture referenced


class SearchReposTests(SandboxedPathsTestCase):
    def test_returns_parsed_repos_on_success(self):
        mock_response = mock.Mock(status_code=200)
        mock_response.json.return_value = {
            "items": [
                {"full_name": "octocat/hello-world", "description": "A demo repo.",
                 "html_url": "https://github.com/octocat/hello-world", "stargazers_count": 42, "language": "Python"},
            ]
        }
        with mock.patch("requests.get", return_value=mock_response):
            repos = github_api.search_repos("operating systems scheduler")

        self.assertEqual(len(repos), 1)
        self.assertEqual(repos[0]["full_name"], "octocat/hello-world")
        self.assertEqual(repos[0]["stars"], 42)

    def test_network_failure_returns_empty_list(self):
        import requests

        with mock.patch("requests.get", side_effect=requests.RequestException("rate limited")):
            self.assertEqual(github_api.search_repos("data structures"), [])

    def test_bad_json_returns_empty_list(self):
        mock_response = mock.Mock(status_code=200)
        mock_response.json.side_effect = ValueError("bad json")
        with mock.patch("requests.get", return_value=mock_response):
            self.assertEqual(github_api.search_repos("data structures"), [])

    def test_includes_bearer_header_only_when_token_given(self):
        mock_response = mock.Mock(status_code=200)
        mock_response.json.return_value = {"items": []}
        with mock.patch("requests.get", return_value=mock_response) as mock_get:
            github_api.search_repos("x", token="ghp_abc")

        headers = mock_get.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer ghp_abc")


class GetRepoInfoTests(SandboxedPathsTestCase):
    def test_returns_stats_on_success(self):
        mock_response = mock.Mock(status_code=200)
        mock_response.json.return_value = {"stargazers_count": 10, "forks_count": 2, "pushed_at": "2026-01-01T00:00:00Z"}
        with mock.patch("requests.get", return_value=mock_response):
            info = github_api.get_repo_info("octocat", "hello-world")

        self.assertEqual(info["stars"], 10)
        self.assertEqual(info["forks"], 2)

    def test_returns_none_for_404(self):
        mock_response = mock.Mock(status_code=404)
        with mock.patch("requests.get", return_value=mock_response):
            self.assertIsNone(github_api.get_repo_info("octocat", "does-not-exist"))

    def test_returns_none_on_network_failure(self):
        import requests

        with mock.patch("requests.get", side_effect=requests.RequestException("down")):
            self.assertIsNone(github_api.get_repo_info("octocat", "hello-world"))


class ParseOwnerRepoTests(SandboxedPathsTestCase):
    def test_parses_a_normal_url(self):
        self.assertEqual(github_api.parse_owner_repo("https://github.com/octocat/hello-world"), ("octocat", "hello-world"))

    def test_strips_trailing_slash_and_git_suffix(self):
        self.assertEqual(github_api.parse_owner_repo("https://github.com/octocat/hello-world.git/"), ("octocat", "hello-world"))

    def test_non_github_url_returns_none(self):
        self.assertIsNone(github_api.parse_owner_repo("https://gitlab.com/octocat/hello-world"))

    def test_blank_returns_none(self):
        self.assertIsNone(github_api.parse_owner_repo(""))


class PublishToGithubTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.channel = IntegrationConnection.objects.create(
            profile=self.profile, provider="github", display_name="My Portfolio",
            config={"owner": "student", "repo": "portfolio", "posts_path": "posts"},
        )

    def test_unapproved_draft_raises_and_creates_nothing(self):
        draft = ContentDraft.objects.create(profile=self.profile, raw_text="x", status="draft")

        with self.assertRaises(ValueError):
            github_api.publish_to_github(self.channel, draft)

        self.assertEqual(PublishedPost.objects.count(), 0)

    def test_missing_owner_repo_fails_cleanly(self):
        channel = IntegrationConnection.objects.create(
            profile=self.profile, provider="github", display_name="Unconfigured", config={},
        )
        draft = ContentDraft.objects.create(profile=self.profile, raw_text="x", status="approved")

        post = github_api.publish_to_github(channel, draft)

        self.assertEqual(post.status, "failed")
        self.assertIn("owner/repo", post.error_message)

    def test_missing_token_fails_cleanly_without_a_network_call(self):
        # owner/repo are configured (self.channel, from setUp) but no
        # token was ever stored -- publishing to GitHub always needs one,
        # so this should be caught before any real HTTP call is attempted.
        draft = ContentDraft.objects.create(profile=self.profile, raw_text="x", status="approved")

        with mock.patch("requests.put") as mock_put:
            post = github_api.publish_to_github(self.channel, draft)

        mock_put.assert_not_called()
        self.assertEqual(post.status, "failed")
        self.assertIn("token", post.error_message)
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.status, "needs_key")

    def test_successful_publish_creates_new_file_and_flips_draft_to_posted(self):
        draft = ContentDraft.objects.create(profile=self.profile, topic="My Post", raw_text="x", status="approved")

        get_response = mock.Mock(status_code=404)
        put_response = mock.Mock(status_code=201, text="{}")
        put_response.json.return_value = {"content": {"html_url": "https://github.com/student/portfolio/blob/main/posts/x.md"}}

        with mock.patch.object(github_api, "load_channel_token", return_value="fake-token"), \
             mock.patch("requests.get", return_value=get_response), mock.patch("requests.put", return_value=put_response) as mock_put:
            post = github_api.publish_to_github(self.channel, draft)

        self.assertEqual(post.status, "sent")
        self.assertEqual(post.external_url, "https://github.com/student/portfolio/blob/main/posts/x.md")
        self.assertNotIn("sha", mock_put.call_args.kwargs["json"])
        draft.refresh_from_db()
        self.assertEqual(draft.status, "posted")
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.status, "connected")

    def test_existing_file_is_updated_with_its_sha(self):
        draft = ContentDraft.objects.create(profile=self.profile, topic="My Post", raw_text="x", status="approved")

        get_response = mock.Mock(status_code=200)
        get_response.json.return_value = {"sha": "abc123"}
        put_response = mock.Mock(status_code=200, text="{}")
        put_response.json.return_value = {"content": {"html_url": "https://github.com/student/portfolio/blob/main/posts/x.md"}}

        with mock.patch.object(github_api, "load_channel_token", return_value="fake-token"), \
             mock.patch("requests.get", return_value=get_response), mock.patch("requests.put", return_value=put_response) as mock_put:
            github_api.publish_to_github(self.channel, draft)

        self.assertEqual(mock_put.call_args.kwargs["json"]["sha"], "abc123")

    def test_non_2xx_response_marks_failed_and_leaves_draft_approved(self):
        draft = ContentDraft.objects.create(profile=self.profile, raw_text="x", status="approved")

        get_response = mock.Mock(status_code=404)
        put_response = mock.Mock(status_code=422, text="Unprocessable")

        with mock.patch.object(github_api, "load_channel_token", return_value="fake-token"), \
             mock.patch("requests.get", return_value=get_response), mock.patch("requests.put", return_value=put_response):
            post = github_api.publish_to_github(self.channel, draft)

        self.assertEqual(post.status, "failed")
        self.assertIn("422", post.error_message)
        draft.refresh_from_db()
        self.assertEqual(draft.status, "approved")

    def test_network_exception_marks_failed_without_crashing(self):
        draft = ContentDraft.objects.create(profile=self.profile, raw_text="x", status="approved")

        get_response = mock.Mock(status_code=404)
        with mock.patch.object(github_api, "load_channel_token", return_value="fake-token"), \
             mock.patch("requests.get", return_value=get_response), mock.patch("requests.put", side_effect=Exception("connection refused")):
            post = github_api.publish_to_github(self.channel, draft)

        self.assertEqual(post.status, "failed")
        self.assertIn("connection refused", post.error_message)
        draft.refresh_from_db()
        self.assertEqual(draft.status, "approved")
