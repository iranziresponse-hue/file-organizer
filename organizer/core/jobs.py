"""A thread-per-task background job runner -- no Celery/RQ, matches the
free/local-only tooling the rest of this app already uses (see
gui/watcher_controller.py's daemon-thread pattern). Meant for slow,
occasional, single-user operations (a sync, a scan), not high-throughput
work: every enqueue() call gets its own OS thread.

target() should return a short human-readable summary string (or None) on
success -- that becomes BackgroundTask.result_message. Any exception it
raises marks the task failed with str(exc) as the message, and never
propagates past this module (the caller already got its BackgroundTask id
back and moved on).

Every target() is always called with an extra task=ProgressReporter(...)
keyword argument, whether it uses it or not -- a target that doesn't care
about progress/cancellation just needs to accept and ignore it (task=None
in its signature), rather than every caller having to opt in separately.
"""

import logging
import threading

logger = logging.getLogger("organizer.jobs")


def enqueue(kind, target, *args, profile=None, **kwargs):
    from ..models import BackgroundTask

    task = BackgroundTask.objects.create(kind=kind, profile=profile, status="queued")
    thread = threading.Thread(
        target=_run, args=(task.pk, target, args, kwargs), daemon=True,
        name=f"orch-job-{kind}-{task.pk}",
    )
    thread.start()
    return task


def _run(task_pk, target, args, kwargs):
    from django.utils import timezone

    from ..models import BackgroundTask

    BackgroundTask.objects.filter(pk=task_pk).update(status="running", started_at=timezone.now())
    reporter = ProgressReporter(task_pk)
    try:
        message = target(*args, task=reporter, **kwargs)
        # "cancelled" is only truthful if this target actually noticed and
        # acted on a cancel request (reporter.cancel_acknowledged, set the
        # moment is_cancelled() first returns True -- see ProgressReporter
        # below). A target that never checks (MUELE sync, timetable sync)
        # always finishes as "done", even if someone requested a cancel
        # while it happened to be running -- it ran to completion and did
        # real, complete work, so "cancelled" would be a lie regardless of
        # what the DB status column says at this instant.
        final_status = "cancelled" if reporter.cancel_acknowledged else "done"
        BackgroundTask.objects.filter(pk=task_pk).update(
            status=final_status, finished_at=timezone.now(), result_message=(message or "")[:500],
        )
    except Exception as exc:
        logger.warning("Background task %s failed: %s", task_pk, exc)
        BackgroundTask.objects.filter(pk=task_pk).update(
            status="failed", finished_at=timezone.now(), result_message=str(exc)[:500],
        )


def mark_stale_tasks_as_interrupted():
    """Called once on app startup (see organizer.apps.OrganizerConfig.ready).
    Every BackgroundTask row is a daemon thread's progress marker -- it
    only means anything for as long as that thread is alive. If Orch
    closed, reloaded, or crashed while a task was queued/running/
    cancelling, that thread is gone and nothing will ever update the row
    again; left alone it would sit there forever looking "still running"
    to anyone who checks. This sweeps any such leftover row from a
    previous process into a clearly-labeled failure instead."""
    try:
        from ..models import BackgroundTask

        BackgroundTask.objects.filter(status__in=["queued", "running", "cancelling"]).update(
            status="failed",
            result_message="Interrupted -- Orch was closed or restarted before this finished.",
        )
    except Exception as exc:
        # Most likely this table doesn't exist yet (ready() runs before
        # migrations on a brand new install) -- never block app startup
        # over housekeeping.
        logger.warning("Could not sweep stale background tasks on startup: %s", exc)


def request_cancel(task_pk):
    """Asks a running task to stop. Cooperative, not forced -- the target
    function only actually stops the next time it checks
    ProgressReporter.is_cancelled(), so this never interrupts mid-file-move.
    Only meaningful for a target that actually checks; others just finish
    on their own regardless of this flag."""
    from ..models import BackgroundTask

    BackgroundTask.objects.filter(pk=task_pk, status__in=["queued", "running"]).update(status="cancelling")


class ProgressReporter:
    """Passed as task=... into every target() (see module docstring). A
    target that wants granular progress calls .update(); a target that
    supports cooperative cancellation checks .is_cancelled() periodically
    (not every iteration -- that's one extra DB read per check, so this is
    meant to be polled every few files/items, not every single one).

    cancel_acknowledged is what makes the final "cancelled" vs "done"
    status truthful (see _run above): it only ever becomes True from
    inside is_cancelled() itself, so it's a real record of "this specific
    target actually observed a cancel request", not just "someone set a
    DB flag at some point during the run"."""

    def __init__(self, task_pk):
        self.task_pk = task_pk
        self.cancel_acknowledged = False

    def update(self, current, total=None, message=""):
        from ..models import BackgroundTask

        fields = {"progress_current": current}
        if total is not None:
            fields["progress_total"] = total
        if message:
            fields["result_message"] = message[:500]
        BackgroundTask.objects.filter(pk=self.task_pk).update(**fields)

    def is_cancelled(self):
        from ..models import BackgroundTask

        status = BackgroundTask.objects.filter(pk=self.task_pk).values_list("status", flat=True).first()
        cancelling = status == "cancelling"
        if cancelling:
            self.cancel_acknowledged = True
        return cancelling
