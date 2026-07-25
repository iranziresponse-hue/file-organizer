"""Keeps organizer.core.search_index in sync with MoveEvent/FileSummary via
post_save/post_delete, rather than a call at every place either model gets
created (there are several -- watcher._record_event, undo.restore_move,
sorting.relocate_move_event, muele_downloader, direct .objects.create() in
tests, ...). A signal on the model itself is the one place that's
guaranteed to see every write, regardless of which code path made it.

FileSummary.record_id is its own MoveEvent's pk (not the FileSummary's own
pk) -- see organizer/core/search_index.py -- so a search for text that only
appears in a summary still resolves back to the right MoveEvent row.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import FileSummary, LearningActivity, MoveEvent, ResourceRecommendation


@receiver(post_save, sender=MoveEvent)
def _index_move_event(sender, instance, **kwargs):
    from .core import search_index

    search_index.index(
        "move_event", instance.pk, instance.profile_id,
        title=instance.filename, body=f"{instance.filename} {instance.course_code or ''}",
    )


@receiver(post_delete, sender=MoveEvent)
def _unindex_move_event(sender, instance, **kwargs):
    from .core import search_index

    search_index.remove("move_event", instance.pk)
    # A MoveEvent's FileSummary is CASCADE-deleted alongside it (see
    # FileSummary.move_event's on_delete) -- confirmed Django fires
    # FileSummary's own post_delete for that cascade too (registering a
    # receiver for a model disables the ORM's signal-skipping fast-delete
    # path for it), so _unindex_file_summary below already handles that
    # row; nothing extra needed here.


@receiver(post_save, sender=FileSummary)
def _index_file_summary(sender, instance, **kwargs):
    from .core import search_index

    search_index.index(
        "file_summary", instance.move_event_id, instance.move_event.profile_id,
        title=instance.move_event.filename, body=instance.content,
    )


@receiver(post_delete, sender=FileSummary)
def _unindex_file_summary(sender, instance, **kwargs):
    from .core import search_index

    search_index.remove("file_summary", instance.move_event_id)


# --- organizer.core.resource_cache invalidation -----------------------

@receiver(post_save, sender=ResourceRecommendation)
@receiver(post_delete, sender=ResourceRecommendation)
def _invalidate_resource_recommendations_cache(sender, instance, **kwargs):
    from .core import resource_cache

    resource_cache.invalidate_resource_recommendations(instance.profile_id)


@receiver(post_save, sender=LearningActivity)
@receiver(post_delete, sender=LearningActivity)
def _invalidate_timeline_cache(sender, instance, **kwargs):
    from .core import resource_cache

    resource_cache.invalidate_timeline(instance.profile_id)
