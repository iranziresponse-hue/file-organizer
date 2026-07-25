from unittest import mock

from django.test import TestCase

from organizer.core import jobs
from organizer.models import BackgroundTask, Profile


class ImmediateThread:
    """Same pattern as test_watcher.py's ImmediateThread -- runs the target
    synchronously on the calling thread instead of a real background one, so
    these tests are deterministic and never race a real thread."""

    def __init__(self, target=None, args=(), kwargs=None, daemon=None, name=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


class EnqueueTests(TestCase):
    def test_runs_the_target_and_marks_it_done(self):
        with mock.patch.object(jobs.threading, "Thread", ImmediateThread):
            task = jobs.enqueue("muele_sync", lambda task=None: "Synced 3 courses.")

        task.refresh_from_db()
        self.assertEqual(task.status, "done")
        self.assertEqual(task.result_message, "Synced 3 courses.")
        self.assertIsNotNone(task.started_at)
        self.assertIsNotNone(task.finished_at)

    def test_passes_args_and_kwargs_through_to_the_target(self):
        calls = []

        def target(a, b, c=None, task=None):
            calls.append((a, b, c))
            return "done"

        with mock.patch.object(jobs.threading, "Thread", ImmediateThread):
            jobs.enqueue("muele_sync", target, "x", "y", c="z")

        self.assertEqual(calls, [("x", "y", "z")])

    def test_every_target_is_given_a_progress_reporter(self):
        received = []

        def target(task=None):
            received.append(task)
            return "done"

        with mock.patch.object(jobs.threading, "Thread", ImmediateThread):
            jobs.enqueue("muele_sync", target)

        self.assertEqual(len(received), 1)
        self.assertIsInstance(received[0], jobs.ProgressReporter)

    def test_an_exception_marks_the_task_failed_without_raising(self):
        def target(task=None):
            raise RuntimeError("MUELE is unreachable")

        with mock.patch.object(jobs.threading, "Thread", ImmediateThread):
            task = jobs.enqueue("muele_sync", target)

        task.refresh_from_db()
        self.assertEqual(task.status, "failed")
        self.assertIn("MUELE is unreachable", task.result_message)

    def test_stores_the_profile_and_kind(self):
        profile = Profile.objects.create(name="Test", root_path="C:/x")

        with mock.patch.object(jobs.threading, "Thread", ImmediateThread):
            task = jobs.enqueue("timetable_sync", lambda task=None: None, profile=profile)

        self.assertEqual(task.profile, profile)
        self.assertEqual(task.kind, "timetable_sync")

    def test_returns_before_the_thread_runs(self):
        # A real SQLite connection is single-writer, and Django TestCase
        # wraps each test in a transaction on the main thread -- actually
        # starting a real thread here would race that transaction (this was
        # caught as an intermittent "database table is locked" error from a
        # first draft of this test). A stub that records .start() without
        # calling the target is what actually tests "enqueue() returns
        # immediately, before the work runs" without that race.
        started = []

        class RecordingThread:
            def __init__(self, target=None, args=(), kwargs=None, daemon=None, name=None):
                self._target = target

            def start(self):
                started.append(self._target)

        with mock.patch.object(jobs.threading, "Thread", RecordingThread):
            task = jobs.enqueue("muele_sync", lambda task=None: None)

        self.assertEqual(task.status, "queued")
        self.assertEqual(len(started), 1)

    def test_a_target_that_notices_and_honors_a_cancel_request_finishes_cancelled(self):
        task = BackgroundTask.objects.create(kind="large_folder_sort", status="queued")

        def target(task=None):
            # Simulate a cancel request landing while this is running, the
            # same way sort_folder()'s loop actually does: by calling
            # is_cancelled() itself, not by poking the DB row directly.
            BackgroundTask.objects.filter(pk=task_pk).update(status="cancelling")
            task.is_cancelled()
            return "Stopped early."

        task_pk = task.pk
        jobs._run(task.pk, target, (), {})

        task.refresh_from_db()
        self.assertEqual(task.status, "cancelled")
        self.assertEqual(task.result_message, "Stopped early.")

    def test_a_target_that_never_checks_cancellation_finishes_done_even_if_requested(self):
        # The bug this guards against: MUELE sync / timetable sync don't
        # check is_cancelled() at all. If someone requests a cancel while
        # one is running (e.g. by hitting the wrong task id), it must
        # still finish honestly as "done" -- it ran to completion and did
        # real, complete work, regardless of what the DB status column
        # said at some point during the run.
        task = BackgroundTask.objects.create(kind="muele_sync", status="queued")

        def target(task=None):
            BackgroundTask.objects.filter(pk=task_pk).update(status="cancelling")
            return "Sync complete: 5 downloaded."

        task_pk = task.pk
        jobs._run(task.pk, target, (), {})

        task.refresh_from_db()
        self.assertEqual(task.status, "done")
        self.assertEqual(task.result_message, "Sync complete: 5 downloaded.")


class MarkStaleTasksAsInterruptedTests(TestCase):
    def test_marks_every_non_terminal_task_as_failed(self):
        queued = BackgroundTask.objects.create(kind="muele_sync", status="queued")
        running = BackgroundTask.objects.create(kind="large_folder_sort", status="running")
        cancelling = BackgroundTask.objects.create(kind="large_folder_sort", status="cancelling")

        jobs.mark_stale_tasks_as_interrupted()

        for task in (queued, running, cancelling):
            task.refresh_from_db()
            self.assertEqual(task.status, "failed")
            self.assertIn("Interrupted", task.result_message)

    def test_leaves_already_finished_tasks_alone(self):
        done = BackgroundTask.objects.create(kind="muele_sync", status="done", result_message="Synced 3.")
        failed = BackgroundTask.objects.create(kind="muele_sync", status="failed", result_message="no network")
        cancelled = BackgroundTask.objects.create(kind="large_folder_sort", status="cancelled")

        jobs.mark_stale_tasks_as_interrupted()

        done.refresh_from_db()
        failed.refresh_from_db()
        cancelled.refresh_from_db()
        self.assertEqual(done.status, "done")
        self.assertEqual(done.result_message, "Synced 3.")
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.result_message, "no network")
        self.assertEqual(cancelled.status, "cancelled")

    def test_never_raises_even_if_the_query_fails(self):
        with mock.patch(
            "organizer.models.BackgroundTask.objects.filter", side_effect=Exception("no such table"),
        ):
            jobs.mark_stale_tasks_as_interrupted()  # must not raise


class RequestCancelTests(TestCase):
    def test_marks_a_running_task_as_cancelling(self):
        task = BackgroundTask.objects.create(kind="large_folder_sort", status="running")

        jobs.request_cancel(task.pk)

        task.refresh_from_db()
        self.assertEqual(task.status, "cancelling")

    def test_does_not_touch_an_already_finished_task(self):
        task = BackgroundTask.objects.create(kind="large_folder_sort", status="done")

        jobs.request_cancel(task.pk)

        task.refresh_from_db()
        self.assertEqual(task.status, "done")


class ProgressReporterTests(TestCase):
    def test_update_writes_progress_fields(self):
        task = BackgroundTask.objects.create(kind="folder_import_scan", status="running")
        reporter = jobs.ProgressReporter(task.pk)

        reporter.update(5, total=20, message="Scanning...")

        task.refresh_from_db()
        self.assertEqual(task.progress_current, 5)
        self.assertEqual(task.progress_total, 20)
        self.assertEqual(task.result_message, "Scanning...")

    def test_update_without_a_total_leaves_it_indeterminate(self):
        task = BackgroundTask.objects.create(kind="folder_import_scan", status="running")
        reporter = jobs.ProgressReporter(task.pk)

        reporter.update(3)

        task.refresh_from_db()
        self.assertEqual(task.progress_current, 3)
        self.assertIsNone(task.progress_total)

    def test_is_cancelled_false_while_running(self):
        task = BackgroundTask.objects.create(kind="large_folder_sort", status="running")
        self.assertFalse(jobs.ProgressReporter(task.pk).is_cancelled())

    def test_is_cancelled_true_after_a_cancel_request(self):
        task = BackgroundTask.objects.create(kind="large_folder_sort", status="running")
        jobs.request_cancel(task.pk)
        self.assertTrue(jobs.ProgressReporter(task.pk).is_cancelled())

    def test_cancel_acknowledged_stays_false_until_is_cancelled_is_actually_called(self):
        task = BackgroundTask.objects.create(kind="large_folder_sort", status="running")
        jobs.request_cancel(task.pk)
        reporter = jobs.ProgressReporter(task.pk)

        self.assertFalse(reporter.cancel_acknowledged)
        reporter.is_cancelled()
        self.assertTrue(reporter.cancel_acknowledged)

    def test_cancel_acknowledged_stays_false_when_never_cancelled(self):
        task = BackgroundTask.objects.create(kind="large_folder_sort", status="running")
        reporter = jobs.ProgressReporter(task.pk)

        reporter.is_cancelled()

        self.assertFalse(reporter.cancel_acknowledged)
