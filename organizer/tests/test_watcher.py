import json
import os
import threading
import time
from unittest import mock

from organizer.core import paths, watcher
from organizer.models import MoveEvent, Notification, SortDecision

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
        self.assertFalse(watcher.is_ready(target, max_attempts=1))

    def test_unopenable_path_is_not_ready(self):
        # A directory can never be opened as a file -- exercises the same
        # OSError branch a genuinely locked file would hit.
        target = self.downloads / "a_directory"
        target.mkdir(parents=True)
        self.assertFalse(watcher.is_ready(target, max_attempts=1))


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

    def test_media_file_is_left_in_place_when_category_disabled(self):
        # Global sorting is conservative by default: a category the user
        # hasn't opted into never moves a file, and doesn't clutter the
        # inbox either.
        target = self._aged_file("photo.png")

        watcher.move_downloaded_file(target, ai_enabled=False)

        self.assertTrue(target.exists())
        self.assertEqual(MoveEvent.objects.count(), 0)
        self.assertEqual(SortDecision.objects.count(), 0)

    def test_moves_media_file_and_records_event_once_category_is_enabled(self):
        expected_dir = self.personal_root / "Media" / "Images"
        self.make_category("media", destination_path=str(expected_dir), mode="auto")
        target = self._aged_file("photo.png")

        watcher.move_downloaded_file(target, ai_enabled=False)

        expected = expected_dir / "photo.png"
        self.assertTrue(expected.exists())
        self.assertFalse(target.exists())

        event = MoveEvent.objects.get()
        self.assertEqual(event.method, "media")
        self.assertTrue(event.success)
        self.assertIsNone(event.profile)
        self.assertEqual(event.destination_path, str(expected))
        self.assertTrue(event.undo_available)

        decision = SortDecision.objects.get()
        self.assertEqual(decision.status, "moved")
        self.assertEqual(decision.decision_type, "global_auto")
        self.assertEqual(decision.move_event, event)

    def test_review_mode_suggests_without_moving_the_file(self):
        expected_dir = self.personal_root / "Archives"
        self.make_category("archives", destination_path=str(expected_dir), mode="review")
        target = self._aged_file("project.zip")

        watcher.move_downloaded_file(target, ai_enabled=False)

        self.assertTrue(target.exists())
        self.assertEqual(MoveEvent.objects.count(), 0)

        decision = SortDecision.objects.get()
        self.assertEqual(decision.status, "pending")
        self.assertEqual(decision.decision_type, "global_suggested")
        self.assertEqual(decision.suggested_destination, str(expected_dir))

    def test_review_mode_does_not_pile_up_duplicate_pending_decisions(self):
        # The file stays put every poll cycle until the user acts on it --
        # re-scanning it must not create a second pending SortDecision.
        self.make_category("archives", destination_path=str(self.personal_root / "Archives"), mode="review")
        target = self._aged_file("project.zip")

        watcher.move_downloaded_file(target, ai_enabled=False)
        watcher.move_downloaded_file(target, ai_enabled=False)

        self.assertEqual(SortDecision.objects.count(), 1)

    def test_doc_file_routes_into_active_profile_and_records_it(self):
        # TST1000 is a made-up code (not a real Makerere course), so the
        # destination folder stays bare -- see test_rules.py for the
        # "real course code gets its real name" behavior.
        profile = self.make_profile()
        paths.config_path(profile.root_path).write_text(json.dumps({
            "primary_value": "Year 2",
            "secondary_value": "Semester 1",
            "groups": ["TST1000"],
        }))
        target = self._aged_file("TST1000 Assignment 1.docx")

        watcher.move_downloaded_file(target, ai_enabled=False)

        expected = self.profile_root / "Year 2" / "Semester 1" / "TST1000" / "02 Assignments and Coursework" / "TST1000 Assignment 1.docx"
        self.assertTrue(expected.exists())

        event = MoveEvent.objects.get()
        self.assertEqual(event.profile, profile)
        self.assertEqual(event.method, "course_code")
        self.assertEqual(event.course_code, "TST1000")

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

    def test_office_lock_files_are_never_moved(self):
        # "~$Report.docx" is Word's own temporary lock file, created while
        # the real document is open elsewhere -- not real content, and it
        # disappears on its own once the document is closed.
        target = self._aged_file("~$Report.docx", content=b"")

        watcher.move_downloaded_file(target, ai_enabled=False)

        self.assertTrue(target.exists())
        self.assertEqual(MoveEvent.objects.count(), 0)

    def test_a_successful_move_creates_a_notification(self):
        self.make_category("installers", destination_path=str(self.personal_root / "Installers"), mode="auto")
        target = self._aged_file("setup.exe")

        watcher.move_downloaded_file(target, ai_enabled=False)

        notification = Notification.objects.get()
        self.assertIn("setup.exe", notification.message)
        # The drive letter must be identifiable, not just the folder name --
        # a system with files routed across several drives (C:, D:, ...)
        # needs to know which one a notification is actually about.
        self.assertIn(str(self.personal_root.drive), notification.message)

    def test_a_successful_move_triggers_a_drive_backup_attempt_when_enabled(self):
        # Runs the backup thread's target synchronously instead of on a
        # real background thread, so this test is deterministic and never
        # touches the network -- drive_api.backup_file itself is mocked.
        class ImmediateThread:
            def __init__(self, target=None, args=(), kwargs=None, daemon=None):
                self._target = target
                self._args = args
                self._kwargs = kwargs or {}

            def start(self):
                self._target(*self._args, **self._kwargs)

        self.make_category("installers", destination_path=str(self.personal_root / "Installers"), mode="auto")
        target = self._aged_file("setup.exe")

        with mock.patch("organizer.core.sorting.threading.Thread", ImmediateThread), \
                mock.patch("organizer.core.drive_api.load_drive_config", return_value={"enabled": True}), \
                mock.patch("organizer.core.drive_api.backup_file", return_value=True) as backup:
            watcher.move_downloaded_file(target, ai_enabled=False)

        backup.assert_called_once()
        self.assertIn("setup.exe", backup.call_args.args[0])
        event = MoveEvent.objects.get()
        self.assertEqual(event.drive_backup_status, "success")

    def test_no_backup_attempt_when_drive_backup_is_not_turned_on(self):
        class ImmediateThread:
            def __init__(self, target=None, args=(), kwargs=None, daemon=None):
                self._target = target
                self._args = args
                self._kwargs = kwargs or {}

            def start(self):
                self._target(*self._args, **self._kwargs)

        self.make_category("installers", destination_path=str(self.personal_root / "Installers"), mode="auto")
        target = self._aged_file("setup.exe")

        with mock.patch("organizer.core.sorting.threading.Thread", ImmediateThread), \
                mock.patch("organizer.core.drive_api.load_drive_config", return_value=None), \
                mock.patch("organizer.core.drive_api.backup_file") as backup:
            watcher.move_downloaded_file(target, ai_enabled=False)

        backup.assert_not_called()
        event = MoveEvent.objects.get()
        # Not "failed" -- Drive backup simply isn't in use, so there's
        # nothing to retry and nothing to alarm the user about.
        self.assertEqual(event.drive_backup_status, "not_attempted")

    def test_name_collision_gets_a_timestamp_suffix(self):
        images_dir = self.personal_root / "Media" / "Images"
        self.make_category("media", destination_path=str(images_dir), mode="auto")

        first = self._aged_file("photo.png")
        watcher.move_downloaded_file(first, ai_enabled=False)

        second = self._aged_file("photo.png")
        watcher.move_downloaded_file(second, ai_enabled=False)

        self.assertEqual(len(list(images_dir.iterdir())), 2)
        self.assertEqual(MoveEvent.objects.count(), 2)

    def test_sensitive_file_is_held_for_review_not_auto_moved(self):
        # Sensitive files are never silent: they always land in the
        # Decision Inbox instead of moving on their own, even though a
        # destination is known.
        target = self._aged_file("banking password.pdf")

        watcher.move_downloaded_file(target, ai_enabled=False)

        self.assertTrue(target.exists())
        self.assertEqual(MoveEvent.objects.count(), 0)

        decision = SortDecision.objects.get()
        self.assertEqual(decision.status, "pending")
        self.assertEqual(decision.decision_type, "held_sensitive")
        self.assertIn(str(self.personal_root / "Important"), decision.suggested_destination)

    def test_ai_enabled_none_defers_to_profile_setting(self):
        profile = self.make_profile(ai_fallback_enabled=False)
        target = self._aged_file("unmatched notes.docx")

        with mock.patch("organizer.core.ai_classify.classify") as mock_classify:
            watcher.move_downloaded_file(target, ai_enabled=None)

        mock_classify.assert_not_called()


class RunWatcherAndInstallerCleanupTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.enterContext(mock.patch.object(watcher.time, "sleep"))

    def test_initial_sweep_uses_the_configured_downloads_path(self):
        self.make_settings(secondary_downloads_path="")
        expected_dir = self.personal_root / "Media" / "Images"
        self.make_category("media", destination_path=str(expected_dir), mode="auto")
        target = self.downloads / "photo.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"data")
        _age(target, 10)

        # Pre-set the stop event so the blocking loop never runs -- only the
        # unconditional initial sweep before it does.
        stop_event = threading.Event()
        stop_event.set()
        watcher.run_watcher(stop_event=stop_event, poll_seconds=0)

        expected = expected_dir / "photo.png"
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
