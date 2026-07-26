from unittest import mock

from django.contrib.auth import get_user_model
from django.urls import reverse

from organizer.models import MoveEvent, Profile

from .helpers import SandboxedPathsTestCase


class AdminOperationalContractTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.owner_patch = mock.patch("organizer.core.owner_access.owner_mode_enabled", return_value=True)
        self.owner_patch.start()
        self.addCleanup(self.owner_patch.stop)
        self.user = get_user_model().objects.create_superuser(
            username="owner",
            email="owner@example.com",
            password="OrchOwnerPass2026!",
        )
        self.client.force_login(self.user)

    def test_admin_cockpit_uses_live_database_rows(self):
        profile = self.make_profile(name="Live Profile")
        MoveEvent.objects.create(
            profile=profile,
            filename="live-file.pdf",
            source_path="C:/Downloads/live-file.pdf",
            destination_path=str(self.profile_root / "live-file.pdf"),
            method="course_code",
            course_code="CSC2100",
            success=True,
        )

        response = self.client.get(reverse("admin:index"))

        self.assertContains(response, "live-file.pdf")
        self.assertContains(response, "Live Profile")
        self.assertContains(response, "These numbers come from what Orch has actually done")

    def test_admin_cockpit_does_not_show_fake_seed_data(self):
        response = self.client.get(reverse("admin:index"))
        content = response.content.decode("utf-8").lower()

        forbidden = ["lorem ipsum", "sample data", "fake metric", "placeholder total"]
        for phrase in forbidden:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, content)

    def test_admin_cockpit_exposes_diagnostics_sections(self):
        response = self.client.get(reverse("admin:index"))

        self.assertContains(response, "Folder watcher")
        self.assertContains(response, "Stored app data")
        self.assertContains(response, "Folder access")
        self.assertContains(response, "Integration failures")

    def test_admin_cockpit_exposes_maintenance_actions(self):
        response = self.client.get(reverse("admin:index"))

        self.assertContains(response, "Create backup")
        self.assertContains(response, "Restore backup")
        self.assertContains(response, "Clean up stored app data")
        self.assertContains(response, "Refresh search data")

    def test_admin_only_owner_tools_stay_out_of_user_navigation(self):
        response = self.client.get(reverse("dashboard"))
        content = response.content.decode("utf-8")

        self.assertNotIn("/admin/", content)
        self.assertNotIn("Owner Console", content)
        self.assertNotIn("System Admin", content)
