from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone

from pathlib import Path
from types import MethodType

from .models import (
    AppSettings,
    AssignmentItem,
    CareerDigest,
    CareerProfile,
    ContentDraft,
    CourseConfig,
    CourseGuide,
    CurriculumEntry,
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
    SupportMessage,
    ResourceRecommendation,
    ReviewItem,
    SortDecision,
    StudyFocusSession,
    SubjectMemory,
    SubjectTheme,
    StudyGoal,
    SuggestedCourseUnit,
)


def _admin_changelist(model):
    meta = model._meta
    return reverse(f"admin:{meta.app_label}_{meta.model_name}_changelist")


def _path_health(label, raw_path, required=True):
    if not raw_path:
        return {
            "label": label,
            "value": "Not set",
            "state": "warning" if required else "neutral",
            "detail": "No path configured.",
        }
    path = Path(raw_path)
    exists = path.exists()
    return {
        "label": label,
        "value": "Available" if exists else "Missing",
        "state": "good" if exists else ("warning" if required else "neutral"),
        "detail": str(path),
    }


def _percent(part, whole):
    return int((part / whole) * 100) if whole else 0


def _operations_context():
    from datetime import timedelta

    from django.db.models import Count, Q

    now = timezone.now()
    today_start = now - timedelta(hours=24)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)
    settings = AppSettings.objects.first()
    active_profile = Profile.get_active()
    total_moves = MoveEvent.objects.count()
    successful_moves = MoveEvent.objects.filter(success=True).count()
    failed_moves = MoveEvent.objects.filter(success=False).count()
    moves_24h = MoveEvent.objects.filter(timestamp__gte=today_start).count()
    pending_reviews = ReviewItem.objects.filter(status="queued").count()
    active_focus_sessions = StudyFocusSession.objects.filter(status="active").count()
    overdue_reviews = ReviewItem.objects.filter(status="queued", due_at__lt=now).count()
    pending_inbox = SortDecision.objects.filter(status="pending").count()
    open_assignments = AssignmentItem.objects.filter(status="open").count()
    enabled_rules = FolderRule.objects.filter(enabled=True).count()
    planned_integrations = IntegrationConnection.objects.filter(status="planned").count()
    errored_integrations = IntegrationConnection.objects.filter(status="error").count()
    unreviewed_suggestions = SuggestedCourseUnit.objects.filter(reviewed=False).count()

    method_rows = []
    for row in MoveEvent.objects.values("method").annotate(total=Count("id")).order_by("-total")[:8]:
        method_rows.append({
            "label": dict(MoveEvent.METHOD_CHOICES).get(row["method"], row["method"]),
            "value": row["total"],
            "percent": _percent(row["total"], total_moves),
        })

    profile_rows = []
    for row in Profile.objects.values("setup_path").annotate(total=Count("id")).order_by("setup_path"):
        profile_rows.append({
            "label": dict(Profile.SETUP_PATH_CHOICES).get(row["setup_path"], row["setup_path"]),
            "value": row["total"],
            "percent": _percent(row["total"], Profile.objects.count()),
        })

    health = []
    if settings:
        health.extend([
            _path_health("Primary downloads", settings.downloads_path),
            _path_health("Secondary downloads", settings.secondary_downloads_path, required=False),
            _path_health("Library inbox", settings.library_inbox_path),
        ])
    else:
        health.append({
            "label": "App settings",
            "value": "Missing",
            "state": "warning",
            "detail": "No AppSettings row exists yet.",
        })

    if active_profile:
        health.append(_path_health("Active profile root", active_profile.root_path))
    else:
        health.append({
            "label": "Active profile",
            "value": "None",
            "state": "warning",
            "detail": "No profile is currently active.",
        })

    # Deep analytics
    weekly_moves = MoveEvent.objects.filter(timestamp__gte=week_start).count()
    monthly_moves = MoveEvent.objects.filter(timestamp__gte=month_start).count()
    weekly_activities = LearningActivity.objects.filter(happened_at__gte=week_start).count()
    monthly_activities = LearningActivity.objects.filter(happened_at__gte=month_start).count()
    weekly_digests = LearningDigest.objects.filter(period_end__gte=week_start).count()
    monthly_exports = ExportBundle.objects.filter(created_at__gte=month_start).count()

    # Subject analytics
    subject_count = SubjectMemory.objects.count()
    subjects_with_resources = SubjectMemory.objects.filter(resource_count__gt=0).count()
    themes_count = SubjectTheme.objects.count()
    total_activities = LearningActivity.objects.count()

    # MUELE analytics
    muele_connections = IntegrationConnection.objects.filter(provider="muele")
    muele_connected = muele_connections.filter(status="connected").count()
    muele_syncs = LearningActivity.objects.filter(activity_type="muele_sync").count()
    muele_files = MoveEvent.objects.filter(method="muele_sync").count()

    # Digest analytics
    total_digests = LearningDigest.objects.count()
    total_knowledge_packs = ExportBundle.objects.filter(status="ready").count()

    # Review/Inbox analytics
    total_reviews = ReviewItem.objects.count()
    completed_reviews = ReviewItem.objects.filter(status="done").count()

    # Automation accuracy -- how often Orch's own suggestions were approved
    # vs rejected, and how often an auto-move was undone. Cheap aggregation
    # over SortDecision/MoveEvent, no separately-tracked stats needed.
    decisions_approved = SortDecision.objects.filter(status="approved").count()
    decisions_rejected = SortDecision.objects.filter(status="rejected").count()
    decisions_auto_moved = SortDecision.objects.filter(status="moved").count()
    decisions_resolved = decisions_approved + decisions_rejected
    automation_accuracy = _percent(decisions_approved, decisions_resolved)
    undo_rate = _percent(MoveEvent.objects.filter(undo_available=False, success=True).count(), successful_moves)

    # Activity trend (last 7 days)
    activity_trend = []
    for i in range(7):
        day = now - timedelta(days=i)
        day_end = day + timedelta(days=1)
        count = LearningActivity.objects.filter(
            happened_at__gte=day, happened_at__lt=day_end
        ).count()
        activity_trend.append({
            "label": day.strftime("%a"),
            "count": count,
        })
    activity_trend.reverse()

    # Method trend (last 7 days)
    method_trend = []
    for row in MoveEvent.objects.filter(
        timestamp__gte=week_start
    ).values("method").annotate(
        total=Count("id")
    ).order_by("-total")[:5]:
        method_trend.append({
            "label": dict(MoveEvent.METHOD_CHOICES).get(row["method"], row["method"]),
            "count": row["total"],
        })

    # Diagnostics
    try:
        from .core import diagnostics

        watcher_status = diagnostics.get_watcher_status()
        error_summary = diagnostics.get_error_summary()
        db_health = diagnostics.get_database_health()
        folder_permissions = diagnostics.check_all_watched_folders()
        integration_failures = diagnostics.get_integration_failures()
        recent_errors = diagnostics.get_recent_errors(days=1, limit=10)
        backups = diagnostics.list_backups()
        performance = diagnostics.get_performance_summary()
        search_index_health = diagnostics.get_search_index_health()
    except Exception:
        watcher_status = {"running": False, "recent_errors": [], "files_watched_24h": 0}
        error_summary = {"total_failed": 0, "total_success": 0, "failure_rate": 0}
        db_health = {"exists": False, "size_mb": 0, "warnings": ["Diagnostics unavailable"]}
        folder_permissions = []
        integration_failures = []
        recent_errors = []
        backups = []
        performance = {
            "window_days": 7, "files_processed_today": 0, "failed_moves_today": 0,
            "sort_avg_ms": None, "sort_slowest": None, "muele_sync": {"avg_ms": None, "count": 0},
            "timetable_sync": {"avg_ms": None, "count": 0}, "summary_generate": {"avg_ms": None, "count": 0},
            "course_guide_generate": {"avg_ms": None, "count": 0}, "page_loads": [],
            "watcher": {"running": False, "recent_errors": [], "files_watched_24h": 0},
        }
        search_index_health = {"healthy": False, "total_rows": 0, "counts_by_type": {}, "error": "Diagnostics unavailable"}

    return {
        "orch_diagnostics": {
            "watcher": watcher_status,
            "errors": error_summary,
            "database": db_health,
            "permissions": folder_permissions,
            "integration_failures": integration_failures,
            "recent_errors": recent_errors,
            "backups": backups,
        },
        "orch_performance": performance,
        "orch_search_index": search_index_health,
        "orch_analytics": {
            "weekly_moves": weekly_moves,
            "monthly_moves": monthly_moves,
            "decisions_approved": decisions_approved,
            "decisions_rejected": decisions_rejected,
            "decisions_auto_moved": decisions_auto_moved,
            "automation_accuracy": automation_accuracy,
            "undo_rate": undo_rate,
            "weekly_activities": weekly_activities,
            "monthly_activities": monthly_activities,
            "weekly_digests": weekly_digests,
            "monthly_exports": monthly_exports,
            "subject_count": subject_count,
            "subjects_with_resources": subjects_with_resources,
            "themes_count": themes_count,
            "total_activities": total_activities,
            "muele_connected": muele_connected,
            "muele_syncs": muele_syncs,
            "muele_files": muele_files,
            "total_digests": total_digests,
            "total_knowledge_packs": total_knowledge_packs,
            "total_reviews": total_reviews,
            "completed_reviews": completed_reviews,
            "activity_trend": activity_trend,
            "method_trend": method_trend,
        },
        "orch_cards": [
            {
                "label": "Profiles",
                "value": Profile.objects.count(),
                "detail": f"{Profile.objects.filter(is_active=True).count()} active",
                "url": _admin_changelist(Profile),
            },
            {
                "label": "File decisions",
                "value": total_moves,
                "detail": f"{successful_moves} sorted, {failed_moves} failed",
                "url": _admin_changelist(MoveEvent),
            },
            {
                "label": "Last 24 hours",
                "value": moves_24h,
                "detail": "moves recorded",
                "url": _admin_changelist(MoveEvent),
            },
            {
                "label": "Review queue",
                "value": pending_reviews,
                "detail": f"{overdue_reviews} overdue",
                "url": _admin_changelist(ReviewItem),
            },
            {
                "label": "Focus sessions",
                "value": StudyFocusSession.objects.count(),
                "detail": f"{active_focus_sessions} active",
                "url": _admin_changelist(StudyFocusSession),
            },
            {
                "label": "Decision inbox",
                "value": pending_inbox,
                "detail": "pending approvals",
                "url": _admin_changelist(SortDecision),
            },
            {
                "label": "Open assignments",
                "value": open_assignments,
                "detail": "tracked deadlines",
                "url": _admin_changelist(AssignmentItem),
            },
            {
                "label": "Enabled rules",
                "value": enabled_rules,
                "detail": "folder routing rules",
                "url": _admin_changelist(FolderRule),
            },
            {
                "label": "Integrations",
                "value": IntegrationConnection.objects.count(),
                "detail": f"{planned_integrations} planned, {errored_integrations} need attention",
                "url": _admin_changelist(IntegrationConnection),
            },
            {
                "label": "Curriculum contributions",
                "value": SuggestedCourseUnit.objects.count(),
                "detail": f"{unreviewed_suggestions} awaiting review",
                "url": _admin_changelist(SuggestedCourseUnit),
            },
        ],
        "orch_active_profile": active_profile,
        "orch_method_rows": method_rows,
        "orch_profile_rows": profile_rows,
        "orch_health": health,
        "orch_recent_moves": MoveEvent.objects.select_related("profile").order_by("-timestamp")[:10],
        "orch_inbox_items": SortDecision.objects.select_related("profile").order_by("-created_at")[:8],
        "orch_reviews": ReviewItem.objects.select_related("profile").filter(status="queued").order_by("due_at")[:8],
        "orch_integrations": IntegrationConnection.objects.select_related("profile").order_by("provider", "display_name")[:8],
        "orch_updated_at": now,
        "orch_links": {
            "profiles": _admin_changelist(Profile),
            "moves": _admin_changelist(MoveEvent),
            "reviews": _admin_changelist(ReviewItem),
            "focus": _admin_changelist(StudyFocusSession),
            "inbox": _admin_changelist(SortDecision),
            "memory": _admin_changelist(OrganizationMemoryRule),
            "rules": _admin_changelist(FolderRule),
            "imports": _admin_changelist(FolderImportPlan),
            "integrations": _admin_changelist(IntegrationConnection),
            "digests": _admin_changelist(LearningDigest),
            "exports": _admin_changelist(ExportBundle),
            "suggestions": _admin_changelist(SuggestedCourseUnit),
        },
    }


def _orch_index(self, request, extra_context=None):
    from django.contrib import messages
    from django.shortcuts import redirect

    if request.method == "POST" and "_orch_action" in request.POST:
        action = request.POST["_orch_action"]
        from .core import diagnostics as diag

        if action == "create_backup":
            result = diag.create_backup()
            if result.get("path"):
                messages.success(request, f"Backup created: {result.get('size_kb', 0)} KB")
            else:
                messages.error(request, f"Backup failed: {result.get('error', 'Unknown error')}")

        elif action == "restore_backup":
            backup_path = request.POST.get("backup_path", "").strip()
            if not backup_path:
                messages.error(request, "Pick a backup to restore first.")
            else:
                result = diag.restore_backup(backup_path)
                if result.get("success"):
                    messages.success(request, "Database restored. The previous database was backed up first.")
                else:
                    messages.error(request, f"Restore failed: {result.get('error', 'Unknown error')}")

        elif action == "vacuum_db":
            result = diag.vacuum_database()
            if result.get("success"):
                messages.success(request, f"Database vacuumed: {result.get('before_mb', 0)}MB -> {result.get('after_mb', 0)}MB ({result.get('reclaimed_kb', 0)} KB reclaimed)")
            else:
                messages.error(request, f"Vacuum failed: {result.get('error', 'Unknown error')}")

        elif action == "reindex_db":
            result = diag.reindex_database()
            if result.get("success"):
                messages.success(request, "Database reindexed successfully.")
            else:
                messages.error(request, f"Reindex failed: {result.get('error', 'Unknown error')}")

        # Redirect after processing so a page refresh never resubmits a
        # backup/vacuum/reindex action.
        return redirect("admin:index")

    context = {}
    if extra_context:
        context.update(extra_context)
    context.update(_operations_context())
    return AdminSite.index(self, request, extra_context=context)


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "downloads_path",
        "secondary_downloads_path",
        "library_inbox_path",
        "installer_stale_days",
        "installer_delete_days",
    )


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "purpose", "setup_path", "primary_label", "secondary_label", "is_active", "created_at")
    list_filter = ("purpose", "setup_path", "is_active")
    search_fields = ("name", "root_path", "primary_label", "secondary_label")
    date_hierarchy = "created_at"


@admin.register(CourseConfig)
class CourseConfigAdmin(admin.ModelAdmin):
    list_display = ("profile", "primary_value", "secondary_value", "groups", "updated_at")
    search_fields = ("profile__name", "primary_value", "secondary_value")


@admin.register(CurriculumEntry)
class CurriculumEntryAdmin(admin.ModelAdmin):
    list_display = ("code", "profile", "primary_value", "secondary_value", "archived")
    list_filter = ("profile", "archived")
    search_fields = ("code", "keywords", "profile__name")


@admin.register(MoveEvent)
class MoveEventAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "profile", "filename", "method", "course_code", "success", "destination_path")
    list_filter = ("profile", "method", "success")
    search_fields = ("filename", "source_path", "destination_path", "course_code", "error_message")
    date_hierarchy = "timestamp"


@admin.register(FileSummary)
class FileSummaryAdmin(admin.ModelAdmin):
    list_display = ("move_event", "created_at", "updated_at")
    search_fields = ("move_event__filename", "content")
    date_hierarchy = "created_at"


@admin.register(CourseGuide)
class CourseGuideAdmin(admin.ModelAdmin):
    list_display = ("course_code", "profile", "created_at", "updated_at")
    list_filter = ("profile",)
    search_fields = ("course_code", "content", "profile__name")
    date_hierarchy = "created_at"


@admin.register(PastPaperAnalysis)
class PastPaperAnalysisAdmin(admin.ModelAdmin):
    list_display = ("subject_code", "profile", "paper_count", "generated_at")
    list_filter = ("profile",)
    search_fields = ("subject_code", "profile__name")
    date_hierarchy = "generated_at"


@admin.register(GradeTarget)
class GradeTargetAdmin(admin.ModelAdmin):
    list_display = ("subject_code", "profile", "target_percent", "coursework_score", "test_score", "updated_at")
    list_filter = ("profile",)
    search_fields = ("subject_code", "profile__name")
    date_hierarchy = "updated_at"


@admin.register(Flashcard)
class FlashcardAdmin(admin.ModelAdmin):
    list_display = ("front", "subject_code", "profile", "card_type", "status", "due_at", "times_seen", "times_correct")
    list_filter = ("profile", "card_type", "status")
    search_fields = ("front", "back", "subject_code")
    date_hierarchy = "due_at"


@admin.register(LearningActivity)
class LearningActivityAdmin(admin.ModelAdmin):
    list_display = ("happened_at", "profile", "activity_type", "subject_code", "title")
    list_filter = ("profile", "activity_type")
    search_fields = ("title", "details", "subject_code")
    date_hierarchy = "happened_at"


@admin.register(SubjectMemory)
class SubjectMemoryAdmin(admin.ModelAdmin):
    list_display = ("code", "profile", "resource_count", "last_touched_at", "updated_at")
    list_filter = ("profile",)
    search_fields = ("code", "title")


@admin.register(SubjectTheme)
class SubjectThemeAdmin(admin.ModelAdmin):
    list_display = ("subject_code", "name", "profile", "weight", "source", "last_seen_at")
    list_filter = ("profile", "source")
    search_fields = ("subject_code", "name")


@admin.register(AssignmentItem)
class AssignmentItemAdmin(admin.ModelAdmin):
    list_display = ("due_at", "profile", "subject_code", "title", "status", "source")
    list_filter = ("profile", "status", "source")
    search_fields = ("title", "subject_code", "notes")
    date_hierarchy = "due_at"


@admin.register(StudyGoal)
class StudyGoalAdmin(admin.ModelAdmin):
    list_display = ("profile", "subject_code", "title", "status", "target_date")
    list_filter = ("profile", "status")
    search_fields = ("title", "subject_code", "notes")


@admin.register(FolderRule)
class FolderRuleAdmin(admin.ModelAdmin):
    list_display = ("profile", "priority", "name", "match_field", "operator", "pattern", "action", "enabled")
    list_filter = ("profile", "enabled", "action", "match_field")
    search_fields = ("name", "pattern", "subject_code", "category")


@admin.register(FolderImportPlan)
class FolderImportPlanAdmin(admin.ModelAdmin):
    list_display = ("updated_at", "profile", "root_path", "status")
    list_filter = ("profile", "status")
    search_fields = ("root_path", "notes")
    date_hierarchy = "updated_at"


@admin.register(ReviewItem)
class ReviewItemAdmin(admin.ModelAdmin):
    list_display = ("due_at", "profile", "subject_code", "title", "status", "priority")
    list_filter = ("profile", "status", "priority")
    search_fields = ("title", "reason", "subject_code")
    date_hierarchy = "due_at"


@admin.register(StudyFocusSession)
class StudyFocusSessionAdmin(admin.ModelAdmin):
    list_display = ("started_at", "profile", "subject_code", "title", "target_minutes", "status")
    list_filter = ("profile", "status", "subject_code")
    search_fields = ("title", "subject_code", "notes")
    date_hierarchy = "started_at"


@admin.register(SortDecision)
class SortDecisionAdmin(admin.ModelAdmin):
    list_display = ("created_at", "profile", "filename", "decision_type", "confidence", "status")
    list_filter = ("profile", "status", "decision_type")
    search_fields = ("filename", "source_path", "matched_rule", "explanation")
    date_hierarchy = "created_at"


@admin.register(GlobalSortCategory)
class GlobalSortCategoryAdmin(admin.ModelAdmin):
    list_display = ("label", "key", "enabled", "mode", "destination_path")
    list_filter = ("enabled", "mode")


@admin.register(OrganizationMemoryRule)
class OrganizationMemoryRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "profile", "match_type", "match_value", "times_approved", "times_rejected", "enabled")
    list_filter = ("profile", "match_type", "enabled")
    search_fields = ("name", "match_value", "destination_path")


@admin.register(LearningDigest)
class LearningDigestAdmin(admin.ModelAdmin):
    list_display = ("period_end", "profile", "title", "created_at")
    list_filter = ("profile",)
    search_fields = ("title", "content")
    date_hierarchy = "period_end"


@admin.register(IntegrationConnection)
class IntegrationConnectionAdmin(admin.ModelAdmin):
    list_display = ("display_name", "provider", "profile", "status", "base_url", "last_sync_at")
    list_filter = ("provider", "status")
    search_fields = ("display_name", "base_url", "username")


@admin.register(ResourceRecommendation)
class ResourceRecommendationAdmin(admin.ModelAdmin):
    list_display = ("updated_at", "profile", "subject_code", "source_type", "status", "score", "title")
    list_filter = ("profile", "source_type", "status", "subject_code")
    search_fields = ("title", "query", "theme", "reason")
    date_hierarchy = "updated_at"


@admin.register(LearningRoute)
class LearningRouteAdmin(admin.ModelAdmin):
    list_display = ("updated_at", "profile", "subject_code", "theme", "status", "current_step", "title")
    list_filter = ("profile", "status", "subject_code")
    search_fields = ("title", "theme", "subject_code")
    date_hierarchy = "updated_at"


@admin.register(ExportBundle)
class ExportBundleAdmin(admin.ModelAdmin):
    list_display = ("updated_at", "profile", "scope", "subject_code", "title", "status")
    list_filter = ("profile", "scope", "status")
    search_fields = ("title", "subject_code", "output_path")
    date_hierarchy = "updated_at"


@admin.register(SuggestedCourseUnit)
class SuggestedCourseUnitAdmin(admin.ModelAdmin):
    list_display = ("code", "program", "primary_value", "secondary_value", "reviewed", "submitted_at")
    list_filter = ("reviewed", "program")
    search_fields = ("code", "program")
    date_hierarchy = "submitted_at"
    actions = ["mark_reviewed"]

    @admin.action(description="Mark selected as reviewed")
    def mark_reviewed(self, request, queryset):
        queryset.update(reviewed=True)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "profile", "urgency", "created_at", "read_at")
    list_filter = ("urgency", "profile")
    search_fields = ("title", "message")
    date_hierarchy = "created_at"


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "sender_name", "sender_email", "created_at", "emailed_at", "email_error")
    search_fields = ("subject", "sender_name", "sender_email", "message")
    date_hierarchy = "created_at"


@admin.register(CareerProfile)
class CareerProfileAdmin(admin.ModelAdmin):
    list_display = ("profile", "career_track", "weekly_goal", "updated_at")
    list_filter = ("career_track",)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "profile", "status", "github_url", "updated_at")
    list_filter = ("profile", "status")
    search_fields = ("title", "problem_statement", "github_url")
    date_hierarchy = "updated_at"


@admin.register(ProjectUpdate)
class ProjectUpdateAdmin(admin.ModelAdmin):
    list_display = ("project", "created_at")
    search_fields = ("content", "project__title")
    date_hierarchy = "created_at"


@admin.register(CareerDigest)
class CareerDigestAdmin(admin.ModelAdmin):
    list_display = ("profile", "period_start", "period_end", "created_at")
    list_filter = ("profile",)
    date_hierarchy = "period_end"


@admin.register(ContentDraft)
class ContentDraftAdmin(admin.ModelAdmin):
    list_display = ("topic", "profile", "post_type", "status", "created_at")
    list_filter = ("profile", "post_type", "status")
    search_fields = ("topic", "raw_text")
    date_hierarchy = "created_at"


@admin.register(PublishedPost)
class PublishedPostAdmin(admin.ModelAdmin):
    list_display = ("content_draft", "channel", "variant", "status", "created_at")
    list_filter = ("status", "variant", "channel")
    search_fields = ("content_draft__topic", "error_message")
    date_hierarchy = "created_at"


admin.site.site_header = "Orch System Admin"
admin.site.site_title = "Orch Admin"
admin.site.index_title = "Live Operations"
admin.site.index_template = "admin/orch_index.html"
admin.site.index = MethodType(_orch_index, admin.site)
# Without this, clicking the Admin nav link and changing your mind means
# either logging in or closing the window -- there's no link back to the
# dashboard on the stock Django login page.
admin.site.login_template = "admin/orch_login.html"
