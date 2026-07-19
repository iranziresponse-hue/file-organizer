"""MUELE (Makerere University E-Learning Environment) API client.

MUELE runs on the Moodle platform at https://muele.mak.ac.ug and exposes
Moodle's standard REST web services. This module talks to those endpoints.

The token is stored in the operating system keyring (via the `keyring`
library) and never written to the database -- only a reference string is
kept in IntegrationConnection.token_reference.

All public functions return (result, error_message) tuples -- never throw.
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Callable

import requests

MUELE_BASE_URL = "https://muele.mak.ac.ug"
_WS_ENDPOINT = f"{MUELE_BASE_URL}/webservice/rest/server.php"
_LOGIN_URL = f"{MUELE_BASE_URL}/login/index.php"
_TOKEN_URL = f"{MUELE_BASE_URL}/login/token.php"
_DEFAULT_TIMEOUT = 30
_MAX_RETRIES = 3
_RETRY_DELAY = 2  # seconds

logger = logging.getLogger("organizer.muele")


# ---------------------------------------------------------------------------
# Token management via keyring
# ---------------------------------------------------------------------------

_KEYRING_SERVICE = "iranzi-file-organizer-muele"


def store_token(token: str) -> None:
    """Store a MUELE web service token in the OS keyring."""
    import keyring

    keyring.set_password(_KEYRING_SERVICE, "muele_token", token)


def load_token() -> str | None:
    """Load the MUELE token from the OS keyring. Returns None if not set."""
    import keyring

    return keyring.get_password(_KEYRING_SERVICE, "muele_token")


def clear_token() -> None:
    """Remove the MUELE token from the OS keyring."""
    import keyring

    try:
        keyring.delete_password(_KEYRING_SERVICE, "muele_token")
    except keyring.errors.PasswordDeleteError:
        pass


# ---------------------------------------------------------------------------
# Automatic token generation via MUELE login
# ---------------------------------------------------------------------------


def generate_token(
    username: str,
    password: str,
    service: str = "Orch",
    log: Callable | None = None,
) -> tuple[str | None, str | None]:
    """Generate a MUELE web service token using username/password login.

    This calls MUELE's login/token.php endpoint directly, which is the
    standard Moodle token generation API. The token is automatically stored
    in the keyring on success.

    Returns (token, None) on success or (None, error_message) on failure.
    Never throws.
    """
    if not username or not password:
        return None, "Username and password are required."

    try:
        resp = requests.post(
            _TOKEN_URL,
            data={
                "username": username,
                "password": password,
                "service": service,
            },
            timeout=_DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.ConnectionError:
        return None, "Could not reach MUELE. Check your internet connection."
    except requests.Timeout:
        return None, "MUELE login timed out. Try again later."
    except requests.RequestException as exc:
        return None, f"Could not connect to MUELE: {exc}"
    except (json.JSONDecodeError, ValueError):
        return None, "MUELE returned an unexpected response."

    # MUELE returns errors as {"error": "message"}
    if isinstance(data, dict) and "error" in data:
        error_msg = data["error"]
        if log:
            log(f"MUELE login failed: {error_msg}")
        return None, str(error_msg)

    # Success returns {"token": "abc123..."}
    token = data.get("token") if isinstance(data, dict) else None
    if not token:
        return None, "MUELE did not return a token. Check your credentials."

    # Store the token in the keyring
    store_token(token)
    return token, None


def get_muele_login_url() -> str:
    """Return the MUELE login page URL for browser-based authentication."""
    return _LOGIN_URL


def get_muele_token_instructions_url() -> str:
    """Return the URL where users can manually generate a token in MUELE."""
    return f"{MUELE_BASE_URL}/user/managetoken.php"


# ---------------------------------------------------------------------------
# MUELE REST API call with retry logic
# ---------------------------------------------------------------------------


def _api_call(
    wsfunction: str,
    params: dict | None = None,
    token: str | None = None,
    timeout: int = _DEFAULT_TIMEOUT,
    log: Callable | None = None,
) -> tuple[Any, str | None]:
    """Make a MUELE REST API call with automatic retry on transient errors.

    Returns (response_data, None) on success or (None, error_message) on
    failure. Never throws. Retries up to _MAX_RETRIES times with exponential
    backoff on network errors and 5xx server errors.
    """
    if token is None:
        token = load_token()
    if not token:
        return None, (
            "MUELE token not configured. "
            "Go to Integrations > MUELE to connect your account."
        )

    payload = {
        "wstoken": token,
        "wsfunction": wsfunction,
        "moodlewsrestformat": "json",
        **(params or {}),
    }

    last_error = None
    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.post(
                _WS_ENDPOINT,
                data=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.Timeout:
            last_error = f"MUELE API timed out after {timeout}s for {wsfunction}"
            if log:
                log(f"{last_error} (attempt {attempt + 1}/{_MAX_RETRIES})")
            logger.warning(last_error)
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_DELAY * (2 ** attempt))
            continue
        except requests.ConnectionError:
            last_error = "Could not connect to MUELE. Check your internet connection."
            if log:
                log(f"{last_error} (attempt {attempt + 1}/{_MAX_RETRIES})")
            logger.warning(last_error)
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_DELAY * (2 ** attempt))
            continue
        except requests.RequestException as exc:
            # Non-retryable client errors (4xx) or non-network errors
            if resp.status_code and 400 <= resp.status_code < 500:
                return None, f"MUELE request failed (HTTP {resp.status_code}): {exc}"
            last_error = f"MUELE API request failed: {exc}"
            if log:
                log(f"{last_error} (attempt {attempt + 1}/{_MAX_RETRIES})")
            logger.warning(last_error)
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_DELAY * (2 ** attempt))
            continue
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            return None, f"MUELE returned an unexpected response: {exc}"

        # MUELE returns errors as a JSON object with an "exception" key
        if isinstance(data, dict) and "exception" in data:
            error_msg = data.get("message", data.get("errorcode", "Unknown MUELE error"))
            if log:
                log(f"MUELE API error for {wsfunction}: {error_msg}")
            logger.warning("MUELE API error for %s: %s", wsfunction, error_msg)
            return None, str(error_msg)

        return data, None

    return None, last_error or "MUELE is not responding after multiple retries."


# ---------------------------------------------------------------------------
# High-level API functions
# ---------------------------------------------------------------------------


def verify_token(token: str | None = None, log: Callable | None = None) -> tuple[dict | None, str | None]:
    """Verify that a MUELE token is valid by fetching the current user's
    details. Returns (user_info, None) on success or (None, error_message)."""
    t = token or load_token()
    if not t:
        return None, "No token provided."

    data, error = _api_call("core_webservice_get_site_info", token=t, log=log)
    if error:
        return None, error
    if not isinstance(data, dict):
        return None, "Unexpected response from MUELE."

    return {
        "userid": data.get("userid"),
        "username": data.get("username"),
        "fullname": data.get("fullname"),
        "sitename": data.get("sitename"),
        "release": data.get("release"),
    }, None


def get_courses(token: str | None = None, log: Callable | None = None) -> tuple[list, str | None]:
    """Get the list of courses the authenticated user is enrolled in on MUELE.

    Returns (list_of_course_dicts, None) or (None, error_message).
    Each course dict has: id, shortname, fullname, summary, startdate, enddate.
    """
    data, error = _api_call(
        "core_course_get_enrolled_courses_by_timeline_classification",
        {"classification": "all", "limit": 50, "sort": "fullname"},
        token=token, log=log,
    )
    if error:
        return [], error

    courses = data if isinstance(data, list) else data.get("courses", []) if isinstance(data, dict) else []
    result = []
    for c in courses:
        result.append({
            "id": c.get("id"),
            "shortname": c.get("shortname", ""),
            "fullname": c.get("fullname", ""),
            "summary": c.get("summary", ""),
            "startdate": datetime.fromtimestamp(c["startdate"]) if c.get("startdate") else None,
            "enddate": datetime.fromtimestamp(c["enddate"]) if c.get("enddate") else None,
            "course_category": c.get("coursecategory", ""),
        })
    return result, None


def get_course_contents(
    course_id: int,
    token: str | None = None,
    log: Callable | None = None,
) -> tuple[list, str | None]:
    """Get the full content (topics, resources, files) for a MUELE course.

    Returns (list_of_section_dicts, None) or (None, error_message).
    Each section has: id, name, summary, modules[].
    Each module has: id, name, modname (e.g. "resource", "assign", "url"),
    and optionally a file list.
    """
    data, error = _api_call("core_course_get_contents", {"courseid": course_id}, token=token, log=log)
    if error:
        return [], error

    sections = data if isinstance(data, list) else []
    return sections, None


def get_assignments(
    course_ids: list[int] | None = None,
    token: str | None = None,
    log: Callable | None = None,
) -> tuple[list, str | None]:
    """Get all assignments from MUELE for the given courses (or all enrolled).

    Returns (list_of_assignment_dicts, None) or (None, error_message).
    Each assignment has: id, cmid, course, name, duedate, intro, etc.
    """
    params = {"courseids[]": course_ids} if course_ids else {}
    data, error = _api_call("mod_assign_get_assignments", params, token=token, log=log)
    if error:
        return [], error

    courses_data = data.get("courses", []) if isinstance(data, dict) else []
    assignments = []
    for course in courses_data:
        for assign in course.get("assignments", []):
            assignments.append({
                "id": assign.get("id"),
                "cmid": assign.get("cmid"),
                "course_id": course.get("id"),
                "course_name": course.get("fullname", ""),
                "name": assign.get("name", ""),
                "intro": assign.get("intro", ""),
                "duedate": datetime.fromtimestamp(assign["duedate"]) if assign.get("duedate") and assign["duedate"] > 0 else None,
                "allowsubmissionsfromdate": datetime.fromtimestamp(assign["allowsubmissionsfromdate"]) if assign.get("allowsubmissionsfromdate") and assign["allowsubmissionsfromdate"] > 0 else None,
                "grade": assign.get("grade"),
                "timemodified": datetime.fromtimestamp(assign["timemodified"]) if assign.get("timemodified") else None,
            })
    return assignments, None


def get_upcoming_events(
    days: int = 14,
    token: str | None = None,
    log: Callable | None = None,
) -> tuple[list, str | None]:
    """Get upcoming calendar events from MUELE.

    Returns (list_of_event_dicts, None) or (None, error_message).
    """
    data, error = _api_call("core_calendar_get_calendar_upcoming", {"days": days}, token=token, log=log)
    if error:
        return [], error

    events = data.get("events", []) if isinstance(data, dict) else []
    result = []
    for e in events:
        result.append({
            "id": e.get("id"),
            "name": e.get("name", ""),
            "description": e.get("description", ""),
            "timestart": datetime.fromtimestamp(e["timestart"]) if e.get("timestart") else None,
            "timeduration": e.get("timeduration", 0),
            "eventtype": e.get("eventtype", ""),
            "course_id": e.get("course", {}).get("id") if isinstance(e.get("course"), dict) else None,
        })
    return result, None


def get_course_files(
    course_id: int,
    token: str | None = None,
    log: Callable | None = None,
) -> tuple[list, str | None]:
    """Get all downloadable files from a MUELE course's resources.

    Returns (list_of_file_dicts, None) or (None, error_message).
    Each file has: filename, fileurl, filesize, mimetype, section_name, module_name.
    The fileurl includes the token parameter for authenticated download.
    """
    sections, error = get_course_contents(course_id, token=token, log=log)
    if error:
        return [], error

    files = []
    token_val = token or load_token()

    for section in sections:
        section_name = section.get("name", "General")
        for module in section.get("modules", []):
            modname = module.get("modname", "")
            module_name = module.get("name", "")
            # Only process modules that have downloadable files on MUELE
            if modname not in ("resource", "folder", "file", "assign"):
                continue
            for content in module.get("contents", []):
                fileurl = content.get("fileurl", "")
                if not fileurl:
                    continue
                # Append token to file URL for MUELE authentication
                # MUELE uses: pluginfile.php/...?token=xxx
                if token_val:
                    separator = "&" if "?" in fileurl else "?"
                    fileurl = f"{fileurl}{separator}token={token_val}"
                files.append({
                    "filename": content.get("filename", "unnamed"),
                    "fileurl": fileurl,
                    "filesize": content.get("filesize", 0),
                    "mimetype": content.get("mimetype", ""),
                    "filepath": content.get("filepath", "/"),
                    "section_name": section_name,
                    "module_name": module_name,
                    "course_id": course_id,
                    "timecreated": datetime.fromtimestamp(content["timecreated"]) if content.get("timecreated") else None,
                    "timemodified": datetime.fromtimestamp(content["timemodified"]) if content.get("timemodified") else None,
                })
    return files, None