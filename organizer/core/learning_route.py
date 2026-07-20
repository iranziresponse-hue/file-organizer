"""Learning Route -- turns a weak area into a sequenced study path.

For a subject with a weak area (or, failing that, a current-focus topic),
Orch builds a four-step route: find a resource, read a summary, work
through a review, then check confidence. The route is persisted as a
LearningRoute row (organizer/models.py), keyed on (profile, subject_code,
theme), so a student can leave and come back to the same route, marking
steps done as they go without losing progress.

Each step's initial "done" state is a best-effort read of real, already
recorded progress (a saved resource, a summarized file, a cleared review
queue) -- never a guess. A student can also mark a step done by hand via
mark_step_done(), independent of that live signal.
"""


def _pick_subject_and_theme(profile, subject_code=None, theme=None):
    """Resolve the subject/theme pair a route should be built for.

    A subject with an explicit weak area is preferred over one with only a
    current-focus topic, since a weak area is the more urgent thing to
    route the student toward.
    """
    from organizer.models import SubjectMemory

    if subject_code and theme:
        return subject_code, theme

    memories = list(SubjectMemory.objects.filter(profile=profile).order_by("code"))
    if subject_code:
        memory = next((m for m in memories if m.code == subject_code), None)
    else:
        memory = (
            next((m for m in memories if m.weak_areas), None)
            or next((m for m in memories if m.current_focus), None)
            or (memories[0] if memories else None)
        )

    if memory is None:
        return subject_code, theme

    subject_code = subject_code or memory.code
    if not theme:
        if memory.weak_areas:
            theme = memory.weak_areas[0]
        elif memory.current_focus:
            theme = memory.current_focus[0]
        else:
            theme = memory.title or memory.code

    return subject_code, theme


def _build_steps(profile, subject_code, theme):
    """Compute the four route steps and, if one exists, the resource
    recommendation the first step should link to."""
    from organizer.models import FileSummary, MoveEvent, ResourceRecommendation, ReviewItem

    resource = (
        ResourceRecommendation.objects.filter(profile=profile, subject_code=subject_code, theme=theme)
        .exclude(status="dismissed")
        .order_by("-score")
        .first()
    )

    files = MoveEvent.objects.filter(profile=profile, course_code=subject_code, success=True)
    summarizable = sum(1 for event in files if event.is_summarizable())
    summarized = FileSummary.objects.filter(
        move_event__profile=profile, move_event__course_code=subject_code
    ).count()

    reviews = ReviewItem.objects.filter(profile=profile, subject_code=subject_code)
    reviews_done = reviews.filter(status="done").count()
    reviews_queued = reviews.filter(status="queued").count()

    steps = [
        {
            "type": "resource",
            "title": f"Find a resource for {theme}",
            "detail": (
                f"Open the top Resource Radar suggestion for {theme}."
                if resource
                else f"Search Resource Radar for videos and books about {theme}."
            ),
            "url": resource.url if resource else f"/study/resources/?subject={subject_code}",
            "done": bool(resource and resource.status in {"saved", "opened"}),
        },
        {
            "type": "summary",
            "title": f"Read a summary for {subject_code}",
            "detail": (
                f"{summarized} of {summarizable} document(s) already summarized."
                if summarizable
                else "No summarizable documents yet. Sort some files into this subject first."
            ),
            "url": f"/study/subjects/{subject_code}/",
            "done": summarizable > 0 and summarized >= summarizable,
        },
        {
            "type": "review",
            "title": f"Review {theme}",
            "detail": f"{reviews_queued} review(s) queued, {reviews_done} completed.",
            "url": "/study/reviews/",
            "done": reviews_queued == 0 and reviews_done > 0,
        },
        {
            "type": "check",
            "title": f"Confidence check for {theme}",
            "detail": "See how this subject's memory and review history look overall.",
            "url": f"/study/subjects/{subject_code}/",
            "done": False,
        },
    ]
    return steps, resource


def create_or_refresh_route(profile, subject_code=None, theme=None):
    """Create a LearningRoute, or refresh an existing one's steps and
    resource link in place. Manual step status set via mark_step_done()
    survives a refresh; only steps/recommendation are recomputed.

    Returns None if the profile has no subject to build a route for.
    """
    from organizer.models import LearningRoute

    subject_code, theme = _pick_subject_and_theme(profile, subject_code, theme)
    if not subject_code or not theme:
        return None

    steps, resource = _build_steps(profile, subject_code, theme)

    route = LearningRoute.objects.filter(profile=profile, subject_code=subject_code, theme=theme).first()
    if route is None:
        route = LearningRoute(profile=profile, subject_code=subject_code, theme=theme, status="active")

    route.title = f"{subject_code}: {theme}"
    route.steps = steps
    route.recommendation = resource
    route.save()
    return route


def mark_step_done(route, step_index):
    """Mark a step complete by hand and advance to the next one, or mark
    the whole route done if that was the last step.

    Raises IndexError for a step_index outside the route's actual steps,
    rather than silently no-op'ing on what would be a caller bug.
    """
    steps = route.steps or []
    if step_index < 0 or step_index >= len(steps):
        raise IndexError(f"step_index {step_index} is out of range for {len(steps)} step(s)")

    steps[step_index]["done"] = True

    next_step = step_index + 1
    if next_step < len(steps):
        route.current_step = next_step
    else:
        route.status = "done"

    route.steps = steps
    route.save(update_fields=["steps", "current_step", "status", "updated_at"])
    return route
