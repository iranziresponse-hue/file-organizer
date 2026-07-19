"""Study context definitions for each profile purpose.

Each context type gets its own label defaults, routing behavior, icon,
dashboard panels, and suggested integrations. This module is the single
source of truth for how Orch behaves differently for a University student
vs. an Online Learner vs. a Researcher vs. a Work Trainee.
"""

from dataclasses import dataclass, field
from typing import List

from . import paths


@dataclass
class StudyContext:
    """Defines the behavior and appearance of a study context type."""

    purpose: str
    label: str
    icon: str  # emoji
    description: str

    # Group label defaults
    primary_label: str
    secondary_label: str

    # Suggested group values based on the context
    primary_presets: List[str] = field(default_factory=list)
    secondary_presets: List[str] = field(default_factory=list)

    # Which features are enabled for this context
    show_subject_memory: bool = True
    show_review_queue: bool = True
    show_integrations: bool = False
    show_goal_tracking: bool = True
    show_deadlines: bool = False

    # Suggested integrations
    suggested_integrations: List[str] = field(default_factory=list)

    # Default root path hint
    default_root_hint: str = ""

    # Whether subject codes are typically from a verified curriculum
    has_verified_curriculum: bool = False

    def __post_init__(self):
        if not self.default_root_hint:
            self.default_root_hint = str(paths.PERSONAL_ROOT / self.label.replace(" ", ""))


# All supported study contexts
CONTEXTS: dict[str, StudyContext] = {
    "school": StudyContext(
        purpose="school",
        label="University / School",
        icon="🎓",
        description="Academic courses, lecture notes, assignments, past papers, and semester-based study. Supports Makerere University with MUELE integration.",
        primary_label="Year",
        secondary_label="Semester",
        primary_presets=["Year 1", "Year 2", "Year 3", "Year 4", "Year 5"],
        secondary_presets=["Semester 1", "Semester 2", "Semester 3"],
        show_subject_memory=True,
        show_review_queue=True,
        show_integrations=True,
        show_goal_tracking=True,
        show_deadlines=True,
        suggested_integrations=["muele", "calendar"],
        default_root_hint="",
        has_verified_curriculum=True,
    ),
    "online": StudyContext(
        purpose="online",
        label="Online Courses",
        icon="💻",
        description="Udemy, Coursera, edX, bootcamps, and self-paced learning. Track modules, bootcamps, and course completion.",
        primary_label="Year",
        secondary_label="Course",
        primary_presets=["2024", "2025", "2026"],
        secondary_presets=["Python Bootcamp", "Web Dev", "Data Science", "UX Design"],
        show_subject_memory=True,
        show_review_queue=True,
        show_integrations=False,
        show_goal_tracking=True,
        show_deadlines=False,
        suggested_integrations=[],
        has_verified_curriculum=False,
    ),
    "research": StudyContext(
        purpose="research",
        label="Research",
        icon="🔬",
        description="Research papers, journals, experiments, theses, and reference materials. Organize by topics and research phases.",
        primary_label="Topic",
        secondary_label="Phase",
        primary_presets=["Machine Learning", "Data Science", "Biology", "Physics", "Economics"],
        secondary_presets=["Literature Review", "Methodology", "Experiments", "Writing", "Publication"],
        show_subject_memory=True,
        show_review_queue=True,
        show_integrations=False,
        show_goal_tracking=True,
        show_deadlines=True,
        suggested_integrations=["calendar"],
        has_verified_curriculum=False,
    ),
    "work": StudyContext(
        purpose="work",
        label="Work Training",
        icon="💼",
        description="Professional development, certifications, workshops, and workplace learning. Organize by department and training cycle.",
        primary_label="Department",
        secondary_label="Training Cycle",
        primary_presets=["Engineering", "Product", "Design", "Marketing", "Data"],
        secondary_presets=["Q1 2026", "Q2 2026", "Q3 2026", "Q4 2026"],
        show_subject_memory=False,
        show_review_queue=False,
        show_integrations=False,
        show_goal_tracking=True,
        show_deadlines=True,
        suggested_integrations=["calendar"],
        has_verified_curriculum=False,
    ),
    "custom": StudyContext(
        purpose="custom",
        label="Personal Learning",
        icon="🧠",
        description="Any self-directed learning path. Set your own labels, subjects, and structure.",
        primary_label="Category",
        secondary_label="Subcategory",
        primary_presets=["Programming", "Design", "Languages", "Music", "Health"],
        secondary_presets=["Beginner", "Intermediate", "Advanced"],
        show_subject_memory=True,
        show_review_queue=True,
        show_integrations=False,
        show_goal_tracking=True,
        show_deadlines=False,
        suggested_integrations=[],
        has_verified_curriculum=False,
    ),
}


def get_context(purpose: str) -> StudyContext:
    """Get the StudyContext definition for a given purpose string.

    Falls back to 'custom' (Personal Learning) for unknown purposes.
    """
    return CONTEXTS.get(purpose, CONTEXTS["custom"])


def get_context_for_profile(profile) -> StudyContext:
    """Get the StudyContext that applies to a given Profile instance."""
    return get_context(profile.purpose if profile else "custom")


def get_purpose_choices() -> list[tuple[str, str]]:
    """Get purpose choices for use in Django model field choices."""
    return [(p, ctx.label) for p, ctx in CONTEXTS.items()]