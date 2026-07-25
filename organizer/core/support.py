"""Support popup: saves every message locally first, then best-effort
emails it to the admin. A message is never lost just because SMTP isn't
configured yet or a send fails -- it's always in the database either way.
"""

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone


def submit_support_message(name: str, email: str, subject: str, message: str, page_url: str = "") -> tuple:
    """Save the message, then try to email it. Returns (support_message, error).
    error is None on a clean send; otherwise a short, honest reason the
    message was saved but not emailed -- the message itself is never lost.
    """
    from organizer.models import SupportMessage

    record = SupportMessage.objects.create(
        sender_name=name.strip(),
        sender_email=email.strip(),
        subject=subject.strip(),
        message=message.strip(),
        page_url=page_url.strip(),
    )

    if not settings.SUPPORT_EMAIL_CONFIGURED:
        error = "Message saved, but email isn't configured yet (see support_email.example.json)."
        record.email_error = error
        record.save(update_fields=["email_error"])
        return record, error

    email_subject = f"Orch support: {subject.strip() or 'no subject'}"
    body = (
        f"From: {name.strip() or '(no name given)'}\n"
        f"Reply-to: {email.strip() or '(no email given)'}\n"
        f"Page: {page_url.strip() or '(unknown)'}\n\n"
        f"{message.strip()}"
    )

    try:
        send_mail(
            email_subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [settings.SUPPORT_INBOX_ADDRESS],
            fail_silently=False,
        )
    except Exception as exc:
        error = f"Message saved, but the email failed to send: {exc}"
        record.email_error = error
        record.save(update_fields=["email_error"])
        return record, error

    record.emailed_at = timezone.now()
    record.save(update_fields=["emailed_at"])
    return record, None
