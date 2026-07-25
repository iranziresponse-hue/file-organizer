"""Timing instrumentation for the Performance Health Panel (owner console).

organizer.core.perf.measure() wraps an existing operation without changing
its behavior -- it always re-raises whatever the wrapped block raised, and
never lets a failure to *record* the timing break the real operation. Callers
don't need to know or care whether recording succeeded.
"""

import logging
import time
from contextlib import contextmanager
from functools import wraps

from django.db import connection
from django.test.utils import CaptureQueriesContext

logger = logging.getLogger("organizer.perf")

# Pages this measures query count for -- deliberately not every request:
# forcing a debug cursor on every request would add overhead to the exact
# thing being measured, so this stays scoped to the handful of pages named
# in the performance roadmap.
WATCHED_VIEWS = {
    "dashboard", "study_home", "connections_home", "muele_courses",
    "timeline_view", "resource_radar",
}


@contextmanager
def measure(operation, profile=None, detail=""):
    start = time.perf_counter()
    success = True
    try:
        yield
    except Exception:
        success = False
        raise
    finally:
        duration_ms = int((time.perf_counter() - start) * 1000)
        _record(operation, duration_ms, success, detail, profile)


def _record(operation, duration_ms, success, detail, profile, query_count=None):
    try:
        from ..models import PerformanceMetric

        PerformanceMetric.objects.create(
            operation=operation,
            duration_ms=duration_ms,
            query_count=query_count,
            success=success,
            detail=detail[:255],
            profile=profile,
        )
    except Exception as exc:
        logger.warning("Could not record a performance metric: %s", exc)


def measure_view(view_func):
    """Decorator for one of the WATCHED_VIEWS -- records page-load duration
    and DB query count for that request. Only meant for the handful of pages
    actually named in the performance roadmap; not a general-purpose
    middleware, on purpose (see WATCHED_VIEWS)."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        start = time.perf_counter()
        success = True
        ctx = CaptureQueriesContext(connection)
        try:
            with ctx:
                return view_func(request, *args, **kwargs)
        except Exception:
            success = False
            raise
        finally:
            # A crashing view is exactly the kind of thing this panel
            # should be able to show -- PerformanceMetric.success exists
            # for this. Recording only lived on the happy path before,
            # so a view that started throwing would just silently stop
            # showing up here instead of showing up as failing.
            duration_ms = int((time.perf_counter() - start) * 1000)
            try:
                from ..models import Profile

                profile = Profile.get_active()
            except Exception:
                profile = None
            _record(
                "page_load", duration_ms, success=success, detail=view_func.__name__,
                profile=profile, query_count=len(ctx.captured_queries),
            )

    return wrapper
