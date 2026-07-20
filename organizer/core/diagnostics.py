"""Admin diagnostics — deep system health, error reporting, backup/restore,
database maintenance, and permissions checking.

All functions return (result, error_message) tuples — never throw.
"""

import json
import os
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from django.utils import timezone


# ---------------------------------------------------------------------------
# Watcher status
# ---------------------------------------------------------------------------

def get_watcher_status() -> dict:
    """Get the current status of the file watcher.

    Checks the log file for recent activity to determine if the watcher
    appears to be running.
    """
    from . import paths

    status = {
        "running": False,
        "last_activity": None,
        "recent_errors": [],
        "uptime_hours": None,
        "files_watched_24h": 0,
        "poll_interval": "3 seconds (default)",
    }

    # Check the watcher log for recent activity
    log_path = paths.LOG_PATH
    if log_path.exists():
        try:
            last_modified = datetime.fromtimestamp(log_path.stat().st_mtime)
            status["last_activity"] = last_modified.isoformat()

            # If the log was modified within the last 30 seconds, watcher is likely running
            seconds_since = (datetime.now() - last_modified).total_seconds()
            status["running"] = seconds_since < 60

            # Parse recent log lines for errors and activity counts
            try:
                lines = log_path.read_text(encoding="utf-8").splitlines()
                recent_lines = lines[-200:]  # Last 200 lines
                errors = []
                move_count = 0
                first_time = None

                for line in recent_lines:
                    if "FAILED" in line or "error" in line.lower() or "Error" in line:
                        errors.append(line)
                    if "Moved" in line:
                        move_count += 1
                    # Extract timestamps
                    if first_time is None and line.startswith("["):
                        try:
                            ts = line[1:20]
                            first_time = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                        except (ValueError, IndexError):
                            pass

                status["recent_errors"] = errors[-10:]  # Last 10 errors
                status["files_watched_24h"] = move_count

                if first_time:
                    status["uptime_hours"] = round((datetime.now() - first_time).total_seconds() / 3600, 1)

            except (OSError, ValueError):
                pass

        except OSError:
            pass

    return status


def get_watcher_log_tail(lines: int = 50) -> list[str]:
    """Get the last N lines from the watcher log."""
    from . import paths

    log_path = paths.LOG_PATH
    if not log_path.exists():
        return ["No log file found."]

    try:
        all_lines = log_path.read_text(encoding="utf-8").splitlines()
        return all_lines[-lines:]
    except OSError:
        return ["Could not read log file."]


# ---------------------------------------------------------------------------
# Error reporting
# ---------------------------------------------------------------------------

def get_recent_errors(days: int = 7, limit: int = 50) -> list[dict]:
    """Get recent failed moves and system errors."""
    from organizer.models import MoveEvent

    since = timezone.now() - timedelta(days=days)
    failed_moves = MoveEvent.objects.filter(
        success=False, timestamp__gte=since
    ).order_by("-timestamp")[:limit]

    return [
        {
            "id": e.pk,
            "timestamp": e.timestamp.isoformat(),
            "filename": e.filename,
            "error": e.error_message or "Unknown error",
            "method": e.method,
            "source": e.source_path,
        }
        for e in failed_moves
    ]


def get_error_summary(days: int = 7) -> dict:
    """Get a summary of errors grouped by type."""
    from django.db.models import Count

    from organizer.models import MoveEvent

    since = timezone.now() - timedelta(days=days)
    failed = MoveEvent.objects.filter(success=False, timestamp__gte=since)

    by_method = list(
        failed.values("method").annotate(total=Count("id")).order_by("-total")
    )

    return {
        "total_failed": failed.count(),
        "total_success": MoveEvent.objects.filter(success=True, timestamp__gte=since).count(),
        "by_method": by_method,
        "failure_rate": round(
            failed.count() / max(MoveEvent.objects.filter(timestamp__gte=since).count(), 1) * 100,
            1,
        ),
    }


# ---------------------------------------------------------------------------
# Database health
# ---------------------------------------------------------------------------

def get_database_health() -> dict:
    """Check the database health: size, table counts, integrity."""
    from django.db import connection

    from . import paths
    from runtime import app_dir

    db_path = app_dir() / "db.sqlite3"
    health = {
        "path": str(db_path),
        "exists": db_path.exists(),
        "size_bytes": 0,
        "size_mb": 0,
        "table_counts": {},
        "connection_ok": False,
        "warnings": [],
    }

    if not db_path.exists():
        health["warnings"].append("Database file does not exist at the expected path.")
        return health

    try:
        health["size_bytes"] = db_path.stat().st_size
        health["size_mb"] = round(db_path.stat().st_size / (1024 * 1024), 2)
    except OSError:
        health["warnings"].append("Could not read database file size.")

    try:
        # Check database connection and get table row counts
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                health["table_counts"][table] = count

            # Integrity check
            cursor.execute("PRAGMA integrity_check")
            integrity = cursor.fetchone()
            health["integrity"] = integrity[0] if integrity else "unknown"

        health["connection_ok"] = True

        if health.get("integrity") and health["integrity"] != "ok":
            health["warnings"].append(f"Database integrity check failed: {health['integrity']}")

    except Exception as exc:
        health["warnings"].append(f"Database connection error: {exc}")

    return health


# ---------------------------------------------------------------------------
# Integration failures
# ---------------------------------------------------------------------------

def get_integration_failures() -> list[dict]:
    """Get integrations that are in error state or have issues."""
    from organizer.models import IntegrationConnection

    failures = []

    connections = IntegrationConnection.objects.all()
    for conn in connections:
        issues = []

        if conn.status == "error":
            issues.append("Integration is in error state")

        if conn.provider == "muele":
            if not conn.last_sync_at:
                issues.append("Never synced")
            elif (timezone.now() - conn.last_sync_at).days > 7:
                issues.append(f"Last sync was {(timezone.now() - conn.last_sync_at).days} days ago")

        if not conn.base_url:
            issues.append("No URL configured")

        if issues:
            failures.append({
                "id": conn.pk,
                "display_name": conn.display_name,
                "provider": conn.provider,
                "profile": conn.profile.name if conn.profile else "None",
                "status": conn.status,
                "last_sync_at": conn.last_sync_at.isoformat() if conn.last_sync_at else None,
                "issues": issues,
            })

    return failures


# ---------------------------------------------------------------------------
# Permissions checker
# ---------------------------------------------------------------------------

def check_folder_permissions(folder_path: str) -> dict:
    """Check if a folder is readable and writable."""
    path = Path(folder_path)
    result = {
        "path": folder_path,
        "exists": path.exists(),
        "is_dir": path.is_dir() if path.exists() else False,
        "readable": False,
        "writable": False,
        "issues": [],
    }

    if not path.exists():
        result["issues"].append("Folder does not exist")
        return result

    if not path.is_dir():
        result["issues"].append("Path is not a directory")
        return result

    # Check readability
    try:
        os.listdir(str(path))
        result["readable"] = True
    except PermissionError:
        result["issues"].append("No read permission")
    except OSError as exc:
        result["issues"].append(f"Cannot read folder: {exc}")

    # Check writability
    test_file = path / ".orch_write_test"
    try:
        test_file.write_text("test")
        test_file.unlink()
        result["writable"] = True
    except (PermissionError, OSError):
        result["issues"].append("No write permission")

    return result


def check_all_watched_folders() -> list[dict]:
    """Check permissions for all configured watched folders."""
    from organizer.models import AppSettings

    results = []
    settings = AppSettings.objects.first()
    if not settings:
        return []

    # Primary downloads
    if settings.downloads_path:
        result = check_folder_permissions(settings.downloads_path)
        result["label"] = "Primary downloads"
        results.append(result)

    # Secondary downloads
    if settings.secondary_downloads_path:
        result = check_folder_permissions(settings.secondary_downloads_path)
        result["label"] = "Secondary downloads"
        results.append(result)

    # Library inbox
    if settings.library_inbox_path:
        result = check_folder_permissions(settings.library_inbox_path)
        result["label"] = "Library inbox"
        results.append(result)

    # Active profile root
    from organizer.models import Profile

    active = Profile.get_active()

    if active and active.root_path:
        result = check_folder_permissions(active.root_path)
        result["label"] = f"Active profile root ({active.name})"
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Backup and restore
# ---------------------------------------------------------------------------

def create_backup(profile=None, log: Callable | None = None) -> dict:
    """Create a backup of the database and key config files.

    Returns {path, size_bytes, tables_backed_up}.
    """
    from shutil import copy2

    from . import paths
    from runtime import app_dir

    base_dir = app_dir()
    backup_dir = base_dir / "_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"orch_backup_{timestamp}.db"

    db_path = base_dir / "db.sqlite3"
    if not db_path.exists():
        if log:
            log("Database file not found for backup.")
        return {"error": "Database file not found", "path": None}

    try:
        copy2(str(db_path), str(backup_path))
        size = backup_path.stat().st_size

        # Get table count from the backup
        health = get_database_health()
        table_count = len(health.get("table_counts", {}))

        if log:
            log(f"Backup created: {backup_path.name} ({size / 1024:.0f} KB)")

        # Clean up old backups (keep last 10)
        cleanup_backups(keep=10, log=log)

        return {
            "path": str(backup_path),
            "size_bytes": size,
            "size_kb": round(size / 1024, 1),
            "tables_backed_up": table_count,
            "timestamp": timestamp,
        }
    except OSError as exc:
        if log:
            log(f"Backup failed: {exc}")
        return {"error": str(exc), "path": None}


def restore_backup(backup_path: str, log: Callable | None = None) -> dict:
    """Restore the database from a backup file.

    Returns {success: bool, error: str}.
    """
    from shutil import copy2

    from runtime import app_dir

    src = Path(backup_path)
    if not src.exists():
        return {"success": False, "error": "Backup file does not exist"}

    if src.suffix not in (".db", ".sqlite", ".sqlite3"):
        return {"success": False, "error": "Not a valid database backup file"}

    base_dir = app_dir()
    db_path = base_dir / "db.sqlite3"

    try:
        # Create a backup of the current database before overwriting
        current_backup = base_dir / "_backups" / f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        if db_path.exists():
            current_backup.parent.mkdir(parents=True, exist_ok=True)
            copy2(str(db_path), str(current_backup))
            if log:
                log(f"Current database backed up to {current_backup.name}")

        # Restore the backup
        copy2(str(src), str(db_path))
        if log:
            log(f"Database restored from {src.name}")

        return {"success": True, "pre_restore_backup": str(current_backup) if current_backup.exists() else None}
    except OSError as exc:
        if log:
            log(f"Restore failed: {exc}")
        return {"success": False, "error": str(exc)}


def list_backups() -> list[dict]:
    """List available database backups."""
    from runtime import app_dir

    backup_dir = app_dir() / "_backups"
    if not backup_dir.exists():
        return []

    backups = []
    for f in sorted(backup_dir.glob("*.db"), reverse=True):
        backups.append({
            "filename": f.name,
            "path": str(f),
            "size_bytes": f.stat().st_size,
            "size_kb": round(f.stat().st_size / 1024, 1),
            "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        })

    return backups


def cleanup_backups(keep: int = 10, log: Callable | None = None) -> int:
    """Delete old backups, keeping only the most recent N."""
    from runtime import app_dir

    backup_dir = app_dir() / "_backups"
    if not backup_dir.exists():
        return 0

    backups = sorted(backup_dir.glob("*.db"), reverse=True)
    deleted = 0

    for f in backups[keep:]:
        try:
            f.unlink()
            deleted += 1
        except OSError:
            pass

    if deleted and log:
        log(f"Cleaned up {deleted} old backup(s)")

    return deleted


# ---------------------------------------------------------------------------
# Database maintenance
# ---------------------------------------------------------------------------

def vacuum_database(log: Callable | None = None) -> dict:
    """Run VACUUM on the SQLite database to reclaim space."""
    from django.db import connection

    try:
        before = get_database_health()
        with connection.cursor() as cursor:
            cursor.execute("VACUUM")
        after = get_database_health()

        reclaimed = (before.get("size_bytes", 0) or 0) - (after.get("size_bytes", 0) or 0)

        if log:
            log(f"Database vacuumed: {before.get('size_mb', 0)}MB -> {after.get('size_mb', 0)}MB ({reclaimed / 1024:.0f} KB reclaimed)")

        return {
            "success": True,
            "before_mb": before.get("size_mb", 0),
            "after_mb": after.get("size_mb", 0),
            "reclaimed_kb": round(reclaimed / 1024, 1),
        }
    except Exception as exc:
        if log:
            log(f"Vacuum failed: {exc}")
        return {"success": False, "error": str(exc)}


def reindex_database(log: Callable | None = None) -> dict:
    """Reindex the database for better query performance."""
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("REINDEX")
        if log:
            log("Database reindexed successfully")
        return {"success": True}
    except Exception as exc:
        if log:
            log(f"Reindex failed: {exc}")
        return {"success": False, "error": str(exc)}


def get_database_table_details() -> list[dict]:
    """Get detailed information about each database table."""
    from django.db import connection

    details = []
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]

            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                row_count = cursor.fetchone()[0]

                cursor.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in cursor.fetchall()]

                cursor.execute(f"PRAGMA index_list({table})")
                indexes = [row[1] for row in cursor.fetchall()]

                details.append({
                    "name": table,
                    "rows": row_count,
                    "columns": len(columns),
                    "column_names": columns,
                    "indexes": len(indexes),
                    "index_names": indexes,
                })

    except Exception:
        pass

    return details


# ---------------------------------------------------------------------------
# Full system diagnostic report
# ---------------------------------------------------------------------------

def generate_full_diagnostic(log: Callable | None = None) -> dict:
    """Generate a complete system diagnostic report."""
    from organizer.models import Profile

    report = {
        "generated_at": datetime.now().isoformat(),
        "system": _get_system_info(),
        "watcher": get_watcher_status(),
        "errors": get_recent_errors(days=1),
        "error_summary": get_error_summary(),
        "database": get_database_health(),
        "integrations": get_integration_failures(),
        "permissions": check_all_watched_folders(),
        "backups": list_backups(),
        "profiles": [
            {
                "name": p.name,
                "purpose": p.purpose,
                "is_active": p.is_active,
                "subjects": len(p.config.groups) if hasattr(p, "config") and p.config else 0,
            }
            for p in Profile.objects.all()
        ],
    }

    return report


def _get_system_info() -> dict:
    """Get basic system information."""
    import platform

    return {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "hostname": platform.node(),
    }