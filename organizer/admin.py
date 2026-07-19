from django.contrib import admin

from .models import CourseConfig, CurriculumEntry, MoveEvent, Profile


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
