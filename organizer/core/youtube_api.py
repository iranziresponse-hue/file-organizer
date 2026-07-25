"""Real YouTube search results for Resource Radar, via the YouTube Data
API v3. Off by default -- without a key, resources.py falls back to a
plain search-results link instead of specific videos (see build_candidates
in resources.py), same "nothing calls out until configured" shape as
ai_classify.py's Smart Orch integration.

Never allowed to throw or hang whatever called it: any failure (no
network, bad/quota-exceeded key, malformed response) returns an empty
list, and the caller falls back to a search link, same as if this module
weren't configured at all.
"""

import json
import logging
from typing import Callable

import requests

from . import paths

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_DEFAULT_TIMEOUT = 15

logger = logging.getLogger("organizer.youtube")


def load_youtube_config() -> dict | None:
    if not paths.YOUTUBE_CONFIG_PATH.exists():
        return None
    try:
        return json.loads(paths.YOUTUBE_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def search_videos(query: str, max_results: int = 3, log: Callable | None = None) -> list[dict]:
    """Returns up to max_results real videos as
    [{"title", "channel", "video_id", "url", "thumbnail_url"}], newest
    relevant match first per YouTube's own ranking. Empty list if
    YouTube isn't configured or the request fails in any way."""
    config = load_youtube_config()
    if not config or not config.get("enabled") or not config.get("api_key"):
        return []

    try:
        resp = requests.get(
            SEARCH_URL,
            params={
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": max_results,
                "safeSearch": "strict",
                "relevanceLanguage": "en",
                "key": config["api_key"],
            },
            timeout=_DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as exc:
        logger.warning("YouTube search failed for %r: %s", query, exc)
        if log:
            log(f"YouTube search failed: {exc}")
        return []
    except ValueError as exc:
        logger.warning("YouTube search returned bad JSON for %r: %s", query, exc)
        return []

    videos = []
    for item in payload.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        if not video_id or not snippet.get("title"):
            continue
        thumbnails = snippet.get("thumbnails", {})
        thumbnail = (thumbnails.get("medium") or thumbnails.get("default") or {}).get("url", "")
        videos.append({
            "title": snippet["title"],
            "channel": snippet.get("channelTitle", ""),
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail_url": thumbnail,
        })
    return videos
