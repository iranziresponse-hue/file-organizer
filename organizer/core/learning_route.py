"""Learning Route — turns weak areas into a sequenced study path.

For each subject with weak areas, Orch builds a route:
1. Watch a recommended video / read a book chapter (Resource Radar)
2. Create or review a document summary (File Intelligence)
3. Complete a review item (Review Queue)
4. Check progress (Subject Memory stats)

This makes Orch feel like a study coach, not just a file organizer.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List

from django.utils import timezone


@dataclass
class RouteStep:
    """A single step in a learning route."""
    step_number: int
    step_type: str  # "watch", "read", "review", "check"
    title: str
    description: str
    progress: float  # 0.0 to 1.0
    is_complete: bool
    action_url: str | None = None
    action_label: str | None = None
    subject_code: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class SubjectRoute:
    """A learning route for a single subject."""
    subject_code: str
    subject_title: str
    weak_areas: List[str]
    steps: List[RouteStep]
    progress_summary: str
    created_at: datetime = field(default_factory=timezone.now)


def _get_subject_stats(profile, subject_code: str) -> dict:
    """Get study statistics for a subject to build the route."""
    from organizer.models import (
        FileSummary,
        LearningActivity,
        MoveEvent,
        ResourceRecommendation,
        ReviewItem,
        SubjectMemory,
    )

    memory = SubjectMemory.objects.filter(profile=profile, code=subject_code).first()
    if not memory:
        return {"weak_areas": [], "focus": [], "resource_count": 0}

    resources = ResourceRecommendation.objects.filter(
        profile=profile, subject_code=subject_code
    ).exclude(status="dismissed")
    saved_resources = resources.filter(status="saved").count()
    watched_resources = resources.filter(status="opened").count()
    total_resources = resources.count()

    files = MoveEvent.objects.filter(profile=profile, course_code=subject_code, success=True)
    summarizable = sum(1 for e in files if e.is_summarizable())
    summarized = FileSummary.objects.filter(
        move_event__profile=profile, move_event__course_code=subject_code
    ).count()

    reviews = ReviewItem.objects.filter(profile=profile, subject_code=subject_code)
    reviews_done = reviews.filter(status="done").count()
    reviews_queued = reviews.filter(status="queued").count()
    total_reviews = reviews.count()

    return {
        "weak_areas": memory.weak_areas or [],
        "focus": memory.current_focus or [],
        "resource_count": memory.resource_count,
        "last_touched": memory.last_touched_at,
        "saved_resources": saved_resources,
        "watched_resources": watched_resources,
        "total_resources": total_resources,
        "summarizable_files": summarizable,
        "summarized_files": summarized,
        "reviews_done": reviews_done,
        "reviews_queued": reviews_queued,
        "total_reviews": total_reviews,
    }


def build_route_for_subject(profile, subject_code: str) -> SubjectRoute | None:
    """Build a learning route for a single subject based on its weak areas.

    Returns None if the subject has no weak areas to work on.
    """
    from organizer.models import ResourceRecommendation, SubjectMemory

    stats = _get_subject_stats(profile, subject_code)
    memory = SubjectMemory.objects.filter(profile=profile, code=subject_code).first()
    if not memory:
        return None

    weak_areas = stats["weak_areas"]
    if not weak_areas:
        # Use current focus as fallback
        weak_areas = stats["focus"] or [memory.title or subject_code]

    title = memory.title or subject_code
    steps = []
    step_num = 0

    # --- Step 1: Watch or Read (Resource Radar) ---
    has_resources = stats["total_resources"] > 0
    has_saved = stats["saved_resources"] > 0
    has_watched = stats["watched_resources"] > 0

    resource_progress = 0.0
    if has_resources:
        if has_watched:
            resource_progress = 1.0
        elif has_saved:
            resource_progress = 0.5
        else:
            resource_progress = 0.25

    step_num += 1
    steps.append(RouteStep(
        step_number=step_num,
        step_type="watch" if has_saved else "discover",
        title=f"Discover resources for {title}",
        description=f"Find videos and books about: {', '.join(weak_areas[:3])}",
        progress=resource_progress,
        is_complete=has_watched,
        action_url=f"/study/resources/?subject={subject_code}" if not has_saved else None,
        action_label="Explore resources" if not has_saved else None,
        subject_code=subject_code,
    ))

    # --- Step 2: Summarize documents ---
    has_summaries = stats["summarized_files"] > 0
    has_summarizable = stats["summarizable_files"] > 0
    summary_progress = 0.0
    if has_summarizable:
        summary_progress = (stats["summarized_files"] / max(stats["summarizable_files"], 1))

    step_num += 1
    steps.append(RouteStep(
        step_number=step_num,
        step_type="summarize",
        title=f"Study the materials for {title}",
        description=f"You have {stats['summarizable_files']} documents. AI summaries help identify key points, definitions, and likely exam questions.",
        progress=summary_progress,
        is_complete=has_summaries and summary_progress >= 0.5,
        action_url=f"/study/subjects/{subject_code}/" if has_summarizable and not has_summaries else None,
        action_label="View subject materials" if has_summarizable and not has_summaries else None,
        subject_code=subject_code,
        metadata={
            "summarizable": stats["summarizable_files"],
            "summarized": stats["summarized_files"],
        },
    ))

    # --- Step 3: Complete a review ---
    review_progress = 0.0
    if stats["total_reviews"] > 0:
        review_progress = stats["reviews_done"] / max(stats["total_reviews"], 1)
    else:
        review_progress = 0.25  # Implicit progress for no reviews yet

    step_num += 1
    steps.append(RouteStep(
        step_number=step_num,
        step_type="review",
        title=f"Review your knowledge of {title}",
        description=f"Complete spaced-repetition reviews to reinforce what you have learned. {stats['reviews_queued']} reviews in queue.",
        progress=review_progress,
        is_complete=stats["reviews_done"] >= 3,
        action_url="/study/reviews/" if stats["reviews_queued"] > 0 else None,
        action_label="Open review queue" if stats["reviews_queued"] > 0 else "Auto-schedule reviews",
        subject_code=subject_code,
        metadata={
            "reviews_done": stats["reviews_done"],
            "reviews_queued": stats["reviews_queued"],
        },
    ))

    # --- Step 4: Progress check ---
    days_since = None
    if stats["last_touched"]:
        days_since = (timezone.now() - stats["last_touched"]).days

    check_progress = 1.0 if (has_watched and has_summaries and stats["reviews_done"] >= 3) else 0.0
    step_num += 1
    steps.append(RouteStep(
        step_number=step_num,
        step_type="check",
        title=f"Progress check for {title}",
        description=(
            f"Files sorted: {stats['resource_count']}. "
            f"Last activity: {days_since} day(s) ago." if days_since is not None
            else f"Files sorted: {stats['resource_count']}. Start by sorting some files."
        ),
        progress=check_progress,
        is_complete=check_progress >= 0.8,
        action_url=f"/study/subjects/{subject_code}/",
        action_label="View full subject memory",
        subject_code=subject_code,
        metadata={
            "resource_count": stats["resource_count"],
            "days_since_last": days_since,
        },
    ))

    # Calculate overall progress
    overall = sum(s.progress for s in steps) / max(len(steps), 1)
    complete_steps = sum(1 for s in steps if s.is_complete)

    progress_text = (
        "All steps complete -- keep maintaining!" if complete_steps >= len(steps)
        else f"{complete_steps}/{len(steps)} steps complete"
        if complete_steps >= 2
        else "Just getting started -- explore resources"
    )

    return SubjectRoute(
        subject_code=subject_code,
        subject_title=title,
        weak_areas=weak_areas[:5],
        steps=steps,
        progress_summary=progress_text,
    )


def build_routes_for_profile(profile) -> List[SubjectRoute]:
    """Build learning routes for all subjects with weak areas in a profile."""
    from organizer.models import SubjectMemory

    memories = SubjectMemory.objects.filter(profile=profile).order_by("code")
    routes = []

    # First, build routes for subjects with explicit weak areas
    for memory in memories:
        if memory.weak_areas:
            route = build_route_for_subject(profile, memory.code)
            if route:
                routes.append(route)

    # Then, add routes for subjects with current_focus (secondary priority)
    for memory in memories:
        if not memory.weak_areas and memory.current_focus:
            # Avoid duplicates
            if not any(r.subject_code == memory.code for r in routes):
                route = build_route_for_subject(profile, memory.code)
                if route:
                    routes.append(route)

    # Sort: incomplete routes first
    routes.sort(key=lambda r: (
        sum(1 for s in r.steps if s.is_complete) / max(len(r.steps), 1),  # Completion ratio
        -len(r.weak_areas),  # More weak areas = higher priority
    ))

    return routes


def create_or_refresh_route(profile, subject_code=None, theme=None):
    """Create or refresh a LearningRoute for a profile/subject.

    This persists the route as a LearningRoute model record so it can be
    tracked and marked step-by-step in the UI.
    """
    from organizer.models import LearningRoute, SubjectMemory

    if not subject_code:
        memories = SubjectMemory.objects.filter(profile=profile).order_by("code")
        if not memories:
            return None
        subject_code = memories[0].code

    route_data = build_route_for_subject(profile, subject_code)
    if not route_data:
        return None

    steps_data = [
        {
            "step_number": s.step_number,
            "step_type": s.step_type,
            "title": s.title,
            "description": s.description,
            "progress": s.progress,
            "is_complete": s.is_complete,
            "action_url": s.action_url or "",
            "action_label": s.action_label or "",
            "metadata": s.metadata,
        }
        for s in route_data.steps
    ]

    route, _ = LearningRoute.objects.update_or_create(
        profile=profile,
        subject_code=subject_code,
        defaults={
            "title": route_data.progress_summary,
            "steps": steps_data,
            "status": "active",
            "current_step": 0,
        },
    )
    return route


def mark_step_done(route, step_index):
    """Mark a step in a LearningRoute as complete and advance to the next."""
    steps = route.steps or []
    if step_index < 0 or step_index >= len(steps):
        return route

    steps[step_index]["is_complete"] = True
    steps[step_index]["progress"] = 1.0

    # Advance to next incomplete step
    next_step = step_index + 1
    if next_step < len(steps):
        route.current_step = next_step
    else:
        route.status = "done"

    route.steps = steps
    route.save(update_fields=["steps", "current_step", "status", "updated_at"])
    return route


def get_route_context(profile) -> dict:
    """Get the learning route context for the dashboard."""
    routes = build_routes_for_profile(profile)

    total_steps = sum(len(r.steps) for r in routes)
    complete_steps = sum(1 for r in routes for s in r.steps if s.is_complete)

    return {
        "routes": routes,
        "total_subjects": len(routes),
        "total_steps": total_steps,
        "complete_steps": complete_steps,
        "completion_pct": round(complete_steps / max(total_steps, 1) * 100),
    }