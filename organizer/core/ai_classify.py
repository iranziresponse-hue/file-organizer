"""Smart fallback for files the heuristics genuinely can't place. Ported from
Invoke-AIClassify in OrganizeDownloads.ps1 -- currently configured for Groq's
OpenAI-compatible endpoint. Works on the FILENAME only (semantic reasoning
over the name against the course list), not file content.

Never allowed to throw or hang the watcher: any failure (no network, bad key,
timeout, malformed response) returns None and the caller falls back to
_Unsorted, same as if this module didn't exist.
"""

import json
from typing import Callable, Any, Optional

import requests

from . import paths

PROMPT_TEMPLATE = """You are a file-naming classifier for a university student's course folders.
Given a downloaded filename, decide which ONE course code it most likely belongs to,
based on the course topic keywords below. If genuinely no course fits, reply exactly: NONE

Filename: {name}

Courses (code: topic keywords):
{course_list}

Reply with ONLY the course code (e.g. CSC2100) or NONE. No other text."""


def load_ai_config() -> dict | None:
    if not paths.AI_CONFIG_PATH.exists():
        return None
    try:
        return json.loads(paths.AI_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def classify(name: str, curriculum: list, log: Callable | None = None) -> dict | None:
    ai = load_ai_config()
    if not ai or not ai.get("enabled") or not ai.get("api_key"):
        return None
    if not curriculum:
        return None

    course_list = "\n".join(
        f"{course['code']}: {', '.join(course.get('keywords', []))}" for course in curriculum
    )
    prompt = PROMPT_TEMPLATE.format(name=name, course_list=course_list)

    body = {
        "model": ai["model"],
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 10,
        "temperature": 0,
    }

    try:
        response = requests.post(
            f"{ai['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {ai['api_key']}"},
            json=body,
            timeout=8,
        )
        response.raise_for_status()
        answer = response.json()["choices"][0]["message"]["content"].strip()
        if not answer or answer == "NONE":
            return None
        return next((c for c in curriculum if c["code"] == answer), None)
    except Exception as exc:  # network/timeout/bad-key/malformed-response -- never propagate
        if log:
            log(f"AI classify skipped for '{name}': {exc}")
        return None
