"""Runs organizer.core.watcher.run_watcher on a background thread and gives
the tray UI a clean start/stop switch. A fresh threading.Event is created on
every start, matching what watcher.run_watcher expects (see its docstring:
"Pass a fresh Event per run so start/stop/start works without leftover state").
"""

import threading

from organizer.core import watcher


class WatcherController:
    def __init__(self, poll_seconds=3):
        self.poll_seconds = poll_seconds
        self._thread = None
        self._stop_event = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.running:
            return
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=watcher.run_watcher,
            kwargs={"stop_event": self._stop_event, "poll_seconds": self.poll_seconds},
            daemon=True,
            name="organizer-watcher",
        )
        self._thread.start()

    def stop(self, timeout=10):
        if not self.running:
            return
        self._stop_event.set()
        self._thread.join(timeout=timeout)
        self._thread = None
        self._stop_event = None
