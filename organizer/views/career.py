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
    TimetableEntry,
)


def career_home(request):
    """Direction, active projects, weekly goal, latest digest, recent drafts,
    and a simple next-action heuristic."""
    from ..core.contexts import get_context_for_profile

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    ctx = get_context_for_profile(profile)
    career_profile = CareerProfile.get_for(profile)
    config = getattr(profile, "config", None)

    active_projects = Project.objects.filter(profile=profile, status__in=["idea", "building", "testing"])
    latest_digest = CareerDigest.objects.filter(profile=profile).first()
    recent_drafts = ContentDraft.objects.filter(profile=profile)[:5]

    cutoff = timezone.now() - timedelta(days=7)
    stale_project = None
    for project in active_projects:
        latest_update = project.updates.first()
        if not latest_update or latest_update.created_at < cutoff:
            stale_project = project
            break

    if stale_project:
        next_action = f"Log a progress update on '{stale_project.title}'; it's been quiet for a while."
    elif not Project.objects.filter(profile=profile).exists():
        next_action = "Add your first project so Orch can keep its files, links, and progress together."
    elif not latest_digest:
        next_action = "Generate this week's summary to see what moved and what you worked on."
    else:
        next_action = "Review your latest summary and draft something from the work worth sharing."

    return render(request, "organizer/career_home.html", {
        "profile": profile,
        "study_context": ctx,
        "career_profile": career_profile,
        "config": config,
        "active_projects": active_projects,
        "latest_digest": latest_digest,
        "recent_drafts": recent_drafts,
        "next_action": next_action,
        "career_track_choices": CareerProfile.CAREER_TRACK_CHOICES,
    })


def career_profile_update(request):
    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    if request.method == "POST":
        career_profile = CareerProfile.get_for(profile)
        career_track = request.POST.get("career_track", "")
        if career_track in dict(CareerProfile.CAREER_TRACK_CHOICES) or career_track == "":
            career_profile.career_track = career_track
        career_profile.weekly_goal = request.POST.get("weekly_goal", "").strip()[:240]
        career_profile.save()
        messages.success(request, "Career profile updated.")
    return redirect("career_home")


def project_studio(request):
    """List + create projects (single-view action dispatch, same pattern
    as assignment_tracker)."""
    from ..core.contexts import get_context_for_profile

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    ctx = get_context_for_profile(profile)

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        if not title:
            messages.error(request, "Enter a project title.")
            return redirect("project_studio")

        tech_stack = [t.strip() for t in request.POST.get("tech_stack", "").split(",") if t.strip()]
        Project.objects.create(
            profile=profile,
            title=title[:180],
            problem_statement=request.POST.get("problem_statement", ""),
            tech_stack=tech_stack,
            status=request.POST.get("status", "idea"),
            github_url=request.POST.get("github_url", "").strip(),
            folder_path=request.POST.get("folder_path", "").strip(),
        )
        messages.success(request, f"Added project: {title}")
        return redirect("project_studio")

    projects = Project.objects.filter(profile=profile)
    grouped = {"idea": [], "building": [], "testing": [], "shipped": []}
    for project in projects:
        grouped.setdefault(project.status, []).append(project)

    return render(request, "organizer/project_studio.html", {
        "profile": profile,
        "study_context": ctx,
        "grouped": grouped,
        "status_labels": Project.STATUS_CHOICES,
        "total_count": projects.count(),
    })


def project_detail(request, pk):
    from ..core import github_api
    from ..core.contexts import get_context_for_profile

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    project = get_object_or_404(Project, pk=pk, profile=profile)
    ctx = get_context_for_profile(profile)

    if request.method == "POST":
        action = request.POST.get("action", "update")
        if action == "add_update":
            content = request.POST.get("update_content", "").strip()
            if content:
                ProjectUpdate.objects.create(project=project, content=content)
                messages.success(request, "Progress update logged.")
            else:
                messages.error(request, "Enter some update text.")
        elif action == "refresh_github":
            owner_repo = github_api.parse_owner_repo(project.github_url)
            if not owner_repo:
                messages.error(request, "Add a valid github.com project URL first.")
            else:
                token = github_api.get_any_token(profile)
                info = github_api.get_repo_info(*owner_repo, token=token)
                if info is None:
                    messages.error(request, "Couldn't reach that repo on GitHub. Check the URL, or that it's public.")
                else:
                    project.github_stars = info["stars"]
                    project.github_synced_at = timezone.now()
                    project.save(update_fields=["github_stars", "github_synced_at"])
                    messages.success(request, f"Synced: {info['stars']} stars.")
            return redirect("project_detail", pk=project.pk)
        else:
            project.title = request.POST.get("title", project.title).strip()[:180] or project.title
            project.problem_statement = request.POST.get("problem_statement", project.problem_statement)
            project.tech_stack = [t.strip() for t in request.POST.get("tech_stack", "").split(",") if t.strip()]
            project.status = request.POST.get("status", project.status)
            project.github_url = request.POST.get("github_url", project.github_url).strip()
            project.folder_path = request.POST.get("folder_path", project.folder_path).strip()
            project.lessons_learned = request.POST.get("lessons_learned", project.lessons_learned)
            project.portfolio_description = request.POST.get("portfolio_description", project.portfolio_description)
            project.save()
            messages.success(request, "Project updated.")
        return redirect("project_detail", pk=project.pk)

    return render(request, "organizer/project_detail.html", {
        "profile": profile,
        "study_context": ctx,
        "project": project,
        "updates": project.updates.all(),
        "drafts": project.content_drafts.all(),
        "status_choices": Project.STATUS_CHOICES,
        "tech_stack_text": ", ".join(project.tech_stack),
    })


def project_delete(request, pk):
    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    project = get_object_or_404(Project, pk=pk, profile=profile)
    if request.method == "POST":
        title = project.title
        project.delete()
        messages.success(request, f"Deleted project: {title}")
    return redirect("project_studio")


def project_generate_draft(request, pk):
    from ..core import post_composer

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    project = get_object_or_404(Project, pk=pk, profile=profile)
    if request.method == "POST":
        post_type = request.POST.get("post_type", "project_update")
        draft_data = post_composer.generate_draft_from_project(project, post_type=post_type)
        draft = ContentDraft.objects.create(
            profile=project.profile,
            project=project,
            post_type=post_type,
            topic=project.title,
            raw_text=draft_data["raw_text"],
            hashtags=draft_data["hashtags"],
        )
        messages.success(request, "Draft created.")
        return redirect("content_draft_detail", pk=draft.pk)
    return redirect("project_detail", pk=pk)


def career_digest_view(request):
    from ..core.contexts import get_context_for_profile

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    ctx = get_context_for_profile(profile)
    digests = CareerDigest.objects.filter(profile=profile)

    return render(request, "organizer/career_digest.html", {
        "profile": profile,
        "study_context": ctx,
        "digests": digests,
    })


def career_digest_generate(request):
    from ..core import career_digest as career_digest_core

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    if request.method == "POST":
        career_digest_core.generate_weekly_digest(profile, log=write_log)
        messages.success(request, "This week's summary is ready.")
    return redirect("career_digest")


def content_drafts(request):
    from ..core import ai_classify, post_composer
    from ..core.contexts import get_context_for_profile

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    ctx = get_context_for_profile(profile)

    if request.method == "POST":
        raw_text = request.POST.get("raw_text", "").strip()
        if not raw_text:
            messages.error(request, "Enter some draft text.")
            return redirect("content_drafts")

        ContentDraft.objects.create(
            profile=profile,
            post_type=request.POST.get("post_type", "project_update"),
            topic=request.POST.get("topic", "").strip()[:200],
            raw_text=raw_text,
            hashtags=post_composer.suggest_hashtags(raw_text),
        )
        messages.success(request, "Draft created.")
        return redirect("content_drafts")

    drafts = ContentDraft.objects.filter(profile=profile)
    ai_config = ai_classify.load_ai_config() or {}
    ai_enabled = bool(ai_config.get("enabled") and ai_config.get("api_key"))

    return render(request, "organizer/content_drafts.html", {
        "profile": profile,
        "study_context": ctx,
        "drafts": drafts,
        "post_type_choices": ContentDraft.POST_TYPE_CHOICES,
        "ai_enabled": ai_enabled,
    })


def content_draft_detail(request, pk):
    from ..core import ai_classify
    from ..core.contexts import get_context_for_profile

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    draft = get_object_or_404(ContentDraft, pk=pk, profile=profile)
    ctx = get_context_for_profile(profile)

    if request.method == "POST":
        draft.raw_text = request.POST.get("raw_text", draft.raw_text)
        draft.topic = request.POST.get("topic", draft.topic).strip()[:200]
        draft.post_type = request.POST.get("post_type", draft.post_type)
        hashtags_raw = request.POST.get("hashtags", "")
        if hashtags_raw.strip():
            draft.hashtags = [h.strip().lstrip("#") for h in hashtags_raw.split(",") if h.strip()]
        draft.save()
        messages.success(request, "Draft saved.")
        return redirect("content_draft_detail", pk=draft.pk)

    ai_config = ai_classify.load_ai_config() or {}
    ai_enabled = bool(ai_config.get("enabled") and ai_config.get("api_key"))
    variants = [
        ("polished", draft.polished_text, "Polished"),
        ("professional", draft.professional_text, "Professional"),
        ("short", draft.short_text, "Short"),
        ("website", draft.website_text, "Website"),
    ]
    channels = IntegrationConnection.objects.filter(
        profile=profile, provider__in=_PUBLISHING_CHANNEL_PROVIDERS, status__in=["connected", "configured"]
    )

    return render(request, "organizer/content_draft_detail.html", {
        "profile": profile,
        "study_context": ctx,
        "draft": draft,
        "ai_enabled": ai_enabled,
        "variants": variants,
        "hashtags_text": ", ".join(draft.hashtags),
        "channels": channels,
        "published_posts": draft.published_posts.select_related("channel"),
    })


def content_draft_polish(request, pk):
    from ..core import post_composer

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    draft = get_object_or_404(ContentDraft, pk=pk, profile=profile)
    if request.method == "POST":
        style = request.POST.get("style", "")
        field_map = {
            "polished": "polished_text",
            "professional": "professional_text",
            "short": "short_text",
            "website": "website_text",
        }
        field = field_map.get(style)
        if not field:
            messages.error(request, "Unknown style.")
        else:
            result = post_composer.polish_text(draft.raw_text, style, log=write_log)
            if result:
                setattr(draft, field, result)
                draft.save()
                messages.success(request, f"Generated the {style} version.")
            else:
                messages.error(request, "Writing help isn't turned on, or the request failed. Set it up from Settings.")
    return redirect("content_draft_detail", pk=pk)


def content_draft_approve(request, pk):
    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    draft = get_object_or_404(ContentDraft, pk=pk, profile=profile)
    if request.method == "POST":
        draft.status = "approved"
        draft.save(update_fields=["status", "updated_at"])
        messages.success(request, "Draft approved.")
    return redirect("content_draft_detail", pk=pk)


def content_draft_mark_posted(request, pk):
    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    draft = get_object_or_404(ContentDraft, pk=pk, profile=profile)
    if request.method == "POST":
        draft.status = "posted"
        draft.save(update_fields=["status", "updated_at"])
        messages.success(request, "Marked as posted.")
    return redirect("content_draft_detail", pk=pk)


def content_draft_delete(request, pk):
    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    draft = get_object_or_404(ContentDraft, pk=pk, profile=profile)
    if request.method == "POST":
        draft.delete()
        messages.success(request, "Draft deleted.")
    return redirect("content_drafts")


def content_drafts_delete_posted(request):
    """Bulk-clears every already-published draft at once -- the list page
    otherwise has no way to clean up posts that already served their
    purpose, unlike drafts/approved ones a user is still working through."""
    if request.method != "POST":
        return HttpResponse("POST required.", status=405)
    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    count, _ = ContentDraft.objects.filter(profile=profile, status="posted").delete()
    messages.success(request, f"Cleared {count} posted draft(s).")
    return redirect("content_drafts")


_PUBLISHING_CHANNEL_PROVIDERS = ["custom_website", "github"]


def publishing_channels(request):
    from ..core import github_api, publishing

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    if request.method == "POST":
        provider = request.POST.get("provider", "custom_website")

        if provider == "github":
            display_name = request.POST.get("gh_display_name", "").strip() or "GitHub"
            owner = request.POST.get("gh_owner", "").strip()
            repo = request.POST.get("gh_repo", "").strip()
            posts_path = request.POST.get("gh_posts_path", "").strip() or "posts"
            token = request.POST.get("gh_token", "").strip()

            if not owner or not repo:
                messages.error(request, "Give the repo owner and name.")
                return redirect("publishing_channels")

            channel = IntegrationConnection.objects.create(
                profile=profile,
                provider="github",
                display_name=display_name,
                status="needs_key",
                config={"owner": owner, "repo": repo, "posts_path": posts_path},
            )
            if token:
                ok, error_message = github_api.store_channel_token(channel, token)
                if not ok:
                    messages.error(request, f"Channel saved, but the token couldn't be stored securely: {error_message}")
                else:
                    channel.status = "configured"
                    channel.save(update_fields=["status", "updated_at"])
                    messages.success(request, f"Saved {display_name}. You can manage it from Publishing channels.")
            else:
                messages.success(request, f"Channel saved, but you'll need to add a token before you can publish to {display_name}.")
            return redirect("publishing_channels")

        display_name = request.POST.get("display_name", "").strip()
        base_url = request.POST.get("base_url", "").strip()
        api_key = request.POST.get("api_key", "").strip()
        publish_mode = request.POST.get("publish_mode", "draft")

        if not display_name or not base_url:
            messages.error(request, "Give the channel a name and a base URL.")
            return redirect("publishing_channels")

        channel = IntegrationConnection.objects.create(
            profile=profile,
            provider="custom_website",
            display_name=display_name,
            base_url=base_url,
            status="configured",
            config={"publish_mode": publish_mode},
        )
        if api_key:
            ok, error_message = publishing.store_channel_api_key(channel, api_key)
            if not ok:
                channel.status = "needs_key"
                channel.save(update_fields=["status", "updated_at"])
                messages.error(request, f"Channel saved, but the key couldn't be stored securely: {error_message}")
            else:
                messages.success(request, f"Saved {display_name}. You can manage it from Publishing channels.")
        else:
            messages.success(request, f"Saved {display_name}. Add a key later if you want one-click publishing.")
        return redirect("publishing_channels")

    channels = IntegrationConnection.objects.filter(
        profile=profile,
        provider__in=_PUBLISHING_CHANNEL_PROVIDERS + ["linkedin"],
    )

    return render(request, "organizer/publishing_channels.html", {
        "profile": profile,
        "channels": channels,
    })


def publishing_channel_delete(request, pk):
    from ..core import github_api, publishing

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    channel = get_object_or_404(IntegrationConnection, pk=pk, profile=profile, provider__in=_PUBLISHING_CHANNEL_PROVIDERS)
    if request.method == "POST":
        if channel.provider == "github":
            github_api.clear_channel_token(channel)
        else:
            publishing.clear_channel_api_key(channel)
        display_name = channel.display_name
        channel.delete()
        messages.success(request, f"Disconnected {display_name}.")
    return redirect("publishing_channels")


def content_draft_publish(request, pk, channel_pk):
    from ..core import github_api, publishing

    profile = Profile.get_active()
    if not profile:
        messages.error(request, "Activate a profile first.")
        return redirect("dashboard")

    draft = get_object_or_404(ContentDraft, pk=pk, profile=profile)
    channel = get_object_or_404(IntegrationConnection, pk=channel_pk, profile=profile, provider__in=_PUBLISHING_CHANNEL_PROVIDERS)

    if request.method == "POST":
        variant = request.POST.get("variant", "raw")
        publish_fn = github_api.publish_to_github if channel.provider == "github" else publishing.publish_to_custom_website
        try:
            post = publish_fn(channel, draft, variant=variant, log=write_log)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("content_draft_detail", pk=pk)

        if post.status == "sent":
            messages.success(request, f"Published to {channel.display_name}.")
        else:
            messages.error(request, f"Publishing to {channel.display_name} failed: {post.error_message}")

    return redirect("content_draft_detail", pk=pk)


def content_draft_export_markdown(request, pk):
    from ..core import publishing

    profile = Profile.get_active()
    if not profile:
        return HttpResponse("Activate a profile first.", status=400)

    draft = get_object_or_404(ContentDraft, pk=pk, profile=profile)
    variant = request.GET.get("variant", "raw")
    markdown = publishing.export_markdown(draft, variant=variant)
    response = HttpResponse(markdown, content_type="text/markdown; charset=utf-8")
    safe_name = re.sub(r"[^\w\-. ]", "_", draft.topic or draft.get_post_type_display()) or "post"
    response["Content-Disposition"] = f'attachment; filename="{safe_name}.md"'
    return response


def content_draft_export_html(request, pk):
    from ..core import publishing

    profile = Profile.get_active()
    if not profile:
        return HttpResponse("Activate a profile first.", status=400)

    draft = get_object_or_404(ContentDraft, pk=pk, profile=profile)
    variant = request.GET.get("variant", "raw")
    html = publishing.export_html(draft, variant=variant)
    response = HttpResponse(html, content_type="text/html; charset=utf-8")
    safe_name = re.sub(r"[^\w\-. ]", "_", draft.topic or draft.get_post_type_display()) or "post"
    response["Content-Disposition"] = f'attachment; filename="{safe_name}.html"'
    return response
