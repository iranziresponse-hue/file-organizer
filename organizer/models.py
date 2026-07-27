from pathlib import Path

from django.db import models
from django.utils import timezone


class AppSettings(models.Model):
    """Single-row, app-wide settings that aren't specific to any one
    profile: where to watch for downloads, where ebooks land, how long
    installers sit before cleanup. Defaults are computed from this
    machine's own user profile the first time this row is created --
    never hardcoded to one person's drive layout. Editable from the
    dashboard at any time."""

    GLOBAL_DEFAULT_MODE_CHOICES = [
        ("leave", "Leave files alone"),
        ("suggest", "Suggest only"),
        ("auto_confident", "Auto only when confident"),
    ]

    downloads_path = models.CharField(max_length=1024)
    secondary_downloads_path = models.CharField(
        max_length=1024,
        blank=True,
        help_text="Optional second folder to watch, e.g. downloads on another drive. Leave blank to disable.",
    )
    library_inbox_path = models.CharField(max_length=1024)
    installer_stale_days = models.PositiveIntegerField(default=30)
    installer_delete_days = models.PositiveIntegerField(default=60)
    global_default_mode = models.CharField(
        max_length=16,
        choices=GLOBAL_DEFAULT_MODE_CHOICES,
        default="leave",
        help_text="What to do with a file that matches no profile, rule, or enabled category.",
    )

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


class GlobalSortCategory(models.Model):
    """One row per non-profile sorting category (media, ebooks, archives,
    installers, code, sensitive). Everything outside a profile's own trusted
    routing is opt-in: a category only moves files once the user has
    switched it on here. `sensitive` is always present and always enabled in
    "review" mode -- the UI locks it so it can never be turned off or set to
    auto -- private files must never move without the user seeing them
    first.
    """

    KEY_CHOICES = [
        ("media", "Media (images, music, video)"),
        ("ebooks", "Ebooks"),
        ("archives", "Archives"),
        ("installers", "Installers"),
        ("code", "Code/project files"),
        ("sensitive", "Sensitive files"),
    ]
    MODE_CHOICES = [
        ("review", "Suggest (always ask first)"),
        ("auto_high_confidence", "Auto-move when confident"),
        ("auto", "Always auto-move"),
    ]

    key = models.CharField(max_length=16, choices=KEY_CHOICES, unique=True)
    label = models.CharField(max_length=64)
    enabled = models.BooleanField(default=False)
    destination_path = models.CharField(max_length=1024, blank=True)
    mode = models.CharField(max_length=24, choices=MODE_CHOICES, default="review")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.label

    @classmethod
    def ensure_defaults(cls):
        """Seed all six categories the first time any of them is needed --
        same on-demand get_or_create pattern as AppSettings.get_solo(), so
        nothing here assumes a particular install order. `sensitive` is
        seeded already enabled and locked to review; the other five start
        disabled, keeping global sorting conservative until the user opts
        each one in."""
        from .core import paths

        defaults = [
            ("media", "Media", False, str(paths.PERSONAL_ROOT / "Media"), "review"),
            ("ebooks", "Ebooks", False, str(paths.DEFAULT_LIBRARY_INBOX), "review"),
            ("archives", "Archives", False, str(paths.PERSONAL_ROOT / "Archives"), "review"),
            ("installers", "Installers", False, str(paths.PERSONAL_ROOT / "Installers"), "review"),
            ("code", "Code/project files", False, str(paths.WORK_UNSORTED), "review"),
            ("sensitive", "Sensitive files", True, str(paths.IMPORTANT_ROOT), "review"),
        ]
        for key, label, enabled, destination_path, mode in defaults:
            cls.objects.get_or_create(
                key=key,
                defaults={
                    "label": label,
                    "enabled": enabled,
                    "destination_path": destination_path,
                    "mode": mode,
                },
            )
        return cls.objects.all()


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
    dismissed_setup_items = models.JSONField(
        default=list, blank=True,
        help_text="Keys of optional setup checklist items the user chose to hide (see dashboard's service mesh).",
    )

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


class OrganizationMemoryRule(models.Model):
    """A rule Orch learned from repeated user decisions, not one the user
    built by hand (that's FolderRule). Created the first time a Decision
    Inbox suggestion is approved with "Always do this", then reused as a
    +confidence_boost signal the next time a similar file shows up --
    checked before global category suggestions so a pattern the user has
    already taught Orch about wins over a generic category guess. Fully
    visible/editable/disableable from the Organization Memory page --
    learning here is never a black box."""

    MATCH_TYPE_CHOICES = [
        ("extension", "File extension"),
        ("filename_contains", "Filename contains"),
        ("folder_source", "Source folder"),
        ("subject_code", "Subject code"),
        ("mime_group", "File type group"),
    ]

    profile = models.ForeignKey(
        Profile, on_delete=models.SET_NULL, null=True, blank=True, related_name="organization_memory_rules"
    )
    name = models.CharField(max_length=120)
    match_type = models.CharField(max_length=24, choices=MATCH_TYPE_CHOICES, default="extension")
    match_value = models.CharField(max_length=240)
    destination_path = models.CharField(max_length=1024)
    confidence_boost = models.SmallIntegerField(default=25)
    times_approved = models.PositiveIntegerField(default=0)
    times_rejected = models.PositiveIntegerField(default=0)
    enabled = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-times_approved", "match_type", "match_value"]
        indexes = [models.Index(fields=["profile", "enabled", "match_type"])]

    def __str__(self):
        return self.name or f"{self.get_match_type_display()}: {self.match_value}"


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
        return f"{self.code} ({self.program}, {self.primary_value}, {self.secondary_value})"


class MoveEvent(models.Model):
    METHOD_CHOICES = [
        ("course_code", "Subject code in filename"),
        ("topic", "Topic keyword match"),
        ("ai", "Smart Orch suggestion"),
        ("ebook", "Ebook detected"),
        ("sensitive", "Sensitive filename/extension"),
        ("media", "Media file type"),
        ("installer", "Installer"),
        ("archive", "Archive file"),
        ("work_unsorted", "Code/project file"),
        ("unsorted", "No subject or topic match"),
        ("needs_sorting", "No active profile"),
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
    explanation = models.CharField(
        max_length=500, blank=True, help_text="Plain-language reason this file was moved here."
    )
    confidence = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="0-100 confidence score at the time of the decision. Blank for older/manual rows."
    )
    decision_source = models.CharField(
        max_length=24, blank=True, help_text="Matches SortDecision.decision_type -- which pipeline stage decided this."
    )
    undo_available = models.BooleanField(
        default=True, help_text="Set False once this move has been undone via organizer.core.undo.restore_move."
    )
    DRIVE_BACKUP_STATUS_CHOICES = [
        ("not_attempted", "Not attempted"),
        ("success", "Backed up"),
        ("failed", "Failed"),
    ]
    drive_backup_status = models.CharField(
        max_length=16, choices=DRIVE_BACKUP_STATUS_CHOICES, default="not_attempted",
        help_text="Set by organizer.core.drive_api.backup_file's fire-and-forget upload after a move. "
                   "'failed' covers offline/quota/not-connected as well as a real upload error -- "
                   "anything that means the file isn't actually backed up yet.",
    )

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


class PastPaperAnalysis(models.Model):
    """Local, free topic-frequency analysis over a subject's own past
    papers (any file already routed to its "03 Past Papers and Tests"
    folder -- see organizer.core.rules.category_from_path). No paid AI:
    text extraction and topic detection both reuse the same local
    machinery organizer.core.summarize and organizer.core.topics already
    use for document summaries and Subject Themes.

    Detects RECURRING TOPICS across multiple papers' questions, not
    literal repeated questions -- different years rarely phrase a question
    identically, so this never claims verbatim-repetition detection. One
    row per (profile, subject_code); regenerating overwrites in place,
    same pattern as CourseGuide."""

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="past_paper_analyses")
    subject_code = models.CharField(max_length=32)
    paper_count = models.PositiveIntegerField(default=0)
    # [{"text": str, "marks": int|None, "source_file": str}, ...]
    questions = models.JSONField(default=list, blank=True)
    # [{"name": str, "weight": int, "evidence": [str]}, ...] -- same shape
    # organizer.core.topics already produces for SubjectTheme.
    topics = models.JSONField(default=list, blank=True)
    # {topic_name: total_marks_seen} -- best-effort keyword match, not a
    # rigorous marks audit; labeled as such everywhere it's shown.
    marks_by_topic = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("profile", "subject_code")
        ordering = ["subject_code"]

    def __str__(self):
        return f"Past paper analysis for {self.subject_code} ({self.profile.name})"


class GradeTarget(models.Model):
    """What a student needs in the exam to hit a target overall grade,
    given coursework/test/exam weights and whatever marks are already
    known. A None score means "not yet scored", not zero -- see
    organizer.core.grade_planner.required_exam_score for how that
    distinction is surfaced as a "provisional" projection rather than a
    silent assumption. One row per (profile, subject_code); saving again
    overwrites in place, same pattern as CourseGuide/PastPaperAnalysis."""

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="grade_targets")
    subject_code = models.CharField(max_length=32)
    coursework_weight = models.PositiveSmallIntegerField(default=30, help_text="Percent of the final grade")
    coursework_score = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Blank means not yet scored")
    test_weight = models.PositiveSmallIntegerField(default=0, help_text="Percent of the final grade")
    test_score = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Blank means not yet scored")
    exam_weight = models.PositiveSmallIntegerField(default=70, help_text="Percent of the final grade")
    target_percent = models.PositiveSmallIntegerField(default=70, help_text="Overall percentage target")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("profile", "subject_code")
        ordering = ["subject_code"]

    def __str__(self):
        return f"Grade target for {self.subject_code} ({self.profile.name})"


class Flashcard(models.Model):
    """Active recall card, generated locally from content Orch already
    has -- a past paper question (organizer.core.past_papers), or a
    heading/definition parsed out of an AI FileSummary
    (organizer.core.summarize.parse_structured_text). No paid AI calls of
    its own: generation is pure extraction over existing text.

    `back` is deliberately blank for a past-paper question -- this app has
    no source of truth for the correct answer, and fabricating one would
    be worse than leaving it for the student to fill in from their own
    revision. Graded in place (not by spawning a new row per occurrence,
    unlike ReviewItem) along the same spaced-repetition ladder
    organizer.core.review uses, via organizer.core.flashcards.grade_flashcard.
    """

    CARD_TYPE_CHOICES = [
        ("past_paper_question", "Past paper question"),
        ("definition", "Definition"),
        ("concept", "Concept explainer"),
        ("manual", "Manual"),
    ]
    STATUS_CHOICES = [
        ("active", "Active"),
        ("archived", "Archived"),
    ]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="flashcards")
    subject_code = models.CharField(max_length=32, blank=True)
    card_type = models.CharField(max_length=24, choices=CARD_TYPE_CHOICES, default="manual")
    front = models.CharField(max_length=500)
    back = models.TextField(blank=True, help_text="Blank is valid -- e.g. a past-paper question with no known answer.")
    source_label = models.CharField(max_length=200, blank=True, help_text="The file this card was generated from, if any")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="active")
    interval_index = models.PositiveSmallIntegerField(default=0)
    due_at = models.DateTimeField(default=timezone.now)
    times_seen = models.PositiveIntegerField(default=0)
    times_correct = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_at"]
        indexes = [
            models.Index(fields=["profile", "status", "due_at"]),
            models.Index(fields=["profile", "subject_code"]),
        ]

    def __str__(self):
        return self.front


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
    # Tracks the most severe deadline-warning stage already notified about
    # ("warning", "urgent", "missed"), so check_deadlines can run on every
    # dashboard/study page load without sending the same warning twice.
    deadline_notified_stage = models.CharField(max_length=16, blank=True)
    evidence_path = models.CharField(
        max_length=1024, blank=True,
        help_text="A file or folder the student points at as proof of work -- a draft, a submission screenshot, whatever counts as evidence this isn't being ignored.",
    )
    # [{"text": str, "done": bool}, ...] -- "draft status" from the product
    # ask is deliberately derived from this ratio at render time rather than
    # a separate field: a second status axis alongside `status` above would
    # just be two sources of truth for the same "how far along is this"
    # question.
    checklist = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["status", "due_at", "-created_at"]
        indexes = [
            models.Index(fields=["profile", "status", "due_at"]),
            models.Index(fields=["profile", "subject_code"]),
        ]

    def __str__(self):
        return self.title

    @property
    def checklist_progress(self):
        """(done_count, total_count) over the checklist -- the basis for
        the derived draft-status label everywhere this is displayed."""
        items = self.checklist or []
        done = sum(1 for item in items if item.get("done"))
        return done, len(items)

    @property
    def draft_status(self):
        done, total = self.checklist_progress
        if total == 0:
            return "not_started"
        if done == 0:
            return "not_started"
        if done < total:
            return "in_progress"
        return "ready"


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


class StudyFocusSession(models.Model):
    """A focused study block tied to one context. It keeps the timer target,
    subject, review items, resource links, weak areas, and notes together so
    Orch can turn organization into actual study follow-up."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("abandoned", "Abandoned"),
    ]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="focus_sessions")
    subject_code = models.CharField(max_length=32, blank=True)
    title = models.CharField(max_length=180)
    target_minutes = models.PositiveIntegerField(default=25)
    review_item_ids = models.JSONField(default=list, blank=True)
    resource_ids = models.JSONField(default=list, blank=True)
    weak_areas = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="active")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["status", "-started_at"]
        indexes = [
            models.Index(fields=["profile", "status", "-started_at"]),
            models.Index(fields=["profile", "subject_code"]),
        ]

    def __str__(self):
        return self.title


class SortDecision(models.Model):
    """The trust layer's single decision log. One row is created for every
    file the sorting pipeline holds, suggests, or auto-moves (never for a
    file left untouched because nothing matched -- see
    organizer.core.sorting.decide_for_file). Auto-moved files still get a
    row here (status="moved", linked to the MoveEvent it produced) so every
    decision -- not just uncertain ones -- has a stored, plain-language
    explanation. Uncertain ones (status="pending") are what the Decision
    Inbox page shows for approval."""

    DECISION_TYPE_CHOICES = [
        ("profile_auto", "Profile auto-sort"),
        ("global_suggested", "Global category suggestion"),
        ("global_auto", "Global category auto-move"),
        ("held_sensitive", "Held for review (sensitive)"),
        ("manual", "Manual"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("moved", "Moved"),
        ("undone", "Undone"),
    ]

    profile = models.ForeignKey(
        Profile, on_delete=models.SET_NULL, null=True, blank=True, related_name="sort_decisions"
    )
    move_event = models.OneToOneField(
        MoveEvent, on_delete=models.SET_NULL, null=True, blank=True, related_name="sort_decision"
    )
    filename = models.CharField(max_length=512)
    source_path = models.CharField(max_length=1024, blank=True)
    suggested_destination = models.CharField(max_length=1024, blank=True)
    final_destination = models.CharField(max_length=1024, blank=True)
    decision_type = models.CharField(max_length=24, choices=DECISION_TYPE_CHOICES, default="manual")
    confidence = models.PositiveSmallIntegerField(default=0)
    explanation = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    matched_rule = models.CharField(max_length=120, blank=True)
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
        ("mak_timetable", "Makerere Timetable"),
        ("moodle", "Moodle"),
        ("calendar", "Calendar"),
        ("drive", "Cloud drive"),
        ("notion", "Notion"),
        ("local", "Local folder"),
        # Publishing connectors (Career tab, Post Composer) -- reuses this
        # same "external connection, secrets kept out of the DB" model
        # rather than a second parallel one. "linkedin" is a recognized
        # choice for schema stability, but has no working connect flow
        # yet: a real integration needs a registered LinkedIn Developer
        # app (client ID/secret) only the user can obtain, and the OAuth
        # design rule (never a password login) means it isn't built until
        # that's available.
        ("custom_website", "Custom website API"),
        ("markdown_export", "Markdown export"),
        ("html_export", "HTML export"),
        ("manual_copy", "Manual copy"),
        ("linkedin", "LinkedIn"),
        ("github", "GitHub"),
    ]
    STATUS_CHOICES = [
        ("planned", "Ready to connect"),
        ("configured", "Set up, not yet verified"),
        ("connected", "Connected"),
        ("needs_key", "Needs a key or token"),
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


class TimetableEntry(models.Model):
    """One row of a Makerere Timetable (timetable.mak.ac.ug) result, synced
    for a profile's specific group (e.g. "SE-2"). Teaching/Recess rows repeat
    every week (weekday + time only, no date -- the site itself doesn't
    publish a semester start date), so `weekday` matching is recomputed
    fresh against today rather than stored as a one-off date. Test/
    Examination rows are date-specific; `specific_date` holds it when the
    site's "Week N (day - day Month)" label could be parsed with confidence,
    otherwise it stays null and `date_label` keeps the raw text so nothing
    gets guessed into a wrong reminder time."""

    KIND_CHOICES = [
        ("teaching", "Teaching"),
        ("recess", "Recess Term"),
        ("test", "Test"),
        ("examination", "Examination"),
    ]
    WEEKDAY_CHOICES = [
        (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"),
        (3, "Thursday"), (4, "Friday"), (5, "Saturday"),
    ]

    SOURCE_CHOICES = [
        ("synced", "Synced"),
        ("manual", "Manual"),
    ]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="timetable_entries")
    connection = models.ForeignKey(
        IntegrationConnection, on_delete=models.CASCADE, related_name="timetable_entries",
        null=True, blank=True,
        help_text="Null for a manually-added entry -- there's no live source to attribute it to.",
    )
    source = models.CharField(max_length=8, choices=SOURCE_CHOICES, default="synced")
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY_CHOICES, null=True, blank=True)
    specific_date = models.DateField(null=True, blank=True)
    date_label = models.CharField(max_length=120, blank=True)
    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    course_code = models.CharField(max_length=32, blank=True)
    course_name = models.CharField(max_length=180, blank=True)
    room = models.CharField(max_length=64, blank=True)
    lecturer = models.CharField(max_length=120, blank=True)
    raw_group = models.CharField(max_length=64)
    last_notified_on = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["kind", "weekday", "specific_date", "start_time"]
        indexes = [
            models.Index(fields=["profile", "kind", "weekday"]),
            models.Index(fields=["profile", "kind", "specific_date"]),
        ]

    def __str__(self):
        label = self.course_code or self.course_name or "Timetable entry"
        return f"{label} ({self.get_kind_display()})"


class TimetableDocument(models.Model):
    """A PDF the user uploaded by hand -- for when the official timetable
    site (timetable.mak.ac.ug) hasn't published something yet, e.g. exam
    timetables that lag behind or a college that posts them elsewhere.
    Orch stores and serves the file back; it never tries to parse dates out
    of it, same reasoning as TimetableEntry.date_label staying raw text
    instead of a guessed date."""

    KIND_CHOICES = TimetableEntry.KIND_CHOICES + [("other", "Other")]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="timetable_documents")
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, default="other")
    title = models.CharField(max_length=180)
    original_filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=1024)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title or self.original_filename


class ResourceRecommendation(models.Model):
    """Learning resource suggestions grounded in the user's own subject
    memory, themes, weak areas, and recent files. These rows are transparent
    discovery links, not fabricated claims about a specific video or book."""

    SOURCE_CHOICES = [
        ("youtube", "YouTube"),
        ("book", "Book"),
        ("article", "Article"),
        ("github_repo", "GitHub repo"),
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


class Notification(models.Model):
    """A notification event, persisted so it survives even if the tray's
    toast popup is missed or the desktop app wasn't running to show it.
    organizer.core.notifications still pushes a live toast via the tray
    icon; this table is what backs the notifications page in the web UI."""

    URGENCY_CHOICES = [
        ("low", "Low"),
        ("normal", "Normal"),
        ("critical", "Critical"),
    ]

    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications"
    )
    title = models.CharField(max_length=180)
    message = models.CharField(max_length=500, blank=True)
    urgency = models.CharField(max_length=16, choices=URGENCY_CHOICES, default="normal")
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class SupportMessage(models.Model):
    """A message sent through the "Contact support" popup. Always saved
    here first, then emailed to the admin (config.settings.SUPPORT_INBOX_ADDRESS)
    if support_email.json is configured -- so a message is never lost even
    if the email send fails or hasn't been set up yet."""

    sender_name = models.CharField(max_length=120, blank=True)
    sender_email = models.CharField(max_length=254, blank=True)
    subject = models.CharField(max_length=180, blank=True)
    message = models.TextField()
    page_url = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    emailed_at = models.DateTimeField(null=True, blank=True)
    email_error = models.CharField(max_length=500, blank=True)
    app_state = models.JSONField(
        default=dict, blank=True,
        help_text="Optional diagnostic snapshot (app version, setup status, recent errors) the "
                   "sender chose to attach from the support popup's 'Include app diagnostics' checkbox.",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.subject or f"{self.sender_name or self.sender_email or 'Anonymous'}: {self.message[:40]}"


# ---------------------------------------------------------------------------
# Career tab -- coursework, projects, and society life turned into visible
# career progress. See organizer.core.career_digest / post_composer.
# ---------------------------------------------------------------------------

class CareerProfile(models.Model):
    """One row per Profile -- the student's career track and current
    weekly goal. Same lazy-singleton-per-profile pattern as AppSettings,
    just scoped per Profile instead of app-wide."""

    CAREER_TRACK_CHOICES = [
        ("backend_engineer", "Backend Engineer"),
        ("ai_engineer", "AI Engineer"),
        ("cybersecurity_analyst", "Cybersecurity Analyst"),
        ("data_analyst", "Data Analyst"),
        ("mobile_developer", "Mobile Developer"),
        ("cloud_engineer", "Cloud Engineer"),
        ("other", "Other"),
    ]

    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name="career_profile")
    career_track = models.CharField(max_length=32, choices=CAREER_TRACK_CHOICES, blank=True)
    weekly_goal = models.CharField(max_length=240, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Career profile for {self.profile.name}"

    @classmethod
    def get_for(cls, profile):
        obj, _ = cls.objects.get_or_create(profile=profile)
        return obj


class Project(models.Model):
    """A student engineering project, tracked as a career asset rather
    than just a folder of files. `folder_path` is an optional pointer to
    where the project's own files already live on disk -- this app has no
    file-upload pipeline anywhere, so screenshots/docs are referenced by
    path, not uploaded."""

    STATUS_CHOICES = [
        ("idea", "Idea"),
        ("building", "Building"),
        ("testing", "Testing"),
        ("shipped", "Shipped"),
    ]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="projects")
    title = models.CharField(max_length=180)
    problem_statement = models.TextField(blank=True)
    tech_stack = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="idea")
    github_url = models.URLField(blank=True)
    github_stars = models.PositiveIntegerField(null=True, blank=True)
    github_synced_at = models.DateTimeField(null=True, blank=True)
    folder_path = models.CharField(max_length=1024, blank=True)
    lessons_learned = models.TextField(blank=True)
    portfolio_description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "-updated_at"]
        indexes = [models.Index(fields=["profile", "status"])]

    def __str__(self):
        return self.title


class ProjectUpdate(models.Model):
    """One weekly-progress log entry for a Project -- append-only, never
    edited in place, so the log stays an honest history."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="updates")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Update on {self.project.title} ({self.created_at:%Y-%m-%d})"


class CareerDigest(models.Model):
    """A generated weekly narrative of what the student studied and
    built, one row per calendar week (`period_start` is that week's
    Monday). Regenerating within the same week updates that week's row in
    place (`update_or_create` keyed on `(profile, period_start)`, see
    organizer.core.career_digest.generate_weekly_digest) rather than
    piling up duplicates from repeated clicks -- but a new week always
    gets its own row, so this still reads as a real history over time,
    unlike CourseGuide/PastPaperAnalysis' single regenerable snapshot."""

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="career_digests")
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_end"]
        unique_together = ("profile", "period_start")
        indexes = [models.Index(fields=["profile", "-period_end"])]

    def __str__(self):
        return f"Career digest {self.period_start:%Y-%m-%d} to {self.period_end:%Y-%m-%d}"


class ContentDraft(models.Model):
    """A draft social/portfolio post. "Orch drafts. Orch beautifies. User
    approves. Then user clicks Post." -- this model IS that trust flow:
    `raw_text` is always locally generated, the four style variants are an
    optional AI upgrade (blank if Smart Orch isn't configured, never a
    fabricated substitute), and `status` only ever moves forward through
    an explicit user action (approve, then a self-reported "posted" mark
    after they've manually copied and posted it themselves). No automated
    publishing exists yet -- that's a later slice, and it will plug into
    this same approve-then-post flow rather than replace it."""

    POST_TYPE_CHOICES = [
        ("project_update", "Project update"),
        ("lesson_learned", "Lesson learned"),
        ("course_reflection", "Course reflection"),
        ("society_event", "Society/event participation"),
        ("tutorial", "Tutorial thread"),
        ("problem_solution", "Problem/solution story"),
        ("portfolio_launch", "Portfolio launch"),
        ("internship_update", "Internship search update"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("posted", "Posted"),
    ]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="content_drafts")
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="content_drafts")
    career_digest = models.ForeignKey(
        CareerDigest, on_delete=models.SET_NULL, null=True, blank=True, related_name="content_drafts"
    )
    post_type = models.CharField(max_length=24, choices=POST_TYPE_CHOICES, default="project_update")
    topic = models.CharField(max_length=200, blank=True, help_text="Free-text label for a draft not tied to a project or digest")
    raw_text = models.TextField()
    polished_text = models.TextField(blank=True)
    professional_text = models.TextField(blank=True)
    short_text = models.TextField(blank=True)
    website_text = models.TextField(blank=True)
    hashtags = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["profile", "status"])]

    def __str__(self):
        return self.topic or self.raw_text[:60]


class PublishedPost(models.Model):
    """A per-channel publish attempt for a ContentDraft. A draft can be
    approved once and published to several channels, each with its own
    outcome -- this is what actually varies per channel, unlike approval
    (a single fact about the content, already on ContentDraft.status).
    `payload_sent` is kept as an audit trail of exactly what left this
    machine. `channel` is SET_NULL so publish history survives a channel
    being reconfigured or removed."""

    VARIANT_CHOICES = [
        ("raw", "Raw"),
        ("polished", "Polished"),
        ("professional", "Professional"),
        ("short", "Short"),
        ("website", "Website"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
    ]

    content_draft = models.ForeignKey(ContentDraft, on_delete=models.CASCADE, related_name="published_posts")
    channel = models.ForeignKey(
        IntegrationConnection, on_delete=models.SET_NULL, null=True, blank=True, related_name="published_posts"
    )
    variant = models.CharField(max_length=16, choices=VARIANT_CHOICES, default="raw")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    payload_sent = models.JSONField(default=dict, blank=True)
    response_status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    external_url = models.URLField(blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["content_draft", "-created_at"])]

    def __str__(self):
        channel_name = self.channel.display_name if self.channel else "deleted channel"
        return f"{self.get_status_display()} to {channel_name}"


class PerformanceMetric(models.Model):
    """One timed operation, recorded by organizer.core.perf.measure(). A
    single generic log rather than a duration field bolted onto MoveEvent/
    IntegrationConnection -- keeps every operation this measures additive,
    and adding a new timed operation later is just one more OPERATION_CHOICES
    entry, not a schema change."""

    OPERATION_CHOICES = [
        ("sort_file", "Sort file"),
        ("muele_sync", "MUELE sync"),
        ("timetable_sync", "Timetable sync"),
        ("summary_generate", "Summary generation"),
        ("course_guide_generate", "Course guide generation"),
        ("page_load", "Page load"),
        ("drive_backup", "Drive backup"),
        ("github_publish", "GitHub publish"),
        ("folder_import_scan", "Folder import scan"),
    ]

    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, null=True, blank=True, related_name="performance_metrics"
    )
    operation = models.CharField(max_length=32, choices=OPERATION_CHOICES)
    duration_ms = models.PositiveIntegerField()
    query_count = models.PositiveIntegerField(null=True, blank=True)
    success = models.BooleanField(default=True)
    detail = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["operation", "-created_at"])]

    def __str__(self):
        return f"{self.get_operation_display()}: {self.duration_ms}ms"


class BackgroundTask(models.Model):
    """One slow operation run off the request/response cycle by
    organizer.core.jobs.enqueue() -- a thread-per-task runner, not a real
    task queue (no Celery/RQ, matches the free/local-only tooling the rest
    of this app uses). progress_total null means indeterminate (show a
    spinner, not a bar)."""

    KIND_CHOICES = [
        ("muele_sync", "MUELE sync"),
        ("timetable_sync", "Timetable sync"),
        ("drive_backup", "Drive backup"),
        ("summary_generate", "Summary generation"),
        ("course_guide_generate", "Course guide generation"),
        ("folder_import_scan", "Folder import scan"),
        ("github_publish", "GitHub publish"),
        ("large_folder_sort", "Large folder sort"),
    ]
    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("running", "Running"),
        ("done", "Done"),
        ("failed", "Failed"),
        ("cancelling", "Cancelling"),
        ("cancelled", "Cancelled"),
    ]

    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, null=True, blank=True, related_name="background_tasks"
    )
    kind = models.CharField(max_length=32, choices=KIND_CHOICES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="queued")
    progress_current = models.PositiveIntegerField(default=0)
    progress_total = models.PositiveIntegerField(null=True, blank=True)
    result_message = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} ({self.get_status_display()})"


class FileIndexEntry(models.Model):
    """Per-file bookkeeping so a repeated folder scan (today:
    organizer.core.study.create_import_plan(); later: any large-folder
    pass) can skip files that haven't changed since last time, instead of
    re-deriving everything from scratch on every scan. size+modified_at
    (raw stat() values, not Django DateTimeFields -- this is an internal
    comparison key, never displayed) catch the overwhelming majority of
    "unchanged" cases without opening the file at all. content_hash is
    populated lazily by organizer.core.file_index.compute_content_hash(),
    only when a caller needs certainty beyond size+mtime.

    profile is required, deliberately, not null=True: SQLite's UNIQUE
    constraint treats every NULL as distinct from every other NULL (this
    is standard SQL, not an SQLite quirk -- confirmed against this exact
    engine), so unique_together on (profile, path) would silently allow
    duplicate rows the moment profile was ever None. Every real caller
    already has a concrete profile in hand, so there's no real use case
    being given up here -- only an ambiguity being closed off (see
    organizer.core.file_index, whose three functions now require profile
    too, to fail fast and clearly at the call site instead of a confusing
    IntegrityError from this constraint)."""

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="file_index_entries")
    path = models.CharField(max_length=1024)
    size = models.BigIntegerField()
    modified_at = models.FloatField(help_text="Raw stat().st_mtime at last scan.")
    content_hash = models.CharField(max_length=64, blank=True)
    last_classification = models.CharField(max_length=255, blank=True)
    last_summary_status = models.CharField(max_length=32, blank=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_seen_at"]
        constraints = [
            models.UniqueConstraint(fields=["profile", "path"], name="unique_file_index_entry_per_profile_path"),
        ]

    def __str__(self):
        return self.path
