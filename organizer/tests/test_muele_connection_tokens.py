"""Two profiles, each with their own MUELE connection, must never share a
token: `run_muele_sync`'s background loop used to load one global token
before looping over every connected profile, so a second profile's sync
silently ran with the first profile's credentials. Locks in the fix:
store_connection_token/load_connection_token/clear_connection_token key on
connection.pk, and the background loop loads each connection's own token.
"""

from threading import Event
from unittest import mock

from organizer.core import muele_api, muele_downloader
from organizer.models import IntegrationConnection

from .helpers import SandboxedPathsTestCase


class ConnectionTokenKeyringTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile_a = self.make_profile(name="Profile A")
        self.profile_b = self.make_profile(name="Profile B", is_active=False)
        self.connection_a = IntegrationConnection.objects.create(
            profile=self.profile_a, provider="muele", display_name="MUELE", status="connected",
        )
        self.connection_b = IntegrationConnection.objects.create(
            profile=self.profile_b, provider="muele", display_name="MUELE", status="connected",
        )
        self.addCleanup(muele_api.clear_connection_token, self.connection_a)
        self.addCleanup(muele_api.clear_connection_token, self.connection_b)
        # Isolate from this machine's real pending/global token (if any) --
        # load_connection_token's legacy-migration fallback would otherwise
        # adopt real leftover state into these test connections, and this
        # class must never write to or clear a real credential.
        self.enterContext(mock.patch.object(muele_api, "load_token", return_value=None))

    def test_each_connection_keeps_its_own_token(self):
        try:
            import keyring  # noqa: F401
        except ImportError:
            self.skipTest("keyring package not installed in this environment")

        muele_api.store_connection_token(self.connection_a, "token-for-a")
        muele_api.store_connection_token(self.connection_b, "token-for-b")

        self.assertEqual(muele_api.load_connection_token(self.connection_a), "token-for-a")
        self.assertEqual(muele_api.load_connection_token(self.connection_b), "token-for-b")

    def test_clearing_one_connections_token_does_not_touch_the_other(self):
        try:
            import keyring  # noqa: F401
        except ImportError:
            self.skipTest("keyring package not installed in this environment")

        muele_api.store_connection_token(self.connection_a, "token-for-a")
        muele_api.store_connection_token(self.connection_b, "token-for-b")

        muele_api.clear_connection_token(self.connection_a)

        self.assertIsNone(muele_api.load_connection_token(self.connection_a))
        self.assertEqual(muele_api.load_connection_token(self.connection_b), "token-for-b")


class LegacyGlobalTokenMigrationTests(SandboxedPathsTestCase):
    """Connections that were `connected` before per-connection tokens
    existed must self-heal on next read, not silently look disconnected.
    Fully mocked -- never touches this machine's real global pending token,
    which store_token/load_token/clear_token would otherwise read, mutate,
    or delete for real."""

    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.connection = IntegrationConnection.objects.create(
            profile=self.profile, provider="muele", display_name="MUELE", status="connected",
        )
        self.addCleanup(muele_api.clear_connection_token, self.connection)

    def test_adopts_a_leftover_global_token_and_clears_it(self):
        with mock.patch.object(muele_api, "load_token", return_value="legacy-global-token") as load_token, \
             mock.patch.object(muele_api, "clear_token") as clear_token:
            result = muele_api.load_connection_token(self.connection)

        self.assertEqual(result, "legacy-global-token")
        load_token.assert_called_once()
        clear_token.assert_called_once()
        self.assertEqual(muele_api.load_connection_token(self.connection), "legacy-global-token")

    def test_does_not_touch_a_connection_that_already_has_its_own_token(self):
        muele_api.store_connection_token(self.connection, "own-token")

        with mock.patch.object(muele_api, "load_token", return_value="legacy-global-token") as load_token, \
             mock.patch.object(muele_api, "clear_token") as clear_token:
            result = muele_api.load_connection_token(self.connection)

        self.assertEqual(result, "own-token")
        load_token.assert_not_called()
        clear_token.assert_not_called()


class ConnectionTokenKeyringFallbackTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.connection = IntegrationConnection.objects.create(
            profile=self.profile, provider="muele", display_name="MUELE",
        )

    def test_store_returns_false_and_a_message_without_keyring(self):
        with mock.patch.dict("sys.modules", {"keyring": None}):
            ok, message = muele_api.store_connection_token(self.connection, "a-token")

        self.assertFalse(ok)
        self.assertIsNotNone(message)

    def test_load_returns_none_without_keyring(self):
        with mock.patch.dict("sys.modules", {"keyring": None}):
            self.assertIsNone(muele_api.load_connection_token(self.connection))

    def test_clear_never_raises_without_keyring(self):
        with mock.patch.dict("sys.modules", {"keyring": None}):
            muele_api.clear_connection_token(self.connection)  # should not raise


class RunMueleSyncMultiProfileTests(SandboxedPathsTestCase):
    def test_background_loop_uses_each_connections_own_token(self):
        profile_a = self.make_profile(name="Profile A")
        profile_b = self.make_profile(name="Profile B", is_active=False)
        IntegrationConnection.objects.create(
            profile=profile_a, provider="muele", display_name="MUELE", status="connected",
        )
        IntegrationConnection.objects.create(
            profile=profile_b, provider="muele", display_name="MUELE", status="connected",
        )

        tokens_by_profile = {"Profile A": "token-for-a", "Profile B": "token-for-b"}
        calls = []

        def fake_load_connection_token(connection):
            return tokens_by_profile[connection.profile.name]

        def fake_sync_profile_courses(profile, token=None, log=None):
            calls.append((profile.name, token))
            return {"downloaded": 0, "skipped": 0, "errors": 0}

        def fake_sync_assignments(profile, token=None, log=None):
            return 0

        stop_event = Event()

        def stop_after_one_pass(*args, **kwargs):
            stop_event.set()
            return 300  # poll_seconds arg to stop_event.wait, irrelevant once set

        with mock.patch.object(muele_api, "load_connection_token", side_effect=fake_load_connection_token), \
             mock.patch.object(muele_downloader, "sync_profile_courses", side_effect=fake_sync_profile_courses), \
             mock.patch.object(muele_downloader, "sync_assignments", side_effect=fake_sync_assignments), \
             mock.patch.object(stop_event, "wait", side_effect=stop_after_one_pass):
            muele_downloader.run_muele_sync(stop_event=stop_event, poll_seconds=0)

        self.assertEqual(len(calls), 2)
        self.assertIn(("Profile A", "token-for-a"), calls)
        self.assertIn(("Profile B", "token-for-b"), calls)
