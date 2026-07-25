"""Post Composer -- generates ContentDraft raw text locally from a
Project or a CareerDigest, and offers optional AI-polished variants
(polished / professional / short / website). "Orch drafts. Orch
beautifies. User approves. Then user clicks Post." -- this module is the
"drafts" and "beautifies" halves; approval and posting are handled by the
view/model layer, never here.

No AI is required for a usable draft: `generate_draft_from_project`/
`generate_draft_from_digest`/`suggest_hashtags` are pure local templating.
`polish_text` is the only AI-touching function, and it returns None (never
a fabricated substitute) when Smart Orch isn't configured or the call
fails.
"""

from typing import Callable, Optional

_PROJECT_TEMPLATES = {
    "project_update": "Progress update on {title}: {problem}\n\nTech stack: {stack}\nStatus: {status}\n{latest_update}",
    "lesson_learned": "A lesson from building {title}: {lessons}",
    "tutorial": "How I approached {title}: {problem}\n\nBuilt with {stack}.",
    "problem_solution": "The problem: {problem}\n\nHow {title} solves it, built with {stack}.",
    "portfolio_launch": "Just shipped {title}. {portfolio_description}\n\nBuilt with {stack}.{github}",
}

_STYLE_PROMPTS = {
    "polished": (
        "Rewrite the following as a polished, engaging social media post (LinkedIn style), "
        "3-5 sentences, first person. Do not invent any fact, number, or achievement not "
        "already present in the text.\n\n{text}"
    ),
    "professional": (
        "Rewrite the following in a formal, professional tone suitable for a corporate "
        "LinkedIn audience, first person. Do not invent any fact, number, or achievement not "
        "already present in the text.\n\n{text}"
    ),
    "short": (
        "Condense the following into a punchy 1-2 sentence version suitable for a short-form "
        "post. Do not invent any fact, number, or achievement not already present in the "
        "text.\n\n{text}"
    ),
    "website": (
        "Rewrite the following as a short blog-style paragraph for a personal website, first "
        "person. Do not invent any fact, number, or achievement not already present in the "
        "text.\n\n{text}"
    ),
}


def suggest_hashtags(text: str, tech_stack: Optional[list] = None, subject_codes: Optional[list] = None) -> list:
    """Local keyword heuristic -- tech-stack entries and subject codes,
    plus a fixed Makerere tag. No AI needed."""
    tags = []
    for item in tech_stack or []:
        tag = "".join(ch for ch in str(item) if ch.isalnum())
        if tag:
            tags.append(tag)
    for code in subject_codes or []:
        tag = "".join(ch for ch in str(code) if ch.isalnum())
        if tag:
            tags.append(tag)
    tags.append("Makerere")

    seen = set()
    result = []
    for tag in tags:
        key = tag.lower()
        if key not in seen:
            seen.add(key)
            result.append(tag)
    return result[:8]


def generate_draft_from_project(project, post_type: str = "project_update") -> dict:
    stack = ", ".join(str(item) for item in project.tech_stack) if project.tech_stack else "no tech stack recorded yet"
    latest_update = project.updates.first()
    latest_update_text = latest_update.content.strip() if latest_update else ""
    github = f"\n\n{project.github_url}" if project.github_url else ""

    context = {
        "title": project.title,
        "problem": project.problem_statement.strip() or "no problem statement recorded yet",
        "stack": stack,
        "status": project.get_status_display(),
        "latest_update": latest_update_text,
        "lessons": project.lessons_learned.strip() or "no lessons recorded yet",
        "portfolio_description": project.portfolio_description.strip() or project.problem_statement.strip(),
        "github": github,
    }

    template = _PROJECT_TEMPLATES.get(post_type, _PROJECT_TEMPLATES["project_update"])
    raw_text = template.format(**context).strip()
    hashtags = suggest_hashtags(raw_text, tech_stack=project.tech_stack)
    return {"raw_text": raw_text, "hashtags": hashtags}


def generate_draft_from_digest(digest, post_type: str = "course_reflection") -> dict:
    raw_text = digest.content.strip()
    if post_type == "course_reflection":
        raw_text = f"This week in my studies:\n\n{raw_text}"
    hashtags = suggest_hashtags(raw_text)
    return {"raw_text": raw_text, "hashtags": hashtags}


def polish_text(raw_text: str, style: str, log: Optional[Callable] = None) -> Optional[str]:
    """style in {"polished", "professional", "short", "website"}. Returns
    None when the style is unrecognized, Smart Orch isn't configured, or
    the call fails."""
    from . import ai_classify

    prompt_template = _STYLE_PROMPTS.get(style)
    if not prompt_template:
        return None

    ai = ai_classify.load_ai_config()
    if not ai or not ai.get("enabled") or not ai.get("api_key"):
        return None

    body = {
        "model": ai["model"],
        "messages": [{"role": "user", "content": prompt_template.format(text=raw_text[:3000])}],
        "max_tokens": 300,
        "temperature": 0.5,
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
            log(f"Post polish ({style}) skipped: {exc}")
        return None
