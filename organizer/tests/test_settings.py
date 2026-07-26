import json
from unittest import mock

from django.urls import reverse

from organizer.core import owner_access, paths
from organizer.models import AppSettings, GlobalSortCategory

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

    def test_ai_settings_are_not_written_when_untouched(self):
        # Saving the form without ever touching the AI section shouldn't
        # create ai_config.json out of nothing for users who don't use it.
        self.make_settings()

        self.client.post(reverse("settings_edit"), {
            "downloads_path": "C:/Downloads",
            "secondary_downloads_path": "",
            "library_inbox_path": "C:/Library",
            "installer_stale_days": "30",
            "installer_delete_days": "60",
        })

        self.assertFalse(paths.AI_CONFIG_PATH.exists())

    def test_enabling_ai_and_setting_a_key_writes_ai_config(self):
        self.make_settings()

        self.client.post(reverse("settings_edit"), {
            "downloads_path": "C:/Downloads",
            "secondary_downloads_path": "",
            "library_inbox_path": "C:/Library",
            "installer_stale_days": "30",
            "installer_delete_days": "60",
            "ai_enabled": "on",
            "ai_api_key": "gsk_test_key_123",
        })

        self.assertTrue(paths.AI_CONFIG_PATH.exists())
        import json
        saved = json.loads(paths.AI_CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertTrue(saved["enabled"])
        self.assertEqual(saved["api_key"], "gsk_test_key_123")

    def test_blank_api_key_does_not_erase_an_existing_one(self):
        self.make_settings()
        paths.AI_CONFIG_PATH.write_text(
            '{"enabled": true, "api_key": "gsk_existing_key", "model": "llama-3.1-8b-instant"}',
            encoding="utf-8",
        )

        self.client.post(reverse("settings_edit"), {
            "downloads_path": "C:/Downloads",
            "secondary_downloads_path": "",
            "library_inbox_path": "C:/Library",
            "installer_stale_days": "30",
            "installer_delete_days": "60",
            "ai_enabled": "on",
            "ai_api_key": "",
        })

        import json
        saved = json.loads(paths.AI_CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(saved["api_key"], "gsk_existing_key")

    def test_enabling_drive_backup_writes_client_credentials(self):
        self.make_settings()

        self.client.post(reverse("settings_edit"), {
            "downloads_path": "C:/Downloads",
            "secondary_downloads_path": "",
            "library_inbox_path": "C:/Library",
            "installer_stale_days": "30",
            "installer_delete_days": "60",
            "drive_enabled": "on",
            "drive_client_id": "test-client-id",
            "drive_client_secret": "test-client-secret",
        })

        self.assertTrue(paths.DRIVE_CONFIG_PATH.exists())
        import json
        saved = json.loads(paths.DRIVE_CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertTrue(saved["enabled"])
        self.assertEqual(saved["client_id"], "test-client-id")
        self.assertEqual(saved["client_secret"], "test-client-secret")

    def test_blank_drive_credentials_do_not_erase_existing_ones(self):
        self.make_settings()
        paths.DRIVE_CONFIG_PATH.write_text(
            '{"enabled": true, "client_id": "existing-id", "client_secret": "existing-secret"}',
            encoding="utf-8",
        )

        self.client.post(reverse("settings_edit"), {
            "downloads_path": "C:/Downloads",
            "secondary_downloads_path": "",
            "library_inbox_path": "C:/Library",
            "installer_stale_days": "30",
            "installer_delete_days": "60",
            "drive_enabled": "on",
            "drive_client_id": "",
            "drive_client_secret": "",
        })

        import json
        saved = json.loads(paths.DRIVE_CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(saved["client_id"], "existing-id")
        self.assertEqual(saved["client_secret"], "existing-secret")

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

    def test_owner_mode_is_off_by_default(self):
        self.make_settings()

        response = self.client.get(reverse("settings_edit"))

        self.assertContains(response, "Not set up yet")
        self.assertFalse(owner_access.owner_mode_enabled())

    def test_enabling_owner_mode_writes_the_config_file(self):
        self.make_settings()

        self.client.post(reverse("owner_mode_toggle"), {"enabled": "true"})

        self.assertTrue(owner_access.owner_mode_enabled())
        saved = json.loads(self.owner_config_path.read_text(encoding="utf-8"))
        self.assertTrue(saved["owner_mode"])

    def test_turning_owner_mode_off_again_updates_the_file(self):
        self.make_settings()
        self.owner_config_path.write_text(json.dumps({"owner_mode": True}), encoding="utf-8")

        self.client.post(reverse("owner_mode_toggle"), {"enabled": "false"})

        self.assertFalse(owner_access.owner_mode_enabled())

    def test_saving_unrelated_settings_never_touches_owner_mode(self):
        # Regression test: owner_mode used to be one more field bundled
        # into this same form, so saving anything else on this page (with
        # the checkbox not part of that particular POST) silently reset it
        # to off -- even for someone who'd already set up their account.
        self.make_settings()
        self.owner_config_path.write_text(json.dumps({"owner_mode": True}), encoding="utf-8")

        self.client.post(reverse("settings_edit"), {
            "downloads_path": "C:/Downloads",
            "secondary_downloads_path": "",
            "library_inbox_path": "C:/Library",
            "installer_stale_days": "30",
            "installer_delete_days": "60",
        })

        self.assertTrue(owner_access.owner_mode_enabled())

    def test_owner_console_section_is_hidden_from_a_packaged_build(self):
        # Every install of Orch (this developer's machine included) runs on
        # 127.0.0.1, so an IP check alone can't tell "the developer" apart
        # from any other student running their own local copy. The feature
        # must not even be visible in the exe students actually download --
        # only in a from-source dev checkout (see owner_access.py).
        self.make_settings()

        with mock.patch("organizer.core.owner_access.is_packaged_build", return_value=True):
            response = self.client.get(reverse("settings_edit"))

        self.assertNotContains(response, "Owner console")
        self.assertNotContains(response, 'id="owner-mode-toggle"')

    def test_owner_mode_toggle_is_a_404_on_a_packaged_build(self):
        self.make_settings()

        with mock.patch("organizer.core.owner_access.is_packaged_build", return_value=True):
            response = self.client.post(reverse("owner_mode_toggle"), {"enabled": "true"})

        self.assertEqual(response.status_code, 404)
        self.assertFalse(self.owner_config_path.exists())

    def test_a_stale_config_file_cannot_turn_on_owner_mode_in_a_packaged_build(self):
        self.owner_config_path.write_text(json.dumps({"owner_mode": True}), encoding="utf-8")

        with mock.patch("organizer.core.owner_access.is_packaged_build", return_value=True):
            enabled = owner_access.owner_mode_enabled()

        self.assertFalse(enabled)


class AutomationControlSettingsTests(SandboxedPathsTestCase):
    def test_get_seeds_and_renders_all_six_categories(self):
        self.make_settings()

        response = self.client.get(reverse("settings_edit"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(GlobalSortCategory.objects.count(), 6)
        self.assertContains(response, "Sorting control")
        self.assertContains(response, "Sensitive files")

    def test_enabling_a_category_and_setting_its_mode_saves(self):
        self.make_settings()
        GlobalSortCategory.ensure_defaults()

        self.client.post(reverse("settings_edit"), {
            "downloads_path": "C:/Downloads",
            "secondary_downloads_path": "",
            "library_inbox_path": "C:/Library",
            "installer_stale_days": "30",
            "installer_delete_days": "60",
            "global_default_mode": "leave",
            "category_media_enabled": "on",
            "category_media_destination": "C:/Personal/Media",
            "category_media_mode": "auto_high_confidence",
        })

        media = GlobalSortCategory.objects.get(key="media")
        self.assertTrue(media.enabled)
        self.assertEqual(media.destination_path, "C:/Personal/Media")
        self.assertEqual(media.mode, "auto_high_confidence")

    def test_sensitive_category_cannot_be_disabled_via_the_form(self):
        # The sensitive category is deliberately excluded from the editable
        # fields the view processes -- there is no "category_sensitive_enabled"
        # field to submit, so it can never be turned off from this form.
        self.make_settings()
        GlobalSortCategory.ensure_defaults()

        self.client.post(reverse("settings_edit"), {
            "downloads_path": "C:/Downloads",
            "secondary_downloads_path": "",
            "library_inbox_path": "C:/Library",
            "installer_stale_days": "30",
            "installer_delete_days": "60",
        })

        sensitive = GlobalSortCategory.objects.get(key="sensitive")
        self.assertTrue(sensitive.enabled)
        self.assertEqual(sensitive.mode, "review")

    def test_category_test_api_identifies_a_matching_file(self):
        response = self.client.post(reverse("category_test"), {
            "category": "media",
            "test_filename": "holiday.jpg",
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["matched"])

    def test_category_test_api_flags_sensitive_files_regardless_of_category(self):
        response = self.client.post(reverse("category_test"), {
            "category": "media",
            "test_filename": "wifi password.jpg",
        })

        data = response.json()
        self.assertFalse(data["matched"])
        self.assertIn("sensitive", data["action"])
