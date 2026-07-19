"""Resource Radar recommendations for videos and books.

The engine only creates transparent discovery links from the user's own
subjects, themes, weak areas, and recent files. It does not invent rankings,
video titles, authors, or availability.
"""

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus


@dataclass(frozen=True)
class ResourceCandidate:
    subject_code: str
    theme: str
    source_type: str
    title: str
    query: str
    url: str
    reason: str
    score: int


def _clean_text(value, fallback="learning topic"):
    text = " ".join(str(value or "").replace("_", " ").split())
    return text[:140] or fallback


def _youtube_url(query):
    return f"https://www.youtube.com/results?search_query={quote_plus(query)}"


def _book_url(query):
    return f"https://openlibrary.org/search?q={quote_plus(query)}"


def _subject_topics(profile, subject_code=None):
    from organizer.models import MoveEvent, SubjectMemory, SubjectTheme

    memories = SubjectMemory.objects.filter(profile=profile)
    if subject_code:
        memories = memories.filter(code=subject_code)

    topics = []
    for memory in memories.order_by("code"):
        seen = set()

        for weak in memory.weak_areas or []:
            name = _clean_text(weak)
            key = name.lower()
            if key not in seen:
                topics.append((memory.code, name, 90, "weak area"))
                seen.add(key)

        for focus in memory.current_focus or []:
            name = _clean_text(focus)
            key = name.lower()
            if key not in seen:
                topics.append((memory.code, name, 72, "current focus"))
                seen.add(key)

        themes = SubjectTheme.objects.filter(
            profile=profile,
            subject_code=memory.code,
        ).order_by("-weight", "name")[:8]
        for theme in themes:
            name = _clean_text(theme.name)
            key = name.lower()
            if key not in seen:
                topics.append((memory.code, name, 50 + min(theme.weight, 40), "subject theme"))
                seen.add(key)

        if not seen:
            recent_files = MoveEvent.objects.filter(
                profile=profile,
                course_code=memory.code,
                success=True,
            ).order_by("-timestamp")[:3]
            for event in recent_files:
                name = _clean_text(Path(event.filename).stem, memory.code)
                key = name.lower()
                if key not in seen:
                    topics.append((memory.code, name, 40, "recent file"))
                    seen.add(key)

        if not seen:
            topics.append((memory.code, _clean_text(memory.title or memory.code), 32, "subject"))

    return topics


def build_candidates(profile, subject_code=None, limit=16):
    candidates = []
    for code, theme, score, reason_source in _subject_topics(profile, subject_code=subject_code):
        subject = _clean_text(code, "General")
        topic = _clean_text(theme)

        video_query = f"{subject} {topic} lecture tutorial"
        book_query = f"{subject} {topic} textbook study guide"

        candidates.append(
            ResourceCandidate(
                subject_code=code,
                theme=topic,
                source_type="youtube",
                title=f"Find strong video lessons for {subject}: {topic}",
                query=video_query,
                url=_youtube_url(video_query),
                reason=f"Based on {reason_source}: {topic}",
                score=score + 8,
            )
        )
        candidates.append(
            ResourceCandidate(
                subject_code=code,
                theme=topic,
                source_type="book",
                title=f"Find books and study guides for {subject}: {topic}",
                query=book_query,
                url=_book_url(book_query),
                reason=f"Based on {reason_source}: {topic}",
                score=score,
            )
        )

    candidates.sort(key=lambda item: (-item.score, item.subject_code, item.source_type, item.query))
    return candidates[:limit]


def sync_recommendations(profile, subject_code=None, limit=16):
    from organizer.models import ResourceRecommendation

    results = []
    for candidate in build_candidates(profile, subject_code=subject_code, limit=limit):
        item, _ = ResourceRecommendation.objects.update_or_create(
            profile=profile,
            subject_code=candidate.subject_code,
            source_type=candidate.source_type,
            query=candidate.query,
            defaults={
                "theme": candidate.theme,
                "title": candidate.title,
                "url": candidate.url,
                "reason": candidate.reason,
                "score": candidate.score,
            },
        )
        results.append(item)
    return results


def recommendations_for_profile(profile, subject_code=None, include_dismissed=False, limit=30):
    from organizer.models import ResourceRecommendation

    items = ResourceRecommendation.objects.filter(profile=profile)
    if subject_code:
        items = items.filter(subject_code=subject_code)
    if not include_dismissed:
        items = items.exclude(status="dismissed")
    return items.order_by("status", "-score", "-updated_at")[:limit]


def set_recommendation_status(item, status):
    allowed = {"suggested", "saved", "dismissed", "opened"}
    if status not in allowed:
        raise ValueError(f"Unknown recommendation status: {status}")
    item.status = status
    item.save(update_fields=["status", "updated_at"])
    return item
