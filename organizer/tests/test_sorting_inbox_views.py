from django.urls import reverse

from organizer.models import MoveEvent, OrganizationMemoryRule, SortDecision

from .helpers import SandboxedPathsTestCase


class SortingInboxPageTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_empty_state_when_no_pending_items(self):
        response = self.client.get(reverse("sorting_inbox"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No pending items")

    def test_pending_item_renders_with_stable_hooks_for_the_ajax_layer(self):
        item = SortDecision.objects.create(
            profile=self.profile,
            filename="BIO101 notes.pdf",
            source_path=str(self.downloads / "BIO101 notes.pdf"),
            suggested_destination=str(self.profile_root / "BIO101"),
            confidence=60,
            status="pending",
        )

        response = self.client.get(reverse("sorting_inbox"))
        content = response.content.decode()

        self.assertContains(response, "BIO101 notes.pdf")
        # Hooks the realtime inbox-actions.js script depends on to find and
        # remove a row, and to sync the stat counters, without a page reload.
        self.assertIn('data-pk="%d"' % item.pk, content)
        self.assertIn('data-inbox-action', content)
        self.assertIn('id="stat-pending"', content)
        self.assertIn('id="pending-count"', content)

    def test_requires_active_profile(self):
        self.profile.is_active = False
        self.profile.save()

        response = self.client.get(reverse("sorting_inbox"))

        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)


class InboxApproveViewTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.source = self.downloads / "BIO101 notes.pdf"
        self.source.parent.mkdir(parents=True, exist_ok=True)
        self.source.write_bytes(b"notes")
        self.destination = self.profile_root / "BIO101"
        self.item = SortDecision.objects.create(
            profile=self.profile,
            filename=self.source.name,
            source_path=str(self.source),
            suggested_destination=str(self.destination),
            confidence=60,
            explanation="Matched rule 'Route biology notes'",
            matched_rule="Route biology notes",
            status="pending",
        )

    def test_approve_moves_file_and_redirects_to_inbox(self):
        response = self.client.post(reverse("inbox_approve", args=[self.item.pk]))

        self.assertRedirects(response, reverse("sorting_inbox"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, "approved")
        self.assertTrue((self.destination / self.source.name).exists())
        self.assertTrue(MoveEvent.objects.filter(profile=self.profile, filename=self.source.name).exists())

    def test_approve_with_remember_creates_an_organization_memory_rule(self):
        response = self.client.post(reverse("inbox_approve", args=[self.item.pk]), {"remember": "1"})

        self.assertRedirects(response, reverse("sorting_inbox"))
        rule = OrganizationMemoryRule.objects.get(profile=self.profile, match_type="extension", match_value="pdf")
        self.assertEqual(rule.times_approved, 1)
        self.assertEqual(rule.destination_path, str(self.destination))

    def test_approve_redirect_response_carries_a_message_with_the_stable_id(self):
        # inbox-actions.js swaps this exact element in on a successful
        # AJAX action, so the id has to actually be there when a message
        # is present (unlike a plain GET with nothing queued).
        response = self.client.post(reverse("inbox_approve", args=[self.item.pk]), follow=True)

        self.assertIn('id="page-messages"', response.content.decode())

    def test_approve_response_no_longer_lists_the_item_as_pending(self):
        # This is exactly what inbox-actions.js checks to decide whether the
        # action actually succeeded server-side.
        response = self.client.post(reverse("inbox_approve", args=[self.item.pk]), follow=True)

        self.assertNotIn('data-pk="%d"' % self.item.pk, response.content.decode())

    def test_ignore_marks_item_rejected_and_leaves_file_in_place(self):
        response = self.client.post(reverse("inbox_ignore", args=[self.item.pk]))

        self.assertRedirects(response, reverse("sorting_inbox"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, "rejected")
        self.assertTrue(self.source.exists())

    def test_ignore_with_never_again_penalizes_the_matching_memory_rule(self):
        OrganizationMemoryRule.objects.create(
            profile=self.profile,
            name="Files ending in .pdf",
            match_type="extension",
            match_value="pdf",
            destination_path=str(self.destination),
        )

        self.client.post(reverse("inbox_ignore", args=[self.item.pk]), {"never_again": "1"})

        rule = OrganizationMemoryRule.objects.get(profile=self.profile, match_type="extension", match_value="pdf")
        self.assertEqual(rule.times_rejected, 1)

    def test_reroute_moves_file_to_the_chosen_destination(self):
        new_destination = self.profile_root / "Custom" / "Folder"

        response = self.client.post(
            reverse("inbox_reroute", args=[self.item.pk]),
            {"new_destination": str(new_destination)},
        )

        self.assertRedirects(response, reverse("sorting_inbox"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, "approved")
        self.assertTrue((new_destination / self.source.name).exists())

    def test_reroute_without_a_destination_leaves_item_pending(self):
        response = self.client.post(reverse("inbox_reroute", args=[self.item.pk]), {"new_destination": ""}, follow=True)

        self.item.refresh_from_db()
        self.assertEqual(self.item.status, "pending")
        # inbox-actions.js relies on this to detect the failure and fall
        # back to a real page reload instead of silently removing the row.
        self.assertIn('data-pk="%d"' % self.item.pk, response.content.decode())

    def test_reroute_outside_trusted_roots_is_rejected_unconfirmed(self):
        outside = self.profile_root.parent / "Somewhere Else Entirely"

        response = self.client.post(
            reverse("inbox_reroute", args=[self.item.pk]),
            {"new_destination": str(outside)},
            follow=True,
        )

        self.item.refresh_from_db()
        self.assertEqual(self.item.status, "pending")
        self.assertFalse(outside.exists())
        self.assertContains(response, "outside your usual Orch folders")

    def test_reroute_outside_trusted_roots_succeeds_once_confirmed(self):
        outside = self.profile_root.parent / "Somewhere Else Entirely"

        response = self.client.post(
            reverse("inbox_reroute", args=[self.item.pk]),
            {"new_destination": str(outside), "confirm_external": "1"},
        )

        self.assertRedirects(response, reverse("sorting_inbox"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, "approved")
        self.assertTrue((outside / self.source.name).exists())
