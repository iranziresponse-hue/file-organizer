from django.urls import reverse

from organizer.core import paths
from organizer.models import AppSettings

from .helpers import SandboxedPathsTestCase


class AppSettingsModelTests(SandboxedPathsTestCase):
    def test_get_solo_creates_a_row_with_sandboxed_defaults(self):
        self.assertEqual(AppSettings.objects.count(), 0)

        settings = AppSettings.get_solo()

        self.assertEqual(AppSettings.objects.count(), 1)
        self.assertEqual(settings.downloads_path, str(paths.DEFAULT_DOWNLOADS))
        self.assertEqual(settings.library_inbox_path, str(paths.DEFAULT_LIBRARY_INBOX))
        self.assertEqual(settings.secondary_downloads_path, "")
        self.assertEqual(settings.installer_stale_days, 30)
        self.assertEqual(settings.installer_delete_days, 60)

    def test_get_solo_is_a_singleton(self):
        first = AppSettings.get_solo()
        first.downloads_path = "changed"
        first.save()

        second = AppSettings.get_solo()

        self.assertEqual(AppSettings.objects.count(), 1)
        self.assertEqual(second.pk, first.pk)
        self.assertEqual(second.downloads_path, "changed")

    def test_str(self):
        self.assertEqual(str(AppSettings.get_solo()), "App settings")


class SettingsViewTests(SandboxedPathsTestCase):
    def test_get_renders_current_values(self):
        self.make_settings(downloads_path="C:/MyDownloads")
        response = self.client.get(reverse("settings_edit"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "C:/MyDownloads")

    def test_post_updates_settings(self):
        self.make_settings()

        response = self.client.post(reverse("settings_edit"), {
            "downloads_path": "C:/NewDownloads",
            "secondary_downloads_path": "D:/OtherDownloads",
            "library_inbox_path": "C:/NewLibrary",
            "installer_stale_days": "10",
            "installer_delete_days": "20",
        })

        self.assertRedirects(response, reverse("settings_edit"))
        settings = AppSettings.get_solo()
        self.assertEqual(settings.downloads_path, "C:/NewDownloads")
        self.assertEqual(settings.secondary_downloads_path, "D:/OtherDownloads")
        self.assertEqual(settings.library_inbox_path, "C:/NewLibrary")
        self.assertEqual(settings.installer_stale_days, 10)
        self.assertEqual(settings.installer_delete_days, 20)

    def test_blank_secondary_downloads_disables_it(self):
        self.make_settings(secondary_downloads_path="D:/SomeDownloads")

        self.client.post(reverse("settings_edit"), {
            "downloads_path": "C:/Downloads",
            "secondary_downloads_path": "",
            "library_inbox_path": "C:/Library",
            "installer_stale_days": "30",
            "installer_delete_days": "60",
        })

        self.assertEqual(AppSettings.get_solo().secondary_downloads_path, "")

    def test_non_numeric_day_values_are_ignored_not_fatal(self):
        settings = self.make_settings(installer_stale_days=30, installer_delete_days=60)

        response = self.client.post(reverse("settings_edit"), {
            "downloads_path": settings.downloads_path,
            "secondary_downloads_path": "",
            "library_inbox_path": settings.library_inbox_path,
            "installer_stale_days": "not-a-number",
            "installer_delete_days": "also-not-a-number",
        })

        self.assertEqual(response.status_code, 302)
        settings.refresh_from_db()
        self.assertEqual(settings.installer_stale_days, 30)
        self.assertEqual(settings.installer_delete_days, 60)
