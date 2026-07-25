"""Caches a small, deliberately narrow set of read paths: resource
recommendations and the Timeline page's activity feed. Each depends on
exactly one model, invalidated via that model's post_save/post_delete
signal (see organizer/signals.py) -- so a write always shows up on the very
next read, not "eventually" or "within N seconds".

Everything else this session's performance research looked at (service
mesh, connection status, war room, weak-area summaries) was deliberately
left uncached: their staleness triggers include local JSON config files and
OS keyring state that have no DB-visible "changed" signal today, and a
wrong-looking "Connected"/"Disconnected" badge is a worse bug than a few
extra milliseconds of local SQLite query time. Caching those safely would
need a real invalidation signal for config-file/keyring changes first
(e.g. a real AppSettings.updated_at, or an explicit cache.delete() call
added at every settings-writing view) -- not something to bolt on as an
afterthought here.

Both cached reads below are parameterized (resource recommendations by
subject_code, timeline by days/activity_type), so a single write can't just
delete "the" cache key for a profile -- there may be several cached
variants of it. Each uses a per-profile generation counter instead:
bumping it invalidates every variant at once without enumerating every
parameter combination that's ever been cached.
"""

from django.core.cache import cache

# A safety net, not the primary invalidation mechanism -- every write path
# that matters already calls the invalidate_*() functions below via a
# signal. This just bounds how long a *missed* invalidation could live.
_TIMEOUT = 300


def _generation(namespace, profile_id):
    key = f"{namespace}_gen:{profile_id}"
    gen = cache.get(key)
    if gen is None:
        gen = 0
        cache.set(key, gen, None)
    return gen


def _bump_generation(namespace, profile_id):
    key = f"{namespace}_gen:{profile_id}"
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, None)


def get_or_set_resource_recommendations(profile_id, subject_code, compute_fn):
    generation = _generation("resource_recs", profile_id)
    key = f"resource_recs:{profile_id}:{generation}:{subject_code or 'all'}"
    value = cache.get(key)
    if value is None:
        value = compute_fn()
        cache.set(key, value, _TIMEOUT)
    return value


def invalidate_resource_recommendations(profile_id):
    _bump_generation("resource_recs", profile_id)


def get_or_set_timeline(profile_id, days, activity_type, compute_fn):
    generation = _generation("timeline", profile_id)
    key = f"timeline:{profile_id}:{generation}:{days}:{activity_type or 'all'}"
    value = cache.get(key)
    if value is None:
        value = compute_fn()
        cache.set(key, value, _TIMEOUT)
    return value


def invalidate_timeline(profile_id):
    _bump_generation("timeline", profile_id)
