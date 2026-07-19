"""Local-only owner access gates for packaged troubleshooting tools."""

import json
import os
from pathlib import Path

from runtime import app_dir

OWNER_MODE_ENV = "ORCH_OWNER_MODE"
OWNER_CONFIG_FILENAME = "orch-owner.json"
TRUTHY_VALUES = {"1", "true", "yes", "on", "owner"}
LOCAL_ADDRESSES = {"127.0.0.1", "::1", "localhost"}


def owner_config_path():
    return app_dir() / OWNER_CONFIG_FILENAME


def _read_owner_config(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def owner_mode_enabled():
    env_value = os.environ.get(OWNER_MODE_ENV, "").strip().lower()
    if env_value in TRUTHY_VALUES:
        return True

    config = _read_owner_config(owner_config_path())
    return str(config.get("owner_mode", "")).strip().lower() in TRUTHY_VALUES


def is_local_address(value):
    if not value:
        return False
    address = value.split(",")[0].strip().lower()
    return address in LOCAL_ADDRESSES or address.startswith("127.")


def request_allowed(request):
    return owner_mode_enabled() and is_local_address(request.META.get("REMOTE_ADDR"))
