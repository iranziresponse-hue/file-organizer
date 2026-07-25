from django.urls import reverse

from organizer.models import MoveEvent, OrganizationMemoryRule, SortDecision

from .helpers import SandboxedPathsTestCase


class OrganizationMemoryPageTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_empty_state_when_nothing_learned_yet(self):
        response = self.client.get(reverse("organization_memory"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nothing learned yet")

    def test_learned_rule_is_listed(self):
        OrganizationMemoryRule.objects.create(
            profile=self.profile,
            name="Files ending in .zip",
            match_type="extension",
            match_value="zip",
            destination_path=str(self.personal_root / "Archives"),
            times_approved=3,
        )

        response = self.client.get(reverse("organization_memory"))

        self.assertContains(response, "Files ending in .zip")
        self.assertContains(response, "3")

    def test_toggle_disables_an_enabled_rule(self):
        rule = OrganizationMemoryRule.objects.create(
            profile=self.profile,
            name="Files ending in .zip",
            match_type="extension",
            match_value="zip",
            destination_path=str(self.personal_root / "Archives"),
        )

        self.client.post(reverse("organization_memory_rule_update", args=[rule.pk]), {"action": "toggle"})

        rule.refresh_from_db()
        self.assertFalse(rule.enabled)

    def test_reset_clears_learning_counters(self):
        rule = OrganizationMemoryRule.objects.create(
            profile=self.profile,
            name="Files ending in .zip",
            match_type="extension",
            match_value="zip",
            destination_path=str(self.personal_root / "Archives"),
            times_approved=5,
            times_rejected=2,
        )

        self.client.post(reverse("organization_memory_rule_update", args=[rule.pk]), {"action": "reset"})

        rule.refresh_from_db()
        self.assertEqual(rule.times_approved, 0)
        self.assertEqual(rule.times_rejected, 0)

    def test_delete_removes_the_rule(self):
        rule = OrganizationMemoryRule.objects.create(
            profile=self.profile,
            name="Files ending in .zip",
            match_type="extension",
            match_value="zip",
            destination_path=str(self.personal_root / "Archives"),
        )

        self.client.post(reverse("organization_memory_rule_delete", args=[rule.pk]))

        self.assertFalse(OrganizationMemoryRule.objects.filter(pk=rule.pk).exists())


class OrganizationDNAPageTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_empty_state_when_no_activity(self):
        response = self.client.get(reverse("organization_dna"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No activity yet")

    def test_reports_top_folders_and_extensions_from_move_events(self):
        dest_dir = self.profile_root / "CSC2100" / "Notes"
        MoveEvent.objects.create(
            profile=self.profile,
            filename="week1.pdf",
            source_path=str(self.downloads / "week1.pdf"),
            destination_path=str(dest_dir / "week1.pdf"),
            method="course_code",
            course_code="CSC2100",
            success=True,
        )
        MoveEvent.objects.create(
            profile=self.profile,
            filename="week2.pdf",
            source_path=str(self.downloads / "week2.pdf"),
            destination_path=str(dest_dir / "week2.pdf"),
            method="course_code",
            course_code="CSC2100",
            success=True,
        )

        response = self.client.get(reverse("organization_dna"))

        self.assertContains(response, str(dest_dir))
        self.assertContains(response, ".pdf")
        self.assertContains(response, "CSC2100")

    def test_pending_and_sensitive_counts_come_from_sort_decisions(self):
        SortDecision.objects.create(
            profile=self.profile, filename="secret.pem", decision_type="held_sensitive", status="pending",
        )
        SortDecision.objects.create(
            profile=self.profile, filename="photo.png", decision_type="global_suggested", status="pending",
        )

        response = self.client.get(reverse("organization_dna"))

        self.assertEqual(response.context["stats"]["pending_review"], 2)
        self.assertEqual(response.context["stats"]["held_sensitive"], 1)
