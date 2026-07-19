from django.contrib.auth import get_user_model
from django.urls import reverse

from organizer.models import MoveEvent, ReviewItem

from .helpers import SandboxedPathsTestCase


class UserNavigationTests(SandboxedPathsTestCase):
    def test_admin_link_is_hidden_from_app_navigation(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "/admin/")


class AdminCockpitTests(SandboxedPathsTestCase):
    def test_admin_index_shows_live_operational_data(self):
        user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password",
        )
        self.client.force_login(user)
        profile = self.make_profile(name="University")
        move = MoveEvent.objects.create(
            profile=profile,
            filename="CSC2100 notes.pdf",
            source_path="C:/Downloads/CSC2100 notes.pdf",
            destination_path=str(self.profile_root / "CSC2100 notes.pdf"),
            method="course_code",
            course_code="CSC2100",
            success=True,
        )
        ReviewItem.objects.create(
            profile=profile,
            move_event=move,
            subject_code="CSC2100",
            title="Review CSC2100 notes",
            due_at=move.timestamp,
        )

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Orch system cockpit")
        self.assertContains(response, "Every number below comes from current database rows")
        self.assertContains(response, "CSC2100 notes.pdf")
        self.assertContains(response, "Review CSC2100 notes")
        self.assertContains(response, "File decisions")
