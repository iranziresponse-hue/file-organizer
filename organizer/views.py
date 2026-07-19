import json
import re
import string
from pathlib import Path

from django.contrib import messages
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .core import makerere, paths
from .core import summarize as summarize_core
from .models import AppSettings, CourseConfig, CourseGuide, FileSummary, MoveEvent, Profile

PURPOSE_LABEL_DEFAULTS = {
    "school": {"primary_label": "Year", "secondary_label": "Semester"},
    "online": {"primary_label": "Year", "secondary_label": "Course"},
    "research": {"primary_label": "Topic", "secondary_label": "Phase"},
    "work": {"primary_label": "Department", "secondary_label": "Training Cycle"},
    "custom": {"primary_label": "Year", "secondary_label": "Semester"},
}


def _write_config_json(profile, config):
    payload = {
        "_comment": (
            "Edit this from the Orch dashboard, or by hand at the start of a "
            f"new {profile.secondary_label.lower()}. primary_value/"
            f"secondary_value become folder names under {profile.root_path}."
        ),
        "primary_value": config.primary_value,
        "secondary_value": config.secondary_value,
        "groups": config.groups,
    }
    try:
        target = paths.config_path(profile.root_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return True, None
    except OSError as exc:
        return False, str(exc)


def _parse_groups(raw):
    return [g.strip() for g in raw.split(",") if g.strip()]


_SKIP_DIR_NAMES = {"$recycle.bin", "system volume information"}


def _is_accessible_dir(path):
    try:
        return path.is_dir()
    except OSError:
        return False


def browse_folders(request):
    """Read-only directory listing of this machine's own filesystem, used by
    the folder-browser picker and the existing-subfolder suggestions in the
    profile forms. The dashboard only ever binds to 127.0.0.1 (see
    gui/server.py), so this is local-machine-only, same trust boundary as
    everything else here -- no separate auth layer, consistent with the rest
    of the app.
    """
    raw_path = request.GET.get("path", "").strip()

    if not raw_path:
        drives = []
        for letter in string.ascii_uppercase:
            root = Path(f"{letter}:/")
            if _is_accessible_dir(root):
                drives.append({"name": f"{letter}:\\", "path": str(root)})
        return JsonResponse({"path": "", "parent": None, "folders": drives})

    path = Path(raw_path)
    if not _is_accessible_dir(path):
        return JsonResponse({"error": "That folder doesn't exist or can't be opened."}, status=400)

    try:
        children = [
            p for p in path.iterdir()
            if _is_accessible_dir(p) and not p.name.startswith(".") and p.name.lower() not in _SKIP_DIR_NAMES
        ]
    except OSError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    folders = sorted(
        ({"name": p.name, "path": str(p)} for p in children),
        key=lambda f: f["name"].lower(),
    )
    parent = str(path.parent) if path.parent != path else None
    return JsonResponse({"path": str(path), "parent": parent, "folders": folders})


def dashboard(request):
    profile = Profile.get_active()
    events = MoveEvent.objects.filter(profile=profile) if profile else MoveEvent.objects.none()
    recent_events = events[:50]
    method_counts = list(events.values("method").annotate(total=Count("id")).order_by("-total"))
    method_labels = dict(MoveEvent.METHOD_CHOICES)
    for row in method_counts:
        row["label"] = method_labels.get(row["method"], row["method"])
    course_counts = (
        events.exclude(course_code__isnull=True)
        .exclude(course_code="")
        .values("course_code")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    config = getattr(profile, "config", None) if profile else None
    guided_codes = set(
        CourseGuide.objects.filter(profile=profile).values_list("course_code", flat=True)
    ) if profile else set()

    context = {
        "profile": profile,
        "has_any_profile": Profile.objects.exists(),
        "recent_events": recent_events,
        "method_counts": method_counts,
        "course_counts": course_counts,
        "config": config,
        "guided_codes": guided_codes,
        "total_moves": events.count(),
    }
    return render(request, "organizer/dashboard.html", context)


def profiles_list(request):
    profiles = Profile.objects.all()
    return render(request, "organizer/profiles_list.html", {"profiles": profiles})


def profile_wizard(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        purpose = request.POST.get("purpose") or "custom"
        primary_label = request.POST.get("primary_label", "").strip() or "Year"
        secondary_label = request.POST.get("secondary_label", "").strip() or "Semester"
        root_path = request.POST.get("root_path", "").strip()
        primary_value = request.POST.get("primary_value", "").strip()
        secondary_value = request.POST.get("secondary_value", "").strip()
        groups = _parse_groups(request.POST.get("groups", ""))
        ai_fallback_enabled = bool(request.POST.get("ai_fallback_enabled"))

        if not name or not root_path:
            messages.error(request, "A profile needs at least a name and a folder to organize into.")
            return render(request, "organizer/profile_wizard.html", {
                "purposes": Profile.PURPOSE_CHOICES,
                "purpose_defaults": PURPOSE_LABEL_DEFAULTS,
                "form": request.POST,
            })

        profile = Profile.objects.create(
            name=name,
            purpose=purpose,
            primary_label=primary_label,
            secondary_label=secondary_label,
            root_path=root_path,
            ai_fallback_enabled=ai_fallback_enabled,
            is_active=True,
        )
        config = CourseConfig.objects.create(
            profile=profile,
            primary_value=primary_value,
            secondary_value=secondary_value,
            groups=groups,
        )
        ok, error = _write_config_json(profile, config)
        if ok:
            messages.success(request, f"'{profile.name}' is set up and active.")
        else:
            messages.error(request, f"Profile saved, but could not write _config.json: {error}")

        return redirect("dashboard")

    return render(request, "organizer/profile_wizard.html", {
        "purposes": Profile.PURPOSE_CHOICES,
        "purpose_defaults": PURPOSE_LABEL_DEFAULTS,
    })


def start(request):
    """First stop when setting up a profile: a Makerere-specific guided
    path, or the generic wizard for everyone else."""
    return render(request, "organizer/start.html")


def makerere_wizard(request):
    colleges_json = makerere.as_json()

    if request.method == "POST":
        college_name = request.POST.get("college", "").strip()
        school_name = request.POST.get("school", "").strip()
        program = request.POST.get("program", "").strip()
        year_value = request.POST.get("year_value", "").strip()
        semester_value = request.POST.get("semester_value", "").strip()
        root_path = request.POST.get("root_path", "").strip()
        groups = _parse_groups(request.POST.get("groups", ""))
        ai_fallback_enabled = bool(request.POST.get("ai_fallback_enabled"))

        college = makerere.get_college_by_name(college_name)

        if not college or not school_name or not program or not root_path or not year_value or not semester_value:
            messages.error(
                request,
                "Pick your college and school, fill in your program, year, semester, and a folder to organize into.",
            )
            return render(request, "organizer/makerere_wizard.html", {
                "colleges": makerere.COLLEGES,
                "colleges_json": colleges_json,
                "default_root_hint": str(paths.PERSONAL_ROOT / "Makerere"),
                "form": request.POST,
            })

        profile_name = f"{program} ({college['code']}) - Makerere University"
        profile = Profile.objects.create(
            name=profile_name,
            purpose="school",
            primary_label="Year",
            secondary_label="Semester",
            root_path=root_path,
            ai_fallback_enabled=ai_fallback_enabled,
            is_active=True,
        )
        config = CourseConfig.objects.create(
            profile=profile,
            primary_value=f"Year {year_value}",
            secondary_value=f"Semester {semester_value}",
            groups=groups,
        )
        ok, error = _write_config_json(profile, config)
        if ok:
            messages.success(request, f"'{profile.name}' is set up and active.")
        else:
            messages.error(request, f"Profile saved, but could not write _config.json: {error}")

        return redirect("dashboard")

    return render(request, "organizer/makerere_wizard.html", {
        "colleges": makerere.COLLEGES,
        "colleges_json": colleges_json,
        "default_root_hint": str(paths.PERSONAL_ROOT / "Makerere"),
    })


def profile_edit(request, pk):
    profile = get_object_or_404(Profile, pk=pk)
    config = getattr(profile, "config", None)

    if request.method == "POST":
        profile.name = request.POST.get("name", "").strip() or profile.name
        profile.primary_label = request.POST.get("primary_label", "").strip() or profile.primary_label
        profile.secondary_label = request.POST.get("secondary_label", "").strip() or profile.secondary_label
        profile.root_path = request.POST.get("root_path", "").strip() or profile.root_path
        profile.ai_fallback_enabled = bool(request.POST.get("ai_fallback_enabled"))
        profile.save()

        if config is None:
            config = CourseConfig(profile=profile)
        config.primary_value = request.POST.get("primary_value", "").strip()
        config.secondary_value = request.POST.get("secondary_value", "").strip()
        config.groups = _parse_groups(request.POST.get("groups", ""))
        config.save()

        ok, error = _write_config_json(profile, config)
        if ok:
            messages.success(request, "Profile updated.")
        else:
            messages.error(request, f"Saved to database but could not write _config.json: {error}")

        return redirect("profile_edit", pk=profile.pk)

    return render(request, "organizer/profile_edit.html", {"profile": profile, "config": config})


def profile_activate(request, pk):
    profile = get_object_or_404(Profile, pk=pk)
    if request.method == "POST":
        profile.is_active = True
        profile.save()
        messages.success(request, f"'{profile.name}' is now active.")
    return redirect("profiles_list")


def profile_delete(request, pk):
    profile = get_object_or_404(Profile, pk=pk)
    if request.method == "POST":
        name = profile.name
        profile.delete()
        messages.success(request, f"Deleted '{name}'.")
    return redirect("profiles_list")


def settings_edit(request):
    settings = AppSettings.get_solo()

    if request.method == "POST":
        settings.downloads_path = request.POST.get("downloads_path", "").strip() or settings.downloads_path
        settings.secondary_downloads_path = request.POST.get("secondary_downloads_path", "").strip()
        settings.library_inbox_path = request.POST.get("library_inbox_path", "").strip() or settings.library_inbox_path
        try:
            settings.installer_stale_days = max(1, int(request.POST.get("installer_stale_days", "")))
        except ValueError:
            pass
        try:
            settings.installer_delete_days = max(1, int(request.POST.get("installer_delete_days", "")))
        except ValueError:
            pass
        settings.save()
        messages.success(request, "Settings saved.")
        return redirect("settings_edit")

    return render(request, "organizer/settings_edit.html", {
        "settings": settings,
        "default_downloads": str(paths.DEFAULT_DOWNLOADS),
        "default_library_inbox": str(paths.DEFAULT_LIBRARY_INBOX),
    })


def move_summarize(request, pk):
    if request.method != "POST":
        return JsonResponse({"error": "POST required."}, status=405)

    event = get_object_or_404(MoveEvent, pk=pk)
    content, error = summarize_core.generate_summary(event.destination_path)
    if error:
        return JsonResponse({"error": error}, status=400)

    FileSummary.objects.update_or_create(move_event=event, defaults={"content": content})
    return JsonResponse({"ok": True})


def move_summary_view(request, pk):
    event = get_object_or_404(MoveEvent, pk=pk)
    summary = getattr(event, "summary", None)
    if summary is None:
        return JsonResponse({"error": "No summary yet -- generate one first."}, status=404)

    return JsonResponse({
        "filename": event.filename,
        "html": summarize_core.render_html(summary.content),
        "created_at": summary.created_at.strftime("%Y-%m-%d %H:%M"),
    })


def move_summary_pdf(request, pk):
    event = get_object_or_404(MoveEvent, pk=pk)
    summary = getattr(event, "summary", None)
    if summary is None:
        return HttpResponse("No summary yet.", status=404)

    pdf_bytes = summarize_core.render_pdf(event.filename, summary.content)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    safe_name = re.sub(r"[^\w\-. ]", "_", Path(event.filename).stem) or "summary"
    response["Content-Disposition"] = f'attachment; filename="{safe_name} summary.pdf"'
    return response


def course_guide_generate(request, profile_pk, code):
    if request.method != "POST":
        return JsonResponse({"error": "POST required."}, status=405)

    profile = get_object_or_404(Profile, pk=profile_pk)
    config = getattr(profile, "config", None)
    level = f"{config.primary_value} {config.secondary_value}".strip() if config else ""

    content, error = summarize_core.generate_course_guide(code, program=profile.name, level=level)
    if error:
        return JsonResponse({"error": error}, status=400)

    CourseGuide.objects.update_or_create(profile=profile, course_code=code, defaults={"content": content})
    return JsonResponse({"ok": True})


def course_guide_view(request, profile_pk, code):
    profile = get_object_or_404(Profile, pk=profile_pk)
    guide = CourseGuide.objects.filter(profile=profile, course_code=code).first()
    if guide is None:
        return JsonResponse({"error": "No guide yet -- generate one first."}, status=404)

    return JsonResponse({
        "course_code": code,
        "html": summarize_core.render_html(guide.content),
        "created_at": guide.created_at.strftime("%Y-%m-%d %H:%M"),
    })


def course_guide_pdf(request, profile_pk, code):
    profile = get_object_or_404(Profile, pk=profile_pk)
    guide = CourseGuide.objects.filter(profile=profile, course_code=code).first()
    if guide is None:
        return HttpResponse("No guide yet.", status=404)

    pdf_bytes = summarize_core.render_pdf(code, guide.content)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    safe_name = re.sub(r"[^\w\-. ]", "_", code) or "course-guide"
    response["Content-Disposition"] = f'attachment; filename="{safe_name} guide.pdf"'
    return response
