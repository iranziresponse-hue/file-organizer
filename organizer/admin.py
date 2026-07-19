from django.contrib import admin

from .models import AppSettings, CourseConfig, CurriculumEntry, FileSummary, MoveEvent, Profile


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    list_display = ("downloads_path", "secondary_downloads_path", "library_inbox_path")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "purpose", "primary_label", "secondary_label", "is_active", "created_at")
    list_filter = ("purpose", "is_active")


@admin.register(CourseConfig)
class CourseConfigAdmin(admin.ModelAdmin):
    list_display = ("profile", "primary_value", "secondary_value", "groups", "updated_at")


@admin.register(CurriculumEntry)
class CurriculumEntryAdmin(admin.ModelAdmin):
    list_display = ("code", "profile", "primary_value", "secondary_value", "archived")
    search_fields = ("code",)


@admin.register(MoveEvent)
class MoveEventAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "profile", "filename", "method", "course_code", "success")
    list_filter = ("profile", "method", "success")
    search_fields = ("filename", "destination_path")


@admin.register(FileSummary)
class FileSummaryAdmin(admin.ModelAdmin):
    list_display = ("move_event", "created_at", "updated_at")
