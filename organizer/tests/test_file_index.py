from unittest import mock

from organizer.core import file_index
from organizer.models import FileIndexEntry

from .helpers import SandboxedPathsTestCase


class CheckAndRecordTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_a_never_seen_file_is_reported_as_changed(self):
        target = self.profile_root / "notes.pdf"
        target.write_text("content", encoding="utf-8")

        unchanged = file_index.check_and_record(target, self.profile)

        self.assertFalse(unchanged)
        self.assertTrue(FileIndexEntry.objects.filter(path=file_index._key(target)).exists())

    def test_calling_it_again_with_no_changes_reports_unchanged(self):
        target = self.profile_root / "notes.pdf"
        target.write_text("content", encoding="utf-8")

        file_index.check_and_record(target, self.profile)
        unchanged = file_index.check_and_record(target, self.profile)

        self.assertTrue(unchanged)
        self.assertEqual(FileIndexEntry.objects.filter(path=file_index._key(target)).count(), 1)

    def test_editing_the_file_is_reported_as_changed(self):
        target = self.profile_root / "notes.pdf"
        target.write_text("content", encoding="utf-8")
        file_index.check_and_record(target, self.profile)

        target.write_text("different, longer content", encoding="utf-8")
        unchanged = file_index.check_and_record(target, self.profile)

        self.assertFalse(unchanged)
        entry = FileIndexEntry.objects.get(path=file_index._key(target))
        self.assertEqual(entry.size, target.stat().st_size)

    def test_a_missing_file_is_reported_as_changed_and_not_recorded(self):
        target = self.profile_root / "gone.pdf"

        unchanged = file_index.check_and_record(target, self.profile)

        self.assertFalse(unchanged)
        self.assertFalse(FileIndexEntry.objects.filter(path=file_index._key(target)).exists())

    def test_entries_are_scoped_per_profile(self):
        target = self.profile_root / "notes.pdf"
        target.write_text("content", encoding="utf-8")
        profile_b = self.make_profile(name="B", is_active=False)

        file_index.check_and_record(target, self.profile)
        unchanged_for_b = file_index.check_and_record(target, profile_b)

        self.assertFalse(unchanged_for_b)
        self.assertEqual(FileIndexEntry.objects.filter(path=file_index._key(target)).count(), 2)

    def test_records_classification_and_summary_status_when_given(self):
        target = self.profile_root / "notes.pdf"
        target.write_text("content", encoding="utf-8")

        file_index.check_and_record(target, self.profile, classification="BIO101", summary_status="generated")

        entry = FileIndexEntry.objects.get(path=file_index._key(target))
        self.assertEqual(entry.last_classification, "BIO101")
        self.assertEqual(entry.last_summary_status, "generated")

    def test_a_broken_write_never_raises(self):
        target = self.profile_root / "notes.pdf"
        target.write_text("content", encoding="utf-8")

        with mock.patch(
            "organizer.models.FileIndexEntry.objects.update_or_create", side_effect=Exception("db down"),
        ):
            unchanged = file_index.check_and_record(target, self.profile)

        self.assertFalse(unchanged)


class CheckAndRecordSeparateTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_check_is_read_only(self):
        target = self.profile_root / "notes.pdf"
        target.write_text("content", encoding="utf-8")

        self.assertFalse(file_index.check(target, self.profile))
        self.assertFalse(FileIndexEntry.objects.exists())

        file_index.record(target, self.profile)
        self.assertTrue(file_index.check(target, self.profile))


class PathNormalizationTests(SandboxedPathsTestCase):
    """The real bug this guards against: on Windows the same file can be
    named with different casing, or reached through a relative path with
    '..' segments, or an absolute vs relative form -- a naive str(path)
    key would treat all of those as different files and never actually
    detect "unchanged", quietly defeating the whole point of the index."""

    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_different_casing_of_the_same_path_is_the_same_entry(self):
        target = self.profile_root / "Notes.PDF"
        target.write_text("content", encoding="utf-8")
        file_index.check_and_record(target, self.profile)

        differently_cased = self.profile_root / "notes.pdf"
        unchanged = file_index.check(differently_cased, self.profile)

        self.assertTrue(unchanged)
        self.assertEqual(FileIndexEntry.objects.count(), 1)

    def test_a_path_with_dot_dot_segments_resolves_to_the_same_entry(self):
        target = self.profile_root / "notes.pdf"
        target.write_text("content", encoding="utf-8")
        file_index.check_and_record(target, self.profile)

        roundabout = self.profile_root / "Sibling" / ".." / "notes.pdf"
        unchanged = file_index.check(roundabout, self.profile)

        self.assertTrue(unchanged)

    def test_relative_and_absolute_forms_of_the_same_path_agree(self):
        import os

        target = self.profile_root / "notes.pdf"
        target.write_text("content", encoding="utf-8")
        file_index.check_and_record(target, self.profile)

        old_cwd = os.getcwd()
        os.chdir(str(self.profile_root))
        try:
            from pathlib import Path
            unchanged = file_index.check(Path("notes.pdf"), self.profile)
        finally:
            os.chdir(old_cwd)

        self.assertTrue(unchanged)


class ComputeContentHashTests(SandboxedPathsTestCase):
    def test_returns_a_stable_hash_for_the_same_content(self):
        target = self.profile_root / "notes.pdf"
        target.write_text("content", encoding="utf-8")

        first = file_index.compute_content_hash(target)
        second = file_index.compute_content_hash(target)

        self.assertIsNotNone(first)
        self.assertEqual(first, second)

    def test_returns_none_for_a_missing_file(self):
        self.assertIsNone(file_index.compute_content_hash(self.profile_root / "gone.pdf"))
