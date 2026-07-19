"""Polling watcher -- ported from the bottom half of OrganizeDownloads.ps1
(Move-DownloadedFile, Invoke-InstallerCleanup, and the main loop).

POLLING, not a filesystem-events library (watchdog/FileSystemWatcher) --
deliberate choice carried over from the PowerShell version, where a
Register-ObjectEvent/FileSystemWatcher approach was found to silently never
fire its handler when run as a detached background process. Polling every
few seconds is simple, reliably testable, and fast enough that "instant"
from a human's perspective is unaffected.
"""

import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import ai_classify, paths, rules

SKIP_NAMES = {"_config.json", "desktop.ini"}


def write_log(message):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}\n"
    try:
        paths.LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with paths.LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def _record_event(**fields):
    # Imported lazily so this module (and its unit tests) work without
    # django.setup() having been called first.
    from organizer.models import MoveEvent

    MoveEvent.objects.create(**fields)


def is_ready(file_path: Path, attempts=10):
    """Two independent checks that a file is actually done downloading, not
    one -- either alone has a gap:

    1. Lock check: if still locked after retrying, skip this cycle entirely,
       don't force the move (forcing a move on a file still open for writing
       yanks it out from under the download).
    2. Size-stability check: some browsers/downloaders release and briefly
       re-acquire the file handle BETWEEN write chunks. The lock check alone
       can catch a file during exactly one of those gaps and grab a file
       that's genuinely still growing -- worse, since that can abort the
       download outright rather than just corrupting the tail end.
    """
    for _ in range(attempts):
        try:
            with open(file_path, "rb"):
                pass
            size_a = file_path.stat().st_size
            time.sleep(1)
            if not file_path.exists():
                return False
            size_b = file_path.stat().st_size
            if size_a == size_b:
                return True
        except OSError:
            pass  # still locked -- fall through to the retry wait below
        time.sleep(1)
    return False


def move_downloaded_file(file_path: Path, ai_enabled=True):
    if not file_path.exists() or file_path.is_dir():
        return

    name = file_path.name
    if name in SKIP_NAMES or name.startswith("organize-log"):
        return

    # Brand-new file (written within the last 2 seconds) -- don't even look
    # at it yet.
    if (datetime.now().timestamp() - file_path.stat().st_mtime) < 2:
        return

    def _ai_classify(n, curriculum):
        return ai_classify.classify(n, curriculum, log=write_log)

    dest = rules.get_destination(file_path, ai_classify=_ai_classify if ai_enabled else None)
    if dest is None:
        return

    if not is_ready(file_path):
        write_log(f"Skipped '{name}' this cycle -- still locked or still growing, will retry")
        return

    dest.path.mkdir(parents=True, exist_ok=True)

    target = dest.path / name
    if target.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = dest.path / f"{target.stem}_{stamp}{target.suffix}"

    try:
        shutil.move(str(file_path), str(target))
        write_log(f"Moved '{name}' -> {dest.path}")
        _record_event(
            filename=name,
            source_path=str(file_path),
            destination_path=str(target),
            method=dest.method,
            course_code=dest.course_code,
            success=True,
        )
    except OSError as exc:
        write_log(f"FAILED to move '{name}': {exc}")
        _record_event(
            filename=name,
            source_path=str(file_path),
            destination_path=str(target),
            method=dest.method,
            course_code=dest.course_code,
            success=False,
            error_message=str(exc),
        )


def run_installer_cleanup():
    """Two-stage cleanup, scoped to Documents\\Personal\\Installers only --
    nothing outside it, no other drive, ever touched."""
    installers_root = paths.PERSONAL_ROOT / "Installers"
    if not installers_root.exists():
        return
    review_root = installers_root / "_ToReview"
    review_root.mkdir(parents=True, exist_ok=True)

    now = datetime.now()

    for item in installers_root.iterdir():
        if not item.is_file():
            continue
        age_days = (now.timestamp() - item.stat().st_mtime) / 86400
        if age_days >= paths.INSTALLER_STALE_DAYS:
            dest = review_root / item.name
            try:
                shutil.move(str(item), str(dest))
                write_log(f"Installer '{item.name}' untouched {int(age_days)}d -> moved to _ToReview")
            except OSError as exc:
                write_log(f"FAILED to move stale installer '{item.name}': {exc}")

    for item in review_root.iterdir():
        if not item.is_file():
            continue
        age_days = (now.timestamp() - item.stat().st_mtime) / 86400
        if age_days >= paths.INSTALLER_DELETE_DAYS:
            try:
                item.unlink()
                write_log(f"Installer '{item.name}' untouched {int(age_days)}d in _ToReview -> permanently deleted")
            except OSError as exc:
                write_log(f"FAILED to delete stale installer '{item.name}': {exc}")


def run_watcher(stop_event=None, poll_seconds=3):
    """Blocking polling loop. stop_event: threading.Event, checked each cycle
    so a GUI can stop this cleanly from another thread. Pass a fresh Event
    per run so start/stop/start works without leftover state.

    CRITICAL: DOWNLOADS2 (D:\\myDownloads) must NEVER be swept in full -- only
    files created/modified AFTER this process started. Its historical backlog
    (hundreds of files, some of them real project material) must never be
    touched by a generic sort; this happened once with the PowerShell version
    and had to be reversed via the log. watcher_start_time is the guard.
    """
    paths.DOWNLOADS.mkdir(parents=True, exist_ok=True)

    # Initial sweep of whatever's already in Downloads -- deliberately does
    # NOT include DOWNLOADS2's backlog, same as the PowerShell version.
    for item in paths.DOWNLOADS.iterdir():
        if item.is_file():
            move_downloaded_file(item)
    run_installer_cleanup()

    watcher_start_time = datetime.now()
    write_log(
        f"Organizer started, watching {paths.DOWNLOADS} and {paths.DOWNLOADS2} "
        f"(poll mode, downloads2 new-files-only since {watcher_start_time:%Y-%m-%d %H:%M:%S})"
    )
    last_installer_cleanup = datetime.now()

    while stop_event is None or not stop_event.is_set():
        try:
            for item in paths.DOWNLOADS.iterdir():
                if item.is_file():
                    move_downloaded_file(item)
        except OSError:
            pass

        try:
            if paths.DOWNLOADS2.exists():
                for item in paths.DOWNLOADS2.iterdir():
                    if not item.is_file():
                        continue
                    stat = item.stat()
                    created = datetime.fromtimestamp(stat.st_ctime)
                    modified = datetime.fromtimestamp(stat.st_mtime)
                    if created > watcher_start_time or modified > watcher_start_time:
                        move_downloaded_file(item)
        except OSError:
            pass

        if datetime.now() - last_installer_cleanup >= timedelta(hours=1):
            run_installer_cleanup()
            last_installer_cleanup = datetime.now()

        if stop_event is not None:
            stop_event.wait(poll_seconds)
        else:
            time.sleep(poll_seconds)
