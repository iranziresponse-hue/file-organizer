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
