"""AI-powered long-form summaries for a sorted document, cross-referenced
against its sibling files in the same destination folder. Mirrors
ai_classify.py's contract: never throws, never fabricates when it has
nothing real to work from -- any failure (unreadable file, no API key,
network error, bad response) surfaces as a plain error message, not a
crash and not an invented summary.
"""

import re
from pathlib import Path

import requests

from . import ai_classify

# Sized to stay well under Groq's free-tier 6000 tokens-per-minute limit for
# this model, confirmed directly against the real API (a prompt built from
# the old, larger caps reliably triggered a 413 "Request too large" error
# from Groq itself, not a real connectivity problem). At these caps, a real
# full-length lecture PDF measured about 2200 prompt tokens plus the 2000
# max_tokens response budget below, comfortably under the limit.
MAX_SOURCE_CHARS = 9000
MAX_RELATED_FILES = 3
MAX_RELATED_CHARS = 500
MIN_SOURCE_CHARS = 200

SUPPORTED_EXTENSIONS = {"pdf", "docx"}

PROMPT_TEMPLATE = """You are writing a long, explicit study companion for a document. The goal is to make the reader want to actually read the source material and understand exactly how it fits with the other material already sitting next to it.

Document: {filename}

Full extracted text of the document (may be truncated):
\"\"\"
{source_text}
\"\"\"

Related files already in the same folder (use these to connect the dots, reference them by name where relevant, and explain how this document builds on, contrasts with, or sets up the others):
{related_text}

Write a long, thorough, unambiguous summary and study guide. Requirements:
- Open with a short, compelling hook (2 to 4 sentences) that makes clear why this document matters and is worth reading now.
- Be explicit and detailed, not a short blurb. Aim for real depth: explain the actual content, not just topics.
- Structure the output using this exact convention: one line starting with "# " for the title, and lines starting with "## " for section headings. Do not use any other heading depth. Leave a blank line between paragraphs.
- Include at minimum: an overview, a detailed breakdown of the key content, a section connecting this document to the related files listed above (skip that section only if none were given), and a closing section on what to focus on or do next.
- Write in full prose paragraphs. Do not use bullet points, numbered lists, or asterisks anywhere.
- Never use an em dash anywhere. Use a comma, period, or parentheses instead.
- Never use a line made only of dashes, underscores, or asterisks as a divider.
- Do not invent details the given text does not support. If the extracted text looks incomplete or garbled, say so plainly instead of making something up.
"""


def _extract_pdf_text(path, max_chars):
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    chunks = []
    total = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        chunks.append(text)
        total += len(text)
        if total >= max_chars:
            break
    return "\n".join(chunks)[:max_chars]


def _extract_docx_text(path, max_chars):
    import docx

    document = docx.Document(str(path))
    text = "\n".join(p.text for p in document.paragraphs)
    return text[:max_chars]


def extract_text(path, max_chars=MAX_SOURCE_CHARS):
    ext = Path(path).suffix.lstrip(".").lower()
    try:
        if ext == "pdf":
            return _extract_pdf_text(path, max_chars)
        if ext == "docx":
            return _extract_docx_text(path, max_chars)
    except Exception:
        return ""
    return ""


def find_related_files(path, limit=MAX_RELATED_FILES):
    """Other summarizable files already sitting in the same destination
    folder -- the context the prompt uses to connect this document to the
    rest of what's already there."""
    path = Path(path)
    folder = path.parent
    if not folder.exists():
        return []
    related = []
    for sibling in sorted(folder.iterdir()):
        if sibling == path or not sibling.is_file():
            continue
        if sibling.suffix.lstrip(".").lower() not in SUPPORTED_EXTENSIONS:
            continue
        related.append(sibling)
        if len(related) >= limit:
            break
    return related


def _related_context(related_files):
    if not related_files:
        return "(No other related files were found in this folder.)"
    blocks = []
    for f in related_files:
        snippet = extract_text(f, max_chars=MAX_RELATED_CHARS).strip()
        blocks.append(f"[{f.name}]\n{snippet or '(No readable text extracted.)'}")
    return "\n\n".join(blocks)


def _call_ai_completion(prompt, max_tokens, service_label, ai, log=None):
    """POST a chat completion request to the configured AI provider.

    Returns (content, None) on success or (None, error_message) on
    failure. Never throws. Distinguishes what actually went wrong (request
    too large, rate limited, bad key, genuine network failure) instead of
    reporting one generic "couldn't connect" for every failure mode -- a
    real request that exceeded Groq's tokens-per-minute limit was
    previously masked as a connectivity problem, which it never was.
    """
    body = {
        "model": ai["model"],
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.4,
    }

    try:
        response = requests.post(
            f"{ai['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {ai['api_key']}"},
            json=body,
            timeout=90,
        )
    except requests.Timeout:
        if log:
            log(f"{service_label} timed out.")
        return None, "The AI service took too long to respond. Try again."
    except requests.ConnectionError as exc:
        if log:
            log(f"{service_label} could not connect: {exc}")
        return None, "Couldn't reach the AI service. Check your internet connection."
    except requests.RequestException as exc:
        if log:
            log(f"{service_label} request failed: {exc}")
        return None, "Couldn't reach the AI service. Try again in a moment."
    except Exception as exc:  # anything unexpected. Never propagate
        if log:
            log(f"{service_label} failed unexpectedly: {exc}")
        return None, "Couldn't reach the AI service. Try again in a moment."

    if response.status_code == 413:
        if log:
            log(f"{service_label} rejected as too large: {response.text[:300]}")
        return None, "This document is too long to summarize in one go. Try a shorter document."
    if response.status_code == 429:
        if log:
            log(f"{service_label} was rate-limited: {response.text[:300]}")
        return None, "The AI service's rate limit was reached. Wait about a minute and try again."
    if response.status_code in (401, 403):
        if log:
            log(f"{service_label} rejected the API key: {response.text[:300]}")
        return None, "Your AI API key was rejected. Check ai_config.json."

    try:
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        if log:
            log(f"{service_label} returned an unexpected response: {exc}")
        return None, "The AI service returned an unexpected response. Try again."

    if not content:
        return None, "The AI service returned an empty response. Try again."

    return content, None


def _sanitize(content):
    # Belt and suspenders -- the prompt already forbids these, but strip
    # them regardless of whether the model actually listened.
    content = content.replace("\u2014", ",")
    return re.sub(r"^[\-_*]{3,}\s*$", "", content, flags=re.MULTILINE)


def generate_summary(file_path, log=None):
    """Returns (content, None) on success or (None, error_message) on
    failure. content is raw structured text (the "# "/"## " convention),
    ready for parse_structured_text()."""
    file_path = Path(file_path)
    ext = file_path.suffix.lstrip(".").lower()

    if ext not in SUPPORTED_EXTENSIONS:
        return None, "Summaries are only available for PDF and Word documents right now."

    if not file_path.exists():
        return None, "This file isn't where the log says it should be anymore."

    ai = ai_classify.load_ai_config()
    if not ai or not ai.get("enabled") or not ai.get("api_key"):
        return None, "AI isn't configured yet. Add your API key to ai_config.json to use summaries."

    source_text = extract_text(file_path)
    if len(source_text.strip()) < MIN_SOURCE_CHARS:
        return None, "Couldn't extract enough readable text from this file (it may be a scanned document or an image-only PDF)."

    related_files = find_related_files(file_path)
    prompt = PROMPT_TEMPLATE.format(
        filename=file_path.name,
        source_text=source_text,
        related_text=_related_context(related_files),
    )

    content, error = _call_ai_completion(
        prompt,
        max_tokens=2000,
        service_label=f"Summary generation for '{file_path.name}'",
        ai=ai,
        log=log,
    )
    if error:
        return None, error

    return _sanitize(content), None


COURSE_GUIDE_PROMPT_TEMPLATE = """You are writing a general academic guide for a university course unit. You do not have access to this institution's actual official syllabus for this course. Do not invent specific facts you cannot know: no specific lecturer names, no specific assessment weightings, no specific week-by-week schedule, and do not claim this is the official curriculum. Instead, give an honest, well-grounded overview of what a course with this code and title typically covers at this level of study, based on how courses with this kind of code and title are generally structured in a program like this one.

Course code: {course_code}
Program context: {program}
Academic level: {level}

Write a long, thorough, unambiguous guide. Requirements:
- Open with a short, compelling hook (2 to 4 sentences) that makes clear why this course matters and what a student stands to gain from taking it seriously.
- Be explicit and detailed, not a short blurb.
- Structure the output using this exact convention: one line starting with "# " for the title, and lines starting with "## " for section headings. Do not use any other heading depth. Leave a blank line between paragraphs.
- Include at minimum: an overview of what this course is generally about, a breakdown of the topics a course like this typically covers, how it usually connects to other courses in a program like this, and a closing section on how to approach it and what to focus on.
- Write in full prose paragraphs. Do not use bullet points, numbered lists, or asterisks anywhere.
- Never use an em dash anywhere. Use a comma, period, or parentheses instead.
- Never use a line made only of dashes, underscores, or asterisks as a divider.
- Be explicit that this is a general guide, not an official syllabus, if you are not confident about institution-specific details.
"""


def generate_course_guide(course_code, program="", level="", log=None):
    """Returns (content, None) on success or (None, error_message) on
    failure, same shape as generate_summary(). Unlike generate_summary,
    there is no source document to ground this in -- just the course code
    and whatever program/level context the caller has -- so the prompt is
    explicit about not inventing institution-specific facts it cannot know.
    """
    course_code = (course_code or "").strip()
    if not course_code:
        return None, "No course code given."

    ai = ai_classify.load_ai_config()
    if not ai or not ai.get("enabled") or not ai.get("api_key"):
        return None, "AI isn't configured yet. Add your API key to ai_config.json to use course guides."

    prompt = COURSE_GUIDE_PROMPT_TEMPLATE.format(
        course_code=course_code,
        program=program or "not specified",
        level=level or "not specified",
    )

    content, error = _call_ai_completion(
        prompt,
        max_tokens=3000,
        service_label=f"Course guide generation for '{course_code}'",
        ai=ai,
        log=log,
    )
    if error:
        return None, error

    return _sanitize(content), None


_LIST_ITEM_RE = re.compile(r"^[*\-]\s+(.*)$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def parse_structured_text(content):
    """Turns the "# Title" / "## Heading" / paragraph convention into a list
    of (kind, text) tuples -- kind is "h1", "h2", "li", or "p". Shared by the
    HTML popup and the PDF export so both render from exactly the same
    structure.

    The prompt asks for only "# "/"## " and full prose, no lists, but models
    don't always comply -- headings of any depth ("### ", "#### ", ...) and
    "* "/"- " bullet lines are recognized rather than leaking through as
    literal "###"/"*" characters in a paragraph.
    """
    blocks = []
    paragraph_lines = []

    def flush():
        if paragraph_lines:
            text = " ".join(line.strip() for line in paragraph_lines).strip()
            if text:
                blocks.append(("p", text))
            paragraph_lines.clear()

    for line in content.splitlines():
        stripped = line.strip()
        heading_match = _HEADING_RE.match(stripped)
        list_match = _LIST_ITEM_RE.match(stripped) if not heading_match else None
        if heading_match:
            flush()
            level = len(heading_match.group(1))
            kind = "h1" if level == 1 else "h2"
            blocks.append((kind, heading_match.group(2).strip()))
        elif list_match:
            flush()
            blocks.append(("li", list_match.group(1).strip()))
        elif not stripped:
            flush()
        else:
            paragraph_lines.append(line)
    flush()
    return blocks


def _escape_html(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline_markup(text, bold_tag="strong"):
    """Escapes text and turns **bold** into a real tag -- the one bit of
    inline markdown models reliably reach for even when told to write plain
    prose. bold_tag is "strong" for HTML, "b" for reportlab's markup subset.
    """
    parts = []
    last = 0
    for m in _BOLD_RE.finditer(text):
        parts.append(_escape_html(text[last:m.start()]))
        parts.append(f"<{bold_tag}>{_escape_html(m.group(1))}</{bold_tag}>")
        last = m.end()
    parts.append(_escape_html(text[last:]))
    return "".join(parts)


def render_html(content):
    """Renders parsed blocks into an HTML fragment for the summary popup."""
    parts = []
    in_list = False
    for kind, text in parse_structured_text(content):
        if kind == "li":
            if not in_list:
                parts.append("<ul>")
                in_list = True
            parts.append(f"<li>{_inline_markup(text)}</li>")
            continue
        if in_list:
            parts.append("</ul>")
            in_list = False
        if kind == "h1":
            parts.append(f"<h1>{_inline_markup(text)}</h1>")
        elif kind == "h2":
            parts.append(f"<h2>{_inline_markup(text)}</h2>")
        else:
            parts.append(f"<p>{_inline_markup(text)}</p>")
    if in_list:
        parts.append("</ul>")
    return "".join(parts)


def render_pdf(filename, content):
    """Builds a downloadable PDF from the same parsed structure the popup
    view renders, so what you see and what you download always match."""
    from io import BytesIO

    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=0.9 * inch,
        rightMargin=0.9 * inch,
        topMargin=0.9 * inch,
        bottomMargin=0.9 * inch,
        title=filename,
    )
    styles = getSampleStyleSheet()
    h1_style = ParagraphStyle("SummaryH1", parent=styles["Heading1"], spaceAfter=14)
    h2_style = ParagraphStyle("SummaryH2", parent=styles["Heading2"], spaceBefore=16, spaceAfter=8)
    body_style = ParagraphStyle("SummaryBody", parent=styles["BodyText"], leading=16, spaceAfter=10)
    li_style = ParagraphStyle("SummaryLi", parent=body_style, leftIndent=18, bulletIndent=6)

    story = []
    for kind, text in parse_structured_text(content):
        safe = _inline_markup(text, bold_tag="b")
        if kind == "h1":
            story.append(Paragraph(safe, h1_style))
        elif kind == "h2":
            story.append(Paragraph(safe, h2_style))
        elif kind == "li":
            story.append(Paragraph("- " + safe, li_style))
        else:
            story.append(Paragraph(safe, body_style))
    if not story:
        story.append(Paragraph("No content.", body_style))

    doc.build(story)
    return buffer.getvalue()
