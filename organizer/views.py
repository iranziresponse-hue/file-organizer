import json
import re
import string
from pathlib import Path

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .core import (
    digest as digest_core,
    makerere,
    makerere_curricula,
    muele_api,
    muele_downloader,
    notifications,
    owner_access,
    paths,
    study,
)
from .core import summarize as summarize_core
from .models import (
    AppSettings,
    CourseConfig,
    CourseGuide,
    ExportBundle,
    FileSummary,
    FolderImportPlan,
    FolderRule,
    IntegrationConnection,
    LearningActivity,
    LearningDigest,
    LearningRoute,
    MoveEvent,
    Profile,
    ResourceRecommendation,
    ReviewItem,
    SortingInboxItem,
    SubjectMemory,
    SubjectTheme,
    StudyGoal,
    SuggestedCourseUnit,
)

PURPOSE_LABEL_DEFAULTS = {
    "school": {"primary_label": "Year", "secondary_label": "Semester"},
    "online": {"primary_label": "Year", "secondary_label": "Course"},
    "research": {"primary_label": "Topic", "secondary_label": "Phase"},
    "work": {"primary_label": "Department", "secondary_label": "Training Cycle"},
    "custom": {"primary_label": "Year", "secondary_label": "Semester"},
}


def _owner_not_found():
    return HttpResponse("Not found", status=404)


def owner_console(request):
    if not owner_access.request_allowed(request):
        return _owner_not_found()

    User = get_user_model()
    if not User.objects.filter(is_staff=True).exists():
        return redirect("owner_setup")

    return redirect("admin:index")


def owner_setup(request):
    if not owner_access.request_allowed(request):
        return _owner_not_found()

    User = get_user_model()
    if User.objects.filter(is_staff=True).exists():
        return redirect("owner_console")

    errors = []
    values = {"username": "", "email": ""}

    if request.method == "POST":
        values["username"] = request.POST.get("username", "").strip()
        values["email"] = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if not values["username"]:
            errors.append("Choose an owner username.")
        elif User.objects.filter(username=values["username"]).exists():
            errors.append("That username is already in use.")

        if password != confirm_password:
            errors.append("The passwords do not match.")

        try:
            validate_password(password)
        except ValidationError as exc:
            errors.extend(exc.messages)

        if not errors:
            user = User.objects.create_superuser(
                username=values["username"],
                email=values["email"],
                password=password,
            )
            login(request, user)
            messages.success(request, "Owner access is ready.")
            return redirect("admin:index")

    return render(
        request,
        "organizer/owner_setup.html",
        {
            "errors": errors,
            "values": values,
            "owner_config_path": owner_access.owner_config_path(),
        },
    )


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


def _save_unverified_course_units(program, primary_value, secondary_value, codes):
    """When Orch has no verified curriculum for this program/year/semester,
    keep what the student actually typed so an admin can later check it
    against an official Makerere source and add it to makerere_curricula.py
    by hand. Never treated as verified, never shown to other students as fact."""
    if makerere_curricula.get_course_units(program, primary_value, secondary_value):
        return
    for code in codes:
        SuggestedCourseUnit.objects.get_or_create(
            program=program,
            primary_value=primary_value,
            secondary_value=secondary_value,
            code=code,
        )


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

    # Paginate recent events -- 25 per page instead of loading all 50 at once.
    paginator = Paginator(events, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # MUELE integration status for the dashboard panel
    muele_connection = None
    muele_courses_count = 0
    muele_upcoming_deadlines = []
    if profile:
        from .models import AssignmentItem, IntegrationConnection, MueleCourse

        muele_connection = IntegrationConnection.objects.filter(
            profile=profile, provider="muele"
        ).first()
        if muele_connection:
            muele_courses_count = MueleCourse.objects.filter(
                connection=muele_connection, auto_download=True
            ).count()
            muele_upcoming_deadlines = AssignmentItem.objects.filter(
                profile=profile, source="muele", status="open"
            ).order_by("due_at")[:5]

    context = {
        "profile": profile,
        "has_any_profile": Profile.objects.exists(),
        "page_obj": page_obj,
        "method_counts": method_counts,
        "course_counts": course_counts,
        "config": config,
        "guided_codes": guided_codes,
        "total_moves": events.count(),
        "muele_connection": muele_connection,
        "muele_courses_count": muele_courses_count,
        "muele_upcoming_deadlines": muele_upcoming_deadlines,
    }
    return render(request, "organizer/dashboard.html", context)


def profiles_list(request):
    profiles = Profile.objects.all()
    return render(request, "organizer/profiles_list.html", {"profiles": profiles})


def digest_overview(request):
    """Dedicated page showing all digests with detail view and generation."""
    from .core.contexts import get_context_for_profile

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    ctx = get_context_for_profile(profile)

    if request.method == "POST":
        action = request.POST.get("action", "")
        period = request.POST.get("period", "weekly")
        if action == "generate":
            if period == "daily":
                digest = digest_core.generate_daily_digest(profile)
            else:
                digest = digest_core.generate_weekly_digest(profile)
            if digest:
                messages.success(request, f"{period.title()} digest created.")
            else:
                messages.info(request, "No activity to report in this period.")
            return redirect("digest_overview")

    digests = digest_core.get_recent_digests(profile, limit=20)
    schedule_info = digest_core.get_digest_schedule_info(profile)

    return render(request, "organizer/digest_overview.html", {
        "profile": profile,
        "study_context": ctx,
        "digests": digests,
        "schedule_info": schedule_info,
    })


def digest_detail(request, pk):
    """View a single digest with full content."""
    from .core.contexts import get_context_for_profile

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    digest = get_object_or_404(LearningDigest, pk=pk, profile=profile)
    ctx = get_context_for_profile(profile)

    return render(request, "organizer/digest_detail.html", {
        "profile": profile,
        "study_context": ctx,
        "digest": digest,
    })


def export_bundles(request):
    """View and manage portable knowledge packs."""
    import os

    from django.http import FileResponse

    from .core.contexts import get_context_for_profile
    from .core import export as export_core

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    ctx = get_context_for_profile(profile)

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "create":
            scope = request.POST.get("scope", "profile")
            subject_code = request.POST.get("subject_code", "").strip()
            title = request.POST.get("title", "").strip()
            result = export_core.create_knowledge_pack(
                profile,
                scope=scope,
                subject_code=subject_code if scope == "subject" else None,
                title=title or None,
            )
            if result["status"] == "ready":
                messages.success(request, f"Knowledge pack ready: {result['title']}")
            elif result["status"] == "failed":
                messages.error(request, f"Export failed: {result['manifest'].get('error', 'Unknown error')}")
            return redirect("export_bundles")

    bundles = ExportBundle.objects.filter(profile=profile).order_by("-created_at")
    subject_memories = SubjectMemory.objects.filter(profile=profile)

    return render(request, "organizer/export_bundles.html", {
        "profile": profile,
        "study_context": ctx,
        "bundles": bundles,
        "subject_memories": subject_memories,
    })


def _sanitize_filename(name: str) -> str:
    """Make a string safe for use as a filename."""
    safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in name)
    return safe.strip() or "untitled"


def export_download(request, pk):
    """Download a knowledge pack ZIP file."""
    import os

    from django.http import FileResponse, Http404

    profile = Profile.get_active()
    bundle = get_object_or_404(ExportBundle, pk=pk, profile=profile)

    if bundle.status != "ready" or not bundle.output_path:
        messages.error(request, "This knowledge pack is not ready yet.")
        return redirect("export_bundles")

    zip_path = Path(bundle.output_path)
    if not zip_path.exists():
        messages.error(request, "The file no longer exists on disk.")
        return redirect("export_bundles")

    response = FileResponse(
        open(str(zip_path), "rb"),
        content_type="application/zip",
        as_attachment=True,
        filename=f"{_sanitize_filename(bundle.title)}.zip",
    )
    return response


def export_delete(request, pk):
    """Delete a knowledge pack."""
    import os

    profile = Profile.get_active()
    bundle = get_object_or_404(ExportBundle, pk=pk, profile=profile)
    if request.method == "POST":
        # Delete the ZIP file if it exists
        if bundle.output_path:
            try:
                Path(bundle.output_path).unlink(missing_ok=True)
            except OSError:
                pass
        bundle.delete()
        messages.success(request, f"Deleted '{bundle.title}'.")
    return redirect("export_bundles")


def resource_radar(request):
    """Recommend transparent video and book discovery links from subject
    memory, themes, weak areas, and recent files."""
    from .core import resources as resource_core
    from .core.contexts import get_context_for_profile

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    ctx = get_context_for_profile(profile)
    subject_code = request.GET.get("subject", "").strip()

    if request.method == "POST":
        action = request.POST.get("action", "")
        recommendation_pk = request.POST.get("recommendation_pk")

        if action == "generate":
            selected_subject = request.POST.get("subject_code", "").strip() or None
            created = resource_core.sync_recommendations(profile, subject_code=selected_subject, limit=24)
            messages.success(request, f"Resource Radar refreshed {len(created)} recommendation(s).")
            if selected_subject:
                return redirect(f"{reverse('resource_radar')}?subject={selected_subject}")
            return redirect("resource_radar")

        if recommendation_pk:
            item = get_object_or_404(ResourceRecommendation, pk=recommendation_pk, profile=profile)
            if action in {"saved", "suggested", "dismissed", "opened"}:
                resource_core.set_recommendation_status(item, action)
                return redirect(request.POST.get("next") or "resource_radar")

    recommendations = resource_core.recommendations_for_profile(
        profile,
        subject_code=subject_code or None,
        limit=40,
    )
    subject_memories = SubjectMemory.objects.filter(profile=profile).order_by("code")
    saved_count = ResourceRecommendation.objects.filter(profile=profile, status="saved").count()

    return render(request, "organizer/resource_radar.html", {
        "profile": profile,
        "study_context": ctx,
        "subject_memories": subject_memories,
        "recommendations": recommendations,
        "current_subject": subject_code,
        "saved_count": saved_count,
    })


def learning_routes(request):
    """Guided study routes from weak area to resource, summary, review,
    and confidence check."""
    from .core.contexts import get_context_for_profile
    from .core import learning_route as route_engine

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    ctx = get_context_for_profile(profile)

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "generate":
            subject_code = request.POST.get("subject_code", "").strip() or None
            # Refresh recommendations and routes
            from .core import resources as resource_core
            resource_core.sync_recommendations(profile, subject_code=subject_code, limit=24)
            messages.success(request, "Learning routes refreshed.")
            return redirect("learning_routes")

    route_context = route_engine.get_route_context(profile)

    return render(request, "organizer/learning_routes.html", {
        "profile": profile,
        "study_context": ctx,
        "routes": route_context["routes"],
        "total_subjects": route_context["total_subjects"],
        "total_steps": route_context["total_steps"],
        "complete_steps": route_context["complete_steps"],
        "completion_pct": route_context["completion_pct"],
    })


def study_home(request):
    from .core.contexts import get_context_for_profile

    profile = Profile.get_active()
    ctx = get_context_for_profile(profile)

    if profile and request.method == "POST" and request.POST.get("action") == "create_digest":
        result = digest_core.generate_weekly_digest(profile)
        if result:
            messages.success(request, "Weekly digest created.")
        else:
            messages.info(request, "No activity to report this week.")
        return redirect("study_home")

    foundation = study.ensure_learning_foundation(profile) if profile else {}
    context = {
        "profile": profile,
        "study_context": ctx,
        "foundation": foundation,
        "subject_memories": SubjectMemory.objects.filter(profile=profile) if profile and ctx.show_subject_memory else [],
        "subject_themes": SubjectTheme.objects.filter(profile=profile)[:12] if profile and ctx.show_subject_memory else [],
        "review_items": ReviewItem.objects.filter(profile=profile, status="queued")[:8] if profile and ctx.show_review_queue else [],
        "digests": LearningDigest.objects.filter(profile=profile)[:4] if profile else [],
        "activities": LearningActivity.objects.filter(profile=profile)[:12] if profile else [],
        "inbox_items": SortingInboxItem.objects.filter(profile=profile, status="pending")[:8] if profile else [],
        "connections": IntegrationConnection.objects.filter(profile=profile) if profile and ctx.show_integrations else [],
        "export_bundles": ExportBundle.objects.filter(profile=profile)[:4] if profile else [],
        "folder_rules": FolderRule.objects.filter(profile=profile)[:8] if profile else [],
        "import_plans": FolderImportPlan.objects.filter(profile=profile)[:4] if profile else [],
        "resource_recommendations": ResourceRecommendation.objects.filter(profile=profile).exclude(status="dismissed")[:6] if profile else [],
        "learning_routes": LearningRoute.objects.filter(profile=profile).exclude(status="done")[:4] if profile else [],
        "study_goals": StudyGoal.objects.filter(profile=profile)[:4] if profile and ctx.show_goal_tracking else [],
    }
    return render(request, "organizer/study.html", context)


def muele_connection(request):
    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Create or activate a Makerere profile first.")
        return redirect("start")

    connection = study.ensure_makerere_connection(profile)
    if connection is None:
        connection = IntegrationConnection.objects.create(
            profile=profile,
            provider="muele",
            display_name="Makerere MUELE",
            base_url=study.MUELE_BASE_URL,
            status="planned",
            config={
                "platform": "Moodle",
                "sync_targets": ["course_files", "assignments", "calendar"],
            },
        )

    if request.method == "POST":
        connection.username = request.POST.get("username", "").strip()
        connection.base_url = request.POST.get("base_url", "").strip() or study.MUELE_BASE_URL
        connection.status = "planned"
        connection.config = {
            **(connection.config or {}),
            "college": request.POST.get("college", "").strip(),
            "sync_targets": request.POST.getlist("sync_targets") or ["course_files", "assignments", "calendar"],
            "next_step": "Add secure credential storage and Moodle web service sync.",
        }
        connection.save()
        messages.success(request, "MUELE connection details saved.")
        return redirect("study_home")

    return render(request, "organizer/muele_connection.html", {
        "profile": profile,
        "connection": connection,
        "muele_url": study.MUELE_BASE_URL,
    })


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
            setup_path="manual",
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
        study.ensure_learning_foundation(profile)
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
    curricula_json = {name: data["years"] for name, data in makerere_curricula.CURRICULA.items()}

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
                "curricula_json": curricula_json,
                "default_root_hint": str(paths.PERSONAL_ROOT / "Makerere"),
                "form": request.POST,
            })

        profile_name = f"{program} ({college['code']}) - Makerere University"
        profile = Profile.objects.create(
            name=profile_name,
            purpose="school",
            setup_path="makerere",
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
        _save_unverified_course_units(program, config.primary_value, config.secondary_value, groups)
        ok, error = _write_config_json(profile, config)
        study.ensure_learning_foundation(profile)
        if ok:
            messages.success(request, f"'{profile.name}' is set up and active.")
        else:
            messages.error(request, f"Profile saved, but could not write _config.json: {error}")

        return redirect("dashboard")

    return render(request, "organizer/makerere_wizard.html", {
        "colleges": makerere.COLLEGES,
        "colleges_json": colleges_json,
        "curricula_json": curricula_json,
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


def review_queue(request):
    """Smart review queue with spaced repetition scheduling and user workflow."""
    from django.utils import timezone

    from .core.contexts import get_context_for_profile
    from .core import review as review_core

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    ctx = get_context_for_profile(profile)

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "auto_schedule":
            count = review_core.auto_schedule_reviews(profile)
            if count:
                messages.success(request, f"Scheduled {count} new review item(s).")
            else:
                messages.info(request, "No new items to schedule.")
            return redirect("review_queue")

    stats = review_core.get_stats(profile)
    due_items = review_core.get_due_reviews(profile, limit=20)
    recent_done = ReviewItem.objects.filter(profile=profile, status="done").order_by("-completed_at")[:5]
    overdue_count = review_core.reschedule_overdue(profile)

    return render(request, "organizer/review_queue.html", {
        "profile": profile,
        "study_context": ctx,
        "stats": stats,
        "due_items": due_items,
        "recent_done": recent_done,
        "now": timezone.now(),
    })


def review_mark_done(request, pk):
    """Mark a review item as completed."""
    from .core import review as review_core

    item = get_object_or_404(ReviewItem, pk=pk)
    if request.method == "POST":
        review_core.mark_review_done(item)
        messages.success(request, f"'{item.title}' marked as done.")
    return redirect("review_queue")


def review_skip(request, pk):
    """Skip a review item."""
    from .core import review as review_core

    item = get_object_or_404(ReviewItem, pk=pk)
    if request.method == "POST":
        review_core.skip_review(item)
        messages.info(request, f"'{item.title}' skipped.")
    return redirect("review_queue")


def timeline_view(request):
    """Rich visual timeline with filtering by type and time range."""
    from datetime import timedelta

    from django.utils import timezone

    from .core.contexts import get_context_for_profile

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    ctx = get_context_for_profile(profile)

    # Parse filters
    days = request.GET.get("days", "30")
    try:
        days = int(days)
    except (ValueError, TypeError):
        days = 30
    filter_type = request.GET.get("type", "")

    since = timezone.now() - timedelta(days=days)

    # Load activities and MoveEvents for this profile
    activities = LearningActivity.objects.filter(
        profile=profile, happened_at__gte=since
    ).order_by("-happened_at")[:200]

    if filter_type:
        activities = activities.filter(activity_type=filter_type)

    # Build timeline event dicts
    icon_map = {
        "file_sorted": "📄",
        "summary_created": "📝",
        "review_scheduled": "🔄",
        "digest_created": "📊",
        "muele_sync": "📚",
        "manual_note": "📌",
    }
    marker_map = {
        "file_sorted": "file",
        "summary_created": "summary",
        "review_scheduled": "review",
        "digest_created": "digest",
        "muele_sync": "muele",
        "manual_note": "note",
    }
    type_labels = dict(LearningActivity.ACTIVITY_CHOICES)

    events = []
    for act in activities:
        events.append({
            "title": act.title,
            "icon": icon_map.get(act.activity_type, "📌"),
            "marker_class": marker_map.get(act.activity_type, "note"),
            "type_label": type_labels.get(act.activity_type, act.activity_type),
            "subject_code": act.subject_code or "",
            "details": act.details[:120] if act.details else "",
            "time": act.happened_at.strftime("%Y-%m-%d %H:%M"),
            "timestamp": act.happened_at,
        })

    # Group by date
    from itertools import groupby

    def date_key(e):
        return e["timestamp"].strftime("%A, %B %d, %Y")

    events.sort(key=lambda e: e["timestamp"], reverse=True)
    timeline_groups = []
    for day_label, group in groupby(events, key=date_key):
        timeline_groups.append((day_label, list(group)))

    day_options = [7, 30, 90, 9999]

    return render(request, "organizer/timeline.html", {
        "profile": profile,
        "study_context": ctx,
        "timeline_groups": timeline_groups,
        "activity_types": LearningActivity.ACTIVITY_CHOICES,
        "current_filter": filter_type,
        "days": str(days),
        "day_options": day_options,
    })


def subject_dashboard(request):
    """Semantic subject dashboard showing themes, activity, and learning
    context across all subjects."""
    from django.utils import timezone

    from .core import topics as topics_core
    from .core.contexts import get_context_for_profile

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    ctx = get_context_for_profile(profile)

    all_memories = SubjectMemory.objects.filter(profile=profile).order_by("code")

    if request.method == "POST" and request.POST.get("action") == "refresh_topics":
        subject_code = request.POST.get("subject_code", "") or None
        results = topics_core.process_all_subjects(profile) if not subject_code else {subject_code: len(topics_core.process_subject_topics(profile, subject_code))}
        total = sum(results.values())
        messages.success(request, f"Topics refreshed: {total} themes extracted across {len(results)} subjects.")
        return redirect("subject_dashboard")

    # Build dashboard data for each subject
    subject_data = []
    for memory in all_memories:
        themes = SubjectTheme.objects.filter(
            profile=profile, subject_code=memory.code
        ).order_by("-weight")[:10]

        # Recent activity for this subject
        recent_activity = LearningActivity.objects.filter(
            profile=profile, subject_code=memory.code
        ).order_by("-happened_at")[:3]

        subject_data.append({
            "code": memory.code,
            "title": memory.title or memory.code,
            "resource_count": memory.resource_count,
            "last_touched_at": memory.last_touched_at,
            "themes": [
                {
                    "name": t.name,
                    "weight": t.weight,
                    "source": t.source,
                    "evidence_count": len(t.evidence or []),
                }
                for t in themes
            ],
            "top_theme": themes[0].name if themes else "",
            "theme_count": len(themes),
            "recent_activity": [
                {
                    "title": a.title,
                    "time": a.happened_at.strftime("%Y-%m-%d %H:%M"),
                }
                for a in recent_activity
            ],
        })

    # Global topic cloud: most prominent themes across all subjects
    global_themes = SubjectTheme.objects.filter(profile=profile).order_by("-weight")[:30]

    return render(request, "organizer/subject_dashboard.html", {
        "profile": profile,
        "study_context": ctx,
        "subject_data": subject_data,
        "global_themes": [
            {
                "name": t.name,
                "weight": t.weight,
                "subject_code": t.subject_code,
            }
            for t in global_themes
        ],
        "total_subjects": all_memories.count(),
        "total_themes": SubjectTheme.objects.filter(profile=profile).count(),
    })


def sorting_inbox(request):
    """Decision inbox for approving/rerouting/ignoring files."""
    from .core.contexts import get_context_for_profile
    from .core import sorting

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    ctx = get_context_for_profile(profile)
    stats = sorting.get_inbox_stats(profile)
    pending_items = sorting.get_pending_inbox(profile)

    return render(request, "organizer/sorting_inbox.html", {
        "profile": profile,
        "study_context": ctx,
        "stats": stats,
        "pending_items": pending_items,
    })


def inbox_approve(request, pk):
    """Approve a pending inbox item."""
    from .core import sorting

    item = get_object_or_404(SortingInboxItem, pk=pk)
    if request.method == "POST":
        if sorting.approve_inbox_item(item):
            messages.success(request, f"Approved: {item.filename}")
        else:
            messages.error(request, f"Could not approve {item.filename}")
    return redirect("sorting_inbox")


def inbox_reroute(request, pk):
    """Reroute a pending inbox item to a different destination."""
    from .core import sorting

    item = get_object_or_404(SortingInboxItem, pk=pk)
    if request.method == "POST":
        new_dest = request.POST.get("new_destination", "").strip()
        if new_dest:
            if sorting.reroute_inbox_item(item, new_dest):
                messages.success(request, f"Rerouted: {item.filename}")
            else:
                messages.error(request, f"Could not reroute {item.filename}")
    return redirect("sorting_inbox")


def inbox_ignore(request, pk):
    """Ignore a pending inbox item."""
    from .core import sorting

    item = get_object_or_404(SortingInboxItem, pk=pk)
    if request.method == "POST":
        sorting.ignore_inbox_item(item)
        messages.info(request, f"Ignored: {item.filename}")
    return redirect("sorting_inbox")


def folder_rules(request):
    """Visual folder rule builder."""
    from .core.contexts import get_context_for_profile

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    ctx = get_context_for_profile(profile)

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "create":
            FolderRule.objects.create(
                profile=profile,
                name=request.POST.get("name", "New rule")[:120],
                priority=int(request.POST.get("priority", 100)),
                match_field=request.POST.get("match_field", "filename"),
                operator=request.POST.get("operator", "contains"),
                pattern=request.POST.get("pattern", ""),
                file_extensions=request.POST.getlist("file_extensions"),
                subject_code=request.POST.get("subject_code", ""),
                category=request.POST.get("category", ""),
                action=request.POST.get("action_type", "route"),
                enabled=request.POST.get("enabled") == "on",
            )
            messages.success(request, "Rule created.")
            return redirect("folder_rules")
        elif action == "toggle":
            rule_pk = request.POST.get("rule_pk")
            rule = get_object_or_404(FolderRule, pk=rule_pk, profile=profile)
            rule.enabled = not rule.enabled
            rule.save()
            return redirect("folder_rules")
        elif action == "delete":
            rule_pk = request.POST.get("rule_pk")
            rule = get_object_or_404(FolderRule, pk=rule_pk, profile=profile)
            rule.delete()
            messages.success(request, "Rule deleted.")
            return redirect("folder_rules")

    rules_list = FolderRule.objects.filter(profile=profile).order_by("priority")

    return render(request, "organizer/folder_rules.html", {
        "profile": profile,
        "study_context": ctx,
        "rules": rules_list,
    })


def import_plans(request):
    """Import from existing folders — approve/apply/reject workflow."""
    from .core.contexts import get_context_for_profile
    from .core import sorting, study

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    ctx = get_context_for_profile(profile)

    if request.method == "POST":
        action = request.POST.get("action", "")
        plan_pk = request.POST.get("plan_pk")
        plan = get_object_or_404(FolderImportPlan, pk=plan_pk) if plan_pk else None

        if action == "scan":
            root_path = request.POST.get("root_path", "").strip()
            if not root_path:
                messages.error(request, "Enter a folder path to scan.")
            else:
                plan = study.create_import_plan(root_path, profile=profile)
                messages.success(request, f"Scanned: found {len(plan.proposed_subjects)} subjects, {len(plan.proposed_rules)} proposed rules.")
            return redirect("import_plans")

        elif action == "approve" and plan:
            if sorting.approve_import_plan(plan, profile):
                messages.success(request, f"Plan approved: subjects and rules adopted.")
            return redirect("import_plans")

        elif action == "apply" and plan:
            if sorting.apply_import_plan(plan, profile):
                messages.success(request, f"Plan applied: folder structure created.")
            return redirect("import_plans")

        elif action == "reject" and plan:
            sorting.reject_import_plan(plan)
            messages.info(request, "Plan rejected.")
            return redirect("import_plans")

    plans = FolderImportPlan.objects.filter(profile=profile).order_by("-updated_at")

    return render(request, "organizer/import_plans.html", {
        "profile": profile,
        "study_context": ctx,
        "plans": plans,
    })


def first_run_checklist(request):
    """First-run onboarding page with setup checklist."""
    from .core.contexts import get_context_for_profile, get_context

    profile = Profile.get_active()
    settings = AppSettings.get_solo() if AppSettings.objects.exists() else None
    ctx = get_context_for_profile(profile) if profile else get_context("custom")

    # Build checklist items
    checklist = []

    # 1. Profile configured
    if profile:
        checklist.append({
            "id": "profile",
            "label": "Profile configured",
            "detail": f"'{profile.name}' — {profile.purpose} context",
            "done": True,
            "url": "profile_edit" if profile else "start",
        })
    else:
        checklist.append({
            "id": "profile",
            "label": "Create a profile",
            "detail": "Choose Makerere or Manual setup path",
            "done": False,
            "url": "start",
        })

    # 2. Downloads folder set
    if settings and settings.downloads_path:
        from pathlib import Path
        path = Path(settings.downloads_path)
        checklist.append({
            "id": "downloads",
            "label": "Downloads folder configured",
            "detail": str(path),
            "done": path.exists(),
            "url": "settings_edit",
            "warning": not path.exists(),
        })
    else:
        checklist.append({
            "id": "downloads",
            "label": "Set downloads folder",
            "detail": "Orch needs to know where to watch for files",
            "done": False,
            "url": "settings_edit",
        })

    # 3. Profile has subjects
    config = getattr(profile, "config", None) if profile else None
    has_subjects = bool(config and config.groups)
    checklist.append({
        "id": "subjects",
        "label": "Subjects added",
        "detail": f"{len(config.groups) if config and config.groups else 0} subjects configured" if has_subjects else "Add subjects so Orch knows where to route files",
        "done": has_subjects,
        "url": "profile_edit" if profile else "start",
    })

    # 4. Watcher running
    checklist.append({
        "id": "watcher",
        "label": "File watcher active",
        "detail": "Watches for new files in Downloads folder",
        "done": True,
        "url": None,
        "info": "Enabled by default in system tray",
    })

    # 5. AI configured (optional)
    ai_configured = paths.AI_CONFIG_PATH.exists()
    checklist.append({
        "id": "ai",
        "label": "AI features",
        "detail": "AI summaries and smart classification" if ai_configured else "Optional — configure for AI summaries and guides",
        "done": ai_configured,
        "url": None,
        "optional": True,
    })

    # 6. MUELE connected (if Makerere profile)
    if profile and profile.setup_path == "makerere":
        muele = IntegrationConnection.objects.filter(profile=profile, provider="muele").first()
        checklist.append({
            "id": "muele",
            "label": "MUELE connected",
            "detail": "Sync course materials and assignments" if muele and muele.status == "connected" else "Connect MUELE for auto-sync",
            "done": bool(muele and muele.status == "connected"),
            "url": "muele_connect",
        })

    done_count = sum(1 for c in checklist if c.get("done"))
    total_count = sum(1 for c in checklist if not c.get("optional"))

    return render(request, "organizer/first_run.html", {
        "profile": profile,
        "study_context": ctx,
        "checklist": checklist,
        "done_count": done_count,
        "total_count": total_count,
    })


def undo_recent(request):
    """View and restore recently moved files."""
    from .core.contexts import get_context_for_profile
    from .core import undo

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    ctx = get_context_for_profile(profile)

    if request.method == "POST":
        action = request.POST.get("action", "")
        move_pk = request.POST.get("move_pk")
        event = get_object_or_404(MoveEvent, pk=move_pk) if move_pk else None

        if action == "restore" and event:
            if undo.restore_move(event):
                messages.success(request, f"Restored: {event.filename}")
            else:
                messages.error(request, f"Could not restore {event.filename}")
            return redirect("undo_recent")

        elif action == "restore_all":
            count = undo.restore_recent(profile, minutes=60)
            if count:
                messages.success(request, f"Restored {count} file(s) from the last hour.")
            else:
                messages.info(request, "No files to restore.")
            return redirect("undo_recent")

    stats = undo.get_undo_stats(profile)
    restorable = undo.get_restorable_moves(profile)

    return render(request, "organizer/undo_recent.html", {
        "profile": profile,
        "study_context": ctx,
        "stats": stats,
        "restorable": restorable,
    })


def rule_test(request):
    """Test a folder rule against a filename before saving."""
    from .core import sorting

    profile = Profile.get_active()
    if not profile:
        return JsonResponse({"error": "No active profile"}, status=400)

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    rule_data = {
        "name": request.POST.get("name", "Test rule"),
        "match_field": request.POST.get("match_field", "filename"),
        "operator": request.POST.get("operator", "contains"),
        "pattern": request.POST.get("pattern", ""),
        "file_extensions": request.POST.getlist("file_extensions"),
        "subject_code": request.POST.get("subject_code", ""),
        "category": request.POST.get("category", ""),
        "action": request.POST.get("action_type", "route"),
    }

    test_filename = request.POST.get("test_filename", "").strip()
    if not test_filename:
        return JsonResponse({"error": "Enter a filename to test"}, status=400)

    # Create a temporary rule object to evaluate
    from django.db.models import Model
    from .models import FolderRule

    # Build a mock rule-like dict
    from types import SimpleNamespace
    mock_rule = SimpleNamespace(**rule_data)

    from pathlib import Path
    test_path = Path(test_filename)
    matched, dest = sorting.evaluate_rule(mock_rule, test_path.name, test_path)

    result = {
        "matched": matched,
        "destination": dest,
        "rule": rule_data["name"],
        "filename": test_filename,
    }

    if dest == "__IGNORE__":
        result["action"] = "File will be ignored"
    elif dest == "__INBOX__":
        result["action"] = "File will be sent to inbox for review"
    elif dest:
        result["action"] = f"File will be routed to: {dest}"
    else:
        result["action"] = "File will NOT match this rule"

    return JsonResponse(result)


def preview_scan(request):
    """Preview what Orch would do with files in an existing folder."""
    from .core import sorting, rules as routing_rules

    profile = Profile.get_active()
    if not profile:
        return JsonResponse({"error": "No active profile"}, status=400)

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    folder_path = request.POST.get("folder_path", "").strip()
    if not folder_path:
        return JsonResponse({"error": "Enter a folder path"}, status=400)

    path = Path(folder_path)
    if not path.exists() or not path.is_dir():
        return JsonResponse({"error": "Folder does not exist"}, status=400)

    # Scan the folder
    from organizer.models import FolderRule

    rules = FolderRule.objects.filter(profile=profile, enabled=True).order_by("priority")
    files_found = []
    matched_count = 0
    unmatched_count = 0

    for f in sorted(path.iterdir()):
        if not f.is_file():
            continue

        file_info = {"filename": f.name, "matched": False, "rule": None, "destination": None}

        # Check against rules
        for rule in rules:
            matched, dest = sorting.evaluate_rule(rule, f.name, f)
            if matched:
                file_info["matched"] = True
                file_info["rule"] = rule.name
                if dest == "__IGNORE__":
                    file_info["destination"] = "Ignored"
                elif dest == "__INBOX__":
                    file_info["destination"] = "Inbox"
                elif dest:
                    file_info["destination"] = dest
                matched_count += 1
                break

        # If no rule matched, show what the default routing would do
        if not file_info["matched"]:
            default_dest = routing_rules.get_destination(f, profile_root=profile.root_path)
            if default_dest:
                file_info["destination"] = str(default_dest.path)
                file_info["rule"] = "Default routing"
            unmatched_count += 1

        files_found.append(file_info)

    return JsonResponse({
        "folder": str(path),
        "total_files": len(files_found),
        "matched": matched_count,
        "unmatched": unmatched_count,
        "files": files_found[:100],  # Limit to 100 for preview
    })


def learning_routes(request):
    """Learning Route page: turn weak areas into a sequenced study path."""
    from .core import learning_route as route_engine
    from .core.contexts import get_context_for_profile

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    ctx = get_context_for_profile(profile)
    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "generate":
            subject_code = request.POST.get("subject_code", "").strip() or None
            theme = request.POST.get("theme", "").strip() or None
            route = route_engine.create_or_refresh_route(profile, subject_code=subject_code, theme=theme)
            messages.success(request, f"Learning route ready: {route.title}")
            return redirect("learning_routes")

        if action == "step_done":
            route = get_object_or_404(LearningRoute, pk=request.POST.get("route_pk"), profile=profile)
            step_index = int(request.POST.get("step_index", 0))
            route_engine.mark_step_done(route, step_index)
            return redirect("learning_routes")

    subject_memories = SubjectMemory.objects.filter(profile=profile).order_by("code")
    routes = LearningRoute.objects.filter(profile=profile).order_by("status", "subject_code", "-updated_at")

    return render(request, "organizer/learning_routes.html", {
        "profile": profile,
        "study_context": ctx,
        "subject_memories": subject_memories,
        "routes": routes,
    })


def learning_route(request):
    return learning_routes(request)


def subject_memory_detail(request, code):
    """Full subject memory detail page with resources, themes, assignments, reviews."""
    from django.utils import timezone

    from .core.contexts import get_context_for_profile

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    ctx = get_context_for_profile(profile)

    memory = get_object_or_404(SubjectMemory, profile=profile, code=code)
    themes = SubjectTheme.objects.filter(profile=profile, subject_code=code).order_by("-weight")[:20]
    assignments = AssignmentItem.objects.filter(profile=profile, subject_code=code).order_by("due_at")
    reviews = ReviewItem.objects.filter(profile=profile, subject_code=code, status="queued").order_by("due_at")[:10]
    resources = MoveEvent.objects.filter(profile=profile, course_code=code, success=True).order_by("-timestamp")[:50]
    activities = LearningActivity.objects.filter(profile=profile, subject_code=code).order_by("-happened_at")[:20]
    guide = CourseGuide.objects.filter(profile=profile, course_code=code).first()

    return render(request, "organizer/subject_memory.html", {
        "profile": profile,
        "study_context": ctx,
        "memory": memory,
        "themes": themes,
        "assignments": assignments,
        "reviews": reviews,
        "reviews_count": reviews.count(),
        "resources": resources,
        "activities": activities,
        "guide": guide,
        "now": timezone.now(),
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


# ---------------------------------------------------------------------------
# MUELE Integration Views
# ---------------------------------------------------------------------------


def muele_connect(request):
    """Connect to MUELE and generate a web service token.

    Two methods:
    1. Automatic: Enter MUELE username + password -> generate_token() -> stored in keyring
    2. Manual: Paste existing token from MUELE security keys page
    """
    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Create or activate a profile first.")
        return redirect("start")

    connection = IntegrationConnection.objects.filter(
        profile=profile, provider="muele"
    ).first()

    token_status = None
    user_info = None
    login_error = None

    if request.method == "POST":
        action = request.POST.get("action", "")

        # Method 1: Automatic login with MUELE username + password
        if action == "login":
            username = request.POST.get("login_username", "").strip()
            password = request.POST.get("login_password", "")

            if not username or not password:
                messages.error(request, "Enter your MUELE username and password.")
            else:
                token, error = muele_api.generate_token(username, password)
                if error:
                    messages.error(request, f"MUELE login failed: {error}")
                    login_error = error
                elif token:
                    token_status = "valid"
                    user_info, _ = muele_api.verify_token(token)
                    messages.success(
                        request,
                        f"Logged in to MUELE as {user_info['fullname'] if user_info else username}"
                    )

        # Method 2: Manual token entry
        elif action == "verify_token":
            token = request.POST.get("token", "").strip()
            if token:
                user_info, error = muele_api.verify_token(token)
                if error:
                    messages.error(request, f"Token verification failed: {error}")
                    token_status = "invalid"
                else:
                    token_status = "valid"
                    muele_api.store_token(token)
                    messages.success(request, f"Connected as {user_info['fullname']}")

        elif action == "save_connection":
            # Check for stored token
            stored_token = muele_api.load_token()
            if not stored_token:
                messages.error(request, "Connect to MUELE first via login or token entry.")
                return redirect("muele_connect")

            # Update or create the connection
            if connection is None:
                connection = IntegrationConnection.objects.create(
                    profile=profile,
                    provider="muele",
                    display_name="Makerere MUELE",
                    base_url=study.MUELE_BASE_URL,
                    status="connected",
                    username=request.POST.get("username", "").strip(),
                    config={
                        "sync_targets": request.POST.getlist("sync_targets") or ["course_files", "assignments", "calendar"],
                        "college": request.POST.get("college", "").strip(),
                    },
                )
            else:
                connection.status = "connected"
                connection.username = request.POST.get("username", "").strip() or connection.username
                connection.config = {
                    **(connection.config or {}),
                    "college": request.POST.get("college", "").strip(),
                    "sync_targets": request.POST.getlist("sync_targets") or ["course_files", "assignments", "calendar"],
                }
                connection.save()
            messages.success(request, "MUELE connection saved.")

            # Fetch and save courses
            courses, error = muele_api.get_courses()
            if not error and courses:
                from .models import MueleCourse

                for course in courses:
                    MueleCourse.objects.update_or_create(
                        connection=connection,
                        course_id=course["id"],
                        defaults={
                            "course_name": course["fullname"],
                            "course_code": course["shortname"],
                            "auto_download": True,
                            "enrolled": True,
                        },
                    )
                messages.success(request, f"Found {len(courses)} MUELE courses.")
            return redirect("muele_courses")

    # Check if token is already stored
    stored_token = muele_api.load_token()
    if stored_token:
        user_info, _ = muele_api.verify_token(stored_token)
        if user_info:
            token_status = "valid"

    return render(request, "organizer/muele_connect.html", {
        "profile": profile,
        "connection": connection,
        "token_status": token_status,
        "user_info": user_info,
        "login_error": login_error,
        "muele_url": study.MUELE_BASE_URL,
    })


def muele_courses(request):
    """View and manage synced MUELE courses."""
    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Create or activate a profile first.")
        return redirect("start")

    connection = IntegrationConnection.objects.filter(
        profile=profile, provider="muele"
    ).first()

    if not connection:
        return redirect("muele_connect")

    from .models import MueleCourse

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "toggle_auto_download":
            course_id = request.POST.get("course_id")
            enabled = request.POST.get("enabled") == "true"
            MueleCourse.objects.filter(connection=connection, course_id=course_id).update(
                auto_download=enabled
            )
            return JsonResponse({"ok": True})

        elif action == "refresh_courses":
            courses, error = muele_api.get_courses()
            if error:
                messages.error(request, f"Could not refresh courses: {error}")
            else:
                for course in courses:
                    MueleCourse.objects.update_or_create(
                        connection=connection,
                        course_id=course["id"],
                        defaults={
                            "course_name": course["fullname"],
                            "course_code": course["shortname"],
                            "enrolled": True,
                        },
                    )
                messages.success(request, f"Refreshed {len(courses)} courses.")
            return redirect("muele_courses")

        elif action == "sync_now":
            result = muele_downloader.sync_profile_courses(profile)
            assign_count = muele_downloader.sync_assignments(profile)
            notifications.notify_muele_sync(result)
            messages.success(
                request,
                f"Sync complete: {result['downloaded']} downloaded, "
                f"{result['skipped']} skipped, {result['errors']} errors. "
                f"{assign_count} new assignments."
            )
            return redirect("muele_courses")

    courses = MueleCourse.objects.filter(connection=connection).order_by("course_name")
    token_ok = bool(muele_api.load_token())

    return render(request, "organizer/muele_courses.html", {
        "profile": profile,
        "connection": connection,
        "courses": courses,
        "token_ok": token_ok,
        "muele_url": study.MUELE_BASE_URL,
    })


def muele_sync_status(request):
    """JSON endpoint for the dashboard to show live MUELE sync status."""
    profile = Profile.get_active()
    if not profile:
        return JsonResponse({"connected": False})

    from .models import MueleCourse

    connection = IntegrationConnection.objects.filter(
        profile=profile, provider="muele", status="connected"
    ).first()

    if not connection:
        return JsonResponse({"connected": False})

    courses = MueleCourse.objects.filter(connection=connection)
    upcoming = AssignmentItem.objects.filter(
        profile=profile, source="muele", status="open"
    ).order_by("due_at")[:5]

    return JsonResponse({
        "connected": True,
        "last_sync": connection.last_sync_at.isoformat() if connection.last_sync_at else None,
        "courses_total": courses.count(),
        "courses_auto_download": courses.filter(auto_download=True).count(),
        "upcoming_deadlines": [
            {
                "title": a.title,
                "due_at": a.due_at.isoformat() if a.due_at else None,
                "subject": a.subject_code,
                "status": a.status,
            }
            for a in upcoming
        ],
    })
