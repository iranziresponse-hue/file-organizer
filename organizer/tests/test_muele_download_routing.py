"""download_file() used to re-resolve Profile.get_active() internally and
ignore the profile it was actually called for -- so a background sync of
Profile B's MUELE courses while Profile A was active in the UI would land
B's real files inside A's folder tree, with the MoveEvent attributed to A.
Locks in the fix: download_file takes `profile` explicitly and routes
using that profile's own root, regardless of which profile is active.
"""

from pathlib import Path
from unittest import mock

from organizer.core import muele_downloader
from organizer.models import MoveEvent

from .helpers import SandboxedPathsTestCase


class DownloadFileProfileRoutingTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile_a = self.make_profile(name="Profile A", is_active=True)
        # Deliberately not sharing a name prefix with self.profile_root
        # ("Profile") -- a naive str.startswith() check on the two paths
        # would otherwise produce a false positive.
        self.other_root = self.profile_root.parent / "Second Root"
        self.other_root.mkdir(parents=True, exist_ok=True)
        self.profile_b = self.make_profile(name="Profile B", root_path=str(self.other_root), is_active=False)

        self.cache_dir = self.profile_root.parent / "_muele_cache_test"
        self.enterContext(mock.patch.object(muele_downloader, "_DOWNLOAD_CACHE", self.cache_dir))
        # _is_already_synced/_mark_synced persist to a real file in the
        # project directory by default -- sandboxed here too, otherwise
        # one test run's "already synced" state leaks into the next real
        # run of this app outside of tests.
        self.enterContext(
            mock.patch.object(muele_downloader, "_SYNC_STATE_PATH", self.profile_root.parent / "_muele_sync_state_test.json")
        )

    def _fake_download_response(self, content=b"%PDF-1.4 fake pdf content"):
        response = mock.Mock(status_code=200)
        response.raise_for_status.return_value = None
        response.iter_content.return_value = [content]
        return response

    def test_downloads_for_a_non_active_profile_land_under_that_profiles_root(self):
        # Profile A is active, but we're downloading a file for Profile B's
        # sync -- it must never land under A's root.
        file_info = {
            "filename": "lecture_notes.pdf",
            "fileurl": "https://muele.mak.ac.ug/fake/lecture_notes.pdf",
            "course_id": 42,
            "section_name": "General",
        }

        with mock.patch("requests.get", return_value=self._fake_download_response()):
            dest = muele_downloader.download_file(file_info, self.profile_b, token="fake-token")

        self.assertIsNotNone(dest)
        dest_path = Path(dest)
        self.assertTrue(dest_path.is_relative_to(self.other_root))
        self.assertFalse(dest_path.is_relative_to(self.profile_root))

    def test_move_event_is_attributed_to_the_synced_profile_not_the_active_one(self):
        file_info = {
            "filename": "assignment_brief.pdf",
            "fileurl": "https://muele.mak.ac.ug/fake/assignment_brief.pdf",
            "course_id": 43,
            "section_name": "General",
        }

        with mock.patch("requests.get", return_value=self._fake_download_response()):
            dest = muele_downloader.download_file(file_info, self.profile_b, token="fake-token")

        self.assertIsNotNone(dest)
        event = MoveEvent.objects.get(method="muele_sync", filename="assignment_brief.pdf")
        self.assertEqual(event.profile, self.profile_b)
        self.assertNotEqual(event.profile, self.profile_a)
