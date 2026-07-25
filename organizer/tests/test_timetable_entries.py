from datetime import date
from unittest import mock

from django.urls import reverse

from organizer.core import timetable_sync
from organizer.models import IntegrationConnection, TimetableEntry

from .helpers import SandboxedPathsTestCase


class TimetableEntryCreateViewTests(SandboxedPathsTestCase):
    def test_get_is_not_allowed(self):
        response = self.client.get(reverse("timetable_entry_create"))
        self.assertEqual(response.status_code, 405)

    def test_without_an_active_profile_redirects_without_creating(self):
        response = self.client.post(reverse("timetable_entry_create"), {
            "kind": "test", "start_time": "09:00", "specific_date": "2026-08-01",
        })
        self.assertRedirects(response, reverse("dashboard"))
        self.assertFalse(TimetableEntry.objects.exists())

    def test_creates_a_manual_entry_with_a_specific_date(self):
        self.make_profile()

        response = self.client.post(reverse("timetable_entry_create"), {
            "kind": "examination",
            "specific_date": "2026-08-01",
            "start_time": "09:00",
            "end_time": "12:00",
            "course_code": "CSC 2100",
            "course_name": "Data Structures",
            "room": "MSB 1",
        })

        self.assertRedirects(response, reverse("timetable_view"))
        entry = TimetableEntry.objects.get()
        self.assertEqual(entry.source, "manual")
        self.assertIsNone(entry.connection)
        self.assertEqual(entry.kind, "examination")
        self.assertEqual(entry.specific_date, date(2026, 8, 1))
        self.assertEqual(entry.course_code, "CSC 2100")

    def test_creates_a_manual_entry_with_a_weekday(self):
        self.make_profile()

        response = self.client.post(reverse("timetable_entry_create"), {
            "kind": "teaching", "weekday": "2", "start_time": "08:00",
        })

        self.assertRedirects(response, reverse("timetable_view"))
        entry = TimetableEntry.objects.get()
        self.assertEqual(entry.weekday, 2)
        self.assertIsNone(entry.specific_date)

    def test_rejects_an_entry_with_neither_weekday_nor_date(self):
        self.make_profile()

        response = self.client.post(reverse("timetable_entry_create"), {
            "kind": "teaching", "start_time": "08:00",
        })

        self.assertRedirects(response, reverse("timetable_view"))
        self.assertFalse(TimetableEntry.objects.exists())

    def test_rejects_an_invalid_kind(self):
        self.make_profile()

        response = self.client.post(reverse("timetable_entry_create"), {
            "kind": "not-a-real-kind", "start_time": "08:00", "weekday": "0",
        })

        self.assertRedirects(response, reverse("timetable_view"))
        self.assertFalse(TimetableEntry.objects.exists())


class TimetableEntryDeleteViewTests(SandboxedPathsTestCase):
    def test_get_is_not_allowed(self):
        profile = self.make_profile()
        entry = TimetableEntry.objects.create(
            profile=profile, source="manual", kind="test", weekday=0,
            start_time="09:00", raw_group="",
        )
        response = self.client.get(reverse("timetable_entry_delete", args=[entry.pk]))
        self.assertEqual(response.status_code, 405)

    def test_deletes_a_manual_entry(self):
        profile = self.make_profile()
        entry = TimetableEntry.objects.create(
            profile=profile, source="manual", kind="test", weekday=0,
            start_time="09:00", raw_group="",
        )

        response = self.client.post(reverse("timetable_entry_delete", args=[entry.pk]))

        self.assertRedirects(response, reverse("timetable_view"))
        self.assertFalse(TimetableEntry.objects.filter(pk=entry.pk).exists())

    def test_refuses_to_delete_a_synced_entry(self):
        profile = self.make_profile()
        connection = IntegrationConnection.objects.create(
            profile=profile, provider="mak_timetable", display_name="Makerere Timetable",
        )
        entry = TimetableEntry.objects.create(
            profile=profile, connection=connection, source="synced", kind="teaching",
            weekday=0, start_time="09:00", raw_group="SE-2",
        )

        response = self.client.post(reverse("timetable_entry_delete", args=[entry.pk]))

        self.assertRedirects(response, reverse("timetable_view"))
        self.assertTrue(TimetableEntry.objects.filter(pk=entry.pk).exists())

    def test_cannot_delete_another_profiles_entry(self):
        profile = self.make_profile()
        other = self.make_profile(name="Other", is_active=False)
        entry = TimetableEntry.objects.create(
            profile=other, source="manual", kind="test", weekday=0,
            start_time="09:00", raw_group="",
        )

        response = self.client.post(reverse("timetable_entry_delete", args=[entry.pk]))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(TimetableEntry.objects.filter(pk=entry.pk).exists())


class ManualEntriesSurviveSyncTests(SandboxedPathsTestCase):
    @mock.patch.object(timetable_sync, "fetch_timetable_html")
    def test_a_full_replace_sync_never_touches_manual_entries(self, mock_fetch):
        profile = self.make_profile()
        connection = IntegrationConnection.objects.create(
            profile=profile, provider="mak_timetable", display_name="Makerere Timetable",
            config={
                "academic_year_id": "1", "academic_year_label": "2025/2026",
                "semester_id": "1", "college": "COCIS", "group": "SE-2",
            },
        )
        manual = TimetableEntry.objects.create(
            profile=profile, source="manual", kind="teaching", weekday=0,
            start_time="08:00", raw_group="",
        )
        mock_fetch.return_value = ("<div id='content-wrapper'></div>", None)

        timetable_sync.sync_group_timetable(profile, connection)

        manual.refresh_from_db()
        self.assertEqual(manual.source, "manual")
