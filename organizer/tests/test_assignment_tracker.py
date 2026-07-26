from django.urls import reverse
from django.utils import timezone

from organizer.models import AssignmentItem

from .helpers import SandboxedPathsTestCase


class AssignmentTrackerPageTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_requires_active_profile(self):
        self.profile.is_active = False
        self.profile.save()

        response = self.client.get(reverse("assignment_tracker"))

        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_empty_state(self):
        response = self.client.get(reverse("assignment_tracker"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nothing here")

    def test_creates_a_manual_assignment_with_a_checklist(self):
        response = self.client.post(reverse("assignment_tracker"), {
            "title": "CSC2100 Assignment 2",
            "subject_code": "CSC2100",
            "due_at": "",
            "notes": "Covers hashing",
            "checklist_text": "Read the brief\n[x] Draft outline\nWrite and review",
        })

        self.assertRedirects(response, reverse("assignment_tracker"))
        item = AssignmentItem.objects.get(profile=self.profile)
        self.assertEqual(item.title, "CSC2100 Assignment 2")
        self.assertEqual(item.subject_code, "CSC2100")
        self.assertEqual(item.source, "manual")
        self.assertEqual(len(item.checklist), 3)
        self.assertFalse(item.checklist[0]["done"])
        self.assertTrue(item.checklist[1]["done"])
        self.assertEqual(item.checklist[1]["text"], "Draft outline")

    def test_blank_title_is_rejected(self):
        response = self.client.post(reverse("assignment_tracker"), {"title": "", "checklist_text": ""})

        self.assertRedirects(response, reverse("assignment_tracker"))
        self.assertEqual(AssignmentItem.objects.count(), 0)

    def test_grouped_by_status_in_the_response(self):
        AssignmentItem.objects.create(profile=self.profile, title="Open one", status="open")
        AssignmentItem.objects.create(profile=self.profile, title="Submitted one", status="submitted")

        response = self.client.get(reverse("assignment_tracker"))

        self.assertContains(response, "Open one")
        self.assertContains(response, "Submitted one")
        self.assertEqual(response.context["open_count"], 1)


class AssignmentTrackerItemUpdateTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.item = AssignmentItem.objects.create(
            profile=self.profile,
            title="Lab report",
            subject_code="BIO101",
            status="open",
            checklist=[{"text": "Draft", "done": False}, {"text": "Submit", "done": False}],
        )

    def test_toggle_checklist_item_flips_done(self):
        self.client.post(reverse("assignment_tracker_item_update", args=[self.item.pk]), {
            "action": "toggle_checklist_item",
            "index": "0",
        })

        self.item.refresh_from_db()
        self.assertTrue(self.item.checklist[0]["done"])
        self.assertFalse(self.item.checklist[1]["done"])

    def test_mark_submitted_changes_status(self):
        self.client.post(reverse("assignment_tracker_item_update", args=[self.item.pk]), {
            "action": "mark_submitted",
        })

        self.item.refresh_from_db()
        self.assertEqual(self.item.status, "submitted")

    def test_full_update_saves_evidence_and_checklist(self):
        self.client.post(reverse("assignment_tracker_item_update", args=[self.item.pk]), {
            "action": "update",
            "title": "Lab report v2",
            "subject_code": "BIO101",
            "status": "open",
            "notes": "Rubric: 40% analysis",
            "evidence_path": "C:/Users/me/Documents/lab-draft.docx",
            "checklist_text": "[x] Draft\n[x] Submit",
        })

        self.item.refresh_from_db()
        self.assertEqual(self.item.title, "Lab report v2")
        self.assertEqual(self.item.evidence_path, "C:/Users/me/Documents/lab-draft.docx")
        self.assertEqual(self.item.draft_status, "ready")

    def test_checklist_progress_and_draft_status_derive_correctly(self):
        self.assertEqual(self.item.checklist_progress, (0, 2))
        self.assertEqual(self.item.draft_status, "not_started")

        self.item.checklist[0]["done"] = True
        self.item.save()
        self.assertEqual(self.item.checklist_progress, (1, 2))
        self.assertEqual(self.item.draft_status, "in_progress")

    def test_delete_removes_the_assignment(self):
        self.client.post(reverse("assignment_tracker_item_delete", args=[self.item.pk]))

        self.assertFalse(AssignmentItem.objects.filter(pk=self.item.pk).exists())


class AssignmentTrackerArchiveMissedTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_archives_only_missed_assignments(self):
        missed = AssignmentItem.objects.create(profile=self.profile, title="Late one", status="missed")
        open_item = AssignmentItem.objects.create(profile=self.profile, title="Still open", status="open")

        response = self.client.post(reverse("assignment_tracker_archive_missed"))

        self.assertRedirects(response, reverse("assignment_tracker"))
        missed.refresh_from_db()
        open_item.refresh_from_db()
        self.assertEqual(missed.status, "archived")
        self.assertEqual(open_item.status, "open")

    def test_get_is_not_allowed(self):
        response = self.client.get(reverse("assignment_tracker_archive_missed"))
        self.assertEqual(response.status_code, 405)
