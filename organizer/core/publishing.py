"""Publishing Connectors -- the first real (non-manual) posting path for
Post Composer drafts. "Orch drafts. Orch beautifies. User approves. Then
user clicks Post." -- `publish_to_custom_website` IS that final click for
a Custom Website channel; it refuses to run on anything the user hasn't
explicitly approved first.

Channels are IntegrationConnection rows (provider="custom_website"), the
same "external connection, secrets kept out of the database" model
MUELE/Timetable/Drive already use -- not a second parallel model. The API
key itself lives in the OS keyring, never in the database, following the
exact same store/load/clear contract as organizer.core.muele_api's token
functions: never throws, a missing keyring package or backend is treated
as "not configured" rather than a crash.
"""

import logging
from html import escape
from typing import Callable, Optional

logger = logging.getLogger("organizer.publishing")

_KEYRING_SERVICE = "iranzi-file-organizer-publishing"

MAX_RESPONSE_BODY_CHARS = 2000


def _keyring_key(channel) -> str:
    return f"channel_{channel.pk}_api_key"


def store_channel_api_key(channel, key: str) -> tuple[bool, Optional[str]]:
    """Stores a channel's API key in the OS keyring. Returns (True, None)
    on success or (False, error_message) if the keyring package is
    missing or no OS credential backend is available."""
    try:
        import keyring

        keyring.set_password(_KEYRING_SERVICE, _keyring_key(channel), key)
        return True, None
    except ImportError:
        logger.warning("keyring package not installed; cannot store publishing channel API key.")
        return False, "The keyring package is not installed, so the key can't be saved securely."
    except Exception as exc:
        logger.warning("Could not store publishing channel API key in the OS keyring: %s", exc)
        return False, f"Could not save the key to your OS credential store: {exc}"


def load_channel_api_key(channel) -> Optional[str]:
    """Returns None if not set, and also if the keyring package is
    missing or unreachable -- an unreachable key store is treated the
    same as no key, rather than crashing whatever page asked."""
    try:
        import keyring

        return keyring.get_password(_KEYRING_SERVICE, _keyring_key(channel))
    except ImportError:
        logger.warning("keyring package not installed; treating publishing channel as unconfigured.")
        return None
    except Exception as exc:
        logger.warning("Could not read publishing channel API key from the OS keyring: %s", exc)
        return None


def clear_channel_api_key(channel) -> None:
    """Removes a channel's API key from the OS keyring. Never throws."""
    try:
        import keyring

        keyring.delete_password(_KEYRING_SERVICE, _keyring_key(channel))
    except ImportError:
        logger.warning("keyring package not installed; nothing to clear.")
    except Exception as exc:
        logger.warning("Could not clear publishing channel API key from the OS keyring: %s", exc)


def build_payload(draft, variant: str = "raw", status: str = "draft") -> dict:
    """The generic {"title", "body", "tags", "status"} shape. `body` falls
    back to raw_text when the requested variant is blank -- never sends an
    empty body just because a polished version wasn't generated."""
    variant_field = {
        "raw": "raw_text",
        "polished": "polished_text",
        "professional": "professional_text",
        "short": "short_text",
        "website": "website_text",
    }.get(variant, "raw_text")

    body = (getattr(draft, variant_field, "") or "").strip() or draft.raw_text
    title = draft.topic.strip() if draft.topic.strip() else draft.get_post_type_display()

    return {
        "title": title,
        "body": body,
        "tags": list(draft.hashtags or []),
        "status": status,
    }


def publish_to_custom_website(channel, draft, variant: str = "raw", log: Optional[Callable] = None):
    """Publishes `draft` to a custom_website `channel`. Raises ValueError
    if `draft` isn't approved yet -- this is the trust-flow gate, not
    optional. Returns the created PublishedPost either way (sent or
    failed); a raised ValueError means no PublishedPost was created at all
    since nothing was attempted."""
    from organizer.models import PublishedPost

    if draft.status != "approved":
        raise ValueError("This draft hasn't been approved yet -- approve it before publishing.")

    publish_mode = (channel.config or {}).get("publish_mode", "draft")
    payload = build_payload(draft, variant=variant, status=publish_mode)
    api_key = load_channel_api_key(channel)

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        import requests

        response = requests.post(channel.base_url, json=payload, headers=headers, timeout=15)
        response_body = response.text[:MAX_RESPONSE_BODY_CHARS]

        if 200 <= response.status_code < 300:
            external_url = ""
            try:
                data = response.json()
                if isinstance(data, dict):
                    external_url = data.get("url") or data.get("external_url") or ""
            except ValueError:
                pass

            post = PublishedPost.objects.create(
                content_draft=draft, channel=channel, variant=variant, status="sent",
                payload_sent=payload, response_status_code=response.status_code,
                response_body=response_body, external_url=external_url,
            )
            draft.status = "posted"
            draft.save(update_fields=["status", "updated_at"])
            if channel.status != "connected":
                channel.status = "connected"
                channel.save(update_fields=["status", "updated_at"])
            if log:
                log(f"Published draft #{draft.pk} to {channel.display_name}")
            return post

        post = PublishedPost.objects.create(
            content_draft=draft, channel=channel, variant=variant, status="failed",
            payload_sent=payload, response_status_code=response.status_code,
            response_body=response_body,
            error_message=f"HTTP {response.status_code}",
        )
        if log:
            log(f"Publish failed for draft #{draft.pk}: HTTP {response.status_code}")
        return post

    except Exception as exc:
        post = PublishedPost.objects.create(
            content_draft=draft, channel=channel, variant=variant, status="failed",
            payload_sent=payload, error_message=str(exc)[:500],
        )
        if log:
            log(f"Publish failed for draft #{draft.pk}: {exc}")
        return post


def export_markdown(draft, variant: str = "raw") -> str:
    payload = build_payload(draft, variant=variant)
    tags_line = ", ".join(payload["tags"])
    lines = [
        "---",
        f"title: {payload['title']}",
        f"tags: [{tags_line}]",
        f"status: {payload['status']}",
        "---",
        "",
        payload["body"],
    ]
    return "\n".join(lines)


def export_html(draft, variant: str = "raw") -> str:
    """A minimal, properly-escaped article wrapper. Draft text is plain
    prose, not the "# "/"## " structured convention
    organizer.core.summarize.render_html expects, so that function isn't
    reused here."""
    payload = build_payload(draft, variant=variant)
    body_html = "".join(f"<p>{escape(line)}</p>" for line in payload["body"].splitlines() if line.strip())
    tags_html = "".join(f'<span class="tag">{escape(tag)}</span>' for tag in payload["tags"])
    return (
        f"<article>\n"
        f"<h1>{escape(payload['title'])}</h1>\n"
        f"{body_html}\n"
        f'<div class="tags">{tags_html}</div>\n'
        f"</article>"
    )
