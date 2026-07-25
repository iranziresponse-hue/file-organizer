"""SQLite FTS5-backed search index, shared across every model Orch lets you
search: MoveEvent (recent moves / filenames + course codes) and FileSummary
(summary text). One virtual table (see migration 0029), disambiguated by
record_type, rather than one FTS table per source.

index()/remove() never raise -- a search-index write failing must never
break the real save/create it's piggybacking on (same swallow-and-log
philosophy as organizer.core.perf). search() is the opposite: it raises on
any failure, so its caller (organizer.views.dashboard's Recent Moves search)
can fall back to the plain icontains filter it used before this existed,
rather than the dashboard silently showing wrong results.
"""

import logging
import re

from django.db import connection

logger = logging.getLogger("organizer.search_index")

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def index(record_type, record_id, profile_id, title="", body=""):
    try:
        remove(record_type, record_id)
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO search_index (record_type, record_id, profile_id, title, body) "
                "VALUES (%s, %s, %s, %s, %s)",
                [record_type, record_id, profile_id, title or "", body or ""],
            )
    except Exception as exc:
        logger.warning("Could not index %s #%s for search: %s", record_type, record_id, exc)


def remove(record_type, record_id):
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM search_index WHERE record_type = %s AND record_id = %s",
                [record_type, record_id],
            )
    except Exception as exc:
        logger.warning("Could not remove %s #%s from the search index: %s", record_type, record_id, exc)


def _to_fts_query(raw):
    """A bare user search string can contain characters (quotes, *, :, -,
    parens) that are syntax in FTS5's own query language, not literal text.
    Stripping to plain alphanumeric tokens and quoting+prefix-matching each
    one avoids ever handing FTS5 a string it can't parse."""
    tokens = _TOKEN_RE.findall(raw or "")
    return " ".join(f'"{tok}"*' for tok in tokens)


def search(query, profile_id, record_types=None, limit=50):
    """Returns [(record_type, record_id), ...] matching query, scoped to one
    profile. Raises on any failure -- callers fall back to their own
    non-indexed search rather than trust a partially-broken query."""
    fts_query = _to_fts_query(query)
    if not fts_query:
        return []

    sql = (
        "SELECT record_type, record_id FROM search_index "
        "WHERE search_index MATCH %s AND profile_id = %s"
    )
    params = [fts_query, profile_id]
    if record_types:
        placeholders = ", ".join(["%s"] * len(record_types))
        sql += f" AND record_type IN ({placeholders})"
        params.extend(record_types)
    sql += " LIMIT %s"
    params.append(limit)

    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def health_check() -> dict:
    """For the owner cockpit's Performance panel. index()/remove()/search()
    all swallow or isolate their own failures on purpose (see module
    docstring) so a broken index never breaks the app for the person using
    it -- but that same swallowing means a genuinely broken index (a
    corrupted virtual table, a schema mismatch after a botched migration)
    could otherwise fail silently forever with nothing ever surfacing it.
    This is the one place that's allowed to just look and report, honestly,
    whether the index is actually working right now. Never raises."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT record_type, COUNT(*) FROM search_index GROUP BY record_type")
            counts = dict(cursor.fetchall())
        total = sum(counts.values())

        # A real MATCH query, not just a row count -- confirms the FTS5
        # virtual table itself is genuinely queryable, not just present.
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM search_index WHERE search_index MATCH %s LIMIT 1", ['"orch"*'])
            cursor.fetchall()

        return {"healthy": True, "total_rows": total, "counts_by_type": counts, "error": ""}
    except Exception as exc:
        logger.warning("Search index health check failed: %s", exc)
        return {"healthy": False, "total_rows": 0, "counts_by_type": {}, "error": str(exc)}
