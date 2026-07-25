from unittest import mock

from django.test import TestCase
from django.urls import reverse

from organizer.core import search_index
from organizer.models import FileSummary, MoveEvent, Profile

from .helpers import SandboxedPathsTestCase


class IndexRoundTripTests(TestCase):
    def test_index_then_search_finds_it(self):
        search_index.index("move_event", 1, profile_id=1, title="notes.pdf", body="notes.pdf CSC2100")

        self.assertEqual(search_index.search("csc21", 1), [("move_event", 1)])
        self.assertEqual(search_index.search("notes", 1), [("move_event", 1)])

    def test_remove_then_search_finds_nothing(self):
        search_index.index("move_event", 1, profile_id=1, title="notes.pdf", body="notes.pdf")
        search_index.remove("move_event", 1)

        self.assertEqual(search_index.search("notes", 1), [])

    def test_reindexing_the_same_record_does_not_duplicate_it(self):
        search_index.index("move_event", 1, profile_id=1, title="a.pdf", body="a.pdf")
        search_index.index("move_event", 1, profile_id=1, title="b.pdf", body="b.pdf")

        self.assertEqual(search_index.search("b", 1), [("move_event", 1)])
        self.assertEqual(search_index.search("a", 1), [])

    def test_search_is_scoped_to_one_profile(self):
        search_index.index("move_event", 1, profile_id=1, title="shared.pdf", body="shared.pdf")
        search_index.index("move_event", 2, profile_id=2, title="shared.pdf", body="shared.pdf")

        self.assertEqual(search_index.search("shared", 1), [("move_event", 1)])
        self.assertEqual(search_index.search("shared", 2), [("move_event", 2)])

    def test_record_types_filter_narrows_results(self):
        search_index.index("move_event", 1, profile_id=1, title="x", body="course notes")
        search_index.index("file_summary", 1, profile_id=1, title="x", body="course notes")

        both = search_index.search("course", 1)
        self.assertEqual(len(both), 2)

        only_summaries = search_index.search("course", 1, record_types=["file_summary"])
        self.assertEqual(only_summaries, [("file_summary", 1)])

    def test_special_characters_do_not_raise(self):
        search_index.index("move_event", 1, profile_id=1, title="a.pdf", body="a.pdf")
        # These would be syntax errors to FTS5's own query parser if handed
        # through unsanitized -- the point of this test is that none of them
        # raise, not what they happen to match.
        for weird in ['"quoted"', "AND OR NOT", "a:b", "(unbalanced", "***", ""]:
            search_index.search(weird, 1)

    def test_a_broken_index_write_never_raises(self):
        with mock.patch("django.db.connection.cursor", side_effect=Exception("db down")):
            search_index.index("move_event", 1, profile_id=1, title="x", body="x")
            search_index.remove("move_event", 1)
        # Reaching this line at all is the assertion -- neither call raised.

    def test_search_raises_so_callers_can_fall_back(self):
        with mock.patch("django.db.connection.cursor", side_effect=Exception("db down")):
            with self.assertRaises(Exception):
                search_index.search("x", 1)


class SignalIndexingTests(SandboxedPathsTestCase):
    def test_creating_a_move_event_indexes_it_automatically(self):
        profile = self.make_profile()
        event = MoveEvent.objects.create(
            profile=profile, filename="CSC2100 slides.pdf",
            destination_path=str(self.profile_root / "x.pdf"), method="course_code",
            course_code="CSC2100",
        )

        self.assertEqual(search_index.search("csc21", profile.pk), [("move_event", event.pk)])

    def test_deleting_a_move_event_removes_it_from_the_index(self):
        profile = self.make_profile()
        event = MoveEvent.objects.create(
            profile=profile, filename="notes.pdf",
            destination_path=str(self.profile_root / "x.pdf"), method="course_code",
        )
        self.assertEqual(search_index.search("notes", profile.pk), [("move_event", event.pk)])

        event.delete()

        self.assertEqual(search_index.search("notes", profile.pk), [])

    def test_creating_a_file_summary_indexes_its_content(self):
        profile = self.make_profile()
        event = MoveEvent.objects.create(
            profile=profile, filename="unrelated.pdf",
            destination_path=str(self.profile_root / "x.pdf"), method="course_code",
        )
        FileSummary.objects.create(move_event=event, content="binary search trees and traversal")

        matches = search_index.search("traversal", profile.pk, record_types=["file_summary"])
        self.assertEqual(matches, [("file_summary", event.pk)])

    def test_deleting_a_move_event_also_removes_its_summarys_index_row(self):
        profile = self.make_profile()
        event = MoveEvent.objects.create(
            profile=profile, filename="unrelated.pdf",
            destination_path=str(self.profile_root / "x.pdf"), method="course_code",
        )
        FileSummary.objects.create(move_event=event, content="binary search trees")
        self.assertEqual(
            search_index.search("binary", profile.pk, record_types=["file_summary"]),
            [("file_summary", event.pk)],
        )

        event.delete()

        self.assertEqual(search_index.search("binary", profile.pk, record_types=["file_summary"]), [])


class DashboardSearchUsesTheIndexTests(SandboxedPathsTestCase):
    def test_matches_text_that_only_appears_in_a_summary(self):
        profile = self.make_profile()
        event = MoveEvent.objects.create(
            profile=profile, filename="lecture4.pdf",
            destination_path=str(self.profile_root / "lecture4.pdf"), method="course_code",
            success=True,
        )
        FileSummary.objects.create(move_event=event, content="an overview of graph algorithms")

        response = self.client.get(reverse("dashboard"), {"q": "graph algorithms"})

        table_rows = list(response.context["page_obj"].object_list)
        self.assertEqual([e.filename for e in table_rows], ["lecture4.pdf"])

    def test_falls_back_to_icontains_if_the_index_query_fails(self):
        profile = self.make_profile()
        MoveEvent.objects.create(
            profile=profile, filename="biology_notes.pdf",
            destination_path=str(self.profile_root / "biology_notes.pdf"), method="course_code",
            success=True,
        )

        with mock.patch("organizer.core.search_index.search", side_effect=Exception("fts unavailable")):
            response = self.client.get(reverse("dashboard"), {"q": "bio"})

        table_rows = list(response.context["page_obj"].object_list)
        self.assertEqual([e.filename for e in table_rows], ["biology_notes.pdf"])


class HealthCheckTests(TestCase):
    def test_reports_healthy_with_a_row_count_when_working(self):
        search_index.index("move_event", 1, profile_id=1, title="a.pdf", body="a.pdf")
        search_index.index("file_summary", 1, profile_id=1, title="a.pdf", body="notes about a")

        health = search_index.health_check()

        self.assertTrue(health["healthy"])
        self.assertEqual(health["total_rows"], 2)
        self.assertEqual(health["counts_by_type"], {"move_event": 1, "file_summary": 1})
        self.assertEqual(health["error"], "")

    def test_reports_healthy_and_zero_rows_when_empty(self):
        health = search_index.health_check()

        self.assertTrue(health["healthy"])
        self.assertEqual(health["total_rows"], 0)

    def test_reports_unhealthy_without_raising_when_the_table_is_unreachable(self):
        with mock.patch("django.db.connection.cursor", side_effect=Exception("no such table: search_index")):
            health = search_index.health_check()

        self.assertFalse(health["healthy"])
        self.assertEqual(health["total_rows"], 0)
        self.assertIn("no such table", health["error"])
