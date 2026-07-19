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
    MoveEvent,
    Profile,
    ReviewItem,
    SortingInboxItem,
    SubjectMemory,
    SubjectTheme,
    StudyGoal,
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
    now = timezone.now()
    today_start = now - timezone.timedelta(hours=24)
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

    return {
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
        },
    }


def _orch_index(self, request, extra_context=None):
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


@admin.register(ExportBundle)
class ExportBundleAdmin(admin.ModelAdmin):
    list_display = ("updated_at", "profile", "scope", "subject_code", "title", "status")
    list_filter = ("profile", "scope", "status")
    search_fields = ("title", "subject_code", "output_path")
    date_hierarchy = "updated_at"


admin.site.site_header = "Orch System Admin"
admin.site.site_title = "Orch Admin"
admin.site.index_title = "Live Operations"
admin.site.index_template = "admin/orch_index.html"
admin.site.index = MethodType(_orch_index, admin.site)
