import json

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from .core import paths
from .models import AppSettings, CourseConfig, MoveEvent, Profile

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

    context = {
        "profile": profile,
        "has_any_profile": Profile.objects.exists(),
        "recent_events": recent_events,
        "method_counts": method_counts,
        "course_counts": course_counts,
        "config": config,
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
