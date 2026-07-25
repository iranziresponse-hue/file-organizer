import json
from unittest import mock

from organizer.core import file_index, jobs, sorting
from organizer.models import CourseConfig, MoveEvent, SortDecision

from .helpers import SandboxedPathsTestCase


class SortFolderTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.make_settings()
        CourseConfig.objects.create(
            profile=self.profile, primary_value="Year 2", secondary_value="Semester 1", groups=["BIO101"],
        )
        from organizer.core import paths

        paths.config_path(self.profile.root_path).write_text(json.dumps({
            "primary_value": "Year 2", "secondary_value": "Semester 1", "groups": ["BIO101"],
        }))
        self.messy = self.profile_root.parent / "Messy"
        self.messy.mkdir(parents=True)

    def test_missing_folder_returns_a_clear_message_without_raising(self):
        summary = sorting.sort_folder(str(self.profile_root.parent / "does-not-exist"), self.profile)
        self.assertIn("does not exist", summary)

    def test_moves_a_matching_file_using_the_real_pipeline(self):
        target = self.messy / "BIO101 cells.pdf"
        target.write_bytes(b"cell notes")

        summary = sorting.sort_folder(str(self.messy), self.profile)

        self.assertFalse(target.exists())  # really moved, not just logged
        self.assertIn("1 moved", summary)
        event = MoveEvent.objects.get(filename="BIO101 cells.pdf")
        self.assertTrue(event.success)
        self.assertEqual(event.course_code, "BIO101")

    def test_a_sensitive_file_is_held_for_review_not_auto_moved(self):
        target = self.messy / "passwords.txt"
        target.write_bytes(b"secret")

        summary = sorting.sort_folder(str(self.messy), self.profile)

        self.assertTrue(target.exists())  # held in place, not moved out from under the user
        self.assertIn("1 sent to Decision Inbox", summary)
        self.assertTrue(SortDecision.objects.filter(filename="passwords.txt", status="pending").exists())

    def test_an_unmatched_file_is_left_in_place(self):
        target = self.messy / "random.xyz"
        target.write_bytes(b"?")

        summary = sorting.sort_folder(str(self.messy), self.profile)

        self.assertTrue(target.exists())
        self.assertIn("1 left in place", summary)

    def test_rerunning_skips_a_file_already_seen_and_left_unmoved(self):
        target = self.messy / "random.xyz"
        target.write_bytes(b"?")
        sorting.sort_folder(str(self.messy), self.profile)

        second = sorting.sort_folder(str(self.messy), self.profile)

        self.assertIn("1 unchanged since last time", second)
        self.assertIn("0 left in place", second)

    def test_editing_a_previously_left_file_makes_it_get_reevaluated(self):
        target = self.messy / "random.xyz"
        target.write_bytes(b"?")
        sorting.sort_folder(str(self.messy), self.profile)

        target.write_bytes(b"a much longer file than before, definitely different size")
        second = sorting.sort_folder(str(self.messy), self.profile)

        self.assertIn("1 left in place", second)
        self.assertIn("0 unchanged since last time", second)

    def test_one_failing_file_does_not_stop_the_rest_of_the_scan(self):
        good = self.messy / "BIO101 notes.pdf"
        good.write_bytes(b"notes")
        bad = self.messy / "BIO101 broken.pdf"
        bad.write_bytes(b"notes")

        real_process_file = sorting.process_file

        def flaky(file_path, *args, **kwargs):
            if file_path.name == "BIO101 broken.pdf":
                raise OSError("permission denied")
            return real_process_file(file_path, *args, **kwargs)

        with mock.patch.object(sorting, "process_file", side_effect=flaky):
            summary = sorting.sort_folder(str(self.messy), self.profile)

        self.assertIn("1 moved", summary)
        self.assertIn("1 failed", summary)
        self.assertFalse(good.exists())
        self.assertTrue(bad.exists())

    def test_reports_progress_through_the_task_reporter(self):
        (self.messy / "a.xyz").write_bytes(b"1")
        (self.messy / "b.xyz").write_bytes(b"2")
        updates = []

        class RecordingReporter:
            def update(self, current, total=None, message=""):
                updates.append((current, total))

            def is_cancelled(self):
                return False

        sorting.sort_folder(str(self.messy), self.profile, task=RecordingReporter())

        self.assertEqual(updates[-1], (2, 2))

    def test_cancelling_stops_the_scan_early_between_files(self):
        for i in range(10):
            (self.messy / f"file{i}.xyz").write_bytes(str(i).encode())

        class CancelAfterOne:
            def __init__(self):
                self.calls = 0

            def update(self, current, total=None, message=""):
                pass

            def is_cancelled(self):
                self.calls += 1
                return self.calls > 1  # lets the first check-point pass, cancels on the next

        summary = sorting.sort_folder(str(self.messy), self.profile, task=CancelAfterOne())

        self.assertIn("Cancelled after", summary)
        remaining = list(self.messy.glob("*.xyz"))
        self.assertGreater(len(remaining), 0)  # the scan really did stop early
