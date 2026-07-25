"""Every mutation/detail endpoint that fetches a model instance by pk must
scope that lookup to the active profile -- otherwise switching the active
profile and reusing/guessing another profile's object pk lets one profile
act on another's data. One test per view flagged in this sweep: create the
object under `self.owner`, switch the active profile to `self.attacker`,
hit the view with the owner's object pk, and confirm it 404s rather than
silently operating on someone else's row.
"""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from organizer.models import (
    AssignmentItem,
    ContentDraft,
    Flashcard,
    FolderImportPlan,
    GradeTarget,
    IntegrationConnection,
    MoveEvent,
    OrganizationMemoryRule,
    Project,
    ReviewItem,
    SortDecision,
)

from .helpers import SandboxedPathsTestCase


class ProfileIsolationTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.make_profile(name="Owner")
        self.attacker = self.make_profile(name="Attacker", is_active=False)

    def switch_to_attacker(self):
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        self.attacker.is_active = True
        self.attacker.save(update_fields=["is_active"])

    def make_move_event(self, **overrides):
        fields = {
            "profile": self.owner, "filename": "notes.pdf", "source_path": "C:/Downloads/notes.pdf",
            "destination_path": str(self.profile_root / "notes.pdf"), "method": "unsorted",
        }
        fields.update(overrides)
        return MoveEvent.objects.create(**fields)

    # -- MoveEvent --------------------------------------------------------

    def test_move_relocate_is_scoped_to_active_profile(self):
        event = self.make_move_event()
        self.switch_to_attacker()
        response = self.client.post(reverse("move_relocate", args=[event.pk]), {"new_destination": str(self.profile_root)})
        self.assertEqual(response.status_code, 404)

    def test_move_undo_is_scoped_to_active_profile(self):
        event = self.make_move_event()
        self.switch_to_attacker()
        response = self.client.post(reverse("move_undo", args=[event.pk]))
        self.assertEqual(response.status_code, 404)

    def test_move_summarize_is_scoped_to_active_profile(self):
        event = self.make_move_event()
        self.switch_to_attacker()
        response = self.client.post(reverse("move_summarize", args=[event.pk]))
        self.assertEqual(response.status_code, 404)

    def test_move_summary_view_is_scoped_to_active_profile(self):
        event = self.make_move_event()
        self.switch_to_attacker()
        response = self.client.get(reverse("move_summary_view", args=[event.pk]))
        self.assertEqual(response.status_code, 404)

    def test_move_summary_pdf_is_scoped_to_active_profile(self):
        event = self.make_move_event()
        self.switch_to_attacker()
        response = self.client.get(reverse("move_summary_pdf", args=[event.pk]))
        self.assertEqual(response.status_code, 404)

    def test_undo_recent_restore_is_scoped_to_active_profile(self):
        event = self.make_move_event()
        self.switch_to_attacker()
        response = self.client.post(reverse("undo_recent"), {"action": "restore", "move_pk": event.pk})
        self.assertEqual(response.status_code, 404)

    # -- ReviewItem ---------------------------------------------------------

    def make_review_item(self, **overrides):
        fields = {"profile": self.owner, "title": "Revise binary trees", "due_at": timezone.now() + timedelta(days=1)}
        fields.update(overrides)
        return ReviewItem.objects.create(**fields)

    def test_review_mark_done_is_scoped_to_active_profile(self):
        item = self.make_review_item()
        self.switch_to_attacker()
        response = self.client.post(reverse("review_mark_done", args=[item.pk]))
        self.assertEqual(response.status_code, 404)

    def test_review_skip_is_scoped_to_active_profile(self):
        item = self.make_review_item()
        self.switch_to_attacker()
        response = self.client.post(reverse("review_skip", args=[item.pk]))
        self.assertEqual(response.status_code, 404)

    # -- SortDecision -------------------------------------------------------

    def make_sort_decision(self, **overrides):
        fields = {"profile": self.owner, "filename": "notes.pdf", "suggested_destination": str(self.profile_root)}
        fields.update(overrides)
        return SortDecision.objects.create(**fields)

    def test_inbox_approve_is_scoped_to_active_profile(self):
        item = self.make_sort_decision()
        self.switch_to_attacker()
        response = self.client.post(reverse("inbox_approve", args=[item.pk]))
        self.assertEqual(response.status_code, 404)

    def test_inbox_reroute_is_scoped_to_active_profile(self):
        item = self.make_sort_decision()
        self.switch_to_attacker()
        response = self.client.post(reverse("inbox_reroute", args=[item.pk]), {"new_destination": str(self.profile_root)})
        self.assertEqual(response.status_code, 404)

    def test_inbox_ignore_is_scoped_to_active_profile(self):
        item = self.make_sort_decision()
        self.switch_to_attacker()
        response = self.client.post(reverse("inbox_ignore", args=[item.pk]))
        self.assertEqual(response.status_code, 404)

    # -- OrganizationMemoryRule ----------------------------------------------

    def test_organization_memory_rule_update_is_scoped_to_active_profile(self):
        rule = OrganizationMemoryRule.objects.create(
            profile=self.owner, name="PDFs to CSC2100", match_value=".pdf", destination_path=str(self.profile_root),
        )
        self.switch_to_attacker()
        response = self.client.post(reverse("organization_memory_rule_update", args=[rule.pk]), {"action": "toggle"})
        self.assertEqual(response.status_code, 404)

    def test_organization_memory_rule_delete_is_scoped_to_active_profile(self):
        rule = OrganizationMemoryRule.objects.create(
            profile=self.owner, name="PDFs to CSC2100", match_value=".pdf", destination_path=str(self.profile_root),
        )
        self.switch_to_attacker()
        response = self.client.post(reverse("organization_memory_rule_delete", args=[rule.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(OrganizationMemoryRule.objects.filter(pk=rule.pk).exists())

    # -- FolderImportPlan -----------------------------------------------------

    def test_import_plans_approve_is_scoped_to_active_profile(self):
        plan = FolderImportPlan.objects.create(profile=self.owner, root_path=str(self.profile_root))
        self.switch_to_attacker()
        response = self.client.post(reverse("import_plans"), {"action": "approve", "plan_pk": plan.pk})
        self.assertEqual(response.status_code, 404)

    # -- AssignmentItem -------------------------------------------------------

    def make_assignment(self, **overrides):
        fields = {"profile": self.owner, "title": "Lab report"}
        fields.update(overrides)
        return AssignmentItem.objects.create(**fields)

    def test_assignment_tracker_item_update_is_scoped_to_active_profile(self):
        item = self.make_assignment()
        self.switch_to_attacker()
        response = self.client.post(reverse("assignment_tracker_item_update", args=[item.pk]), {"title": "Hijacked"})
        self.assertEqual(response.status_code, 404)

    def test_assignment_tracker_item_delete_is_scoped_to_active_profile(self):
        item = self.make_assignment()
        self.switch_to_attacker()
        response = self.client.post(reverse("assignment_tracker_item_delete", args=[item.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(AssignmentItem.objects.filter(pk=item.pk).exists())

    # -- GradeTarget ----------------------------------------------------------

    def test_grade_target_delete_is_scoped_to_active_profile(self):
        target = GradeTarget.objects.create(profile=self.owner, subject_code="CSC2100")
        self.switch_to_attacker()
        response = self.client.post(reverse("grade_target_delete", args=[target.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(GradeTarget.objects.filter(pk=target.pk).exists())

    # -- Flashcard --------------------------------------------------------------

    def make_flashcard(self, **overrides):
        fields = {"profile": self.owner, "card_type": "manual", "front": "What is a stack?"}
        fields.update(overrides)
        return Flashcard.objects.create(**fields)

    def test_flashcard_grade_is_scoped_to_active_profile(self):
        card = self.make_flashcard()
        self.switch_to_attacker()
        response = self.client.post(reverse("flashcard_grade", args=[card.pk]), {"remembered": "1"})
        self.assertEqual(response.status_code, 404)

    def test_flashcard_delete_is_scoped_to_active_profile(self):
        card = self.make_flashcard()
        self.switch_to_attacker()
        response = self.client.post(reverse("flashcard_delete", args=[card.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Flashcard.objects.filter(pk=card.pk).exists())

    # -- Project ------------------------------------------------------------------

    def test_project_delete_is_scoped_to_active_profile(self):
        project = Project.objects.create(profile=self.owner, title="Orch")
        self.switch_to_attacker()
        response = self.client.post(reverse("project_delete", args=[project.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Project.objects.filter(pk=project.pk).exists())

    def test_project_generate_draft_is_scoped_to_active_profile(self):
        project = Project.objects.create(profile=self.owner, title="Orch")
        self.switch_to_attacker()
        response = self.client.post(reverse("project_generate_draft", args=[project.pk]))
        self.assertEqual(response.status_code, 404)

    # -- ContentDraft ---------------------------------------------------------------

    def make_draft(self, **overrides):
        fields = {"profile": self.owner, "raw_text": "Shipped a feature."}
        fields.update(overrides)
        return ContentDraft.objects.create(**fields)

    def test_content_draft_polish_is_scoped_to_active_profile(self):
        draft = self.make_draft()
        self.switch_to_attacker()
        response = self.client.post(reverse("content_draft_polish", args=[draft.pk]), {"style": "polished"})
        self.assertEqual(response.status_code, 404)

    def test_content_draft_approve_is_scoped_to_active_profile(self):
        draft = self.make_draft()
        self.switch_to_attacker()
        response = self.client.post(reverse("content_draft_approve", args=[draft.pk]))
        self.assertEqual(response.status_code, 404)
        draft.refresh_from_db()
        self.assertEqual(draft.status, "draft")

    def test_content_draft_mark_posted_is_scoped_to_active_profile(self):
        draft = self.make_draft()
        self.switch_to_attacker()
        response = self.client.post(reverse("content_draft_mark_posted", args=[draft.pk]))
        self.assertEqual(response.status_code, 404)

    def test_content_draft_delete_is_scoped_to_active_profile(self):
        draft = self.make_draft()
        self.switch_to_attacker()
        response = self.client.post(reverse("content_draft_delete", args=[draft.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(ContentDraft.objects.filter(pk=draft.pk).exists())

    def test_content_draft_export_markdown_is_scoped_to_active_profile(self):
        draft = self.make_draft()
        self.switch_to_attacker()
        response = self.client.get(reverse("content_draft_export_markdown", args=[draft.pk]))
        self.assertEqual(response.status_code, 404)

    def test_content_draft_export_html_is_scoped_to_active_profile(self):
        draft = self.make_draft()
        self.switch_to_attacker()
        response = self.client.get(reverse("content_draft_export_html", args=[draft.pk]))
        self.assertEqual(response.status_code, 404)

    # -- IntegrationConnection / publishing --------------------------------------------

    def make_channel(self, **overrides):
        fields = {
            "profile": self.owner, "provider": "custom_website", "display_name": "My Blog",
            "base_url": "https://example.com/api/posts", "status": "connected",
        }
        fields.update(overrides)
        return IntegrationConnection.objects.create(**fields)

    def test_publishing_channel_delete_is_scoped_to_active_profile(self):
        channel = self.make_channel()
        self.switch_to_attacker()
        response = self.client.post(reverse("publishing_channel_delete", args=[channel.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(IntegrationConnection.objects.filter(pk=channel.pk).exists())

    def test_content_draft_publish_is_scoped_to_active_profile(self):
        draft = self.make_draft(status="approved")
        channel = self.make_channel()
        self.switch_to_attacker()
        response = self.client.post(reverse("content_draft_publish", args=[draft.pk, channel.pk]))
        self.assertEqual(response.status_code, 404)

    def test_content_draft_publish_rejects_a_channel_from_another_profile(self):
        """Even when the draft belongs to the active profile, a channel
        pk borrowed from another profile must not be usable to publish it."""
        draft = self.make_draft(status="approved")
        other_channel = self.make_channel()  # owned by self.owner
        self.attacker_draft = self.make_draft(profile=self.attacker, status="approved")
        self.switch_to_attacker()

        response = self.client.post(reverse("content_draft_publish", args=[self.attacker_draft.pk, other_channel.pk]))

        self.assertEqual(response.status_code, 404)
