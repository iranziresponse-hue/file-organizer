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
        from .core import paths

        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                "downloads_path": str(paths.DEFAULT_DOWNLOADS),
                "library_inbox_path": str(paths.DEFAULT_LIBRARY_INBOX),
            },
        )
        return obj


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
    SETUP_PATH_CHOICES = [
        ("manual", "Manual setup"),
        ("makerere", "Makerere support"),
    ]

    name = models.CharField(max_length=64)
    purpose = models.CharField(max_length=16, choices=PURPOSE_CHOICES, default="custom")
    setup_path = models.CharField(max_length=16, choices=SETUP_PATH_CHOICES, default="manual")
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


class StudyGoal(models.Model):
    """Goals belong to a study context, not only to school profiles. This
    keeps Orch useful for Makerere students and for manual paths such as
    online learning, research, work training, and personal learning."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("paused", "Paused"),
        ("done", "Done"),
    ]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="study_goals")
    title = models.CharField(max_length=180)
    subject_code = models.CharField(max_length=32, blank=True)
    target_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="active")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "target_date", "-created_at"]
        indexes = [models.Index(fields=["profile", "status"])]

    def __str__(self):
        return self.title


class FolderRule(models.Model):
    """Visual rule-builder foundation. A later UI can edit these rows as
    clauses like: if filename contains BIO101 and type is PDF, send to a
    subject/category destination."""

    MATCH_FIELD_CHOICES = [
        ("filename", "Filename"),
        ("extension", "File extension"),
        ("mime", "File type"),
        ("source_path", "Source path"),
    ]
    OPERATOR_CHOICES = [
        ("contains", "Contains"),
        ("equals", "Equals"),
        ("starts_with", "Starts with"),
        ("ends_with", "Ends with"),
        ("regex", "Regular expression"),
    ]
    ACTION_CHOICES = [
        ("route", "Route file"),
        ("review", "Send to inbox"),
        ("ignore", "Ignore"),
    ]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="folder_rules")
    name = models.CharField(max_length=120)
    enabled = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=100)
    match_field = models.CharField(max_length=24, choices=MATCH_FIELD_CHOICES, default="filename")
    operator = models.CharField(max_length=24, choices=OPERATOR_CHOICES, default="contains")
    pattern = models.CharField(max_length=240)
    file_extensions = models.JSONField(default=list, blank=True)
    subject_code = models.CharField(max_length=32, blank=True)
    category = models.CharField(max_length=64, blank=True)
    destination_template = models.CharField(max_length=512, blank=True)
    action = models.CharField(max_length=16, choices=ACTION_CHOICES, default="route")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "name"]
        indexes = [models.Index(fields=["profile", "enabled", "priority"])]

    def __str__(self):
        return self.name


class FolderImportPlan(models.Model):
    """Import-from-existing-folders foundation. Plans are read-only maps at
    first: Orch can inspect a messy folder, propose subjects and rules, and
    wait for user approval before changing anything."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("scanned", "Scanned"),
        ("approved", "Approved"),
        ("imported", "Imported"),
        ("rejected", "Rejected"),
    ]

    profile = models.ForeignKey(
        Profile, on_delete=models.SET_NULL, null=True, blank=True, related_name="folder_import_plans"
    )
    root_path = models.CharField(max_length=1024)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="draft")
    discovered_folders = models.JSONField(default=list, blank=True)
    discovered_files = models.JSONField(default=list, blank=True)
    proposed_subjects = models.JSONField(default=list, blank=True)
    proposed_rules = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["profile", "status"])]

    def __str__(self):
        return self.root_path


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


class SuggestedCourseUnit(models.Model):
    """A course unit a Makerere student typed in by hand during setup for a
    program/year/semester Orch has no verified official curriculum for yet
    (organizer/core/makerere_curricula.py has no entry, or that year/semester
    is missing from it). Not shown to other students as verified fact -- this
    is a raw student report, surfaced in Django admin so it can be checked
    against an official Makerere source and, if confirmed, added by hand to
    makerere_curricula.py. Never auto-promoted."""

    program = models.CharField(max_length=255)
    primary_value = models.CharField(max_length=64)
    secondary_value = models.CharField(max_length=64)
    code = models.CharField(max_length=32)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed = models.BooleanField(
        default=False,
        help_text="Checked against an official Makerere source. Does not affect what other students see.",
    )

    class Meta:
        unique_together = ("program", "primary_value", "secondary_value", "code")
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.code} -- {self.program} ({self.primary_value}, {self.secondary_value})"


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


class CourseGuide(models.Model):
    """A general, AI-generated academic guide for one of a profile's course
    units -- what a course like this one typically covers and why it
    matters. Explicitly NOT an official syllabus: Orch has no access to any
    institution's actual curriculum documents, so the guide is grounded
    only in the course code/name and the profile's own program/year/
    semester context, and the prompt forbids inventing institution-specific
    specifics it cannot know. One per (profile, course_code) -- regenerating
    overwrites rather than piling up duplicates."""

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="course_guides")
    course_code = models.CharField(max_length=32)
    content = models.TextField(help_text='Structured text using a "# "/"## " heading convention')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("profile", "course_code")

    def __str__(self):
        return f"Guide for {self.course_code} ({self.profile.name})"


class LearningActivity(models.Model):
    """Timeline item for the study cockpit. Most items are derived from
    sorted files, summaries, reviews, or future integrations such as MUELE.
    Keeping this separate from MoveEvent lets Orch tell a learning story
    without coupling every future feature to the file watcher."""

    ACTIVITY_CHOICES = [
        ("file_sorted", "File sorted"),
        ("summary_created", "Summary created"),
        ("review_scheduled", "Review scheduled"),
        ("digest_created", "Digest created"),
        ("muele_sync", "MUELE sync"),
        ("manual_note", "Manual note"),
    ]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="learning_activities")
    move_event = models.ForeignKey(
        MoveEvent, on_delete=models.SET_NULL, null=True, blank=True, related_name="learning_activities"
    )
    activity_type = models.CharField(max_length=32, choices=ACTIVITY_CHOICES)
    subject_code = models.CharField(max_length=32, blank=True)
    title = models.CharField(max_length=160)
    details = models.TextField(blank=True)
    happened_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-happened_at"]
        indexes = [
            models.Index(fields=["profile", "-happened_at"]),
            models.Index(fields=["profile", "subject_code"]),
        ]

    def __str__(self):
        return self.title


class SubjectMemory(models.Model):
    """Per-subject learning memory. It gives Orch a durable place to track
    recent resources, detected themes, weak areas, and last activity before
    richer learning analytics are added."""

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="subject_memories")
    code = models.CharField(max_length=32)
    title = models.CharField(max_length=160, blank=True)
    resource_count = models.PositiveIntegerField(default=0)
    current_focus = models.JSONField(default=list, blank=True)
    weak_areas = models.JSONField(default=list, blank=True)
    last_touched_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("profile", "code")
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} memory"


class SubjectTheme(models.Model):
    """Semantic subject dashboard foundation. Themes are extracted or
    entered as plain metadata so the UI can show focus areas without loud
    model-centric language."""

    SOURCE_CHOICES = [
        ("filename", "Filename"),
        ("summary", "Summary"),
        ("manual", "Manual"),
        ("muele", "MUELE"),
    ]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="subject_themes")
    subject_memory = models.ForeignKey(
        SubjectMemory, on_delete=models.CASCADE, related_name="themes", null=True, blank=True
    )
    subject_code = models.CharField(max_length=32)
    name = models.CharField(max_length=120)
    weight = models.PositiveIntegerField(default=1)
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default="filename")
    evidence = models.JSONField(default=list, blank=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["subject_code", "-weight", "name"]
        unique_together = ("profile", "subject_code", "name")
        indexes = [models.Index(fields=["profile", "subject_code"])]

    def __str__(self):
        return f"{self.subject_code}: {self.name}"


class AssignmentItem(models.Model):
    """Assignment/deadline foundation for MUELE and manual contexts."""

    STATUS_CHOICES = [
        ("open", "Open"),
        ("submitted", "Submitted"),
        ("missed", "Missed"),
        ("archived", "Archived"),
    ]
    SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("muele", "MUELE"),
        ("calendar", "Calendar"),
    ]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="assignment_items")
    subject_code = models.CharField(max_length=32, blank=True)
    title = models.CharField(max_length=180)
    due_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="open")
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default="manual")
    source_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "due_at", "-created_at"]
        indexes = [
            models.Index(fields=["profile", "status", "due_at"]),
            models.Index(fields=["profile", "subject_code"]),
        ]

    def __str__(self):
        return self.title


class ReviewItem(models.Model):
    """A spaced-review task generated from sorted learning material or
    entered manually later. This is the backbone for the review queue."""

    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("done", "Done"),
        ("skipped", "Skipped"),
    ]
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
    ]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="review_items")
    move_event = models.ForeignKey(
        MoveEvent, on_delete=models.SET_NULL, null=True, blank=True, related_name="review_items"
    )
    subject_code = models.CharField(max_length=32, blank=True)
    title = models.CharField(max_length=180)
    reason = models.CharField(max_length=240, blank=True)
    due_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="queued")
    priority = models.CharField(max_length=16, choices=PRIORITY_CHOICES, default="normal")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["status", "due_at", "-created_at"]
        indexes = [
            models.Index(fields=["profile", "status", "due_at"]),
            models.Index(fields=["profile", "subject_code"]),
        ]

    def __str__(self):
        return self.title


class SortingInboxItem(models.Model):
    """Trust layer for uncertain decisions. The watcher can place low-
    confidence files here before future UI lets the user approve, redirect,
    or teach Orch a new rule."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rerouted", "Rerouted"),
        ("ignored", "Ignored"),
    ]

    profile = models.ForeignKey(
        Profile, on_delete=models.SET_NULL, null=True, blank=True, related_name="sorting_inbox_items"
    )
    move_event = models.OneToOneField(
        MoveEvent, on_delete=models.SET_NULL, null=True, blank=True, related_name="sorting_inbox_item"
    )
    filename = models.CharField(max_length=512)
    source_path = models.CharField(max_length=1024, blank=True)
    suggested_subject = models.CharField(max_length=32, blank=True)
    suggested_destination = models.CharField(max_length=1024, blank=True)
    confidence = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    reason = models.CharField(max_length=240, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["profile", "status"])]

    def __str__(self):
        return self.filename


class LearningDigest(models.Model):
    """Generated study digest for a time window. It starts with statistics
    and lightweight notes, and can later be expanded into emailed or
    calendar-aware weekly reports."""

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="learning_digests")
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    title = models.CharField(max_length=180)
    content = models.TextField(blank=True)
    metrics = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_end"]
        indexes = [models.Index(fields=["profile", "-period_end"])]

    def __str__(self):
        return self.title


class IntegrationConnection(models.Model):
    """External learning source connection. Secrets are deliberately not
    stored here; token_reference points to a future keyring/credential-store
    entry while the database keeps only metadata and sync state."""

    PROVIDER_CHOICES = [
        ("muele", "Makerere MUELE"),
        ("moodle", "Moodle"),
        ("calendar", "Calendar"),
        ("drive", "Cloud drive"),
        ("notion", "Notion"),
        ("local", "Local folder"),
    ]
    STATUS_CHOICES = [
        ("planned", "Ready to connect"),
        ("connected", "Connected"),
        ("paused", "Paused"),
        ("error", "Needs attention"),
    ]

    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, null=True, blank=True, related_name="integration_connections"
    )
    provider = models.CharField(max_length=24, choices=PROVIDER_CHOICES)
    display_name = models.CharField(max_length=120)
    base_url = models.URLField(blank=True)
    username = models.CharField(max_length=160, blank=True)
    token_reference = models.CharField(max_length=240, blank=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="planned")
    last_sync_at = models.DateTimeField(null=True, blank=True)
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["provider", "display_name"]
        unique_together = ("profile", "provider", "display_name")

    def __str__(self):
        return self.display_name


class MueleCourse(models.Model):
    """A MUELE course the student is enrolled in and has chosen to sync
    with Orch. Each course maps to an IntegrationConnection (the MUELE
    integration) and tracks sync state per course."""

    connection = models.ForeignKey(
        IntegrationConnection, on_delete=models.CASCADE, related_name="muele_courses"
    )
    course_id = models.IntegerField(help_text="MUELE/Moodle internal course ID")
    course_name = models.CharField(max_length=255)
    course_code = models.CharField(max_length=64, blank=True, help_text="e.g. CSC2100, BSE202")
    auto_download = models.BooleanField(
        default=True,
        help_text="Automatically download new files from this course",
    )
    enrolled = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["course_name"]
        unique_together = ("connection", "course_id")
        indexes = [
            models.Index(fields=["connection", "auto_download"]),
        ]

    def __str__(self):
        return f"{self.course_code or self.course_name} (MUELE #{self.course_id})"


class ResourceRecommendation(models.Model):
    """Learning resource suggestions grounded in the user's own subject
    memory, themes, weak areas, and recent files. These rows are transparent
    discovery links, not fabricated claims about a specific video or book."""

    SOURCE_CHOICES = [
        ("youtube", "YouTube"),
        ("book", "Book"),
        ("article", "Article"),
    ]
    STATUS_CHOICES = [
        ("suggested", "Suggested"),
        ("saved", "Saved"),
        ("dismissed", "Dismissed"),
        ("opened", "Opened"),
    ]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="resource_recommendations")
    subject_code = models.CharField(max_length=32, blank=True)
    theme = models.CharField(max_length=140)
    source_type = models.CharField(max_length=16, choices=SOURCE_CHOICES)
    title = models.CharField(max_length=220)
    query = models.CharField(max_length=260)
    url = models.URLField(max_length=1024)
    reason = models.CharField(max_length=280, blank=True)
    score = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="suggested")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "-score", "-updated_at"]
        unique_together = ("profile", "subject_code", "source_type", "query")
        indexes = [
            models.Index(fields=["profile", "status", "-score"]),
            models.Index(fields=["profile", "subject_code", "source_type"]),
        ]

    def __str__(self):
        return f"{self.get_source_type_display()}: {self.title}"


class LearningRoute(models.Model):
    """A guided sequence from weak area to action: resource, summary,
    review, and progress check. Routes let Orch behave like a study coach
    while still keeping every step inspectable."""

    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("active", "Active"),
        ("done", "Done"),
        ("paused", "Paused"),
    ]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="learning_routes")
    subject_code = models.CharField(max_length=32)
    theme = models.CharField(max_length=140)
    title = models.CharField(max_length=220)
    steps = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="planned")
    current_step = models.PositiveIntegerField(default=0)
    recommendation = models.ForeignKey(
        ResourceRecommendation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="learning_routes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "subject_code", "-updated_at"]
        unique_together = ("profile", "subject_code", "theme")
        indexes = [
            models.Index(fields=["profile", "status", "subject_code"]),
        ]

    def __str__(self):
        return self.title


class ExportBundle(models.Model):
    """Portable knowledge pack foundation. A future worker can populate the
    output path with files, summaries, study guides, and a manifest."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("building", "Building"),
        ("ready", "Ready"),
        ("failed", "Failed"),
    ]
    SCOPE_CHOICES = [
        ("profile", "Profile"),
        ("subject", "Subject"),
        ("term", "Term"),
    ]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="export_bundles")
    scope = models.CharField(max_length=16, choices=SCOPE_CHOICES, default="profile")
    subject_code = models.CharField(max_length=32, blank=True)
    title = models.CharField(max_length=180)
    output_path = models.CharField(max_length=1024, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="draft")
    manifest = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title
