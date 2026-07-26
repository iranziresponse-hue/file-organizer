"""Support popup: saves every message locally first, then best-effort
emails it to the admin. A message is never lost just because SMTP isn't
configured yet or a send fails -- it's always in the database either way.
"""

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone


def build_app_state_snapshot(profile) -> dict:
    """A small diagnostic snapshot -- app version, active profile, watcher
    status, and the last few log lines -- attached to a support message
    only when the sender explicitly ticks "Include app diagnostics" in the
    popup. Never collected or sent silently."""
    from organizer import __version__
    from . import diagnostics

    watcher = diagnostics.get_watcher_status()
    return {
        "app_version": __version__,
        "profile": profile.name if profile else None,
        "watcher_running": watcher.get("running"),
        "recent_watcher_errors": watcher.get("recent_errors", [])[-5:],
        "recent_error_log": diagnostics.get_error_log_tail(20),
    }


def _format_app_state(app_state: dict) -> str:
    lines = [
        f"App version: {app_state.get('app_version', 'unknown')}",
        f"Active profile: {app_state.get('profile') or '(none)'}",
        f"Watcher running: {app_state.get('watcher_running')}",
    ]
    watcher_errors = app_state.get("recent_watcher_errors") or []
    if watcher_errors:
        lines.append("Recent watcher errors:")
        lines.extend(f"  {line}" for line in watcher_errors)
    error_log = app_state.get("recent_error_log") or []
    if error_log:
        lines.append("Recent error log:")
        lines.extend(f"  {line}" for line in error_log)
    return "\n".join(lines)


def submit_support_message(
    name: str, email: str, subject: str, message: str, page_url: str = "", app_state: dict | None = None,
) -> tuple:
    """Save the message, then try to email it. Returns (support_message, error).
    error is None on a clean send; otherwise a short, honest reason the
    message was saved but not emailed -- the message itself is never lost.
    app_state, if given, is the user-opted-in diagnostics snapshot from
    build_app_state_snapshot -- stored alongside the message and folded
    into the emailed body, never collected unless the sender chose to.
    """
    from organizer.models import SupportMessage

    record = SupportMessage.objects.create(
        sender_name=name.strip(),
        sender_email=email.strip(),
        subject=subject.strip(),
        message=message.strip(),
        page_url=page_url.strip(),
        app_state=app_state or {},
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
    if app_state:
        body += "\n\n--- App diagnostics (sender opted in) ---\n" + _format_app_state(app_state)

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
