import json
import re
import string
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from ..core import (
    diagnostics,
    digest as digest_core,
    makerere,
    makerere_curricula,
    muele_api,
    muele_downloader,
    notifications,
    owner_access,
    paths,
    perf,
    rules,
    study,
)
from ..core import summarize as summarize_core
from ..core.watcher import write_log
from ..models import (
    AppSettings,
    AssignmentItem,
    CareerDigest,
    CareerProfile,
    ContentDraft,
    CourseConfig,
    CourseGuide,
    ExportBundle,
    FileSummary,
    Flashcard,
    FolderImportPlan,
    FolderRule,
    GlobalSortCategory,
    GradeTarget,
    IntegrationConnection,
    LearningActivity,
    LearningDigest,
    LearningRoute,
    MoveEvent,
    Notification,
    OrganizationMemoryRule,
    PastPaperAnalysis,
    Profile,
    Project,
    ProjectUpdate,
    PublishedPost,
    ResourceRecommendation,
    ReviewItem,
    SortDecision,
    StudyFocusSession,
    SubjectMemory,
    SubjectTheme,
    StudyGoal,
    SuggestedCourseUnit,
    TimetableDocument,
    TimetableEntry,
)


def drive_connect(request):
    """Kicks off the Google OAuth consent flow. Needs a Client ID/secret
    already saved in Settings (from the user's own Google Cloud Console
    project) -- this view never invents or guesses those."""
    import secrets

    from ..core import drive_api

    config = drive_api.load_drive_config()
    if not config or not config.get("client_id"):
        messages.error(request, "Add a Google Client ID and secret in Settings first.")
        return redirect("settings_edit")

    state = secrets.token_urlsafe(24)
    request.session["drive_oauth_state"] = state
    redirect_uri = request.build_absolute_uri(reverse("drive_callback"))
    auth_url = drive_api.build_auth_url(redirect_uri, state)
    if not auth_url:
        messages.error(request, "Add a Google Client ID and secret in Settings first.")
        return redirect("settings_edit")

    return redirect(auth_url)


def drive_callback(request):
    """Where Google redirects back to after the user approves (or denies)
    access, per the redirect_uri drive_connect sent it. Runs on Orch's own
    server, not a separate temporary listener."""
    from ..core import drive_api

    error = request.GET.get("error")
    if error:
        messages.error(request, f"Google Drive connection was not completed: {error}")
        return redirect("settings_edit")

    code = request.GET.get("code", "")
    state = request.GET.get("state", "")
    expected_state = request.session.pop("drive_oauth_state", None)
    if not code or not expected_state or state != expected_state:
        messages.error(request, "Google Drive connection failed: the request could not be verified.")
        return redirect("settings_edit")

    redirect_uri = request.build_absolute_uri(reverse("drive_callback"))
    tokens, exchange_error = drive_api.exchange_code_for_tokens(code, redirect_uri)
    if exchange_error or not tokens or not tokens.get("refresh_token"):
        messages.error(
            request,
            exchange_error or "Google did not grant offline access. Try connecting again.",
        )
        return redirect("settings_edit")

    stored, store_error = drive_api.store_refresh_token(tokens["refresh_token"])
    if not stored:
        messages.error(request, store_error or "Could not save the Drive connection.")
        return redirect("settings_edit")

    email = drive_api.get_account_email(tokens.get("access_token", ""))
    IntegrationConnection.objects.update_or_create(
        profile=None, provider="drive", display_name="Google Drive",
        defaults={"config": {"email": email} if email else {}},
    )
    messages.success(request, f"Connected to Google Drive{f' as {email}' if email else ''}.")
    return redirect("settings_edit")


def drive_disconnect(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required."}, status=405)

    from ..core import drive_api

    drive_api.clear_refresh_token()
    IntegrationConnection.objects.filter(provider="drive").delete()
    return JsonResponse({"ok": True})


def _short_timesince(value):
    if not value:
        return "never"
    delta = timezone.now() - value
    if delta.days:
        return f"{delta.days}d ago"
    hours = delta.seconds // 3600
    if hours:
        return f"{hours}h ago"
    minutes = delta.seconds // 60
    return f"{minutes or 1}m ago"


def _connection_action(url, label):
    return {"url": url, "label": label} if url else None


def _connection_card(
    *,
    title,
    area,
    status,
    status_label,
    detail,
    reason,
    action=None,
    meta="",
    scope="",
):
    return {
        "title": title,
        "area": area,
        "status": status,
        "status_class": status.replace("_", "-"),
        "status_label": status_label,
        "detail": detail,
        "reason": reason,
        "action": action,
        "meta": meta,
        "scope": scope,
    }


def _profile_uses_learning_tools(profile):
    return bool(profile and (profile.purpose in {"school", "online"} or profile.setup_path == "makerere"))


@perf.measure_view
def connections_home(request):
    """Unified service map for everything Orch can connect to.

    The individual setup flows still live where they already did. This page
    is the user's map: what is connected, what needs setup, what is optional,
    and why taking the next action is worth it.
    """
    from ..core import ai_classify, drive_api, youtube_api

    profile = Profile.get_active()
    profile_connections = (
        IntegrationConnection.objects.filter(profile=profile)
        if profile else IntegrationConnection.objects.none()
    )
    global_connections = IntegrationConnection.objects.filter(profile__isnull=True)

    def connection(provider):
        return profile_connections.filter(provider=provider).first()

    def global_connection(provider):
        return global_connections.filter(provider=provider).first()

    muele = connection("muele")
    timetable = connection("mak_timetable")
    timetable_entries = TimetableEntry.objects.filter(profile=profile).count() if profile else 0
    ai_config = ai_classify.load_ai_config() or {}
    youtube_config = youtube_api.load_youtube_config() or {}
    drive_config = drive_api.load_drive_config() or {}
    drive_connection = global_connection("drive")
    drive_email = drive_connection.config.get("email") if drive_connection and drive_connection.config else ""
    drive_ready = bool(drive_config.get("enabled") and drive_config.get("client_id") and drive_config.get("client_secret"))
    drive_connected = bool(drive_ready and drive_api.is_connected())

    custom_channels = profile_connections.filter(provider="custom_website")
    github_channels = profile_connections.filter(provider="github")
    linkedin = connection("linkedin")
    active_categories = GlobalSortCategory.objects.exclude(key="sensitive").filter(enabled=True).count()

    has_profile = bool(profile)
    learning_profile = _profile_uses_learning_tools(profile)
    profile_setup_url = reverse("start")
    publishing_url = reverse("publishing_channels") if has_profile else profile_setup_url
    drafts_url = reverse("content_drafts") if has_profile else profile_setup_url
    academic_cards = [
        _connection_card(
            title="Makerere MUELE",
            area="Learning files",
            status="connected" if muele and muele.status == "connected" else "setup" if has_profile and learning_profile else "not_connected" if has_profile else "blocked",
            status_label="Connected" if muele and muele.status == "connected" else "Set up" if has_profile and learning_profile else "Optional" if has_profile else "Needs profile",
            detail=(
                f"Connected as {muele.username}" if muele and muele.username
                else "Bring in course files, assignment dates, and learning activity when this profile needs it."
            ),
            reason="Useful for Makerere profiles. Other profiles can ignore it and still use Orch normally.",
            action=_connection_action(reverse("muele_courses") if muele and muele.status == "connected" else reverse("muele_connect") if has_profile else profile_setup_url, "Manage" if muele and muele.status == "connected" else "Set up" if has_profile else "Create profile"),
            meta=f"Last sync {_short_timesince(muele.last_sync_at)}" if muele and muele.last_sync_at else "Makerere",
            scope=profile.name if profile else "No active profile",
        ),
        _connection_card(
            title="Makerere Timetable",
            area="Schedule",
            status="connected" if timetable and timetable_entries else "setup" if has_profile and learning_profile else "not_connected" if has_profile else "blocked",
            status_label="Connected" if timetable and timetable_entries else "Set up" if has_profile and learning_profile else "Optional" if has_profile else "Needs profile",
            detail=f"{timetable_entries} timetable entries synced." if timetable_entries else "Add a timetable for classes, sessions, tests, exams, or training times.",
            reason="Useful when this profile has time-based work. It should not be required for ordinary file sorting.",
            action=_connection_action(reverse("timetable_view") if timetable and timetable_entries else reverse("timetable_connect") if has_profile else profile_setup_url, "View" if timetable and timetable_entries else "Set up" if has_profile else "Create profile"),
            meta=timetable.config.get("group", "") if timetable and timetable.config else "Timetable",
            scope=profile.name if profile else "No active profile",
        ),
        _connection_card(
            title="Moodle",
            area="Learning platform",
            status="not_connected",
            status_label="Not connected",
            detail="Generic Moodle support is planned after the Makerere MUELE flow is stable.",
            reason="Useful for profiles that use Moodle, but it should stay optional until the connector is ready.",
            action=None,
            meta="Planned",
            scope="Future",
        ),
        _connection_card(
            title="Calendar",
            area="Schedule bridge",
            status="not_connected",
            status_label="Not connected",
            detail="Calendar sync is not wired yet; Orch currently uses timetable and assignments internally.",
            reason="The right future version should push dated items to your calendar only after approval.",
            action=None,
            meta="Planned",
            scope="Future",
        ),
    ]

    intelligence_cards = [
        _connection_card(
            title="Smart Orch API",
            area="Reasoning layer",
            status="connected" if ai_config.get("enabled") and ai_config.get("api_key") else "setup",
            status_label="Connected" if ai_config.get("enabled") and ai_config.get("api_key") else "Set up",
            detail="Summaries and fallback routing are active." if ai_config.get("enabled") and ai_config.get("api_key") else "Optional API key not configured.",
            reason="Useful for summaries and suggestions, but Orch still sorts locally without it.",
            action=_connection_action(reverse("settings_edit"), "Manage" if ai_config.get("api_key") else "Set up"),
            meta="Optional",
            scope="App-wide",
        ),
        _connection_card(
            title="YouTube Data API",
            area="Resource Radar",
            status="connected" if youtube_config.get("enabled") and youtube_config.get("api_key") else "add",
            status_label="Connected" if youtube_config.get("enabled") and youtube_config.get("api_key") else "Add",
            detail="Real video picks are enabled." if youtube_config.get("enabled") and youtube_config.get("api_key") else "Resource Radar still works with search links.",
            reason="Add it when you want Orch to pick specific videos for saved topics instead of giving a search query.",
            action=_connection_action(reverse("settings_edit"), "Manage" if youtube_config.get("api_key") else "Add"),
            meta="Optional",
            scope="App-wide",
        ),
        _connection_card(
            title="GitHub Repo Search",
            area="Code resources",
            status="connected",
            status_label="Connected",
            detail="Repo recommendations work anonymously without setup.",
            reason="Useful when a topic needs real code examples to inspect.",
            action=_connection_action(reverse("resource_radar"), "Open"),
            meta="No key required",
            scope="App-wide",
        ),
    ]

    storage_cards = [
        _connection_card(
            title="Google Drive Backup",
            area="Cloud backup",
            status="connected" if drive_connected else "setup" if drive_ready else "add",
            status_label="Connected" if drive_connected else "Set up" if drive_ready else "Add",
            detail=(
                f"Connected{f' as {drive_email}' if drive_email else ''}."
                if drive_connected else
                "Google credentials saved; connect the account." if drive_ready else
                "Client ID and secret not configured."
            ),
            reason="Keeps sorted files recoverable while preserving Orch's local-first design.",
            action=_connection_action(reverse("drive_connect") if drive_ready and not drive_connected else reverse("settings_edit"), "Connect" if drive_ready and not drive_connected else "Manage" if drive_connected else "Add"),
            meta="App-wide",
            scope="Backup",
        ),
        _connection_card(
            title="Local Folder Watcher",
            area="Local automation",
            status="connected",
            status_label="Connected",
            detail=f"Watching {AppSettings.get_solo().downloads_path}",
            reason="This is Orch's core engine: files arrive locally, then rules and profiles decide what happens.",
            action=_connection_action(reverse("settings_edit"), "Tune"),
            meta=f"{active_categories} optional categor{'ies' if active_categories != 1 else 'y'} on",
            scope="App-wide",
        ),
        _connection_card(
            title="Notion",
            area="Workspace export",
            status="not_connected",
            status_label="Not connected",
            detail="No Notion connector is implemented yet.",
            reason="Good future target for workspace notes, but it needs a clean permission model before it belongs in Orch.",
            action=None,
            meta="Planned",
            scope="Future",
        ),
    ]

    publishing_cards = [
        _connection_card(
            title="Custom Website API",
            area="Publishing",
            status="connected" if custom_channels.filter(status="connected").exists() else "add",
            status_label="Connected" if custom_channels.filter(status="connected").exists() else "Add",
            detail=f"{custom_channels.count()} website channel{'s' if custom_channels.count() != 1 else ''} configured." if custom_channels.exists() else "Connect your own website or blog endpoint.",
            reason="This is the most flexible route: Orch keeps the draft here, waits for your click, then sends it to your own site.",
            action=_connection_action(publishing_url, "Manage" if custom_channels.exists() else "Add" if has_profile else "Create profile"),
            meta="User-owned API",
            scope=profile.name if profile else "No active profile",
        ),
        _connection_card(
            title="GitHub Publishing",
            area="Publishing",
            status="connected" if github_channels.filter(status="connected").exists() else "setup" if github_channels.exists() else "add",
            status_label="Connected" if github_channels.filter(status="connected").exists() else "Set up" if github_channels.exists() else "Add",
            detail=f"{github_channels.count()} repo channel{'s' if github_channels.count() != 1 else ''} configured." if github_channels.exists() else "Publish approved posts as commits to a repo.",
            reason="Useful when you want approved drafts to become dated commits in a repo you own.",
            action=_connection_action(publishing_url, "Manage" if github_channels.exists() else "Add" if has_profile else "Create profile"),
            meta="Repo commits",
            scope=profile.name if profile else "No active profile",
        ),
        _connection_card(
            title="LinkedIn",
            area="Publishing",
            status="not_connected" if not linkedin else linkedin.status,
            status_label="Not connected" if not linkedin else linkedin.get_status_display(),
            detail="OAuth publishing is not connected. Orch will never ask for your LinkedIn password.",
            reason="The right flow is: Orch suggests a draft, then you click to approve and publish through an official channel.",
            action=_connection_action(publishing_url, "Read setup note" if has_profile else "Create profile"),
            meta="OAuth required",
            scope="Future channel",
        ),
        _connection_card(
            title="Markdown / HTML Export",
            area="Publishing",
            status="connected",
            status_label="Connected",
            detail="Manual exports are ready with no external account.",
            reason="This keeps Orch useful even when APIs are unavailable: copy, upload, or paste anywhere.",
            action=_connection_action(drafts_url, "Open drafts" if has_profile else "Create profile"),
            meta="No setup",
            scope="Local",
        ),
    ]

    groups = [
        {"title": "Learning tools", "detail": "Optional course, timetable, review, and resource helpers.", "cards": academic_cards},
        {"title": "Smart help", "detail": "Optional APIs that make summaries and recommendations sharper.", "cards": intelligence_cards},
        {"title": "Storage and workspace", "detail": "Where Orch watches, backs up, or may export your work.", "cards": storage_cards},
        {"title": "Publishing", "detail": "Where approved drafts can go after your click.", "cards": publishing_cards},
    ]
    all_cards = [card for group in groups for card in group["cards"]]
    connected_count = sum(1 for card in all_cards if card["status"] == "connected")
    actionable_count = sum(1 for card in all_cards if card["status"] in {"add", "setup"})
    blocked_count = sum(1 for card in all_cards if card["status"] in {"blocked", "not_connected", "error", "needs_key"})
    next_action = next((card for card in all_cards if card["status"] == "setup"), None) or next(
        (card for card in all_cards if card["status"] == "add"), None
    )

    failed_backup_count = (
        MoveEvent.objects.filter(profile=profile, drive_backup_status="failed").count() if profile else 0
    )

    return render(request, "organizer/connections.html", {
        "profile": profile,
        "groups": groups,
        "connected_count": connected_count,
        "total_count": len(all_cards),
        "actionable_count": actionable_count,
        "blocked_count": blocked_count,
        "next_action": next_action,
        "failed_backup_count": failed_backup_count,
    })




def drive_backup_retry(request):
    """Re-attempts every MoveEvent this profile's marked as a failed Drive
    backup (offline at the time, quota, expired token, whatever) -- see
    organizer.core.sorting.retry_failed_drive_backups. Runs as a
    background job since a profile with many failed backups could take a
    while to retry them all."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required."}, status=405)

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    from ..core import jobs, sorting

    def _do_retry(task=None):
        return sorting.retry_failed_drive_backups(profile, task=task, log=write_log)

    task = jobs.enqueue("drive_backup", _do_retry, profile=profile)
    return JsonResponse({"ok": True, "task_id": task.pk})


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
                    stored, store_error = muele_api.store_token(token)
                    if stored:
                        token_status = "valid"
                        messages.success(request, f"Connected as {user_info['fullname']}")
                    else:
                        token_status = "invalid"
                        messages.error(request, f"Token verified but could not be saved: {store_error}")

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

            # Fetch and save courses (still via the pending token -- not yet
            # moved to the connection-specific key)
            courses, error = muele_api.get_courses(token=stored_token)
            if not error and courses:
                from ..models import MueleCourse

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

            # The token now belongs to this connection, not the pending
            # login -- move it so other profiles connecting their own MUELE
            # account never share it (see load_connection_token).
            muele_api.store_connection_token(connection, stored_token)
            muele_api.clear_token()
            return redirect("muele_courses")

    # Check if a token is already stored -- this connection's own token if
    # one exists, otherwise a pending token from an in-progress login.
    stored_token = muele_api.load_connection_token(connection) if connection else muele_api.load_token()
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


@perf.measure_view
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

    from ..models import MueleCourse

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "toggle_auto_download":
            course_id = request.POST.get("course_id")
            enabled = request.POST.get("enabled") == "true"
            updated = MueleCourse.objects.filter(connection=connection, course_id=course_id).update(
                auto_download=enabled
            )
            if not updated:
                return JsonResponse({"ok": False, "error": "That course is no longer in your list."})
            return JsonResponse({"ok": True})

        elif action == "refresh_courses":
            courses, error = muele_api.get_courses(token=muele_api.load_connection_token(connection))
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
            # Runs as a background job instead of blocking this request for
            # the full sync duration -- the frontend polls task_status() and
            # reloads once it's done. See organizer.core.jobs.
            from ..core import jobs, perf

            def _do_sync(task=None):
                with perf.measure("muele_sync", profile=profile, detail="sync_now"):
                    result = muele_downloader.sync_profile_courses(profile)
                    assign_count = muele_downloader.sync_assignments(profile)
                notifications.notify_muele_sync(result, profile=profile)
                return (
                    f"Sync complete: {result['downloaded']} downloaded, "
                    f"{result['skipped']} skipped, {result['errors']} errors. "
                    f"{assign_count} new assignments."
                )

            task = jobs.enqueue("muele_sync", _do_sync, profile=profile)
            return JsonResponse({"ok": True, "task_id": task.pk})

    courses = MueleCourse.objects.filter(connection=connection).order_by("course_name")
    token_ok = bool(muele_api.load_connection_token(connection))

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

    from ..models import MueleCourse

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


def timetable_connect(request):
    """Connect Orch to timetable.mak.ac.ug for one specific group (e.g.
    "SE-2"), so Study can show and notify about real lectures/tests/exams.
    The site has no login and no export format, so this walks the same
    Academic Year -> Semester -> College -> Group choices its own page
    does, live, rather than ever guessing which group is the user's."""
    from ..core import timetable_sync

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Create or activate a profile first.")
        return redirect("start")

    connection = IntegrationConnection.objects.filter(profile=profile, provider="mak_timetable").first()

    years, years_error = timetable_sync.fetch_academic_years()
    if years_error:
        messages.error(request, years_error)

    if request.method == "POST":
        academic_year_id = request.POST.get("academic_year_id", "").strip()
        academic_year_label = request.POST.get("academic_year_label", "").strip()
        semester_id = request.POST.get("semester_id", "").strip()
        semester_label = request.POST.get("semester_label", "").strip()
        college = request.POST.get("college", "").strip()
        group = request.POST.get("group", "").strip()

        if not all([academic_year_id, semester_id, college, group]):
            messages.error(request, "Pick an academic year, semester, college, and group first.")
        else:
            connection, _ = IntegrationConnection.objects.update_or_create(
                profile=profile, provider="mak_timetable", display_name="Makerere Timetable",
                defaults={
                    "base_url": timetable_sync.BASE_URL,
                    "status": "planned",
                    "config": {
                        "academic_year_id": academic_year_id,
                        "academic_year_label": academic_year_label,
                        "semester_id": semester_id,
                        "semester_label": semester_label,
                        "college": college,
                        "group": group,
                    },
                },
            )
            count, error = timetable_sync.sync_group_timetable(profile, connection)
            if error and not count:
                messages.error(request, f"Connected, but the sync had trouble: {error}")
            else:
                messages.success(request, f"Connected. Synced {count} timetable entries for {group}.")
            return redirect("timetable_view")

    return render(request, "organizer/timetable_connect.html", {
        "profile": profile,
        "connection": connection,
        "years": years,
    })


def timetable_semesters(request):
    from ..core import timetable_sync

    if request.method != "POST":
        return JsonResponse({"error": "POST required."}, status=405)
    data, error = timetable_sync.fetch_semesters(request.POST.get("academic_year_id"))
    if error:
        return JsonResponse({"error": error}, status=502)
    return JsonResponse({"items": data})


def timetable_colleges(request):
    from ..core import timetable_sync

    if request.method != "POST":
        return JsonResponse({"error": "POST required."}, status=405)
    data, error = timetable_sync.fetch_colleges(
        request.POST.get("academic_year_id"),
        request.POST.get("semester_id"),
        request.POST.get("kind", "teaching"),
    )
    if error:
        return JsonResponse({"error": error}, status=502)
    return JsonResponse({"items": data})


def timetable_groups(request):
    from ..core import timetable_sync

    if request.method != "POST":
        return JsonResponse({"error": "POST required."}, status=405)
    data, error = timetable_sync.fetch_groups(
        request.POST.get("academic_year_id"),
        request.POST.get("semester_id"),
        request.POST.get("kind", "teaching"),
        request.POST.get("college"),
    )
    if error:
        return JsonResponse({"error": error}, status=502)
    return JsonResponse({"items": data})


def timetable_sync_now(request):
    """Kicks off a timetable sync as a background job instead of blocking
    this request for the full sync duration -- the frontend polls
    task_status() for the result. See organizer.core.jobs."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required."}, status=405)

    from ..core import jobs, perf, timetable_sync

    profile = Profile.get_active()
    connection = get_object_or_404(IntegrationConnection, profile=profile, provider="mak_timetable")

    def _do_sync(task=None):
        with perf.measure("timetable_sync", profile=profile, detail=connection.config.get("group", "")):
            count, error = timetable_sync.sync_group_timetable(profile, connection)
        if error and not count:
            raise RuntimeError(error)
        return f"Synced {count} timetable entries."

    task = jobs.enqueue("timetable_sync", _do_sync, profile=profile)
    return JsonResponse({"ok": True, "task_id": task.pk})


def task_status(request, pk):
    """Polled by the frontend after enqueue()-based endpoints (timetable
    sync, MUELE sync) return a task id, so a slow operation doesn't block
    the request that started it."""
    from ..models import BackgroundTask

    profile = Profile.get_active()
    task = get_object_or_404(BackgroundTask, pk=pk, profile=profile)
    return JsonResponse({
        "status": task.status,
        "progress_current": task.progress_current,
        "progress_total": task.progress_total,
        "result_message": task.result_message,
    })


def timetable_view(request):
    """Weekly class grid plus upcoming tests/exams for the active profile,
    synced from timetable.mak.ac.ug."""
    from django.utils import timezone

    from ..core.contexts import get_context_for_profile
    from ..models import TimetableEntry

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    ctx = get_context_for_profile(profile)
    connection = IntegrationConnection.objects.filter(profile=profile, provider="mak_timetable").first()

    weekday_labels = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    by_day = {i: [] for i in range(6)}
    for entry in TimetableEntry.objects.filter(
        profile=profile, kind__in=["teaching", "recess"]
    ).order_by("weekday", "start_time"):
        by_day[entry.weekday].append(entry)

    today = timezone.localdate()
    upcoming = TimetableEntry.objects.filter(
        profile=profile, kind__in=["test", "examination"], specific_date__gte=today
    ).order_by("specific_date", "start_time")[:20]

    manual_entries = TimetableEntry.objects.filter(profile=profile, source="manual").order_by(
        "kind", "specific_date", "weekday", "start_time"
    )
    documents = TimetableDocument.objects.filter(profile=profile)

    return render(request, "organizer/timetable.html", {
        "profile": profile,
        "study_context": ctx,
        "connection": connection,
        "teaching_by_day": [(label, by_day[i]) for i, label in enumerate(weekday_labels)],
        "upcoming": upcoming,
        "manual_entries": manual_entries,
        "documents": documents,
        "weekday_choices": TimetableEntry.WEEKDAY_CHOICES,
        "kind_choices": TimetableEntry.KIND_CHOICES,
        "document_kind_choices": TimetableDocument.KIND_CHOICES,
    })


def timetable_entry_create(request):
    """Type in a class/test/exam by hand -- for whenever the official
    timetable.mak.ac.ug sync doesn't have it (not published yet, or this
    profile has no sync connection at all)."""
    if request.method != "POST":
        return HttpResponse("POST required.", status=405)

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    from django.utils.dateparse import parse_date, parse_time

    kind = request.POST.get("kind", "").strip()
    if kind not in dict(TimetableEntry.KIND_CHOICES):
        messages.error(request, "Pick a valid timetable type.")
        return redirect("timetable_view")

    start_time = parse_time(request.POST.get("start_time", ""))
    if not start_time:
        messages.error(request, "A start time is required.")
        return redirect("timetable_view")
    end_time = parse_time(request.POST.get("end_time", "")) if request.POST.get("end_time") else None

    weekday_raw = request.POST.get("weekday", "").strip()
    weekday = int(weekday_raw) if weekday_raw.isdigit() else None
    specific_date = parse_date(request.POST.get("specific_date", "")) if request.POST.get("specific_date") else None

    if weekday is None and specific_date is None:
        messages.error(request, "Give it a day of the week or a specific date.")
        return redirect("timetable_view")

    TimetableEntry.objects.create(
        profile=profile,
        connection=None,
        source="manual",
        kind=kind,
        weekday=weekday,
        specific_date=specific_date,
        start_time=start_time,
        end_time=end_time,
        course_code=request.POST.get("course_code", "").strip(),
        course_name=request.POST.get("course_name", "").strip(),
        room=request.POST.get("room", "").strip(),
        lecturer=request.POST.get("lecturer", "").strip(),
        raw_group="",
    )
    messages.success(request, "Added to your timetable.")
    return redirect("timetable_view")


def timetable_entry_delete(request, pk):
    if request.method != "POST":
        return HttpResponse("POST required.", status=405)

    profile = Profile.get_active()
    entry = get_object_or_404(TimetableEntry, pk=pk, profile=profile)
    if entry.source != "manual":
        messages.error(request, "Only manually-added entries can be deleted here -- synced ones come and go with the next sync.")
        return redirect("timetable_view")

    entry.delete()
    messages.success(request, "Removed.")
    return redirect("timetable_view")


_ALLOWED_TIMETABLE_DOC_EXT = {".pdf"}
_MAX_TIMETABLE_DOC_BYTES = 20 * 1024 * 1024


def timetable_document_upload(request):
    """Store a PDF the user got some other way (college website, WhatsApp,
    a notice board photo turned into a PDF) so it's at least kept somewhere
    in Orch. Never parsed -- see the model docstring."""
    if request.method != "POST":
        return HttpResponse("POST required.", status=405)

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    upload = request.FILES.get("file")
    if not upload:
        messages.error(request, "Choose a PDF file first.")
        return redirect("timetable_view")

    ext = Path(upload.name).suffix.lower()
    if ext not in _ALLOWED_TIMETABLE_DOC_EXT:
        messages.error(request, "Only PDF files can be uploaded here.")
        return redirect("timetable_view")

    if upload.size > _MAX_TIMETABLE_DOC_BYTES:
        messages.error(request, "That file is too large (20MB limit).")
        return redirect("timetable_view")

    header = upload.read(5)
    upload.seek(0)
    if header != b"%PDF-":
        messages.error(request, "That doesn't look like a real PDF file.")
        return redirect("timetable_view")

    kind = request.POST.get("kind", "other").strip()
    if kind not in dict(TimetableDocument.KIND_CHOICES):
        kind = "other"
    title = request.POST.get("title", "").strip() or Path(upload.name).stem

    target_dir = paths.timetable_documents_dir(profile.root_path)
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w\-. ]", "_", upload.name) or "timetable.pdf"
    destination = target_dir / f"{timezone.now():%Y%m%d%H%M%S}_{safe_name}"
    with destination.open("wb") as fh:
        for chunk in upload.chunks():
            fh.write(chunk)

    TimetableDocument.objects.create(
        profile=profile,
        kind=kind,
        title=title,
        original_filename=upload.name,
        file_path=str(destination),
    )
    messages.success(request, "Uploaded.")
    return redirect("timetable_view")


def timetable_document_download(request, pk):
    profile = Profile.get_active()
    document = get_object_or_404(TimetableDocument, pk=pk, profile=profile)

    file_path = Path(document.file_path)
    if not file_path.exists():
        return HttpResponse("That file is no longer on disk.", status=404)

    response = HttpResponse(file_path.read_bytes(), content_type="application/pdf")
    safe_name = re.sub(r"[^\w\-. ]", "_", document.original_filename) or "timetable.pdf"
    response["Content-Disposition"] = f'inline; filename="{safe_name}"'
    return response


def timetable_document_delete(request, pk):
    if request.method != "POST":
        return HttpResponse("POST required.", status=405)

    profile = Profile.get_active()
    document = get_object_or_404(TimetableDocument, pk=pk, profile=profile)

    file_path = Path(document.file_path)
    if file_path.exists():
        file_path.unlink()
    document.delete()
    messages.success(request, "Deleted.")
    return redirect("timetable_view")
