"""Past Paper Intelligence -- local, free topic-frequency analysis over a
subject's own past papers. No paid AI: text extraction reuses
organizer.core.summarize.extract_text (pypdf/python-docx) and topic
detection reuses organizer.core.topics' existing TF-IDF/frequency layer,
the same machinery Subject Themes already runs on.

A "past paper" is never uploaded through a separate flow -- it's simply
any file the sorter already routed into a subject's "03 Past Papers and
Tests" folder (organizer.core.rules.category_from_path).

Detects RECURRING TOPICS across multiple papers' questions, not literal
repeated questions -- different years rarely phrase a question identically,
so this never claims verbatim-repetition detection.
"""

import re
from pathlib import Path
from typing import Callable, Optional

# A question start, anchored at the beginning of a line: "Q1", "Question 2",
# "1.", "2)" etc. Loose by design (a past paper is expected to be mostly
# numbered questions) -- if nothing in a document matches, extract_questions
# returns an empty list rather than guessing at a false split.
_QUESTION_START = re.compile(r"(?m)^[ \t]*(?:Q(?:uestion)?\.?\s*\d{1,2}\b[.:)]?|\d{1,2}[.)])[ \t]*")
_MARKS_PATTERN = re.compile(r"[\[(]\s*(\d{1,3})\s*marks?\s*[\])]", re.IGNORECASE)

# Every one of these appears near-verbatim in nearly every question on
# nearly every paper -- without stripping them, topics.py's cross-document
# TF-IDF (correctly) flags them as "recurring", but they're exam grammar,
# not a syllabus topic. Only used to clean the text fed to topic
# extraction; the original text is kept for question display/marks.
_MARKS_STRIP = re.compile(r"[\[(]\s*\d{1,3}\s*marks?\s*[\])]", re.IGNORECASE)
_EXAM_COMMAND_WORDS = re.compile(
    r"\b(explain|describe|define|discuss|state|outline|distinguish|compare|contrast|"
    r"list|give|trace|illustrate|analyze|analyse|evaluate|calculate|derive|prove|show|"
    r"briefly|clearly|question)\b",
    re.IGNORECASE,
)


def _clean_for_topic_extraction(text: str) -> str:
    text = _MARKS_STRIP.sub(" ", text)
    return _EXAM_COMMAND_WORDS.sub(" ", text)


MAX_QUESTION_CHARS = 300
MAX_QUESTIONS_PER_PAPER = 40
MAX_TOTAL_QUESTIONS = 200


def extract_questions(text: str, source_file: str = "") -> list[dict]:
    """Splits `text` into questions at each line-start question marker.
    Returns [] if no marker is found at all -- the caller still runs topic
    extraction over the whole document in that case, it just won't have a
    per-question breakdown, and the UI says so rather than pretending the
    whole document is one question."""
    if not text or not text.strip():
        return []

    matches = list(_QUESTION_START.finditer(text))
    if not matches:
        return []

    questions = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[start:end].strip()
        if not chunk:
            continue
        marks_match = _MARKS_PATTERN.search(chunk)
        questions.append({
            "text": chunk[:MAX_QUESTION_CHARS],
            "marks": int(marks_match.group(1)) if marks_match else None,
            "source_file": source_file,
        })
        if len(questions) >= MAX_QUESTIONS_PER_PAPER:
            break
    return questions


def analyze_subject(profile, subject_code: str, log: Optional[Callable] = None):
    """Analyzes every past-paper file already sorted under `subject_code`
    for `profile`. Returns (PastPaperAnalysis | None, skipped_count).
    Returns (None, 0) if there are no past-paper files to analyze at all --
    the caller should not create an empty analysis row in that case."""
    from organizer.models import MoveEvent, PastPaperAnalysis

    from . import rules as routing_rules
    from . import summarize as summarize_core
    from . import topics as topics_core

    events = MoveEvent.objects.filter(profile=profile, course_code=subject_code, success=True)
    past_papers = [
        event for event in events
        if routing_rules.category_from_path(event.destination_path) == "03 Past Papers and Tests"
    ]
    if not past_papers:
        return None, 0

    paper_texts = []
    cleaned_texts_for_topics = []
    paper_filenames = []
    all_questions = []
    skipped = 0

    for event in past_papers:
        path = Path(event.destination_path)
        if not path.exists():
            skipped += 1
            if log:
                log(f"Skipped '{event.filename}' for past-paper analysis: file no longer found")
            continue

        text = summarize_core.extract_text(path)
        if not text.strip():
            skipped += 1
            if log:
                log(f"Skipped '{event.filename}' for past-paper analysis: no extractable text")
            continue

        paper_texts.append(text)
        cleaned_texts_for_topics.append(_clean_for_topic_extraction(text))
        paper_filenames.append(event.filename)
        if len(all_questions) < MAX_TOTAL_QUESTIONS:
            all_questions.extend(extract_questions(text, source_file=event.filename))

    if not paper_texts:
        # Every candidate file was skipped (missing from disk / unreadable)
        # -- nothing to analyze, so don't create an empty row that would
        # read as "0 papers found any topics" instead of "couldn't read
        # any of them".
        return None, skipped

    all_questions = all_questions[:MAX_TOTAL_QUESTIONS]

    topics_out = []
    if cleaned_texts_for_topics:
        for topic in topics_core.extract_topics_from_summaries(cleaned_texts_for_topics, paper_filenames):
            topics_out.append({
                "name": topic["name"],
                "weight": topic["weight"],
                "evidence": topic.get("evidence", []),
            })

    # Best-effort: attribute a question's marks to any topic whose name
    # appears as a substring of that question's text. Not a rigorous marks
    # audit -- labeled as such everywhere it's displayed.
    marks_by_topic: dict[str, int] = {}
    for topic in topics_out:
        name_lower = topic["name"].lower()
        total = sum(
            q["marks"] for q in all_questions
            if q["marks"] and name_lower in q["text"].lower()
        )
        if total:
            marks_by_topic[topic["name"]] = total

    analysis, _ = PastPaperAnalysis.objects.update_or_create(
        profile=profile,
        subject_code=subject_code,
        defaults={
            "paper_count": len(paper_texts),
            "questions": all_questions,
            "topics": topics_out,
            "marks_by_topic": marks_by_topic,
        },
    )

    update_weak_areas(profile, subject_code)

    return analysis, skipped


def update_weak_areas(profile, subject_code: str) -> list[str]:
    """The SubjectMemory.weak_areas producer. Prefers the evidence-backed
    signal (a past-paper topic the student's own files don't cover at all);
    falls back to the weaker "least-covered in your own material" signal
    only when there's no past-paper analysis yet, or nothing stood out."""
    from organizer.models import PastPaperAnalysis, SubjectMemory, SubjectTheme

    memory = SubjectMemory.objects.filter(profile=profile, code=subject_code).first()
    if not memory:
        return []

    own_theme_names = {
        t.name.lower() for t in SubjectTheme.objects.filter(profile=profile, subject_code=subject_code)
    }

    analysis = PastPaperAnalysis.objects.filter(profile=profile, subject_code=subject_code).first()
    if analysis:
        # Evidence-backed case: tested-but-uncovered topics. An empty
        # result here is a real, honest signal ("nothing tested stands out
        # as uncovered") -- it must NOT fall through to the weaker
        # own-themes heuristic below, or a fully-covered subject would get
        # its own covered topics wrongly relabeled as "weak".
        weak = [
            topic.get("name", "") for topic in analysis.topics[:10]
            if topic.get("name") and topic["name"].lower() not in own_theme_names
        ]
    else:
        # No past-paper analysis yet: the only signal available is what the
        # student's own material under- or over-represents.
        least_covered = SubjectTheme.objects.filter(
            profile=profile, subject_code=subject_code
        ).order_by("weight")[:5]
        weak = [t.name for t in least_covered]

    weak = weak[:8]
    memory.weak_areas = weak
    memory.save(update_fields=["weak_areas"])
    return weak
