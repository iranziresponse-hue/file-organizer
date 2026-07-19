"""Background thread controller for MUELE sync, following the same
pattern as WatcherController in gui/watcher_controller.py.

Starts and stops the MUELE sync daemon on a background thread.
"""

import threading
from datetime import datetime

from organizer.core import muele_downloader, notifications


class MueleController:
    """Controls the MUELE background sync thread."""

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def start(self, poll_seconds: int = 1800) -> None:
        """Start the MUELE sync daemon on a background thread."""
        if self._running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=muele_downloader.run_muele_sync,
            kwargs={
                "stop_event": self._stop_event,
                "poll_seconds": poll_seconds,
                "log": self._log,
            },
            daemon=True,
            name="muele-sync",
        )
        self._thread.start()
        self._running = True

    def stop(self) -> None:
        """Signal the sync daemon to stop and wait for it."""
        if not self._running:
            return
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._running = False
        self._thread = None

    def _log(self, message: str) -> None:
        """Log a message from the sync daemon."""
        from organizer.core.watcher import write_log

        write_log(f"[MUELE] {message}")

    def sync_now(self) -> dict:
        """Trigger an immediate sync on the current thread.

        Returns the sync result dict. This blocks until the sync completes,
        so call it from a background thread or a short-lived worker.
        """
        from organizer.models import Profile

        profile = Profile.get_active()
        if not profile:
            return {"downloaded": 0, "skipped": 0, "errors": 0, "courses_synced": 0}

        result = muele_downloader.sync_profile_courses(profile, log=self._log)
        assign_count = muele_downloader.sync_assignments(profile, log=self._log)
        notifications.notify_muele_sync(result)
        self._log(
            f"Manual sync: {result['downloaded']} downloaded, "
            f"{result['skipped']} skipped, {result['errors']} errors, "
            f"{assign_count} new assignments"
        )
        return result