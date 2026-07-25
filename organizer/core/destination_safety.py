"""Guards against reroute/relocate destinations landing outside the
folders Orch is supposed to manage. A typo'd or wrong path in the "Move
file" or "Move somewhere else" dialogs currently creates folders and moves
files anywhere the process can write -- this gives the views a chance to
ask "are you sure?" before that happens, rather than moving first.

Never raises on a malformed path string: an unparseable destination just
resolves as "not trusted" and gets the same confirmation prompt as any
other external folder, not a crash.
"""

from pathlib import Path

from . import paths


def is_within_trusted_roots(destination: str, profile) -> bool:
    """True if `destination` is the same as, or a descendant of, the
    active profile's own root folder, PERSONAL_ROOT, or IMPORTANT_ROOT --
    the folders this app already treats as its own everywhere else."""
    if not destination:
        return False

    try:
        target = Path(destination).expanduser().resolve()
    except (OSError, ValueError):
        return False

    roots = [paths.PERSONAL_ROOT, paths.IMPORTANT_ROOT]
    if profile and profile.root_path:
        roots.append(Path(profile.root_path))

    for root in roots:
        try:
            resolved_root = Path(root).expanduser().resolve()
        except (OSError, ValueError):
            continue
        if target == resolved_root or resolved_root in target.parents:
            return True

    return False
