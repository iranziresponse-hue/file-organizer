import os
import time
from unittest import mock

from organizer.core import watcher
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

    def test_moves_media_file_and_records_event(self):
        target = self._aged_file("photo.png")

        watcher.move_downloaded_file(target, ai_enabled=False)

        expected = self.personal_root / "Media" / "Images" / "photo.png"
        self.assertTrue(expected.exists())
        self.assertFalse(target.exists())

        event = MoveEvent.objects.get()
        self.assertEqual(event.method, "media")
        self.assertTrue(event.success)
        self.assertEqual(event.filename, "photo.png")
        self.assertEqual(event.destination_path, str(expected))

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
