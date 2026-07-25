"""Weekly Career Digest -- a plain, locally-generated narrative of what a
student studied and built in the current calendar week, built from
LearningActivity and ProjectUpdate rows that already exist. No AI required
for the baseline; polish_narrative offers an optional AI rewrite into
flowing prose, the same optional-enhancement pattern
organizer.core.topics already uses (local signal always available, AI
only upgrades it when Smart Orch is configured).
"""

from collections import Counter
from datetime import timedelta
from typing import Callable, Optional

from django.utils import timezone

_POLISH_PROMPT = """You are helping a university student turn a factual weekly
activity log into a short, natural first-person summary suitable for a
career journal or a LinkedIn-style post. Do not invent facts, numbers, or
achievements that are not in the log below -- only rephrase what's there
into flowing prose, 2-4 sentences.

Log:
{content}

Reply with ONLY the rewritten summary, no preamble."""


def _period_bounds(now=None):
    """The current calendar week's Monday 00:00 through now -- stable
    within a week (so regenerating mid-week updates the same row) but
    rolls over to a new row once a new week starts."""
    now = now or timezone.now()
    local_now = timezone.localtime(now)
    period_start = (local_now - timedelta(days=local_now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return period_start, now


def _build_narrative(profile, start, end) -> str:
    from organizer.models import LearningActivity, ProjectUpdate

    activities = LearningActivity.objects.filter(profile=profile, happened_at__gte=start, happened_at__lte=end)
    activity_count = activities.count()
    subject_counts = Counter(a.subject_code for a in activities if a.subject_code)

    updates = list(
        ProjectUpdate.objects.filter(project__profile=profile, created_at__gte=start, created_at__lte=end)
        .select_related("project")
        .order_by("-created_at")
    )

    lines = []

    if subject_counts:
        top_subjects = [code for code, _ in subject_counts.most_common(3)]
        activity_word = "activity" if activity_count == 1 else "activities"
        lines.append(
            f"This week you logged {activity_count} study {activity_word} across "
            f"{len(subject_counts)} subject(s), focused most on {', '.join(top_subjects)}."
        )
    else:
        lines.append("No study activity was logged this week.")

    if updates:
        project_titles = sorted({u.project.title for u in updates})
        plural = "" if len(project_titles) == 1 else "s"
        lines.append(
            f"You logged {len(updates)} update(s) on {len(project_titles)} project{plural}: "
            f"{', '.join(project_titles)}."
        )
        for update in updates[:5]:
            snippet = update.content.strip().replace("\n", " ")[:200]
            lines.append(f"- {update.project.title}: {snippet}")
    else:
        lines.append("No project updates were logged this week.")

    return "\n".join(lines)


def generate_weekly_digest(profile, log: Optional[Callable] = None):
    """Creates or updates this calendar week's CareerDigest for `profile`."""
    from organizer.models import CareerDigest

    period_start, period_end = _period_bounds()
    content = _build_narrative(profile, period_start, period_end)

    digest, _ = CareerDigest.objects.update_or_create(
        profile=profile,
        period_start=period_start,
        defaults={"period_end": period_end, "content": content},
    )
    if log:
        log(f"Generated career digest for {profile.name} ({period_start:%Y-%m-%d} to {period_end:%Y-%m-%d})")
    return digest


def polish_narrative(content: str, log: Optional[Callable] = None) -> Optional[str]:
    """Optional AI rewrite of a digest's local narrative into flowing
    first-person prose. Returns None (never a fabricated substitute) when
    Smart Orch isn't configured or the call fails -- callers must fall
    back to the local narrative, not pretend this succeeded."""
    from . import ai_classify

    ai = ai_classify.load_ai_config()
    if not ai or not ai.get("enabled") or not ai.get("api_key"):
        return None

    body = {
        "model": ai["model"],
        "messages": [{"role": "user", "content": _POLISH_PROMPT.format(content=content[:3000])}],
        "max_tokens": 250,
        "temperature": 0.4,
    }
    try:
        import requests

        response = requests.post(
            f"{ai['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {ai['api_key']}"},
            json=body,
            timeout=15,
        )
        response.raise_for_status()
        answer = response.json()["choices"][0]["message"]["content"].strip()
        return answer or None
    except Exception as exc:
        if log:
            log(f"Career digest polish skipped: {exc}")
        return None
