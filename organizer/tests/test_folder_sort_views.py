from unittest import mock

from django.urls import reverse

from organizer.core import jobs, sorting
from organizer.models import BackgroundTask

from .helpers import SandboxedPathsTestCase
from .test_jobs import ImmediateThread


class FolderSortStartViewTests(SandboxedPathsTestCase):
    def test_get_is_not_allowed(self):
        response = self.client.get(reverse("folder_sort_start"))
        self.assertEqual(response.status_code, 405)

    def test_without_an_active_profile_redirects_without_starting(self):
        response = self.client.post(reverse("folder_sort_start"), {"root_path": str(self.profile_root)})
        self.assertRedirects(response, reverse("dashboard"))
        self.assertFalse(BackgroundTask.objects.exists())

    def test_rejects_a_blank_path(self):
        self.make_profile()
        response = self.client.post(reverse("folder_sort_start"), {"root_path": ""})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(BackgroundTask.objects.exists())

    def test_rejects_a_folder_that_does_not_exist(self):
        self.make_profile()
        response = self.client.post(
            reverse("folder_sort_start"), {"root_path": str(self.profile_root / "nope")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(BackgroundTask.objects.exists())

    def test_enqueues_a_background_task_and_returns_immediately(self):
        self.make_profile()
        messy = self.profile_root.parent / "Messy"
        messy.mkdir()

        with mock.patch.object(jobs.threading, "Thread", ImmediateThread), \
                mock.patch.object(sorting, "sort_folder", return_value="Scanned 0 of 0 file(s)."):
            response = self.client.post(reverse("folder_sort_start"), {"root_path": str(messy)})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        task = BackgroundTask.objects.get(pk=data["task_id"])
        self.assertEqual(task.kind, "large_folder_sort")
        self.assertEqual(task.status, "done")


class FolderSortCancelViewTests(SandboxedPathsTestCase):
    def test_get_is_not_allowed(self):
        profile = self.make_profile()
        task = BackgroundTask.objects.create(profile=profile, kind="large_folder_sort", status="running")
        response = self.client.get(reverse("folder_sort_cancel", args=[task.pk]))
        self.assertEqual(response.status_code, 405)

    def test_marks_a_running_task_as_cancelling(self):
        profile = self.make_profile()
        task = BackgroundTask.objects.create(profile=profile, kind="large_folder_sort", status="running")

        response = self.client.post(reverse("folder_sort_cancel", args=[task.pk]))

        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, "cancelling")

    def test_cannot_cancel_another_profiles_task(self):
        self.make_profile()
        other = self.make_profile(name="Other", is_active=False)
        task = BackgroundTask.objects.create(profile=other, kind="large_folder_sort", status="running")

        response = self.client.post(reverse("folder_sort_cancel", args=[task.pk]))
        self.assertEqual(response.status_code, 404)
