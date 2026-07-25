"""Template filters shared across the dashboard so a course code never
appears on its own when Orch actually knows the course's real name."""

import re

from django import template

from organizer.core import makerere_curricula

register = template.Library()

_YOUTUBE_WATCH_ID_RE = re.compile(r"[?&]v=([A-Za-z0-9_-]{6,})")


@register.filter
def youtube_video_id(url):
    """"https://www.youtube.com/watch?v=abc123" -> "abc123". Returns "" for
    anything else, including the plain /results?search_query= fallback link
    resources.py hands back when no specific video was found -- that one
    has no single video to embed, so it stays a plain "Open" link."""
    match = _YOUTUBE_WATCH_ID_RE.search(url or "")
    return match.group(1) if match else ""


@register.filter
def course_label(code):
    """"CSC2100" -> "CSC2100 - Data Structures and Algorithms". Falls back
    to the bare code when it's not a course Orch has researched (a manually
    typed subject, or a programme not yet covered in makerere_curricula)."""
    if not code:
        return code
    name = makerere_curricula.name_for_code(code)
    return f"{code} - {name}" if name else code


@register.filter
def get_item(mapping, key):
    """Django templates can't do dict[var] with a variable key -- {% for
    status, label in status_labels %}{{ grouped|get_item:status }} is the
    template-language equivalent."""
    if mapping is None:
        return None
    return mapping.get(key)


@register.filter
def checklist_text(checklist):
    """The inverse of views._parse_checklist_text -- renders an
    AssignmentItem.checklist JSON list back into the same one-line-per-item,
    "[x] " -for-done plain text its edit form's textarea round-trips
    through."""
    lines = []
    for item in checklist or []:
        prefix = "[x] " if item.get("done") else ""
        lines.append(f"{prefix}{item.get('text', '')}")
    return "\n".join(lines)
