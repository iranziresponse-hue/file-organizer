import json
import os
import sys
import time
from types import SimpleNamespace
from unittest import mock

from django.utils import timezone

from organizer.core import review, watcher
from organizer.models import CourseConfig, FolderRule, MoveEvent, ReviewItem, SortDecision

from .helpers import SandboxedPathsTestCase


def _age(path, seconds=10):
    old = time.time() - seconds
    os.utime(path, (old, old))


class WatcherRuleAndInboxTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.enterContext(mock.patch.object(watcher.time, "sleep"))
        self.profile = self.make_profile()
        self.make_settings()
        CourseConfig.objects.create(
            profile=self.profile,
            primary_value="Year 2",
            secondary_value="Semester 1",
            groups=["BIO101"],
        )
        from organizer.core import paths

        paths.config_path(self.profile.root_path).write_text(json.dumps({
            "primary_value": "Year 2",
            "secondary_value": "Semester 1",
            "groups": ["BIO101"],
        }))

    def _aged_file(self, filename):
        target = self.downloads / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"notes")
        _age(target)
        return target

    def test_enabled_folder_rule_routes_before_default_logic(self):
        FolderRule.objects.create(
            profile=self.profile,
            name="Route biology slides",
            priority=1,
            match_field="filename",
            operator="contains",
            pattern="slides",
            subject_code="BIO101",
            category="Lecture Slides",
            action="route",
            enabled=True,
        )
        target = self._aged_file("week 4 slides.pdf")

        watcher.move_downloaded_file(target, ai_enabled=False)

        expected = self.profile_root / "Year 2" / "Semester 1" / "BIO101" / "Lecture Slides" / "week 4 slides.pdf"
        self.assertTrue(expected.exists())
        self.assertEqual(MoveEvent.objects.get().destination_path, str(expected))

    def test_review_rule_sends_file_to_inbox_without_moving_it(self):
        FolderRule.objects.create(
            profile=self.profile,
            name="Review uncertain files",
            priority=1,
            match_field="filename",
            operator="contains",
            pattern="unknown",
            action="review",
            enabled=True,
        )
        target = self._aged_file("unknown handout.pdf")

        watcher.move_downloaded_file(target, ai_enabled=False)

        self.assertTrue(target.exists())
        inbox_item = SortDecision.objects.get(profile=self.profile)
        self.assertEqual(inbox_item.filename, "unknown handout.pdf")
        self.assertEqual(inbox_item.status, "pending")
        self.assertIn("Review uncertain files", inbox_item.explanation)


class ReviewRescheduleWorkflowTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.event = MoveEvent.objects.create(
            profile=self.profile,
            filename="CSC2100 trees.pdf",
            source_path="C:/Downloads/CSC2100 trees.pdf",
            destination_path=str(self.profile_root / "CSC2100 trees.pdf"),
            method="course_code",
            course_code="CSC2100",
            success=True,
        )

    def test_done_review_creates_next_queued_review(self):
        item = ReviewItem.objects.create(
            profile=self.profile,
            move_event=self.event,
            subject_code="CSC2100",
            title="Review trees",
            due_at=timezone.now(),
            metadata={"interval_index": 0},
        )

        review.mark_review_done(item)

        item.refresh_from_db()
        next_item = ReviewItem.objects.exclude(pk=item.pk).get()
        self.assertEqual(item.status, "done")
        self.assertEqual(next_item.status, "queued")
        self.assertEqual(next_item.metadata["previous_review"], item.pk)
        self.assertEqual(next_item.metadata["source"], "spaced_repetition")

    def test_skipped_review_creates_shorter_queued_review(self):
        item = ReviewItem.objects.create(
            profile=self.profile,
            move_event=self.event,
            subject_code="CSC2100",
            title="Review trees",
            due_at=timezone.now(),
            metadata={"interval_index": 2},
        )

        review.skip_review(item)

        item.refresh_from_db()
        next_item = ReviewItem.objects.exclude(pk=item.pk).get()
        self.assertEqual(item.status, "skipped")
        self.assertEqual(next_item.status, "queued")
        self.assertEqual(next_item.metadata["source"], "rescheduled_after_skip")


class BatteryPauseTests(SandboxedPathsTestCase):
    def test_battery_info_uses_psutil_when_available(self):
        from gui.desktop_window import PauseDialog

        fake_psutil = SimpleNamespace(
            sensors_battery=lambda: SimpleNamespace(power_plugged=False, percent=42)
        )
        with mock.patch.dict(sys.modules, {"psutil": fake_psutil}):
            status, percent = PauseDialog._get_battery_info()

        self.assertEqual(status, "battery")
        self.assertEqual(percent, 42)

    def test_battery_info_falls_back_without_psutil(self):
        from gui.desktop_window import PauseDialog

        real_import = __import__

        def guarded_import(name, *args, **kwargs):
            if name == "psutil":
                raise ImportError("psutil unavailable")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            status, percent = PauseDialog._get_battery_info()

        self.assertEqual(status, "unknown")
        self.assertEqual(percent, 100)
