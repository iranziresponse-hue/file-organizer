"""One-off backfill for organizer.core.search_index -- indexes every
existing MoveEvent and FileSummary row, for installs that had data before
the search index shipped (migration 0029). New rows are indexed
automatically from here on via organizer.signals' post_save receivers; this
command is only needed once per install, or after directly editing the
database in a way that bypasses the ORM (e.g. a raw SQL restore).
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Backfill the FTS5 search index from existing MoveEvent/FileSummary rows."

    def handle(self, *args, **options):
        from organizer.core import search_index
        from organizer.models import FileSummary, MoveEvent

        move_count = 0
        for event in MoveEvent.objects.all().iterator():
            search_index.index(
                "move_event", event.pk, event.profile_id,
                title=event.filename, body=f"{event.filename} {event.course_code or ''}",
            )
            move_count += 1

        summary_count = 0
        for summary in FileSummary.objects.select_related("move_event").iterator():
            search_index.index(
                "file_summary", summary.move_event_id, summary.move_event.profile_id,
                title=summary.move_event.filename, body=summary.content,
            )
            summary_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Indexed {move_count} move(s) and {summary_count} summary(ies)."
        ))
