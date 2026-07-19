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
    CourseConfig,
    CourseGuide,
    CurriculumEntry,
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
    overdue_reviews = ReviewItem.objects.filter(status="queued", due_at__lt=now).count()
    pending_inbox = SortingInboxItem.objects.filter(status="pending").count()
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
    except Exception:
        watcher_status = {"running": False, "recent_errors": [], "files_watched_24h": 0}
        error_summary = {"total_failed": 0, "total_success": 0, "failure_rate": 0}
        db_health = {"exists": False, "size_mb": 0, "warnings": ["Diagnostics unavailable"]}
        folder_permissions = []
        integration_failures = []
        recent_errors = []
        backups = []

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
        "orch_analytics": {
            "weekly_moves": weekly_moves,
            "monthly_moves": monthly_moves,
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
                "label": "Decision inbox",
                "value": pending_inbox,
                "detail": "pending approvals",
                "url": _admin_changelist(SortingInboxItem),
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
        "orch_inbox_items": SortingInboxItem.objects.select_related("profile").order_by("-created_at")[:8],
        "orch_reviews": ReviewItem.objects.select_related("profile").filter(status="queued").order_by("due_at")[:8],
        "orch_integrations": IntegrationConnection.objects.select_related("profile").order_by("provider", "display_name")[:8],
        "orch_updated_at": now,
        "orch_links": {
            "profiles": _admin_changelist(Profile),
            "moves": _admin_changelist(MoveEvent),
            "reviews": _admin_changelist(ReviewItem),
            "inbox": _admin_changelist(SortingInboxItem),
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

    if request.method == "POST" and "_orch_action" in request.POST:
        action = request.POST["_orch_action"]
        from .core import diagnostics as diag

        if action == "create_backup":
            result = diag.create_backup()
            if result.get("path"):
                messages.success(request, f"Backup created: {result.get('size_kb', 0)} KB")
            else:
                messages.error(request, f"Backup failed: {result.get('error', 'Unknown error')}")

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


@admin.register(SortingInboxItem)
class SortingInboxItemAdmin(admin.ModelAdmin):
    list_display = ("created_at", "profile", "filename", "suggested_subject", "confidence", "status")
    list_filter = ("profile", "status")
    search_fields = ("filename", "source_path", "suggested_subject")
    date_hierarchy = "created_at"


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


admin.site.site_header = "Orch System Admin"
admin.site.site_title = "Orch Admin"
admin.site.index_title = "Live Operations"
admin.site.index_template = "admin/orch_index.html"
admin.site.index = MethodType(_orch_index, admin.site)
