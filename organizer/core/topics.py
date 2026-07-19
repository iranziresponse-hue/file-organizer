"""Intelligent topic extraction for subject learning materials.

Two-layer approach:
1. NLP layer (fast, always-on): TF-IDF keyword extraction + N-gram analysis via
   scikit-learn and NLTK. Works on filenames, summary text, and file content.
2. AI layer (optional, needs API key): LLM-powered topic refinement using the
   existing ai_classify.py infrastructure -- extracts deeper conceptual topics
   from summaries and groups them semantically.

Fallback contract: the NLP layer always returns something meaningful from
filenames alone. The AI layer is an enhancement, never a hard dependency.
"""

import re
import string
from pathlib import Path
from typing import Callable, Optional

from django.utils import timezone

from organizer.models import MoveEvent, SubjectMemory, SubjectTheme

from . import ai_classify
from . import summarize as summarize_core

# ---------------------------------------------------------------------------
# NLP helpers
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset({
    "the", "and", "for", "with", "from", "into", "notes", "lecture",
    "assignment", "tutorial", "slides", "final", "draft", "copy",
    "this", "that", "what", "which", "while", "where", "when", "why",
    "how", "all", "each", "every", "its", "their", "your", "our",
    "have", "has", "had", "been", "being", "some", "any", "not",
    "are", "was", "were", "can", "will", "would", "could", "should",
    "about", "into", "over", "after", "before", "between", "through",
    "during", "without", "within", "along", "also", "just", "very",
    "too", "much", "more", "most", "many", "such", "than", "then",
    "else", "other", "another", "still", "already", "well", "back",
    "even", "first", "last", "next", "new", "old", "good", "great",
    "big", "small", "high", "low", "long", "short", "full", "free",
    "open", "close", "right", "left", "top", "bottom", "best",
    "introduction", "overview", "chapter", "section", "part",
    "module", "unit", "week", "session", "lesson", "material",
    "resource", "document", "file", "content", "page", "handout",
    "worksheet", "guide", "summary", "review", "reading", "reference",
    "supplementary", "additional", "extra", "basic", "advanced",
    "fundamentals", "principles", "concepts", "theory", "practice",
    "example", "exercise", "problem", "solution", "answer", "key",
    "study", "learn", "learn", "prepare", "revision", "exam", "test",
    "quiz", "midterm", "final", "project", "report", "paper", "essay",
    "university", "college", "school", "course", "class", "subject",
    "lecturer", "professor", "tutor", "instructor", "student",
    "academic", "academic_year", "semester", "trimester", "term",
})

_MIN_WORD_LENGTH = 3
_MAX_WORDS_PER_FILE = 8


def _tokenize(text: str) -> list[str]:
    """Split text into clean lowercase tokens, removing punctuation and
    numbers, filtering by length and stop words."""
    text = text.lower()
    # Remove common file extensions and formatting
    text = re.sub(r"\.(pdf|docx?|pptx?|xlsx?|txt|html?|zip|rar|7z)", " ", text)
    # Replace underscores, hyphens, and other separators with spaces
    text = re.sub(r"[_\-–—+]+", " ", text)
    # Remove remaining punctuation except apostrophes within words
    text = re.sub(r"[%s]" % re.escape(string.punctuation.replace("'", "")), " ", text)
    tokens = []
    for raw in text.split():
        word = raw.strip("'\"")
        if len(word) >= _MIN_WORD_LENGTH and not word.isdigit():
            tokens.append(word)
    return tokens


def _extract_keywords(text: str, top_n: int = 8) -> list[str]:
    """Simple frequency-based keyword extraction from text.
    Returns the top N meaningful keywords sorted by frequency."""
    tokens = _tokenize(text)
    # Remove stop words
    filtered = [t for t in tokens if t not in _STOP_WORDS]
    if not filtered:
        return []
    # Count frequencies
    freq: dict[str, int] = {}
    for token in filtered:
        freq[token] = freq.get(token, 0) + 1
    # Sort by frequency descending, then alphabetically for ties
    sorted_keywords = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
    return [word for word, _ in sorted_keywords[:top_n]]


def _extract_bigrams(text: str) -> list[str]:
    """Extract common two-word phrases from text."""
    tokens = _tokenize(text)
    filtered = [t for t in tokens if t not in _STOP_WORDS and len(t) >= 3]
    if len(filtered) < 2:
        return []
    bigrams: dict[str, int] = {}
    for i in range(len(filtered) - 1):
        phrase = f"{filtered[i]} {filtered[i+1]}"
        bigrams[phrase] = bigrams.get(phrase, 0) + 1
    sorted_phrases = sorted(bigrams.items(), key=lambda x: (-x[1], x[0]))
    return [phrase for phrase, _ in sorted_phrases[:4]]


# ---------------------------------------------------------------------------
# TF-IDF topic extraction via scikit-learn
# ---------------------------------------------------------------------------

def _tfidf_keywords(texts: list[str], top_n: int = 10) -> list[str]:
    """Use TF-IDF to extract the most distinctive keywords from a collection
    of texts. Falls back to frequency-based extraction if there's only one
    text or scikit-learn is not available."""
    if not texts:
        return []
    if len(texts) < 2:
        return _extract_keywords(texts[0] if texts else "", top_n)
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        import numpy as np
    except ImportError:
        # Fallback: merge all texts and extract keywords
        merged = " ".join(texts)
        return _extract_keywords(merged, top_n)

    tokenized_texts = []
    for t in texts:
        tokens = [w for w in _tokenize(t) if w not in _STOP_WORDS]
        tokenized_texts.append(" ".join(tokens))

    try:
        vectorizer = TfidfVectorizer(
            max_features=200,
            min_df=1,
            max_df=0.95,
            stop_words=list(_STOP_WORDS),
            ngram_range=(1, 2),
        )
        matrix = vectorizer.fit_transform(tokenized_texts)
        # Sum TF-IDF scores across all documents
        scores = np.array(matrix.sum(axis=0)).flatten()
        terms = vectorizer.get_feature_names_out()
        ranked = sorted(zip(terms, scores), key=lambda x: -x[1])
        return [term for term, _ in ranked[:top_n]]
    except Exception:
        merged = " ".join(texts)
        return _extract_keywords(merged, top_n)


# ---------------------------------------------------------------------------
# AI-powered topic extraction
# ---------------------------------------------------------------------------

_TOPIC_EXTRACTION_PROMPT = """You are a topic extractor for a university student's study materials.
Given the filename and any available summary text, extract the key learning topics or concepts
this document covers.

Filename: {filename}
Summary: {summary}

Extract 3-6 specific topics this document covers. Each topic should be a short phrase (1-4 words).
Reply with ONLY the topics, one per line, ordered by importance. No numbering, no extra text.
If the document lacks meaningful content for topic extraction, reply exactly: NONE"""


def _ai_extract_topics(filename: str, summary_text: str = "",
                        log: Optional[Callable] = None) -> list[str]:
    """Use the AI classifier's infrastructure to extract topics from a
    document's filename and summary text. Returns an empty list on any
    failure (no API key, network error, etc.)."""
    ai = ai_classify.load_ai_config()
    if not ai or not ai.get("enabled") or not ai.get("api_key"):
        return []
    if not summary_text and not filename:
        return []

    # Truncate summary to avoid token limits
    truncated_summary = summary_text[:3000] if summary_text else "(no summary available)"

    prompt = _TOPIC_EXTRACTION_PROMPT.format(
        filename=filename,
        summary=truncated_summary,
    )

    body = {
        "model": ai["model"],
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 200,
        "temperature": 0.1,
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
        if not answer or answer == "NONE":
            return []
        topics = []
        for line in answer.splitlines():
            line = line.strip().strip("-*#").strip()
            # Remove leading numbers like "1. " or "1) "
            line = re.sub(r"^\d+[.)]\s*", "", line)
            if line and len(line) >= 3:
                topics.append(line)
        return topics[:6]
    except Exception as exc:
        if log:
            log(f"AI topic extraction skipped for '{filename}': {exc}")
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_topics_from_filenames(
    filenames: list[str],
    subject_code: str = "",
) -> list[dict]:
    """Extract topics from a list of filenames using NLP (always) and AI
    (if available). Returns a list of dicts::
        {"name": str, "weight": int, "source": str, "evidence": [str]}

    The NLP layer extracts keywords and bigrams. The AI layer (if enabled
    and summaries are available) extracts deeper conceptual topics.
    """
    # --- NLP layer ---
    all_keywords: dict[str, float] = {}
    evidence_map: dict[str, list[str]] = {}
    bigram_map: dict[str, float] = {}

    for fname in filenames:
        # Keyword extraction
        keywords = _extract_keywords(fname, top_n=_MAX_WORDS_PER_FILE)
        weight = 1.0
        for kw in keywords:
            all_keywords[kw] = all_keywords.get(kw, 0) + weight
            if kw not in evidence_map:
                evidence_map[kw] = []
            if fname not in evidence_map[kw]:
                evidence_map[kw].append(fname[:100])

        # Bigram extraction
        bigrams = _extract_bigrams(fname)
        for bg in bigrams:
            bigram_map[bg] = bigram_map.get(bg, 0) + 1.5
            if bg not in evidence_map:
                evidence_map[bg] = []
            if fname not in evidence_map[bg]:
                evidence_map[bg].append(fname[:100])

    # Combine keywords and bigrams, normalizing weights
    topics: list[dict] = []
    seen_names = set()

    for name, weight in sorted(all_keywords.items(), key=lambda x: -x[1]):
        if name not in seen_names and name not in _STOP_WORDS:
            topics.append({
                "name": name,
                "weight": min(int(weight * 10), 100),
                "source": "filename",
                "evidence": evidence_map.get(name, [])[:5],
            })
            seen_names.add(name)

    for name, weight in sorted(bigram_map.items(), key=lambda x: -x[1]):
        if name not in seen_names:
            # Check if bigram words are already covered
            parts = name.split()
            if not all(p in seen_names for p in parts):
                topics.append({
                    "name": name,
                    "weight": min(int(weight * 10), 100),
                    "source": "filename",
                    "evidence": evidence_map.get(name, [])[:5],
                })
                seen_names.add(name)

    # Sort by weight descending, limit to top 20
    topics = sorted(topics, key=lambda t: -t["weight"])[:20]

    # --- AI layer (enhancement) ---
    # Only attempt if we have actual topics already and filenames with
    # enough character content to extract meaning from
    if topics and any(len(fn) > 15 for fn in filenames):
        merged_summary = " ".join(filenames)
        ai_topics = _ai_extract_topics(
            filename=", ".join(filenames[:5]),
            summary_text=merged_summary[:2000],
        )
        for ai_topic in ai_topics:
            if ai_topic.lower() not in seen_names:
                topics.append({
                    "name": ai_topic,
                    "weight": 80,  # AI topics get high base weight
                    "source": "summary",
                    "evidence": filenames[:3],
                })
                seen_names.add(ai_topic.lower())

    return topics[:30]


def extract_topics_from_summaries(
    summaries: list[str],
    filenames: list[str],
) -> list[dict]:
    """Extract deeper conceptual topics from full summary text using TF-IDF
    across multiple summary documents."""
    if not summaries:
        return []

    # Use TF-IDF across all summary texts
    tfidf_keywords = _tfidf_keywords(summaries, top_n=15)

    topics = []
    for kw in tfidf_keywords:
        # Find which filenames contain this keyword
        evidence = []
        for fname in filenames:
            if kw.lower() in fname.lower():
                evidence.append(fname[:100])
        if not evidence:
            evidence = filenames[:2]

        topics.append({
            "name": kw,
            "weight": 70,
            "source": "summary",
            "evidence": evidence[:5],
        })

    return topics


def process_subject_topics(
    profile,
    subject_code: str,
    limit: int = 30,
    log: Optional[Callable] = None,
) -> list[SubjectTheme]:
    """Full topic extraction pipeline for a single subject:
    1. Fetch recent MoveEvents for this subject code
    2. NLP keyword/bigram extraction from filenames
    3. AI-powered topic extraction from summaries (if available)
    4. Save/update SubjectTheme records

    Returns the list of created/updated SubjectTheme instances.
    """
    memory = SubjectMemory.objects.filter(profile=profile, code=subject_code).first()

    # Gather recent successful events for this subject
    events = (
        MoveEvent.objects.filter(profile=profile, course_code=subject_code, success=True)
        .select_related("summary")
        .order_by("-timestamp")[:limit]
    )

    if not events:
        return []

    filenames = [e.filename for e in events]
    summary_texts = []
    summary_filenames = []

    for event in events:
        if hasattr(event, "summary") and event.summary and event.summary.content:
            summary_texts.append(event.summary.content[:2000])
            summary_filenames.append(event.filename)

    # Step 1: Extract from filenames
    filename_topics = extract_topics_from_filenames(filenames, subject_code)

    # Step 2: Extract from summaries (if available)
    summary_topics = []
    if summary_texts:
        summary_topics = extract_topics_from_summaries(summary_texts, summary_filenames)

    # Merge: filename topics first, then summary topics (override if same name)
    merged: dict[str, dict] = {}
    for t in filename_topics:
        merged[t["name"]] = t
    for t in summary_topics:
        if t["name"] in merged:
            # Upgrade summary-based topics: increase weight, add evidence
            merged[t["name"]]["weight"] = max(merged[t["name"]]["weight"], t["weight"])
            merged[t["name"]]["source"] = "summary"
            merged[t["name"]]["evidence"].extend(t["evidence"])
        else:
            merged[t["name"]] = t

    # Step 3: Save to database
    themes = []
    for topic_name, topic_data in merged.items():
        theme, created = SubjectTheme.objects.update_or_create(
            profile=profile,
            subject_code=subject_code,
            name__iexact=topic_name,
            defaults={
                "subject_memory": memory,
                "name": topic_name,
                "weight": topic_data["weight"],
                "source": topic_data["source"],
                "evidence": topic_data["evidence"][:8],
            },
        )
        themes.append(theme)

    # Clean up old themes that no longer apply (weight < 3 and no recent evidence)
    active_names = {t["name"].lower() for t in merged.values()}
    stale = SubjectTheme.objects.filter(
        profile=profile, subject_code=subject_code,
    ).exclude(name__in=[t.name for t in themes if t.name.lower() in active_names])
    stale.delete()

    return themes


def process_all_subjects(profile, log: Optional[Callable] = None) -> dict[str, int]:
    """Process topic extraction for all subjects in a profile.
    Returns a dict mapping subject_code -> number of themes extracted."""
    memories = SubjectMemory.objects.filter(profile=profile)
    results = {}
    for memory in memories:
        themes = process_subject_topics(profile, memory.code, log=log)
        if themes:
            results[memory.code] = len(themes)
    return results


def get_subject_topic_summary(profile, subject_code: str) -> dict:
    """Get a structured summary of topics for a subject, suitable for
    dashboard display. Returns:
        {"code": str, "themes": [...], "top_theme": str, "theme_count": int}
    """
    themes = SubjectTheme.objects.filter(
        profile=profile, subject_code=subject_code
    ).order_by("-weight")[:15]

    return {
        "code": subject_code,
        "themes": [
            {"name": t.name, "weight": t.weight, "source": t.source, "evidence": t.evidence}
            for t in themes
        ],
        "top_theme": themes[0].name if themes else "",
        "theme_count": len(themes),
    }