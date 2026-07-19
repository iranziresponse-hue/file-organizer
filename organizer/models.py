from pathlib import Path

from django.db import models


class AppSettings(models.Model):
    """Single-row, app-wide settings that aren't specific to any one
    profile: where to watch for downloads, where ebooks land, how long
    installers sit before cleanup. Defaults are computed from this
    machine's own user profile the first time this row is created --
    never hardcoded to one person's drive layout. Editable from the
    dashboard at any time."""

    downloads_path = models.CharField(max_length=1024)
    secondary_downloads_path = models.CharField(
        max_length=1024,
        blank=True,
        help_text="Optional second folder to watch, e.g. downloads on another drive. Leave blank to disable.",
    )
    library_inbox_path = models.CharField(max_length=1024)
    installer_stale_days = models.PositiveIntegerField(default=30)
    installer_delete_days = models.PositiveIntegerField(default=60)

    def __str__(self):
        return "App settings"

    @classmethod
    def get_solo(cls):
        obj = cls.objects.first()
        if obj:
            return obj
        from .core import paths

        return cls.objects.create(
            downloads_path=str(paths.DEFAULT_DOWNLOADS),
            library_inbox_path=str(paths.DEFAULT_LIBRARY_INBOX),
        )


class Profile(models.Model):
    """A context to organize files into -- School, Online courses, Work
    training, Research, whatever the user names it. Each profile owns its
    own root folder, its own primary/secondary grouping labels (e.g. "Year"
    / "Semester" for a student, "Year" / "Bootcamp" for an online learner),
    and its own subject list. Exactly one profile is active at a time --
    that's the one the watcher routes files into.
    """

    PURPOSE_CHOICES = [
        ("school", "School"),
        ("online", "Online learning"),
        ("research", "Research"),
        ("work", "Work training"),
        ("custom", "Custom"),
    ]

    name = models.CharField(max_length=64)
    purpose = models.CharField(max_length=16, choices=PURPOSE_CHOICES, default="custom")
    primary_label = models.CharField(max_length=32, default="Year")
    secondary_label = models.CharField(max_length=32, default="Semester")
    root_path = models.CharField(max_length=1024, help_text="Folder this profile organizes files into")
    ai_fallback_enabled = models.BooleanField(
        default=False,
        help_text="Optional: use an AI classifier as a last resort for files that match nothing else. Needs your own API key in ai_config.json.",
    )
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_active:
            Profile.objects.exclude(pk=self.pk).update(is_active=False)

    @classmethod
    def get_active(cls):
        return cls.objects.filter(is_active=True).first()


class CourseConfig(models.Model):
    """Mirrors <profile root>\\_config.json -- the primary/secondary group
    (e.g. Year 2 / Semester 1, or 2026 / Python Bootcamp) a profile is
    currently sorting into. Edited from the dashboard, written back through
    to the JSON file so the watcher's fresh-read-every-poll design keeps
    working unchanged."""

    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name="config")
    primary_value = models.CharField(max_length=64)
    secondary_value = models.CharField(max_length=64)
    groups = models.JSONField(default=list, help_text="Course/subject/module codes for this profile")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.primary_value} / {self.secondary_value}"


class CurriculumEntry(models.Model):
    """Mirrors one entry of <profile root>\\_curriculum_map.json -- used for
    topic-based routing when a filename has no course/subject code in it."""

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="curriculum_entries")
    code = models.CharField(max_length=16)
    primary_value = models.CharField(max_length=64)
    secondary_value = models.CharField(max_length=64)
    archived = models.BooleanField(default=False)
    keywords = models.JSONField(default=list)

    class Meta:
        unique_together = ("profile", "code")

    def __str__(self):
        return self.code


class MoveEvent(models.Model):
    METHOD_CHOICES = [
        ("course_code", "Subject code in filename"),
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

    profile = models.ForeignKey(
        Profile, on_delete=models.SET_NULL, null=True, blank=True, related_name="move_events"
    )
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

    def is_summarizable(self):
        from .core import summarize

        if Path(self.filename).suffix.lstrip(".").lower() not in summarize.SUPPORTED_EXTENSIONS:
            return False
        if not self.destination_path:
            return False
        return Path(self.destination_path).exists()


class FileSummary(models.Model):
    """A long-form AI summary of a sorted document, cross-referenced against
    whatever else was already sitting in its destination folder. One per
    MoveEvent -- regenerating overwrites the previous content rather than
    piling up duplicates."""

    move_event = models.OneToOneField(MoveEvent, on_delete=models.CASCADE, related_name="summary")
    content = models.TextField(help_text='Structured text using a "# "/"## " heading convention')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Summary for {self.move_event.filename}"
