from unittest import mock

from django.urls import reverse

from organizer.core import jobs
from organizer.core import muele_downloader, timetable_sync
from organizer.models import BackgroundTask, IntegrationConnection, MueleCourse

from .helpers import SandboxedPathsTestCase
from .test_jobs import ImmediateThread


class MueleSyncNowViewTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.connection = IntegrationConnection.objects.create(
            profile=self.profile, provider="muele", display_name="MUELE",
        )

    def test_enqueues_a_background_task_and_returns_immediately(self):
        with mock.patch.object(jobs.threading, "Thread", ImmediateThread), \
                mock.patch.object(
                    muele_downloader, "sync_profile_courses",
                    return_value={"downloaded": 2, "skipped": 1, "errors": 0, "courses_synced": 1},
                ), \
                mock.patch.object(muele_downloader, "sync_assignments", return_value=3):
            response = self.client.post(reverse("muele_courses"), {"action": "sync_now"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertIn("task_id", data)

        task = BackgroundTask.objects.get(pk=data["task_id"])
        self.assertEqual(task.kind, "muele_sync")
        self.assertEqual(task.status, "done")
        self.assertIn("2 downloaded", task.result_message)
        self.assertIn("3 new assignments", task.result_message)

    def test_a_sync_failure_marks_the_task_failed_not_the_request(self):
        with mock.patch.object(jobs.threading, "Thread", ImmediateThread), \
                mock.patch.object(
                    muele_downloader, "sync_profile_courses", side_effect=RuntimeError("no network"),
                ):
            response = self.client.post(reverse("muele_courses"), {"action": "sync_now"})

        self.assertEqual(response.status_code, 200)
        task = BackgroundTask.objects.get(pk=response.json()["task_id"])
        self.assertEqual(task.status, "failed")
        self.assertIn("no network", task.result_message)


class TimetableSyncNowViewTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.connection = IntegrationConnection.objects.create(
            profile=self.profile, provider="mak_timetable", display_name="Makerere Timetable",
            config={
                "academic_year_id": "1", "academic_year_label": "2025/2026",
                "semester_id": "1", "college": "COCIS", "group": "SE-2",
            },
        )

    def test_enqueues_a_background_task_and_returns_immediately(self):
        with mock.patch.object(jobs.threading, "Thread", ImmediateThread), \
                mock.patch.object(timetable_sync, "sync_group_timetable", return_value=(12, None)):
            response = self.client.post(reverse("timetable_sync_now"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])

        task = BackgroundTask.objects.get(pk=data["task_id"])
        self.assertEqual(task.kind, "timetable_sync")
        self.assertEqual(task.status, "done")
        self.assertIn("12 timetable entries", task.result_message)

    def test_a_sync_error_with_no_rows_marks_the_task_failed(self):
        with mock.patch.object(jobs.threading, "Thread", ImmediateThread), \
                mock.patch.object(
                    timetable_sync, "sync_group_timetable", return_value=(0, "Site is down"),
                ):
            response = self.client.post(reverse("timetable_sync_now"))

        task = BackgroundTask.objects.get(pk=response.json()["task_id"])
        self.assertEqual(task.status, "failed")
        self.assertIn("Site is down", task.result_message)


class TaskStatusViewTests(SandboxedPathsTestCase):
    def test_reports_the_current_task_state(self):
        profile = self.make_profile()
        task = BackgroundTask.objects.create(
            profile=profile, kind="muele_sync", status="running",
            progress_current=3, progress_total=10,
        )

        response = self.client.get(reverse("task_status", args=[task.pk]))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "running")
        self.assertEqual(data["progress_current"], 3)
        self.assertEqual(data["progress_total"], 10)

    def test_another_profiles_task_404s(self):
        self.make_profile()
        other = self.make_profile(name="Other", is_active=False)
        task = BackgroundTask.objects.create(profile=other, kind="muele_sync", status="done")

        response = self.client.get(reverse("task_status", args=[task.pk]))
        self.assertEqual(response.status_code, 404)
