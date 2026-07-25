"""Portable Knowledge Pack — exports a profile, subject, or term as a
standalone bundle containing:

1. A folder structure mirror of all sorted files
2. Document summaries (HTML and PDF)
3. A folder map (tree view)
4. A reading list (all files with metadata)
5. A comprehensive study-guide PDF with course guides
6. A manifest.json describing the bundle
"""

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable

from django.utils import timezone

from . import paths, summarize
from .paths import BASE_DIR


# Default export directory
_EXPORT_ROOT = BASE_DIR / "_knowledge_packs"


def _ensure_export_root():
    _EXPORT_ROOT.mkdir(parents=True, exist_ok=True)


def _sanitize_filename(name: str) -> str:
    """Make a string safe for use as a filename."""
    safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in name)
    return safe.strip() or "untitled"


def _collect_profile_files(profile, subject_code: str | None = None) -> list:
    """Collect all MoveEvent files for a profile, optionally filtered by
    subject code. Returns list of dicts with file metadata."""
    from organizer.models import FileSummary, MoveEvent

    events = MoveEvent.objects.filter(profile=profile, success=True).order_by("-timestamp")
    if subject_code:
        events = events.filter(course_code=subject_code)

    files = []
    for event in events:
        if not event.destination_path:
            continue
        src = Path(event.destination_path)
        if not src.exists():
            continue

        summary = None
        try:
            if hasattr(event, "summary") and event.summary:
                summary = event.summary.content
        except FileSummary.DoesNotExist:
            pass

        files.append({
            "source_path": str(src),
            "filename": src.name,
            "course_code": event.course_code or "",
            "method": event.method,
            "timestamp": event.timestamp.isoformat() if event.timestamp else "",
            "summary": summary or "",
            "size_bytes": src.stat().st_size,
        })
    return files


def _build_folder_map(files: list) -> dict:
    """Build a nested folder structure from a list of file paths.

    Returns:
    {
        "root_name": "Subject",
        "children": [
            {"name": "01 Lecture Notes", "files": [...], "children": [...]},
        ]
    }
    """
    root: dict = {"name": "root", "files": [], "children": {}}

    for f in files:
        path = Path(f["source_path"])
        parts = list(path.parts)

        # Navigate to the profile-relative structure
        current = root
        for i, part in enumerate(parts[:-1]):  # all except filename
            if part not in current["children"]:
                current["children"][part] = {"name": part, "files": [], "children": {}}
            current = current["children"][part]
        current["files"].append(parts[-1])

    # Convert children dict to sorted list
    def _to_list(node):
        result = {"name": node["name"], "files": sorted(node["files"])}
        if node["children"]:
            result["children"] = sorted(
                (_to_list(v) for v in node["children"].values()),
                key=lambda x: x["name"].lower(),
            )
        return result

    top = sorted(
        (_to_list(v) for v in root["children"].values()),
        key=lambda x: x["name"].lower(),
    )
    return {"structure": top, "total_files": len(files)}


def _build_reading_list(files: list, profile_name: str) -> str:
    """Build a formatted reading list (Markdown)."""
    lines = [
        f"# Reading List: {profile_name}",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"Total files: {len(files)}",
        "",
        "---",
        "",
    ]

    # Group by subject code
    by_subject: dict[str, list] = {}
    for f in files:
        code = f["course_code"] or "_Uncategorized"
        by_subject.setdefault(code, []).append(f)

    for code in sorted(by_subject.keys()):
        subject_files = by_subject[code]
        lines.append(f"## {code}")
        lines.append(f"({len(subject_files)} files)")
        lines.append("")
        for f in sorted(subject_files, key=lambda x: x["filename"]):
            size_kb = f["size_bytes"] / 1024
            lines.append(f"- **{f['filename']}** ({size_kb:.0f} KB, {f['method']})")
            if f.get("timestamp"):
                lines.append(f"  - Sorted: {f['timestamp']}")
            if f.get("summary"):
                lines.append(f"  - Has AI summary")
        lines.append("")

    return "\n".join(lines)


def _build_flashcard_sheet(profile, subject_code: str | None = None) -> str:
    """A Markdown Q/A sheet from active Flashcards -- returns "" (no file
    written by the caller) if there are none in scope, never an empty
    placeholder section."""
    from organizer.models import Flashcard

    cards = Flashcard.objects.filter(profile=profile, status="active")
    if subject_code:
        cards = cards.filter(subject_code=subject_code)
    if not cards.exists():
        return ""

    type_labels = dict(Flashcard.CARD_TYPE_CHOICES)
    by_type: dict[str, list] = {}
    for card in cards.order_by("subject_code", "card_type", "-created_at"):
        by_type.setdefault(card.card_type, []).append(card)

    lines = [f"# Flashcards: {profile.name}", ""]
    for card_type, cards_of_type in by_type.items():
        lines.append(f"## {type_labels.get(card_type, card_type)}")
        lines.append("")
        for card in cards_of_type:
            subject_prefix = f"[{card.subject_code}] " if card.subject_code else ""
            lines.append(f"**Q:** {subject_prefix}{card.front}")
            back = card.back.strip() if card.back.strip() else "*(answer not recorded, fill in from your own notes)*"
            lines.append(f"**A:** {back}")
            lines.append("")
    return "\n".join(lines)


def _build_past_paper_brief(profile, subject_code: str | None = None) -> str:
    """A short Markdown brief of each relevant PastPaperAnalysis' top
    topics -- returns "" if there's no analysis in scope."""
    from organizer.models import PastPaperAnalysis

    analyses = PastPaperAnalysis.objects.filter(profile=profile)
    if subject_code:
        analyses = analyses.filter(subject_code=subject_code)
    if not analyses.exists():
        return ""

    lines = [f"# Past Paper Intelligence: {profile.name}", ""]
    for analysis in analyses.order_by("subject_code"):
        lines.append(f"## {analysis.subject_code}")
        lines.append(f"{analysis.paper_count} paper(s) analyzed, {len(analysis.questions)} question(s) extracted.")
        lines.append("")
        if analysis.topics:
            lines.append("High-probability revision areas:")
            for topic in analysis.topics[:10]:
                lines.append(f"- {topic.get('name', '')} (weight {topic.get('weight', 0)})")
            lines.append("")
    return "\n".join(lines)


def _build_revision_priorities(profile, subject_code: str | None = None) -> str:
    """Weak topics (from the Weakness Radar) plus grade-target projections
    -- returns "" if there's nothing to report in scope."""
    from organizer.models import GradeTarget

    from . import grade_planner, weakness_radar

    weak_rows = weakness_radar.build_radar(profile)["subject_weak_areas"]
    if subject_code:
        weak_rows = [row for row in weak_rows if row["code"] == subject_code]

    targets = GradeTarget.objects.filter(profile=profile)
    if subject_code:
        targets = targets.filter(subject_code=subject_code)

    if not weak_rows and not targets.exists():
        return ""

    lines = [f"# Revision Priorities: {profile.name}", ""]
    if weak_rows:
        lines.append("## Weak topics")
        for row in weak_rows:
            for area in row["weak_areas"]:
                lines.append(f"- {row['code']}: {area}")
        lines.append("")
    if targets.exists():
        lines.append("## Grade targets")
        for target in targets:
            result = grade_planner.required_exam_score(
                coursework_weight=target.coursework_weight,
                coursework_score=target.coursework_score,
                test_weight=target.test_weight,
                test_score=target.test_score,
                exam_weight=target.exam_weight,
                target_percent=target.target_percent,
            )
            lines.append(f"- {target.subject_code}: {result['message']}")
        lines.append("")
    return "\n".join(lines)


def _generate_study_guide_pdf(
    title: str,
    files: list,
    profile,
    subject_code: str | None = None,
) -> bytes | None:
    """Generate a study-guide PDF with course overview, file index,
    summaries, and (if available) AI course guides.

    Returns PDF bytes or None on failure.
    """
    from io import BytesIO

    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    from . import summarize as summarize_core

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=0.8 * inch,
        rightMargin=0.8 * inch,
        topMargin=0.8 * inch,
        bottomMargin=0.8 * inch,
        title=title,
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], spaceAfter=14, fontSize=18)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], spaceBefore=16, spaceAfter=8, fontSize=14)
    h3 = ParagraphStyle("H3", parent=styles["Heading3"], spaceBefore=12, spaceAfter=6, fontSize=12)
    body = ParagraphStyle("Body", parent=styles["BodyText"], leading=14, spaceAfter=8, fontSize=10)
    small = ParagraphStyle("Small", parent=body, fontSize=8, textColor="grey")

    story = []

    # Title page
    story.append(Paragraph(f"<b>{title}</b>", h1))
    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} for {profile.name}",
            body,
        )
    )
    story.append(Spacer(1, 20))

    # Course guide section (if available for a specific subject)
    if subject_code:
        from organizer.models import CourseGuide

        guide = CourseGuide.objects.filter(profile=profile, course_code=subject_code).first()
        if guide:
            story.append(Paragraph("Course Guide", h2))
            story.append(Spacer(1, 8))
            # Parse the structured content and render it
            for kind, text in summarize_core.parse_structured_text(guide.content):
                safe = summarize_core._inline_markup(text, bold_tag="b")
                if kind == "h1":
                    story.append(Paragraph(safe, h1))
                elif kind == "h2":
                    story.append(Paragraph(safe, h2))
                elif kind == "li":
                    story.append(Paragraph(f"• {safe}", body))
                else:
                    story.append(Paragraph(safe, body))
            story.append(Spacer(1, 16))

    # File index
    story.append(Paragraph("File Index", h2))
    story.append(Spacer(1, 8))

    by_subject: dict[str, list] = {}
    for f in files:
        code = f["course_code"] or "_Uncategorized"
        by_subject.setdefault(code, []).append(f)

    for code in sorted(by_subject.keys()):
        subject_files = by_subject[code]
        story.append(Paragraph(f"<b>{code}</b> ({len(subject_files)} files)", h3))
        for f in sorted(subject_files, key=lambda x: x["filename"]):
            size_kb = f["size_bytes"] / 1024
            story.append(Paragraph(
                f"{f['filename']} ({size_kb:.0f} KB, {f['method']})",
                body,
            ))
            if f.get("timestamp"):
                story.append(Paragraph(f"Sorted: {f['timestamp']}", small))
            if f.get("summary"):
                story.append(Paragraph("AI summary available", small))
        story.append(Spacer(1, 8))

    # Summaries section
    has_summaries = any(f.get("summary") for f in files)
    if has_summaries:
        story.append(Spacer(1, 12))
        story.append(Paragraph("Document Summaries", h2))
        story.append(Spacer(1, 8))

        for f in files:
            if not f.get("summary"):
                continue
            story.append(Paragraph(f"<b>{f['filename']}</b>", h3))
            for kind, text in summarize_core.parse_structured_text(f["summary"]):
                safe = summarize_core._inline_markup(text, bold_tag="b")
                if kind == "h1":
                    story.append(Paragraph(f"<b>{safe}</b>", h3))
                elif kind == "h2":
                    story.append(Paragraph(f"<i>{safe}</i>", h3))
                elif kind == "li":
                    story.append(Paragraph(f"• {safe}", body))
                else:
                    story.append(Paragraph(safe, body))
            story.append(Spacer(1, 10))

    doc.build(story)
    return buffer.getvalue()


def create_knowledge_pack(
    profile,
    scope: str = "profile",
    subject_code: str | None = None,
    title: str | None = None,
    log: Callable | None = None,
) -> dict:
    """Generate a complete portable knowledge pack.

    Args:
        profile: The Profile to export.
        scope: "profile", "subject", or "term".
        subject_code: Required for "subject" scope.
        title: Optional title (auto-generated if not given).
        log: Optional logging function.

    Returns:
        dict with keys: bundle_id, title, output_path, status, manifest.
    """
    from organizer.models import ExportBundle

    # Auto-generate title
    if not title:
        if scope == "subject" and subject_code:
            title = f"{subject_code}: Knowledge Pack"
        else:
            title = f"{profile.name}: Knowledge Pack"

    # Create the export bundle database record
    bundle = ExportBundle.objects.create(
        profile=profile,
        scope=scope,
        subject_code=subject_code or "",
        title=title,
        status="building",
    )

    # Determine output directory
    _ensure_export_root()
    safe_name = _sanitize_filename(title)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bundle_dir = _EXPORT_ROOT / f"{safe_name}_{timestamp}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Collect files
        if log:
            log(f"Collecting files for '{title}'...")
        files = _collect_profile_files(profile, subject_code)
        if not files:
            bundle.status = "failed"
            bundle.output_path = ""
            bundle.manifest = {"error": "No files found to export."}
            bundle.save()
            return {
                "bundle_id": bundle.pk,
                "title": title,
                "output_path": "",
                "status": "failed",
                "manifest": bundle.manifest,
            }

        # 2. Copy actual files to the bundle
        if log:
            log(f"Copying {len(files)} files...")
        files_dir = bundle_dir / "files"
        files_dir.mkdir(parents=True)
        copied_files = []
        for f in files:
            src = Path(f["source_path"])
            if not src.exists():
                continue
            # Preserve folder structure under files/
            rel_parts = Path(src).parts
            # Find the profile-relative path
            try:
                profile_idx = rel_parts.index(Path(profile.root_path).name)
                rel_path = Path(*rel_parts[profile_idx + 1:])
            except ValueError:
                rel_path = src.name
            dest = files_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(str(src), str(dest))
                copied_files.append(str(rel_path))
            except (OSError, shutil.Error) as exc:
                if log:
                    log(f"Failed to copy {src.name}: {exc}")

        # 3. Build folder map
        if log:
            log("Building folder map...")
        folder_map = _build_folder_map(files)
        map_path = bundle_dir / "folder_map.json"
        map_path.write_text(json.dumps(folder_map, indent=2), encoding="utf-8")

        # 4. Build reading list
        if log:
            log("Building reading list...")
        reading_list = _build_reading_list(files, profile.name)
        reading_path = bundle_dir / "reading_list.md"
        reading_path.write_text(reading_list, encoding="utf-8")

        # 5. Generate summaries (collect all into one file)
        if log:
            log("Collecting summaries...")
        summaries_dir = bundle_dir / "summaries"
        summaries_dir.mkdir(parents=True)
        summary_count = 0
        for f in files:
            if f.get("summary"):
                summary_file = summaries_dir / f"{_sanitize_filename(f['filename'])}_summary.html"
                try:
                    html = summarize.render_html(f["summary"])
                    summary_file.write_text(html, encoding="utf-8")
                    summary_count += 1
                except Exception as exc:
                    if log:
                        log(f"Failed to render summary for {f['filename']}: {exc}")

        # 6. Generate study-guide PDF
        if log:
            log("Generating study-guide PDF...")
        pdf_bytes = _generate_study_guide_pdf(title, files, profile, subject_code)
        if pdf_bytes:
            pdf_path = bundle_dir / f"{_sanitize_filename(title)}_study_guide.pdf"
            pdf_path.write_bytes(pdf_bytes)

        # 6b. Revision content: flashcards, past-paper brief, weak areas +
        # grade targets. Each is skipped entirely (no file written) rather
        # than writing an empty placeholder when there's nothing in scope.
        if log:
            log("Building revision content...")
        pack_subject_code = subject_code if scope == "subject" else None

        flashcard_sheet = _build_flashcard_sheet(profile, pack_subject_code)
        has_flashcard_sheet = bool(flashcard_sheet)
        if has_flashcard_sheet:
            (bundle_dir / "flashcards.md").write_text(flashcard_sheet, encoding="utf-8")

        past_paper_brief = _build_past_paper_brief(profile, pack_subject_code)
        has_past_paper_brief = bool(past_paper_brief)
        if has_past_paper_brief:
            (bundle_dir / "past_paper_analysis.md").write_text(past_paper_brief, encoding="utf-8")

        revision_priorities = _build_revision_priorities(profile, pack_subject_code)
        has_revision_priorities = bool(revision_priorities)
        if has_revision_priorities:
            (bundle_dir / "revision_priorities.md").write_text(revision_priorities, encoding="utf-8")

        # 7. Build manifest
        manifest = {
            "title": title,
            "profile": profile.name,
            "scope": scope,
            "subject_code": subject_code or "",
            "generated_at": datetime.now().isoformat(),
            "total_files": len(files),
            "files_copied": len(copied_files),
            "summaries": summary_count,
            "has_folder_map": True,
            "has_reading_list": True,
            "has_study_guide_pdf": pdf_bytes is not None,
            "has_flashcard_sheet": has_flashcard_sheet,
            "has_past_paper_brief": has_past_paper_brief,
            "has_revision_priorities": has_revision_priorities,
            "folder_structure": folder_map["structure"],
        }
        manifest_path = bundle_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        # 8. Create ZIP archive
        if log:
            log("Creating ZIP archive...")
        zip_path = _EXPORT_ROOT / f"{safe_name}_{timestamp}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in bundle_dir.rglob("*"):
                if item.is_file():
                    arcname = str(item.relative_to(bundle_dir))
                    zf.write(str(item), arcname)

        # Update bundle record
        bundle.status = "ready"
        bundle.output_path = str(zip_path)
        bundle.manifest = manifest
        bundle.save()

        if log:
            log(f"Knowledge pack ready: {zip_path}")

        return {
            "bundle_id": bundle.pk,
            "title": title,
            "output_path": str(zip_path),
            "status": "ready",
            "manifest": manifest,
        }

    except Exception as exc:
        bundle.status = "failed"
        bundle.manifest = {"error": str(exc)}
        bundle.save()
        if log:
            log(f"Knowledge pack failed: {exc}")
        return {
            "bundle_id": bundle.pk,
            "title": title,
            "output_path": "",
            "status": "failed",
            "manifest": bundle.manifest,
        }