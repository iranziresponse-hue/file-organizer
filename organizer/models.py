from django.db import models


class CourseConfig(models.Model):
    """Mirrors D:\\School\\_config.json. Single-row table -- the semester you're
    currently in. Edited from the dashboard, written back through to the JSON
    file so anything else reading that path keeps working unchanged."""

    current_year = models.CharField(max_length=32)
    current_semester = models.CharField(max_length=32)
    courses = models.JSONField(default=list, help_text="Course codes for the current semester")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.current_year} / {self.current_semester}"


class CurriculumEntry(models.Model):
    """Mirrors one entry of D:\\School\\_curriculum_map.json -- used for
    topic-based routing when a filename has no course code in it."""

    code = models.CharField(max_length=16, unique=True)
    year = models.CharField(max_length=32)
    semester = models.CharField(max_length=32)
    archived = models.BooleanField(default=False)
    keywords = models.JSONField(default=list)

    def __str__(self):
        return self.code


class MoveEvent(models.Model):
    METHOD_CHOICES = [
        ("course_code", "Course code in filename"),
        ("topic", "Topic keyword match"),
        ("ai", "AI classification"),
        ("ebook", "Ebook detected"),
        ("sensitive", "Sensitive filename/extension"),
        ("media", "Media file type"),
        ("installer", "Installer"),
        ("archive", "Archive file"),
        ("work_unsorted", "Code/project file"),
        ("unsorted", "No match -- _Unsorted"),
        ("needs_sorting", "No match -- _NeedsSorting"),
    ]

    timestamp = models.DateTimeField(auto_now_add=True)
    filename = models.CharField(max_length=512)
    source_path = models.CharField(max_length=1024)
    destination_path = models.CharField(max_length=1024, blank=True)
    method = models.CharField(max_length=32, choices=METHOD_CHOICES)
    course_code = models.CharField(max_length=16, blank=True, null=True)
    success = models.BooleanField(default=True)
    error_message = models.CharField(max_length=1024, blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.filename} -> {self.destination_path}"
