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
        record, error = support.submit_support_message("Jordan", "jordan@example.com", "Hello there")

        self.assertIsNotNone(error)
        self.assertEqual(SupportMessage.objects.count(), 1)
        saved = SupportMessage.objects.get()
        self.assertEqual(saved.sender_name, "Jordan")
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
        record, error = support.submit_support_message("Jordan", "jordan@example.com", "Hello there")

        self.assertIsNone(error)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["iranziresponse@gmail.com"])
        self.assertIn("Hello there", mail.outbox[0].body)
        record.refresh_from_db()
        self.assertIsNotNone(record.emailed_at)
        self.assertEqual(record.email_error, "")


class SupportMessageViewTests(TestCase):
    def test_saves_a_valid_message_and_returns_ok(self):
        response = self.client.post(reverse("support_message"), {
            "name": "Jordan",
            "email": "jordan@example.com",
            "message": "Something is broken",
            "page_url": "http://127.0.0.1:8765/study/",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(SupportMessage.objects.count(), 1)

    def test_rejects_an_empty_message(self):
        response = self.client.post(reverse("support_message"), {"name": "Jordan"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.assertEqual(SupportMessage.objects.count(), 0)

    def test_get_is_not_allowed(self):
        response = self.client.get(reverse("support_message"))
        self.assertEqual(response.status_code, 405)
