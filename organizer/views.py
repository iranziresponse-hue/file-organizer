import json

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import redirect, render

from .core import paths
from .models import CourseConfig, MoveEvent


def dashboard(request):
    recent_events = MoveEvent.objects.all()[:50]
    method_counts = list(MoveEvent.objects.values("method").annotate(total=Count("id")).order_by("-total"))
    method_labels = dict(MoveEvent.METHOD_CHOICES)
    for row in method_counts:
        row["label"] = method_labels.get(row["method"], row["method"])
    course_counts = (
        MoveEvent.objects.exclude(course_code__isnull=True)
        .exclude(course_code="")
        .values("course_code")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    config = CourseConfig.objects.order_by("-updated_at").first()

    context = {
        "recent_events": recent_events,
        "method_counts": method_counts,
        "course_counts": course_counts,
        "config": config,
        "total_moves": MoveEvent.objects.count(),
    }
    return render(request, "organizer/dashboard.html", context)


def config_edit(request):
    config = CourseConfig.objects.order_by("-updated_at").first()

    if request.method == "POST":
        current_year = request.POST.get("current_year", "").strip()
        current_semester = request.POST.get("current_semester", "").strip()
        courses_raw = request.POST.get("courses", "")
        courses = [c.strip() for c in courses_raw.split(",") if c.strip()]

        if config is None:
            config = CourseConfig()
        config.current_year = current_year
        config.current_semester = current_semester
        config.courses = courses
        config.save()

        # Write back through to the JSON file so anything reading that path
        # directly (including the old PowerShell script, if it ever runs
        # again) sees the same values.
        payload = {
            "_comment": (
                "Edit this file at the start of every semester, or use the "
                "Orch dashboard instead. current_year/current_semester must "
                "match a folder name that already exists under D:\\School."
            ),
            "current_year": config.current_year,
            "current_semester": config.current_semester,
            "courses": config.courses,
        }
        try:
            paths.CONFIG_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            messages.success(request, "Config saved and written to _config.json.")
        except OSError as exc:
            messages.error(request, f"Saved to database but could not write _config.json: {exc}")

        return redirect("config_edit")

    return render(request, "organizer/config_edit.html", {"config": config})
