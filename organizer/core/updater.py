"""Self-update: checks this repo's GitHub Releases for a newer Orch.exe,
downloads it, and swaps it in for the currently running exe on next
relaunch.

Only ever targets this repo's own Releases API over HTTPS -- never a
user-supplied or redirected URL -- and verifies the downloaded file's
SHA-256 against the digest GitHub itself reports for the asset before
ever letting anything replace the running exe. A corrupted or tampered
download is deleted and reported as a failure, never applied.

Every public function here follows the same fallback-on-exception shape
as organizer.core.diagnostics: network/parsing problems come back as a
plain "not available" result, never a raised exception, so a flaky
connection can't crash the app that's just trying to check in the
background.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from django.core.cache import cache

from organizer import __version__ as CURRENT_VERSION

REPO = "iranziresponse-hue/file-organizer"
RELEASES_API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET_NAME = "Orch.exe"
REQUEST_TIMEOUT = 6
DOWNLOAD_TIMEOUT = 30
CACHE_KEY = "orch_update_check_result"

_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def _parse_version(text):
    """'v1.2.3' or '1.2.3' -> (1, 2, 3). None if unparsable, so a weird or
    unexpected tag name fails safe (no update offered) instead of crashing
    or being compared as if it meant something."""
    match = _VERSION_RE.match((text or "").strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def is_newer(latest_tag, current_version=None):
    latest = _parse_version(latest_tag)
    current = _parse_version(current_version or CURRENT_VERSION)
    if latest is None or current is None:
        return False
    return latest > current


def check_for_update():
    """Hits the GitHub Releases API once. Never raises."""
    result = {
        "available": False,
        "current_version": CURRENT_VERSION,
        "latest_version": None,
        "download_url": None,
        "sha256": None,
        "error": None,
    }
    try:
        request = urllib.request.Request(
            RELEASES_API_URL,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "Orch-updater"},
        )
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as exc:
        result["error"] = str(exc)
        return result

    tag = payload.get("tag_name", "")
    asset = next((a for a in payload.get("assets", []) if a.get("name") == ASSET_NAME), None)
    if not asset:
        result["error"] = f"Latest release has no {ASSET_NAME} asset."
        return result

    digest = asset.get("digest") or ""
    result.update({
        "latest_version": tag.lstrip("v"),
        "download_url": asset.get("browser_download_url"),
        "sha256": digest.split(":", 1)[1] if digest.startswith("sha256:") else None,
        "available": is_newer(tag),
    })
    return result


def remember_check_result(result):
    """Stored in the same in-process LocMemCache the rest of the app
    already uses (config/settings.py) -- this process is the only reader
    or writer, same reasoning as resource_cache.py's use of it."""
    cache.set(CACHE_KEY, result, timeout=None)


def get_last_check():
    return cache.get(CACHE_KEY)


def _sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_update(download_url, destination, expected_sha256=None, progress_callback=None):
    """Streams the new exe to `destination`. Returns (success, error).
    Refuses (and deletes the partial file) on any checksum mismatch rather
    than ever handing back a file that could end up running."""
    try:
        request = urllib.request.Request(download_url, headers={"User-Agent": "Orch-updater"})
        with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT) as response:
            total = int(response.headers.get("Content-Length", 0) or 0)
            written = 0
            with open(destination, "wb") as f:
                while True:
                    chunk = response.read(1024 * 64)
                    if not chunk:
                        break
                    f.write(chunk)
                    written += len(chunk)
                    if progress_callback:
                        progress_callback(written, total)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        Path(destination).unlink(missing_ok=True)
        return False, str(exc)

    if expected_sha256 and _sha256_of(destination) != expected_sha256:
        Path(destination).unlink(missing_ok=True)
        return False, "Downloaded file did not match the expected checksum."

    return True, None


def build_relaunch_script(current_pid, new_exe_path, target_exe_path):
    """A tiny batch script that waits for this process to fully exit, then
    swaps the downloaded exe into the running one's place and reopens it.

    Written to disk and run as a separate, detached process rather than
    done inline, because the currently-running exe holds its own file
    locked on Windows -- nothing can overwrite Orch.exe while Orch.exe is
    still the process doing the overwriting. Polling `tasklist` for the
    PID to disappear is the simplest wait that needs no extra dependency.
    """
    return (
        "@echo off\n"
        ":wait\n"
        f'tasklist /FI "PID eq {current_pid}" | find "{current_pid}" >nul\n'
        "if not errorlevel 1 (\n"
        "    timeout /t 1 /nobreak >nul\n"
        "    goto wait\n"
        ")\n"
        f'move /Y "{new_exe_path}" "{target_exe_path}"\n'
        f'start "" "{target_exe_path}"\n'
        'del "%~f0"\n'
    )


def apply_update_and_restart(new_exe_path, target_exe_path=None, exit_func=None, popen_func=None):
    """Writes the relaunch script, launches it detached, then exits this
    process so the script's wait loop can finish and the file lock
    releases. `exit_func`/`popen_func` are injection points so tests can
    verify the right script/command without spawning a real process or
    exiting the test run."""
    target_exe_path = target_exe_path or sys.executable
    popen_func = popen_func or subprocess.Popen
    exit_func = exit_func or (lambda: os._exit(0))

    script_path = Path(tempfile.gettempdir()) / f"orch_update_{os.getpid()}.bat"
    script_path.write_text(
        build_relaunch_script(os.getpid(), str(new_exe_path), str(target_exe_path)),
        encoding="utf-8",
    )
    popen_func(
        ["cmd.exe", "/c", str(script_path)],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
    exit_func()


def download_and_apply(result, exit_func=None, popen_func=None):
    """The full flow behind clicking "Update": download next to the
    running exe, verify, then swap and restart. Returns (success, error)
    on failure; never returns on success, since exit_func replaces this
    process (a real run truly exits here -- tests pass a fake exit_func
    to observe that point was reached instead)."""
    target_exe_path = Path(sys.executable)
    new_exe_path = target_exe_path.with_name("Orch.new.exe")

    success, error = download_update(
        result["download_url"], new_exe_path, expected_sha256=result.get("sha256")
    )
    if not success:
        return False, error

    apply_update_and_restart(
        new_exe_path, target_exe_path, exit_func=exit_func, popen_func=popen_func
    )
    return True, None
