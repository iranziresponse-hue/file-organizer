"""Developer-only owner access gates for packaged troubleshooting tools.

Every install of Orch (this developer's machine included) runs its own copy
on 127.0.0.1, so an IP check alone can't tell "the developer" apart from any
other student running their own local copy -- it only ever tells "this same
computer" apart from "the network." The feature must therefore never even
exist in a build a student could have downloaded. PyInstaller sets
sys.frozen on the packaged exe (see runtime.py); running from source is only
possible from this private git checkout, so gating on "not frozen" is what
actually keeps this developer-only, not the IP check by itself.
"""

import json
import os
import sys
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


def is_packaged_build():
    """True in the exe distributed to students; False when run from source."""
    return getattr(sys, "frozen", False)


def feature_available():
    """Whether owner mode can exist at all on this install, regardless of
    whether it has been turned on."""
    return not is_packaged_build()


def owner_mode_enabled():
    if not feature_available():
        return False

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
