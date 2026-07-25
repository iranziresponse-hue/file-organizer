"""Active Recall Builder -- local, free flashcard generation and spaced
review. No new AI calls: generation is pure extraction over content Orch
already produced (past-paper questions, AI summaries).

"Keep it local/simple first: headings, bold terms, repeated phrases,
definitions, and past-paper questions" -- per the product ask.
"""

import re
from datetime import timedelta
from typing import Optional

from django.utils import timezone

# Same ladder as organizer.core.review._INTERVALS, mirrored rather than
# imported: review._next_interval is coupled to ReviewItem's create-a-new-
# row-per-occurrence pattern, whereas a flashcard is a persistent, reusable
# entity graded in place. Keeping the same cadence here just keeps the
# whole app's recall rhythm consistent.
INTERVALS = [1, 3, 7, 14, 30, 60, 90]

# "**Term**: definition" or "**Term** - definition" inside a paragraph.
_BOLD_DEFINITION_RE = re.compile(r"\*\*(.+?)\*\*\s*[:\-–]\s*(.+)")

MAX_BACK_CHARS = 800


def generate_from_past_papers(profile, subject_code: str) -> int:
    """One Flashcard per extracted past-paper question. `back` stays blank
    -- this app has no source of truth for the correct answer. Returns the
    number of NEW cards created (re-running after a fresh analysis won't
    duplicate ones that already exist)."""
    from organizer.models import Flashcard, PastPaperAnalysis

    analysis = PastPaperAnalysis.objects.filter(profile=profile, subject_code=subject_code).first()
    if not analysis or not analysis.questions:
        return 0

    created = 0
    for question in analysis.questions:
        front = (question.get("text") or "").strip()
        if not front:
            continue
        _, was_created = Flashcard.objects.get_or_create(
            profile=profile,
            subject_code=subject_code,
            card_type="past_paper_question",
            front=front[:500],
            defaults={"source_label": question.get("source_file", "")},
        )
        created += int(was_created)
    return created


def _save_concept_card(profile, subject_code: str, heading: Optional[str], body_parts: list, source_label: str) -> bool:
    if not heading or not body_parts:
        return False
    body = " ".join(body_parts).strip()
    if not body:
        return False
    from organizer.models import Flashcard

    _, was_created = Flashcard.objects.get_or_create(
        profile=profile,
        subject_code=subject_code,
        card_type="concept",
        front=f"Explain: {heading}"[:500],
        defaults={"back": body[:MAX_BACK_CHARS], "source_label": source_label},
    )
    return was_created


def generate_from_summaries(profile, subject_code: str) -> int:
    """Definition-drill cards from `**Term**: definition` text, and
    concept-explainer cards from each heading plus the text that follows
    it, across every FileSummary already generated for this subject.
    Reuses organizer.core.summarize.parse_structured_text -- the exact
    same "# "/"## " parsing the HTML/PDF summary views already run on --
    instead of a second markdown parser."""
    from organizer.models import FileSummary, Flashcard

    from . import summarize as summarize_core

    summaries = FileSummary.objects.filter(
        move_event__profile=profile, move_event__course_code=subject_code
    ).select_related("move_event")

    created = 0
    for summary in summaries:
        source_label = summary.move_event.filename if summary.move_event else ""
        blocks = summarize_core.parse_structured_text(summary.content or "")

        for kind, text in blocks:
            if kind != "p":
                continue
            for match in _BOLD_DEFINITION_RE.finditer(text):
                term = match.group(1).strip()
                definition = match.group(2).strip()
                if not term or not definition:
                    continue
                _, was_created = Flashcard.objects.get_or_create(
                    profile=profile,
                    subject_code=subject_code,
                    card_type="definition",
                    front=f"Define: {term}"[:500],
                    defaults={"back": definition[:MAX_BACK_CHARS], "source_label": source_label},
                )
                created += int(was_created)

        current_heading = None
        current_body: list = []
        for kind, text in blocks:
            if kind in ("h1", "h2"):
                created += int(_save_concept_card(profile, subject_code, current_heading, current_body, source_label))
                current_heading, current_body = text, []
            elif kind in ("p", "li"):
                current_body.append(text)
        created += int(_save_concept_card(profile, subject_code, current_heading, current_body, source_label))

    return created


def get_due_cards(profile, subject_code: str = "", limit: int = 20):
    from organizer.models import Flashcard

    qs = Flashcard.objects.filter(profile=profile, status="active", due_at__lte=timezone.now())
    if subject_code:
        qs = qs.filter(subject_code=subject_code)
    return qs.order_by("due_at")[:limit]


def grade_flashcard(card, remembered: bool):
    """Advances/regresses `card.interval_index` along the shared ladder and
    pushes `due_at` out (or back) accordingly, in place -- a flashcard is
    reused indefinitely, unlike ReviewItem which spawns a fresh row per
    review occurrence."""
    if remembered:
        card.interval_index = min(card.interval_index + 1, len(INTERVALS) - 1)
        card.times_correct += 1
    else:
        card.interval_index = max(card.interval_index - 1, 0)
    card.times_seen += 1
    card.due_at = timezone.now() + timedelta(days=INTERVALS[card.interval_index])
    card.save()
    return card
