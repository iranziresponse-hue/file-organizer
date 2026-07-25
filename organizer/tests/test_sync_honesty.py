"""last_sync_at must mean "last time this genuinely worked", not "last
time a sync was attempted" -- otherwise unstable campus internet produces
a string of real failures hidden behind a freshly-bumped "just synced"
timestamp. See organizer.core.muele_downloader.sync_profile_courses and
organizer.core.timetable_sync.sync_group_timetable.
"""

from datetime import timedelta
from unittest import mock

from django.utils import timezone

from organizer.core import muele_api, muele_downloader, timetable_sync
from organizer.models import IntegrationConnection, MueleCourse

from .helpers import SandboxedPathsTestCase


class MueleSyncHonestyTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.connection = IntegrationConnection.objects.create(
            profile=self.profile, provider="muele", display_name="MUELE", status="connected",
        )
        self.course = MueleCourse.objects.create(
            connection=self.connection, course_id=1, course_name="Data Structures", auto_download=True,
        )
        self.enterContext(mock.patch.object(muele_api, "load_connection_token", return_value="fake-token"))

    def test_a_clean_sync_updates_last_sync_at_and_stays_connected(self):
        with mock.patch.object(muele_api, "get_course_files", return_value=([], None)):
            muele_downloader.sync_profile_courses(self.profile)

        self.connection.refresh_from_db()
        self.assertIsNotNone(self.connection.last_sync_at)
        self.assertEqual(self.connection.status, "connected")

    def test_a_failing_sync_does_not_overwrite_the_last_known_good_timestamp(self):
        known_good = timezone.now() - timedelta(days=3)
        self.connection.last_sync_at = known_good
        self.connection.save(update_fields=["last_sync_at"])

        with mock.patch.object(muele_api, "get_course_files", return_value=(None, "server unreachable")):
            muele_downloader.sync_profile_courses(self.profile)

        self.connection.refresh_from_db()
        self.assertEqual(self.connection.last_sync_at, known_good)
        self.assertEqual(self.connection.status, "error")

    def test_a_never_synced_connection_stays_never_after_a_failure(self):
        with mock.patch.object(muele_api, "get_course_files", return_value=(None, "server unreachable")):
            muele_downloader.sync_profile_courses(self.profile)

        self.connection.refresh_from_db()
        self.assertIsNone(self.connection.last_sync_at)
        self.assertEqual(self.connection.status, "error")


class TimetableSyncHonestyTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.connection = IntegrationConnection.objects.create(
            profile=self.profile, provider="mak_timetable", display_name="Makerere Timetable",
            config={
                "academic_year_id": "1", "academic_year_label": "2025/2026",
                "semester_id": "1", "college": "COCIS", "group": "SE-2",
            },
        )

    def test_a_clean_sync_with_no_rows_still_updates_last_sync_at(self):
        # Zero classes/exams currently scheduled is a legitimate, non-error
        # outcome -- not every "nothing came back" is a failure.
        with mock.patch.object(timetable_sync, "fetch_timetable_html", return_value=("<div></div>", None)):
            timetable_sync.sync_group_timetable(self.profile, self.connection)

        self.connection.refresh_from_db()
        self.assertIsNotNone(self.connection.last_sync_at)
        self.assertEqual(self.connection.status, "connected")

    def test_a_hard_failure_does_not_overwrite_the_last_known_good_timestamp(self):
        known_good = timezone.now() - timedelta(days=3)
        self.connection.last_sync_at = known_good
        self.connection.save(update_fields=["last_sync_at"])

        with mock.patch.object(timetable_sync, "fetch_timetable_html", return_value=(None, "site is down")):
            timetable_sync.sync_group_timetable(self.profile, self.connection)

        self.connection.refresh_from_db()
        self.assertEqual(self.connection.last_sync_at, known_good)
        self.assertEqual(self.connection.status, "error")
