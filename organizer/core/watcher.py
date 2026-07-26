"""Polling watcher -- ported from the bottom half of OrganizeDownloads.ps1
(Move-DownloadedFile, Invoke-InstallerCleanup, and the main loop).

POLLING, not a filesystem-events library (watchdog/FileSystemWatcher) --
deliberate choice carried over from the PowerShell version, where a
Register-ObjectEvent/FileSystemWatcher approach was found to silently never
fire its handler when run as a detached background process. Polling every
few seconds is simple, reliably testable, and fast enough that "instant"
from a human's perspective is unaffected.
"""

import os
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import paths

SKIP_NAMES = {"_config.json", "desktop.ini"}

# Rotate log when it exceeds this size (5 MB)
_LOG_MAX_BYTES = 5 * 1024 * 1024
# Keep this many rotated copies
_LOG_BACKUP_COUNT = 3


def _rotate_log():
    """Rotate the log file if it exceeds the maximum size, keeping up to
    _LOG_BACKUP_COUNT numbered backups (organize-log.txt, organize-log.txt.1,
    organize-log.txt.2, organize-log.txt.3). Oldest backup is deleted.""" 
    try:
        if paths.LOG_PATH.exists() and paths.LOG_PATH.stat().st_size > _LOG_MAX_BYTES:
            # Shift backups: .2 -> .3, .1 -> .2, etc.
            for i in range(_LOG_BACKUP_COUNT - 1, 0, -1):
                src = Path(f"{paths.LOG_PATH}.{i}")
                dst = Path(f"{paths.LOG_PATH}.{i + 1}")
                if src.exists():
                    shutil.move(str(src), str(dst))
            # Rotate current -> .1
            shutil.move(str(paths.LOG_PATH), str(Path(f"{paths.LOG_PATH}.1")))
    except OSError:
        pass


def write_log(message):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}\n"
    try:
        paths.LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _rotate_log()
        with paths.LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def _record_event(**fields):
    # Imported lazily so this module (and its unit tests) work without
    # django.setup() having been called first.
    from organizer.models import MoveEvent

    return MoveEvent.objects.create(**fields)


def is_ready(file_path: Path, max_attempts=3):
    """Two independent checks that a file is actually done downloading, not
    one -- either alone has a gap:

    1. Lock check: if still locked, skip this cycle entirely -- don't force
       the move (forcing a move on a file still open for writing yanks it out
       from under the download).
    2. Size-stability check: some browsers/downloaders release and briefly
       re-acquire the file handle BETWEEN write chunks. The lock check alone
       can catch a file during exactly one of those gaps and grab a file
       that's genuinely still growing -- worse, since that can abort the
       download outright rather than just corrupting the tail end.

    Non-blocking: instead of sleeping up to 20 seconds holding up the entire
    watcher loop, this does at most 3 quick attempts (~1.5s total) and
    returns False if the file isn't ready yet. The caller will retry on the
    next poll cycle.
    """
    for _ in range(max_attempts):
        try:
            with open(file_path, "rb"):
                pass
            size_a = file_path.stat().st_size
            time.sleep(0.5)
            if not file_path.exists():
                return False
            size_b = file_path.stat().st_size
            if size_a == size_b:
                return True
        except OSError:
            pass  # still locked -- fall through to the retry wait below
        time.sleep(0.5)
    return False


def move_downloaded_file(file_path: Path, ai_enabled=None):
    """ai_enabled: None (the default, used by the real watcher loop) defers
    to the active profile's own ai_fallback_enabled setting. Pass True/False
    explicitly to override it, which is what the test suite does.

    Everything past the basic "is this even a real, finished file" checks
    below is delegated to organizer.core.sorting.process_file -- the trust-
    layer pipeline decides what happens (auto-move, suggest, hold, or leave
    in place) and this function no longer needs to know how."""
    if not file_path.exists() or file_path.is_dir():
        return

    name = file_path.name
    # "~$Report.docx" etc: Microsoft Office's own temporary lock file,
    # created while the real document is open and deleted when it closes.
    # Never real content -- moving/tracking it just clutters the sorted
    # history with junk that vanishes the moment the document is closed.
    if name in SKIP_NAMES or name.startswith("organize-log") or name.startswith("~$"):
        return

    # Brand-new file (written within the last 2 seconds) -- don't even look
    # at it yet.
    if (datetime.now().timestamp() - file_path.stat().st_mtime) < 2:
        return

    from organizer.models import AppSettings, Profile
    from . import sorting as sorting_module

    profile = Profile.get_active()
    settings = AppSettings.get_solo()
    sorting_module.process_file(file_path, profile, settings=settings, log=write_log, ai_enabled=ai_enabled)


def run_installer_cleanup():
    """Two-stage cleanup, scoped to Documents\\Personal\\Installers only --
    nothing outside it, no other drive, ever touched. Thresholds come from
    AppSettings (user-editable), read fresh so a change takes effect on the
    next hourly cleanup, no restart needed."""
    from organizer.models import AppSettings

    settings = AppSettings.get_solo()

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
        if age_days >= settings.installer_stale_days:
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
        if age_days >= settings.installer_delete_days:
            try:
                item.unlink()
                write_log(f"Installer '{item.name}' untouched {int(age_days)}d in _ToReview -> permanently deleted")
            except OSError as exc:
                write_log(f"FAILED to delete stale installer '{item.name}': {exc}")


def _move_one_safely(file_path: Path):
    """move_downloaded_file()'s own pipeline (AI classification, DB writes,
    integration syncs) can raise things well beyond OSError -- a locked
    DB, a malformed AppSettings value, a network error from a sync call
    that isn't itself caught. Before this existed, any single one of those
    on any single file would propagate straight out of the poll loop below
    and kill the watcher thread for good: files would silently just stop
    being sorted, with nothing in the UI to say why, until the app was
    restarted. One bad file must never take down the whole watcher."""
    try:
        move_downloaded_file(file_path)
    except Exception as exc:
        write_log(f"FAILED to process '{file_path.name}', skipping it this cycle: {exc!r}")


def run_watcher(stop_event=None, poll_seconds=3):
    """Blocking polling loop. stop_event: threading.Event, checked each cycle
    so a GUI can stop this cleanly from another thread. Pass a fresh Event
    per run so start/stop/start works without leftover state.

    Both watched folders come from AppSettings, re-read every cycle so
    editing them in the dashboard takes effect on the next poll, no restart
    needed.

    CRITICAL: the secondary folder must NEVER be swept in full -- only files
    created/modified AFTER this process started. Its historical backlog
    (hundreds of files, some of them real project material, on the original
    machine this was ported from) must never be touched by a generic sort;
    this happened once with the PowerShell version and had to be reversed
    via the log. watcher_start_time is the guard.
    """
    from organizer.models import AppSettings

    def _watched_paths():
        settings = AppSettings.get_solo()
        primary = Path(settings.downloads_path)
        secondary = Path(settings.secondary_downloads_path) if settings.secondary_downloads_path else None
        return primary, secondary

    downloads, downloads2 = _watched_paths()
    downloads.mkdir(parents=True, exist_ok=True)

    # Initial sweep of whatever's already in the primary folder -- deliberately
    # does NOT include the secondary folder's backlog, same as the PowerShell
    # version this was ported from.
    for item in downloads.iterdir():
        if item.is_file():
            _move_one_safely(item)
    try:
        run_installer_cleanup()
    except Exception as exc:
        write_log(f"Initial installer cleanup failed, will retry next hour: {exc!r}")

    watcher_start_time = datetime.now()
    secondary_note = f" and {downloads2}" if downloads2 else ""
    write_log(
        f"Organizer started, watching {downloads}{secondary_note} "
        f"(poll mode, secondary folder new-files-only since {watcher_start_time:%Y-%m-%d %H:%M:%S})"
    )
    last_installer_cleanup = datetime.now()

    while stop_event is None or not stop_event.is_set():
        downloads, downloads2 = _watched_paths()

        try:
            for item in downloads.iterdir():
                if item.is_file():
                    _move_one_safely(item)
        except OSError:
            pass

        try:
            if downloads2 and downloads2.exists():
                for item in downloads2.iterdir():
                    if not item.is_file():
                        continue
                    stat = item.stat()
                    created = datetime.fromtimestamp(stat.st_ctime)
                    modified = datetime.fromtimestamp(stat.st_mtime)
                    if created > watcher_start_time or modified > watcher_start_time:
                        _move_one_safely(item)
        except OSError:
            pass

        if datetime.now() - last_installer_cleanup >= timedelta(hours=1):
            try:
                run_installer_cleanup()
            except Exception as exc:
                write_log(f"Installer cleanup cycle failed, will retry next hour: {exc!r}")
            last_installer_cleanup = datetime.now()

        if stop_event is not None:
            stop_event.wait(poll_seconds)
        else:
            time.sleep(poll_seconds)
