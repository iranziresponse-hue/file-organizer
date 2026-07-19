import json
import os
import threading
import time
from unittest import mock

from organizer.core import paths, watcher
from organizer.models import MoveEvent

from .helpers import SandboxedPathsTestCase


def _age(path, seconds=10):
    """move_downloaded_file ignores anything written in the last 2 seconds
    (still-being-downloaded guard) -- back-date mtime so test fixtures read
    as "finished downloading a while ago"."""
    old = time.time() - seconds
    os.utime(path, (old, old))


class IsReadyTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        # is_ready sleeps between checks -- mocked out so tests run instantly
        # instead of waiting on real wall-clock time.
        self.enterContext(mock.patch.object(watcher.time, "sleep"))

    def test_stable_file_is_ready(self):
        target = self.downloads / "download.bin"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"done downloading")

        self.assertTrue(watcher.is_ready(target))

    def test_missing_file_is_not_ready(self):
        target = self.downloads / "gone.bin"
        self.assertFalse(watcher.is_ready(target, attempts=1))

    def test_unopenable_path_is_not_ready(self):
        # A directory can never be opened as a file -- exercises the same
        # OSError branch a genuinely locked file would hit.
        target = self.downloads / "a_directory"
        target.mkdir(parents=True)
        self.assertFalse(watcher.is_ready(target, attempts=1))


class MoveDownloadedFileTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.enterContext(mock.patch.object(watcher.time, "sleep"))

    def _aged_file(self, relative_name, content=b"data", seconds=10):
        target = self.downloads / relative_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        _age(target, seconds)
        return target

    def test_moves_media_file_and_records_event_with_no_active_profile(self):
        target = self._aged_file("photo.png")

        watcher.move_downloaded_file(target, ai_enabled=False)

        expected = self.personal_root / "Media" / "Images" / "photo.png"
        self.assertTrue(expected.exists())
        self.assertFalse(target.exists())

        event = MoveEvent.objects.get()
        self.assertEqual(event.method, "media")
        self.assertTrue(event.success)
        self.assertIsNone(event.profile)
        self.assertEqual(event.destination_path, str(expected))

    def test_doc_file_routes_into_active_profile_and_records_it(self):
        profile = self.make_profile()
        paths.config_path(profile.root_path).write_text(json.dumps({
            "primary_value": "Year 2",
            "secondary_value": "Semester 1",
            "groups": ["CSC2100"],
        }))
        target = self._aged_file("CSC2100 Assignment 1.docx")

        watcher.move_downloaded_file(target, ai_enabled=False)

        expected = self.profile_root / "Year 2" / "Semester 1" / "CSC2100" / "02 Assignments and Coursework" / "CSC2100 Assignment 1.docx"
        self.assertTrue(expected.exists())

        event = MoveEvent.objects.get()
        self.assertEqual(event.profile, profile)
        self.assertEqual(event.method, "course_code")
        self.assertEqual(event.course_code, "CSC2100")

    def test_brand_new_file_is_left_alone_this_cycle(self):
        target = self.downloads / "still-writing.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"x")  # mtime is "now" -- under the 2s guard

        watcher.move_downloaded_file(target, ai_enabled=False)

        self.assertTrue(target.exists())
        self.assertEqual(MoveEvent.objects.count(), 0)

    def test_skip_names_are_ignored(self):
        target = self._aged_file("_config.json", content=b"{}")

        watcher.move_downloaded_file(target, ai_enabled=False)

        self.assertTrue(target.exists())
        self.assertEqual(MoveEvent.objects.count(), 0)

    def test_name_collision_gets_a_timestamp_suffix(self):
        first = self._aged_file("photo.png")
        watcher.move_downloaded_file(first, ai_enabled=False)

        second = self._aged_file("photo.png")
        watcher.move_downloaded_file(second, ai_enabled=False)

        images_dir = self.personal_root / "Media" / "Images"
        self.assertEqual(len(list(images_dir.iterdir())), 2)
        self.assertEqual(MoveEvent.objects.count(), 2)

    def test_sensitive_file_is_routed_to_important(self):
        target = self._aged_file("banking password.pdf")

        watcher.move_downloaded_file(target, ai_enabled=False)

        expected = self.personal_root / "Important" / "banking password.pdf"
        self.assertTrue(expected.exists())
        self.assertEqual(MoveEvent.objects.get().method, "sensitive")

    def test_ai_enabled_none_defers_to_profile_setting(self):
        profile = self.make_profile(ai_fallback_enabled=False)
        target = self._aged_file("unmatched notes.docx")

        with mock.patch("organizer.core.watcher.ai_classify.classify") as mock_classify:
            watcher.move_downloaded_file(target, ai_enabled=None)

        mock_classify.assert_not_called()


class RunWatcherAndInstallerCleanupTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.enterContext(mock.patch.object(watcher.time, "sleep"))

    def test_initial_sweep_uses_the_configured_downloads_path(self):
        self.make_settings(secondary_downloads_path="")
        target = self.downloads / "photo.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"data")
        _age(target, 10)

        # Pre-set the stop event so the blocking loop never runs -- only the
        # unconditional initial sweep before it does.
        stop_event = threading.Event()
        stop_event.set()
        watcher.run_watcher(stop_event=stop_event, poll_seconds=0)

        expected = self.personal_root / "Media" / "Images" / "photo.png"
        self.assertTrue(expected.exists())

    def test_installer_cleanup_uses_configured_thresholds(self):
        # 2 days old clears the stale threshold (moves to _ToReview) but not
        # the delete threshold (stays there, not deleted), so this exercises
        # both configured values in one pass.
        self.make_settings(installer_stale_days=1, installer_delete_days=5)
        installers_root = self.personal_root / "Installers"
        installers_root.mkdir(parents=True)
        stale = installers_root / "setup.exe"
        stale.write_bytes(b"x")
        _age(stale, seconds=2 * 86400)

        watcher.run_installer_cleanup()

        self.assertFalse(stale.exists())
        self.assertTrue((installers_root / "_ToReview" / "setup.exe").exists())
