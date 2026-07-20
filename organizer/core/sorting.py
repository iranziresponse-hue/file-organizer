"""Sorting and trust layer — rule execution, inbox approval workflow,
and import-from-existing-folders apply logic.

Completes the three unfinished features:
1. Folder Rule Builder — execute rules against incoming files
2. Inbox Mode — approve/reroute/ignore files in the decision inbox
3. Import From Existing Folders — approve and apply import plans
"""

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable

from django.utils import timezone

from . import makerere_curricula, paths, rules


# ---------------------------------------------------------------------------
# 1. Folder Rule Execution
# ---------------------------------------------------------------------------

def evaluate_rule(rule, filename: str, file_path: Path) -> tuple[bool, str | None]:
    """Evaluate a FolderRule against a filename.

    Returns (matched, destination_path_or_None).
    """
    from organizer.models import Profile

    target = filename if rule.match_field == "filename" else file_path.suffix.lower()
    if rule.match_field == "extension":
        target = file_path.suffix.lstrip(".").lower()
    elif rule.match_field == "source_path":
        target = str(file_path)

    # File extension filter
    if rule.file_extensions:
        ext = file_path.suffix.lstrip(".").lower()
        if ext not in rule.file_extensions:
            return False, None

    # Match
    matched = False
    pattern = rule.pattern
    if rule.operator == "contains":
        matched = pattern.lower() in target.lower()
    elif rule.operator == "equals":
        matched = target.lower() == pattern.lower()
    elif rule.operator == "starts_with":
        matched = target.lower().startswith(pattern.lower())
    elif rule.operator == "ends_with":
        matched = target.lower().endswith(pattern.lower())
    elif rule.operator == "regex":
        try:
            matched = bool(re.search(pattern, target, re.IGNORECASE))
        except re.error:
            matched = False

    if not matched:
        return False, None

    # Action: ignore — return True with no destination
    if rule.action == "ignore":
        return True, "__IGNORE__"

    # Action: review — return True with inbox signal
    if rule.action == "review":
        return True, "__INBOX__"

    # Action: route — build destination path
    if rule.action == "route" and rule.subject_code:
        profile = rule.profile
        config = rules.load_config(profile.root_path)
        if config:
            dest = (
                Path(profile.root_path)
                / config.get("primary_value", "_Unknown")
                / config.get("secondary_value", "_Unknown")
                / rule.subject_code
                / (rule.category or "Study Material")
            )
        else:
            dest = Path(profile.root_path) / "_Routed" / rule.subject_code
        return True, str(dest)

    return True, None


def execute_rules_for_file(
    file_path: Path,
    profile,
    log: Callable | None = None,
) -> tuple[str | None, str | None]:
    """Run all enabled FolderRules against a file. Returns the first match.

    Returns (destination_path_or_signal, matched_rule_name_or_None).
    Signals: "__IGNORE__" = skip file, "__INBOX__" = send to inbox.
    """
    from organizer.models import FolderRule

    rules_qs = FolderRule.objects.filter(
        profile=profile, enabled=True
    ).order_by("priority")

    for rule in rules_qs:
        try:
            matched, dest = evaluate_rule(rule, file_path.name, file_path)
            if matched:
                if dest == "__IGNORE__":
                    if log:
                        log(f"Rule '{rule.name}' ignored '{file_path.name}'")
                    return "__IGNORE__", rule.name
                if dest == "__INBOX__":
                    if log:
                        log(f"Rule '{rule.name}' sent '{file_path.name}' to inbox")
                    return "__INBOX__", rule.name
                if dest:
                    return dest, rule.name
        except Exception as exc:
            if log:
                log(f"Rule '{rule.name} failed for '{file_path.name}': {exc}")

    return None, None


# ---------------------------------------------------------------------------
# 2. Inbox Approval Workflow
# ---------------------------------------------------------------------------

def create_inbox_item(
    filename: str,
    source_path: str,
    profile=None,
    suggested_subject: str = "",
    suggested_destination: str = "",
    confidence: float = 0.0,
    reason: str = "",
) -> object:
    """Create a SortingInboxItem for manual approval."""
    from organizer.models import SortingInboxItem

    item = SortingInboxItem.objects.create(
        profile=profile,
        filename=filename,
        source_path=source_path,
        suggested_subject=suggested_subject[:32],
        suggested_destination=suggested_destination,
        confidence=confidence,
        reason=reason[:240],
        status="pending",
    )
    return item


def approve_inbox_item(item, log: Callable | None = None) -> bool:
    """Approve a pending inbox item — move the file to its suggested destination.

    Returns True on success.
    """
    if item.status != "pending":
        return False

    dest_path = Path(item.suggested_destination) if item.suggested_destination else None
    source = Path(item.source_path) if item.source_path else None

    if not dest_path or not source or not source.exists():
        item.status = "ignored"
        item.save()
        return False

    try:
        dest_path.mkdir(parents=True, exist_ok=True)
        dest_file = dest_path / item.filename
        if dest_file.exists():
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            dest_file = dest_path / f"{dest_file.stem}_{stamp}{dest_file.suffix}"
        shutil.move(str(source), str(dest_file))
        item.status = "approved"
        item.resolved_at = timezone.now()
        item.save()

        from .watcher import _record_event
        _record_event(
            profile=item.profile,
            filename=item.filename,
            source_path=str(source),
            destination_path=str(dest_file),
            method="course_code",
            course_code=item.suggested_subject or "",
            success=True,
        )
        return True
    except OSError as exc:
        if log:
            log(f"Failed to approve inbox item '{item.filename}': {exc}")
        item.status = "ignored"
        item.save()
        return False


def reroute_inbox_item(item, new_destination: str, log: Callable | None = None) -> bool:
    """Reroute a pending inbox item to a different destination the user
    picked themselves, then move it there. Marked "rerouted" rather than
    "approved" so the inbox stats can tell how often Orch's own suggestion
    needed correcting."""
    if item.status != "pending":
        return False

    item.suggested_destination = new_destination
    item.save()

    moved = approve_inbox_item(item, log=log)
    if moved:
        item.status = "rerouted"
        item.save()
    return moved


def ignore_inbox_item(item) -> None:
    """Ignore a pending inbox item (mark as ignored, leave file in place)."""
    if item.status != "pending":
        return
    item.status = "ignored"
    item.resolved_at = timezone.now()
    item.save()


def get_pending_inbox(profile, limit: int = 50):
    """Get all pending inbox items for a profile."""
    from organizer.models import SortingInboxItem

    return SortingInboxItem.objects.filter(
        profile=profile, status="pending"
    ).order_by("-created_at")[:limit]


def get_inbox_stats(profile) -> dict:
    """Get inbox statistics for a profile."""
    from organizer.models import SortingInboxItem

    return {
        "pending": SortingInboxItem.objects.filter(profile=profile, status="pending").count(),
        "approved": SortingInboxItem.objects.filter(profile=profile, status="approved").count(),
        "rerouted": SortingInboxItem.objects.filter(profile=profile, status="rerouted").count(),
        "ignored": SortingInboxItem.objects.filter(profile=profile, status="ignored").count(),
        "total": SortingInboxItem.objects.filter(profile=profile).count(),
    }


# ---------------------------------------------------------------------------
# 3. Import From Existing Folders — Approve & Apply
# ---------------------------------------------------------------------------

def approve_import_plan(plan, profile, log: Callable | None = None) -> bool:
    """Approve an import plan — adopt proposed subjects and rules.

    Returns True on success.
    """
    if plan.status not in ("draft", "scanned"):
        return False

    from organizer.models import CourseConfig

    plan.status = "approved"
    plan.save()

    # Adopt proposed subjects into the profile's config. Mutate the
    # profile's own cached `.config` (rather than a fresh query) so a
    # caller already holding `profile` sees the update reflected too.
    try:
        config = profile.config
    except CourseConfig.DoesNotExist:
        config = None
    if config and plan.proposed_subjects:
        existing = set(config.groups or [])
        new_subjects = [s for s in plan.proposed_subjects if s not in existing]
        if new_subjects:
            config.groups = list(existing) + new_subjects
            config.save()

    # Create FolderRules for proposed rules
    from organizer.models import FolderRule

    rules_created = 0
    for rule_data in plan.proposed_rules:
        existing = FolderRule.objects.filter(
            profile=profile,
            name=rule_data.get("name", ""),
        ).first()
        if existing:
            continue
        FolderRule.objects.create(
            profile=profile,
            name=rule_data.get("name", f"Import rule {rules_created + 1}")[:120],
            priority=100 + rules_created,
            match_field=rule_data.get("match_field", "filename"),
            operator=rule_data.get("operator", "contains"),
            pattern=rule_data.get("pattern", ""),
            subject_code=rule_data.get("subject_code", ""),
            category=rule_data.get("category", "Study Material"),
            action=rule_data.get("action", "route"),
            enabled=True,
        )
        rules_created += 1

    if log:
        log(f"Import plan approved: {len(plan.proposed_subjects)} subjects, {rules_created} rules")

    return True


def apply_import_plan(plan, profile, log: Callable | None = None) -> bool:
    """Apply an approved import plan — create folder structure.

    Creates the folder hierarchy defined by the plan's discovered folders
    under the profile's root path.

    Returns True on success.
    """
    if plan.status != "approved":
        if log:
            log(f"Cannot apply plan in status '{plan.status}', must be 'approved' first")
        return False

    root = Path(plan.root_path)
    if not root.exists():
        if log:
            log(f"Import root '{root}' does not exist")
        return False

    from organizer.models import CourseConfig

    config = CourseConfig.objects.filter(profile=profile).first()
    if not config:
        if log:
            log("Profile has no config, cannot create folder structure")
        return False

    profile_root = Path(profile.root_path)
    primary = config.primary_value
    secondary = config.secondary_value

    folders_created = 0
    for folder_path in plan.discovered_folders:
        parts = folder_path.split("/")
        if len(parts) >= 2:
            # Structure: <subject>/<category>
            subject, category = parts[0], "/".join(parts[1:])
            dest = profile_root / primary / secondary / subject / category
        elif len(parts) == 1:
            dest = profile_root / primary / secondary / parts[0]
        else:
            continue

        try:
            dest.mkdir(parents=True, exist_ok=True)
            folders_created += 1
        except OSError as exc:
            if log:
                log(f"Failed to create folder '{dest}': {exc}")

    plan.status = "imported"
    plan.save()

    if log:
        log(f"Import applied: {folders_created} folders created under '{profile_root}'")

    return True


def reject_import_plan(plan) -> None:
    """Reject an import plan."""
    if plan.status in ("draft", "scanned", "approved"):
        plan.status = "rejected"
        plan.save()


def ensure_subject_folders(profile) -> dict:
    """Make sure every subject/course-unit folder for this profile's
    current config exists on disk, and that there's only ever ONE folder
    per subject -- never a bare "CODE" sitting alongside a "CODE - Name"
    for the same course.

    - If "CODE - Name" already exists: nothing to do.
    - If only bare "CODE" exists and the real name is known: renamed to
      "CODE - Name" in place (contents preserved) -- a bare code folder is
      never left as a redundant duplicate once its name is knowable.
    - If neither exists: created fresh, named if the name is known.
    - If the name isn't known (not a Makerere course Orch has researched,
      or a manually-typed subject): stays as bare "CODE", same as before.

    Returns {"created": [codes], "existing": [codes], "renamed": [codes]}.
    """
    config = getattr(profile, "config", None)
    if not profile or not profile.root_path or not config or not config.groups:
        return {"created": [], "existing": [], "renamed": []}

    base = Path(profile.root_path) / config.primary_value / config.secondary_value
    created, existing, renamed = [], [], []

    for code in config.groups:
        name = makerere_curricula.name_for_code(code)
        named_folder = (base / f"{code} - {name}") if name else None
        bare_folder = base / code

        if named_folder and named_folder.exists():
            existing.append(code)
        elif bare_folder.exists():
            if named_folder:
                bare_folder.rename(named_folder)
                renamed.append(code)
            else:
                existing.append(code)
        else:
            target = named_folder or bare_folder
            target.mkdir(parents=True, exist_ok=True)
            created.append(code)

    return {"created": created, "existing": existing, "renamed": renamed}