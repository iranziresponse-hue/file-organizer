from django.contrib import admin

from .models import CourseConfig, CurriculumEntry, MoveEvent


@admin.register(CourseConfig)
class CourseConfigAdmin(admin.ModelAdmin):
    list_display = ("current_year", "current_semester", "courses", "updated_at")


@admin.register(CurriculumEntry)
class CurriculumEntryAdmin(admin.ModelAdmin):
    list_display = ("code", "year", "semester", "archived")
    search_fields = ("code",)


@admin.register(MoveEvent)
class MoveEventAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "filename", "method", "course_code", "success")
    list_filter = ("method", "success")
    search_fields = ("filename", "destination_path")
