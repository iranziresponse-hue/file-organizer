"""GitHub integration: real repo recommendations for Resource Radar (no
setup required -- GitHub's Search API allows anonymous use), and a
publishing channel that commits approved Post Composer drafts into a
student's own portfolio repo.

Connecting is via a Personal Access Token, not an OAuth "Sign in with
GitHub" button: Orch is a local desktop app with no public HTTPS callback
URL for GitHub's OAuth redirect step to land on. A PAT is GitHub's own
recommended mechanism for exactly this class of tool (it's how the GitHub
CLI itself authenticates non-interactively) -- an official, scoped,
revocable API credential, not a password.

The token lives only in the OS keyring, never in the database, following
the exact same store/load/clear contract as organizer.core.muele_api and
organizer.core.publishing: never throws, a missing keyring package or
backend is treated as "not configured" rather than a crash.
"""

import base64
import logging
from datetime import datetime, timezone
from typing import Callable, Optional

import requests

logger = logging.getLogger("organizer.github")

_KEYRING_SERVICE = "iranzi-file-organizer-github"
_API_BASE = "https://api.github.com"
_DEFAULT_TIMEOUT = 15
_USER_AGENT = "iranzi-file-organizer-orch"


def _keyring_key(channel) -> str:
    return f"channel_{channel.pk}_token"


def store_channel_token(channel, token: str) -> tuple[bool, Optional[str]]:
    """Stores a GitHub channel's Personal Access Token in the OS keyring.
    Returns (True, None) on success or (False, error_message) if the
    keyring package is missing or no OS credential backend is available."""
    try:
        import keyring

        keyring.set_password(_KEYRING_SERVICE, _keyring_key(channel), token)
        return True, None
    except ImportError:
        logger.warning("keyring package not installed; cannot store GitHub token.")
        return False, "The keyring package is not installed, so the token can't be saved securely."
    except Exception as exc:
        logger.warning("Could not store GitHub token in the OS keyring: %s", exc)
        return False, f"Could not save the token to your OS credential store: {exc}"


def load_channel_token(channel) -> Optional[str]:
    """Returns None if not set, and also if the keyring package is
    missing or unreachable -- an unreachable key store is treated the
    same as no token, rather than crashing whatever page asked."""
    try:
        import keyring

        return keyring.get_password(_KEYRING_SERVICE, _keyring_key(channel))
    except ImportError:
        logger.warning("keyring package not installed; treating GitHub channel as unconfigured.")
        return None
    except Exception as exc:
        logger.warning("Could not read GitHub token from the OS keyring: %s", exc)
        return None


def clear_channel_token(channel) -> None:
    """Removes a GitHub channel's token from the OS keyring. Never throws."""
    try:
        import keyring

        keyring.delete_password(_KEYRING_SERVICE, _keyring_key(channel))
    except ImportError:
        logger.warning("keyring package not installed; nothing to clear.")
    except Exception as exc:
        logger.warning("Could not clear GitHub token from the OS keyring: %s", exc)


def get_any_token(profile) -> Optional[str]:
    """The first connected GitHub channel's token for this profile, or
    None if no GitHub channel is connected. Used to raise Resource
    Radar's anonymous search rate limit when a connection exists."""
    from organizer.models import IntegrationConnection

    channel = IntegrationConnection.objects.filter(profile=profile, provider="github").first()
    if not channel:
        return None
    return load_channel_token(channel)


def _headers(token: Optional[str]) -> dict:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": _USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def search_repos(query: str, token: Optional[str] = None, max_results: int = 3, log: Optional[Callable] = None) -> list[dict]:
    """Returns up to max_results real repos as
    [{"full_name", "description", "url", "stars", "language"}], ranked by
    stars. Empty list if the request fails in any way (rate-limited, no
    network, bad JSON) -- GitHub's anonymous Search API is allowed but
    tightly rate-limited, so a 403 here is expected and not an error."""
    try:
        resp = requests.get(
            f"{_API_BASE}/search/repositories",
            params={"q": f"{query} fork:false", "sort": "stars", "order": "desc", "per_page": max_results},
            headers=_headers(token),
            timeout=_DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as exc:
        logger.warning("GitHub repo search failed for %r: %s", query, exc)
        if log:
            log(f"GitHub repo search failed: {exc}")
        return []
    except ValueError as exc:
        logger.warning("GitHub repo search returned bad JSON for %r: %s", query, exc)
        return []

    repos = []
    for item in payload.get("items", [])[:max_results]:
        full_name = item.get("full_name")
        if not full_name:
            continue
        repos.append({
            "full_name": full_name,
            "description": item.get("description") or "",
            "url": item.get("html_url", f"https://github.com/{full_name}"),
            "stars": item.get("stargazers_count", 0),
            "language": item.get("language") or "",
        })
    return repos


def get_repo_info(owner: str, repo: str, token: Optional[str] = None, log: Optional[Callable] = None) -> Optional[dict]:
    """Returns {"stars", "forks", "updated_at"} for a public (or, with a
    token, private) repo, or None if it can't be reached -- never raises."""
    try:
        resp = requests.get(
            f"{_API_BASE}/repos/{owner}/{repo}",
            headers=_headers(token),
            timeout=_DEFAULT_TIMEOUT,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as exc:
        logger.warning("GitHub repo lookup failed for %s/%s: %s", owner, repo, exc)
        if log:
            log(f"GitHub repo lookup failed: {exc}")
        return None
    except ValueError as exc:
        logger.warning("GitHub repo lookup returned bad JSON for %s/%s: %s", owner, repo, exc)
        return None

    return {
        "stars": payload.get("stargazers_count", 0),
        "forks": payload.get("forks_count", 0),
        "updated_at": payload.get("pushed_at", ""),
    }


def parse_owner_repo(github_url: str) -> Optional[tuple[str, str]]:
    """Extracts (owner, repo) from a github.com URL, or None if it
    doesn't look like one."""
    if "github.com" not in (github_url or ""):
        return None
    parts = [p for p in github_url.strip().rstrip("/").split("/") if p]
    if len(parts) < 2:
        return None
    owner, repo = parts[-2], parts[-1]
    if not owner or not repo:
        return None
    return owner, repo.removesuffix(".git")


def _get_file_sha(owner: str, repo: str, path: str, token: Optional[str]) -> Optional[str]:
    try:
        resp = requests.get(
            f"{_API_BASE}/repos/{owner}/{repo}/contents/{path}",
            headers=_headers(token),
            timeout=_DEFAULT_TIMEOUT,
        )
        if resp.status_code != 200:
            return None
        return resp.json().get("sha")
    except (requests.RequestException, ValueError):
        return None


def _slugify(text: str) -> str:
    slug = "".join(ch if ch.isalnum() else "-" for ch in text.lower())
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:60] or "post"


def publish_to_github(channel, draft, variant: str = "raw", log: Optional[Callable] = None):
    """Commits `draft` as a markdown file into the channel's configured
    portfolio repo. Raises ValueError if `draft` isn't approved yet --
    the same trust-flow gate as publish_to_custom_website. Returns the
    created PublishedPost either way (sent or failed); a raised
    ValueError means no PublishedPost was created since nothing was
    attempted."""
    from organizer.models import PublishedPost
    from . import publishing

    if draft.status != "approved":
        raise ValueError("This draft hasn't been approved yet -- approve it before publishing.")

    config = channel.config or {}
    owner = config.get("owner", "")
    repo = config.get("repo", "")
    posts_path = (config.get("posts_path") or "posts").strip("/")

    if not owner or not repo:
        post = PublishedPost.objects.create(
            content_draft=draft, channel=channel, variant=variant, status="failed",
            payload_sent={}, error_message="This GitHub channel isn't configured with an owner/repo yet.",
        )
        return post

    token = load_channel_token(channel)
    if not token:
        # Publishing to GitHub always needs a token (confirmed: a real
        # write attempt with no Authorization header always 401s) -- if
        # it's missing (never finished storing, cleared, lost), that's
        # knowable up front. Fail cleanly instead of making a doomed
        # network call, and correct the channel's status since it can no
        # longer be "connected"/"configured".
        if channel.status != "needs_key":
            channel.status = "needs_key"
            channel.save(update_fields=["status", "updated_at"])
        post = PublishedPost.objects.create(
            content_draft=draft, channel=channel, variant=variant, status="failed",
            payload_sent={}, error_message="This channel's GitHub token is missing or was cleared. Reconnect it before publishing.",
        )
        return post

    title = draft.topic.strip() if draft.topic.strip() else draft.get_post_type_display()
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    file_path = f"{posts_path}/{date_str}-{_slugify(title)}.md"
    body = publishing.export_markdown(draft, variant=variant)
    payload_sent = {"path": file_path, "owner": owner, "repo": repo}

    sha = _get_file_sha(owner, repo, file_path, token)

    request_payload = {
        "message": f"Add {title}",
        "content": base64.b64encode(body.encode("utf-8")).decode("ascii"),
    }
    if sha:
        request_payload["sha"] = sha

    try:
        response = requests.put(
            f"{_API_BASE}/repos/{owner}/{repo}/contents/{file_path}",
            json=request_payload,
            headers=_headers(token),
            timeout=_DEFAULT_TIMEOUT,
        )
        response_body = response.text[:2000]

        if response.status_code in (200, 201):
            data = response.json()
            external_url = (data.get("content") or {}).get("html_url", "")
            post = PublishedPost.objects.create(
                content_draft=draft, channel=channel, variant=variant, status="sent",
                payload_sent=payload_sent, response_status_code=response.status_code,
                response_body=response_body, external_url=external_url,
            )
            draft.status = "posted"
            draft.save(update_fields=["status", "updated_at"])
            if channel.status != "connected":
                channel.status = "connected"
                channel.save(update_fields=["status", "updated_at"])
            if log:
                log(f"Published draft #{draft.pk} to {channel.display_name} ({file_path})")
            return post

        post = PublishedPost.objects.create(
            content_draft=draft, channel=channel, variant=variant, status="failed",
            payload_sent=payload_sent, response_status_code=response.status_code,
            response_body=response_body, error_message=f"HTTP {response.status_code}",
        )
        if log:
            log(f"Publish to GitHub failed for draft #{draft.pk}: HTTP {response.status_code}")
        return post

    except Exception as exc:
        post = PublishedPost.objects.create(
            content_draft=draft, channel=channel, variant=variant, status="failed",
            payload_sent=payload_sent, error_message=str(exc)[:500],
        )
        if log:
            log(f"Publish to GitHub failed for draft #{draft.pk}: {exc}")
        return post
