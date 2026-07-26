from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from organizer.core import support
from organizer.models import SupportMessage


class SubmitSupportMessageTests(TestCase):
    def test_saves_the_message_even_when_email_is_not_configured(self):
        # Default test settings have no support_email.json, so
        # SUPPORT_EMAIL_CONFIGURED is False -- the message must still be
        # saved, never silently dropped just because email isn't set up.
        record, error = support.submit_support_message("Jordan", "jordan@example.com", "Bug report", "Hello there")

        self.assertIsNotNone(error)
        self.assertEqual(SupportMessage.objects.count(), 1)
        saved = SupportMessage.objects.get()
        self.assertEqual(saved.sender_name, "Jordan")
        self.assertEqual(saved.subject, "Bug report")
        self.assertEqual(saved.message, "Hello there")
        self.assertIsNone(saved.emailed_at)
        self.assertTrue(saved.email_error)

    @override_settings(
        SUPPORT_EMAIL_CONFIGURED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="orch@example.com",
        SUPPORT_INBOX_ADDRESS="iranziresponse@gmail.com",
    )
    def test_emails_the_admin_inbox_when_configured(self):
        record, error = support.submit_support_message("Jordan", "jordan@example.com", "Bug report", "Hello there")

        self.assertIsNone(error)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["iranziresponse@gmail.com"])
        self.assertIn("Hello there", mail.outbox[0].body)
        record.refresh_from_db()
        self.assertIsNotNone(record.emailed_at)
        self.assertEqual(record.email_error, "")

    def test_app_state_is_empty_by_default(self):
        record, _ = support.submit_support_message("Jordan", "jordan@example.com", "Bug report", "Hello there")
        self.assertEqual(record.app_state, {})

    @override_settings(
        SUPPORT_EMAIL_CONFIGURED=True,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="orch@example.com",
        SUPPORT_INBOX_ADDRESS="iranziresponse@gmail.com",
    )
    def test_opted_in_app_state_is_saved_and_emailed(self):
        snapshot = {"app_version": "1.2.0", "profile": "School", "watcher_running": True, "recent_watcher_errors": [], "recent_error_log": ["[2026-01-01] something failed"]}
        record, error = support.submit_support_message(
            "Jordan", "jordan@example.com", "Bug report", "Hello there", app_state=snapshot,
        )

        self.assertIsNone(error)
        record.refresh_from_db()
        self.assertEqual(record.app_state, snapshot)
        self.assertIn("App diagnostics", mail.outbox[0].body)
        self.assertIn("1.2.0", mail.outbox[0].body)
        self.assertIn("something failed", mail.outbox[0].body)


class RedactDiagnosticTextTests(TestCase):
    def test_redacts_the_windows_username_in_a_path(self):
        text = support.redact_diagnostic_text(r"Error sorting C:\Users\jordan\Downloads\notes.pdf")
        self.assertNotIn("jordan", text)
        self.assertIn(r"C:\Users\<user>\Downloads\notes.pdf", text)

    def test_redacts_email_addresses(self):
        text = support.redact_diagnostic_text("Sync failed for jordan@example.com")
        self.assertNotIn("jordan@example.com", text)
        self.assertIn("<email>", text)

    def test_redacts_token_like_values(self):
        text = support.redact_diagnostic_text("MUELE token=abcdef123456 rejected")
        self.assertNotIn("abcdef123456", text)
        self.assertIn("<redacted>", text)

    def test_leaves_plain_text_untouched(self):
        text = support.redact_diagnostic_text("Watcher restarted after a permission error")
        self.assertEqual(text, "Watcher restarted after a permission error")

    def test_empty_string_is_returned_as_is(self):
        self.assertEqual(support.redact_diagnostic_text(""), "")


class BuildAppStateSnapshotTests(TestCase):
    def test_redacts_log_lines_by_default(self):
        from unittest import mock

        with mock.patch(
            "organizer.core.diagnostics.get_watcher_status",
            return_value={"running": True, "recent_errors": [r"Failed: C:\Users\jordan\Downloads\x.pdf"]},
        ), mock.patch(
            "organizer.core.diagnostics.get_error_log_tail",
            return_value=["Contact jordan@example.com for help"],
        ):
            snapshot = support.build_app_state_snapshot(None)

        self.assertNotIn("jordan", snapshot["recent_watcher_errors"][0])
        self.assertNotIn("jordan@example.com", snapshot["recent_error_log"][0])

    def test_include_raw_details_skips_redaction(self):
        from unittest import mock

        with mock.patch(
            "organizer.core.diagnostics.get_watcher_status",
            return_value={"running": True, "recent_errors": [r"Failed: C:\Users\jordan\Downloads\x.pdf"]},
        ), mock.patch(
            "organizer.core.diagnostics.get_error_log_tail",
            return_value=["Contact jordan@example.com for help"],
        ):
            snapshot = support.build_app_state_snapshot(None, include_raw_details=True)

        self.assertIn("jordan", snapshot["recent_watcher_errors"][0])
        self.assertIn("jordan@example.com", snapshot["recent_error_log"][0])


class SupportMessageViewTests(TestCase):
    def test_saves_a_valid_message_and_returns_ok(self):
        response = self.client.post(reverse("support_message"), {
            "name": "Jordan",
            "email": "jordan@example.com",
            "subject": "Bug report",
            "message": "Something is broken",
            "page_url": "http://127.0.0.1:8765/study/",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(SupportMessage.objects.count(), 1)
        self.assertEqual(SupportMessage.objects.get().subject, "Bug report")

    def test_rejects_an_empty_subject(self):
        response = self.client.post(reverse("support_message"), {"name": "Jordan", "message": "Hi"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.assertEqual(SupportMessage.objects.count(), 0)

    def test_rejects_an_empty_message(self):
        response = self.client.post(reverse("support_message"), {"name": "Jordan", "subject": "Bug report"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.assertEqual(SupportMessage.objects.count(), 0)

    def test_get_is_not_allowed(self):
        response = self.client.get(reverse("support_message"))
        self.assertEqual(response.status_code, 405)

    def test_diagnostics_are_not_collected_unless_opted_in(self):
        response = self.client.post(reverse("support_message"), {
            "subject": "Bug report", "message": "Something is broken",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SupportMessage.objects.get().app_state, {})

    def test_diagnostics_are_collected_when_opted_in(self):
        response = self.client.post(reverse("support_message"), {
            "subject": "Bug report", "message": "Something is broken", "include_diagnostics": "1",
        })
        self.assertEqual(response.status_code, 200)
        record = SupportMessage.objects.get()
        self.assertIn("app_version", record.app_state)
        self.assertIn("recent_error_log", record.app_state)

    def test_raw_details_are_ignored_unless_diagnostics_is_also_opted_in(self):
        response = self.client.post(reverse("support_message"), {
            "subject": "Bug report", "message": "Something is broken", "include_raw_details": "1",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SupportMessage.objects.get().app_state, {})

    def test_raw_details_flag_reaches_the_snapshot_builder(self):
        from unittest import mock

        with mock.patch("organizer.core.support.build_app_state_snapshot") as mocked_build:
            mocked_build.return_value = {}
            self.client.post(reverse("support_message"), {
                "subject": "Bug report", "message": "Something is broken",
                "include_diagnostics": "1", "include_raw_details": "1",
            })

        mocked_build.assert_called_once_with(None, include_raw_details=True)
