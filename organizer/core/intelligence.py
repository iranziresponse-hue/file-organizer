"""File intelligence — topic extraction, duplicate detection, related-file
grouping, subject inference, and review-oriented summary generation.

All functions return (result, error_message) tuples — never throw.
"""

import hashlib
import re
from pathlib import Path
from typing import Callable

from datetime import datetime

# Stop words for topic extraction
_STOP_WORDS = {
    "and", "the", "for", "with", "from", "into", "notes", "lecture",
    "assignment", "tutorial", "slides", "final", "draft", "copy", "this",
    "that", "what", "have", "been", "were", "was", "are", "not", "but",
    "also", "very", "just", "about", "over", "such", "each", "than",
    "after", "before", "between", "under", "above", "while", "where",
}


# ---------------------------------------------------------------------------
# Topic extraction
# ---------------------------------------------------------------------------

def extract_topics(filename: str, min_word_length: int = 4) -> list[str]:
    """Extract meaningful topics from a filename.

    Returns a list of topic words/phrases sorted by relevance.
    """
    stem = Path(filename).stem.lower()
    words = []

    # Split on common separators
    for raw in re.split(r"[\s_\-–—,;:()\[\]{}]+", stem):
        word = "".join(c for c in raw if c.isalnum())
        if len(word) >= min_word_length and word not in _STOP_WORDS and not word.isdigit():
            words.append(word)

    return words


def extract_topics_from_text(text: str, max_topics: int = 10) -> list[tuple[str, int]]:
    """Extract important topics from document text with frequency counts.

    Returns [(word, count), ...] sorted by frequency descending.
    """
    import re
    from collections import Counter

    # Clean text
    text_lower = text.lower()
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text_lower)

    # Filter stop words
    filtered = [w for w in words if w not in _STOP_WORDS and not w.isdigit()]
    counter = Counter(filtered)

    # Return top N
    return counter.most_common(max_topics)


def extract_definition_sentences(text: str, max_definitions: int = 5) -> list[str]:
    """Extract sentences that look like definitions from document text.

    Looks for patterns like:
    - "X is/are/refers to/means Y"
    - "X can be defined as Y"
    - "X consists of Y"
    """
    sentences = re.split(r"[.!?]+", text)
    definition_patterns = [
        r"\bis\s+(?:a|an|the|any|one|not)?\s*",
        r"\bare\s+(?:a|an|the|any|one|not)?\s*",
        r"\brefers?\s+to\b",
        r"\bmeans?\b",
        r"\bcan\s+be\s+defined\s+as\b",
        r"\bis\s+defined\s+as\b",
        r"\bconsists?\s+of\b",
        r"\bcomprises?\b",
    ]

    definitions = []
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 20 or len(sentence) > 500:
            continue
        for pattern in definition_patterns:
            if re.search(pattern, sentence, re.IGNORECASE):
                definitions.append(sentence[:200])  # Truncate long definitions
                break

    return definitions[:max_definitions]


def extract_key_phrases(text: str, max_phrases: int = 8) -> list[str]:
    """Extract key phrases (multi-word terms) from document text."""
    import re
    from collections import Counter

    # Find potential multi-word phrases (adjacent capitalized words or technical terms)
    phrases = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text)
    phrases += re.findall(r"\b([a-z]+[A-Z][a-z]+)\b", text)  # camelCase terms

    counter = Counter(phrases)
    return [phrase for phrase, _ in counter.most_common(max_phrases)]


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def compute_file_hash(file_path: Path, algorithm: str = "md5") -> str | None:
    """Compute a file hash for duplicate detection."""
    try:
        h = hashlib.new(algorithm)
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def find_duplicates(profile, algorithm: str = "md5", log: Callable | None = None) -> list[dict]:
    """Find duplicate files across a profile's moved files.

    Returns [(file1_path, file2_path, hash), ...] for duplicates found.
    """
    from organizer.models import MoveEvent

    hashes: dict[str, list[str]] = {}
    duplicates = []

    events = MoveEvent.objects.filter(
        profile=profile, success=True
    ).exclude(destination_path="").order_by("-timestamp")

    for event in events:
        dest = Path(event.destination_path)
        if not dest.exists():
            continue

        file_hash = compute_file_hash(dest, algorithm)
        if not file_hash:
            continue

        if file_hash in hashes:
            for existing in hashes[file_hash]:
                duplicates.append({
                    "file1": existing,
                    "file2": str(dest),
                    "hash": file_hash,
                    "filename": dest.name,
                })
        else:
            hashes[file_hash] = [str(dest)]

    return duplicates


def find_exact_duplicates_by_name(profile) -> list[dict]:
    """Find files with identical names in different folders."""
    from organizer.models import MoveEvent

    name_map: dict[str, list[dict]] = {}
    duplicates = []

    events = MoveEvent.objects.filter(
        profile=profile, success=True
    ).exclude(destination_path="").order_by("-timestamp")

    for event in events:
        dest = Path(event.destination_path)
        if not dest.exists():
            continue

        name = dest.name.lower()
        if name in name_map:
            for existing in name_map[name]:
                duplicates.append({
                    "file1": existing["path"],
                    "file2": str(dest),
                    "filename": dest.name,
                    "source1": existing["source"],
                    "source2": event.source_path,
                })
        else:
            name_map[name] = [{"path": str(dest), "source": event.source_path}]

    return duplicates


# ---------------------------------------------------------------------------
# Related-file grouping
# ---------------------------------------------------------------------------

def find_related_files(
    file_path: Path,
    profile,
    max_related: int = 5,
    log: Callable | None = None,
) -> list[dict]:
    """Find files related to a given file based on subject code, topic,
    and time proximity.

    Returns list of related file dicts sorted by relevance.
    """
    from organizer.models import MoveEvent

    src_path = Path(file_path)
    src_name = src_path.stem.lower()
    src_topics = set(extract_topics(src_path.name))

    # Find the event for this file
    events = MoveEvent.objects.filter(
        profile=profile, success=True
    ).exclude(destination_path="")

    scored: list[tuple[int, object]] = []

    for event in events:
        if event.destination_path == str(file_path):
            continue

        dest = Path(event.destination_path)
        if not dest.exists():
            continue

        score = 0
        reasons = []

        # Same subject code
        if event.course_code:
            ev_code = event.course_code.strip().upper()
            if any(c.upper() == ev_code for c in (src_topics)):
                score += 10
                reasons.append("same_subject")

        # Shared topics in filename
        ev_topics = set(extract_topics(dest.name))
        shared = src_topics & ev_topics
        score += len(shared) * 5
        if shared:
            reasons.append(f"shared_topics:{','.join(shared)}")

        # Same source directory (Downloaded together)
        src_dir = Path(event.source_path).parent if event.source_path else None
        if src_dir and src_dir.name:
            score += 2
            reasons.append("same_source_dir")

        # Time proximity (within 1 hour)
        if event.timestamp:
            event_ts = event.timestamp
            src_event = MoveEvent.objects.filter(
                destination_path=str(file_path)
            ).first()
            if src_event and src_event.timestamp:
                diff = abs((event_ts - src_event.timestamp).total_seconds())
                if diff < 3600:  # Within 1 hour
                    score += 3
                    reasons.append("time_proximity")

        if score > 0:
            scored.append((score, {
                "path": event.destination_path,
                "filename": dest.name,
                "course_code": event.course_code or "",
                "method": event.method,
                "score": score,
                "reasons": reasons,
            }))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for score, item in scored[:max_related]]


# ---------------------------------------------------------------------------
# Subject inference
# ---------------------------------------------------------------------------

def infer_subject_from_filename(
    filename: str,
    known_subjects: list[str],
) -> tuple[str | None, float]:
    """Infer which known subject a filename belongs to.

    Uses filename pattern matching against known subject codes.

    Returns (best_subject_code, confidence_0_to_1).
    """
    name_lower = filename.lower()
    stem_lower = Path(filename).stem.lower()

    best_match = None
    best_score = 0.0

    for subject in known_subjects:
        sub_lower = subject.lower()
        score = 0.0

        # Direct code match in filename
        if sub_lower in name_lower:
            score = 0.95
        # Code in stem
        elif sub_lower in stem_lower:
            score = 0.9
        # Starts with code
        elif name_lower.startswith(sub_lower):
            score = 0.85
        # Partial match (e.g. "CSC2100" matches "CSC")
        elif sub_lower[:3] in name_lower and len(sub_lower) > 3:
            score = 0.4

        if score > best_score:
            best_score = score
            best_match = subject

    return best_match, best_score


def infer_subject_from_content(
    text: str,
    known_subjects: dict[str, list[str]],
) -> tuple[str | None, float]:
    """Infer subject from document content by matching key terms.

    known_subjects: {subject_code: [keywords, ...]}

    Returns (best_subject_code, confidence_0_to_1).
    """
    text_lower = text.lower()
    best_match = None
    best_score = 0.0

    for code, keywords in known_subjects.items():
        score = 0.0
        matched_keywords = []

        for keyword in keywords:
            kw_lower = keyword.lower()
            count = text_lower.count(kw_lower)
            if count > 0:
                score += min(count * 0.05, 0.3)  # Cap per keyword
                matched_keywords.append(keyword)

        if matched_keywords:
            score = min(score, 0.95)
            if score > best_score:
                best_score = score
                best_match = code

    return best_match, best_score


# ---------------------------------------------------------------------------
# Review-oriented summary generation
# ---------------------------------------------------------------------------

def generate_review_summary(
    file_path: Path,
    extracted_text: str,
    log: Callable | None = None,
) -> tuple[str | None, str | None]:
    """Generate a review-oriented summary with:
    - Key points
    - Definitions
    - Likely exam questions
    - Action items

    Uses AI if configured, otherwise uses heuristic extraction.

    Returns (summary_html, None) or (None, error_message).
    """
    from . import ai_classify, summarize

    ai = ai_classify.load_ai_config()
    if ai and ai.get("enabled") and ai.get("api_key"):
        return _generate_ai_review_summary(file_path, extracted_text, log=log)

    return _generate_heuristic_review_summary(file_path, extracted_text)


def _generate_ai_review_summary(
    file_path: Path,
    extracted_text: str,
    log: Callable | None = None,
) -> tuple[str | None, str | None]:
    """Generate review summary using AI."""
    import requests

    from . import ai_classify

    ai = ai_classify.load_ai_config()
    if not ai or not ai.get("api_key"):
        return _generate_heuristic_review_summary(file_path, extracted_text)

    prompt = (
        "You are a study assistant creating a review companion for a document.\n\n"
        f"Document: {file_path.name}\n\n"
        f"Full extracted text:\n\"\"\"\n{extracted_text[:12000]}\n\"\"\"\n\n"
        "Write a thorough study review with these sections. Use this exact format:\n"
        "# Title\n\n"
        "## Key Points\n"
        "Write 5-8 key points from the document in full sentences.\n\n"
        "## Key Definitions\n"
        "List 3-6 important terms and their definitions found in the document.\n\n"
        "## Likely Exam Questions\n"
        "Write 3-5 questions that a lecturer might ask about this material.\n\n"
        "## Action Items\n"
        "List 2-4 specific things to do next to master this material.\n\n"
        "Requirements:\n"
        "- Write in full prose paragraphs for each section.\n"
        "- Do not use bullet points, asterisks, or numbered lists.\n"
        "- Never use an em dash. Use commas or periods instead.\n"
        "- Never use a line made only of dashes or asterisks.\n"
        "- Be specific to this document, not generic.\n"
        "- If the text is too short or garbled, say so plainly."
    )

    try:
        response = requests.post(
            f"{ai['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {ai['api_key']}"},
            json={
                "model": ai["model"],
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 3000,
                "temperature": 0.3,
            },
            timeout=90,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        if content:
            return content, None
    except Exception as exc:
        if log:
            log(f"AI review summary failed for '{file_path.name}': {exc}")

    # Fallback to heuristic
    return _generate_heuristic_review_summary(file_path, extracted_text)


def _generate_heuristic_review_summary(
    file_path: Path,
    extracted_text: str,
) -> tuple[str, None]:
    """Generate review summary using heuristics (no AI needed)."""
    filename = file_path.name
    text = extracted_text[:8000]

    # Extract topics
    topics = extract_topics(filename) + [t for t, _ in extract_topics_from_text(text, 5)]

    # Extract definitions
    definitions = extract_definition_sentences(text)

    # Key phrases
    phrases = extract_key_phrases(text)

    lines = []
    lines.append(f"# Review: {filename}")
    lines.append("")

    # Topics
    lines.append("## Key Topics")
    if topics:
        lines.append(f"Topics detected: {'; '.join(topics[:8])}")
    else:
        lines.append("No significant topics extracted from this document.")
    lines.append("")

    # Key phrases
    lines.append("## Key Phrases")
    if phrases:
        for phrase in phrases:
            lines.append(phrase)
    else:
        lines.append("No significant phrases detected.")
    lines.append("")

    # Definitions
    lines.append("## Possible Definitions")
    if definitions:
        for d in definitions:
            lines.append(d)
    else:
        lines.append("No clear definitions found in the extracted text.")
    lines.append("")

    # Questions (heuristic: look for question marks)
    lines.append("## Questions Found in Text")
    questions = [s.strip() for s in re.split(r"[.!?]+", text) if "?" in s]
    if questions:
        for q in questions[:5]:
            lines.append(q.strip() + "?")
    else:
        lines.append("No explicit questions found in the extracted text.")
    lines.append("")

    # Summary
    word_count = len(text.split())
    lines.append("## Document Stats")
    lines.append(f"Approximately {word_count} words extracted.")
    lines.append(f"Content length: {'Sufficient' if word_count > 100 else 'Very short, text extraction may be incomplete.'}")

    return "\n".join(lines), None


# ---------------------------------------------------------------------------
# Bulk summarization queue
# ---------------------------------------------------------------------------

def queue_bulk_summaries(profile, log: Callable | None = None) -> dict:
    """Queue review summaries for all summarizable files in a profile.

    Returns {queued: int, skipped: int, errors: int}.
    """
    from organizer.models import FileSummary, MoveEvent

    result = {"queued": 0, "skipped": 0, "errors": 0}

    events = MoveEvent.objects.filter(
        profile=profile, success=True
    ).exclude(destination_path="").order_by("-timestamp")

    for event in events:
        if not event.is_summarizable():
            result["skipped"] += 1
            continue

        # Skip if already has a summary
        if hasattr(event, "summary") and event.summary:
            result["skipped"] += 1
            continue

        dest = Path(event.destination_path)
        if not dest.exists():
            result["skipped"] += 1
            continue

        # Generate review summary
        from . import summarize as summarize_core

        extracted = summarize_core.extract_text(dest)
        if not extracted or len(extracted.strip()) < 200:
            result["skipped"] += 1
            continue

        content, error = generate_review_summary(dest, extracted, log=log)
        if error:
            result["errors"] += 1
            if log:
                log(f"Bulk summary failed for '{event.filename}': {error}")
            continue

        if content:
            FileSummary.objects.update_or_create(
                move_event=event,
                defaults={"content": content},
            )
            result["queued"] += 1

    if log:
        log(f"Bulk summarization: {result['queued']} queued, {result['skipped']} skipped, {result['errors']} errors")

    return result


# ---------------------------------------------------------------------------
# AI settings helpers
# ---------------------------------------------------------------------------

def get_ai_config_status() -> dict:
    """Get a human-readable AI configuration status."""
    from . import ai_classify, paths

    config_path = paths.AI_CONFIG_PATH
    config = ai_classify.load_ai_config()

    if not config_path.exists():
        return {
            "configured": False,
            "status": "AI not configured",
            "detail": "No ai_config.json file found.",
            "model": None,
            "provider": None,
        }

    if not config:
        return {
            "configured": False,
            "status": "Invalid config",
            "detail": "ai_config.json exists but could not be read.",
            "model": None,
            "provider": None,
        }

    enabled = config.get("enabled", False)
    api_key = config.get("api_key", "")
    model = config.get("model", "unknown")

    # Detect provider from base_url
    base_url = config.get("base_url", "")
    if "groq" in base_url:
        provider = "Groq"
    elif "openai" in base_url:
        provider = "OpenAI"
    elif "azure" in base_url:
        provider = "Azure OpenAI"
    else:
        provider = "Custom API"

    return {
        "configured": True,
        "status": "Online and active" if enabled else "Installed but disabled",
        "detail": f"Using {provider} {model}" if enabled else f"Configured for {provider} {model} but AI features are turned off",
        "model": model,
        "provider": provider,
        "enabled": enabled,
        "has_key": bool(api_key),
    }


def toggle_ai_enabled(enabled: bool) -> bool:
    """Toggle AI features on/off in ai_config.json.

    Returns True on success.
    """
    import json

    from . import ai_classify, paths

    config = ai_classify.load_ai_config()
    if config is None:
        return False

    config["enabled"] = enabled
    try:
        paths.AI_CONFIG_PATH.write_text(
            json.dumps(config, indent=2),
            encoding="utf-8",
        )
        return True
    except OSError:
        return False