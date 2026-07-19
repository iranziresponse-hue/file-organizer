from unittest import mock

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


class OwnerAccessTests(SandboxedPathsTestCase):
    def test_owner_console_is_hidden_when_owner_mode_is_off(self):
        with mock.patch("organizer.core.owner_access.owner_mode_enabled", return_value=False):
            response = self.client.get(reverse("owner_console"), REMOTE_ADDR="127.0.0.1")

        self.assertEqual(response.status_code, 404)

    def test_owner_console_rejects_non_local_requests(self):
        with mock.patch("organizer.core.owner_access.owner_mode_enabled", return_value=True):
            response = self.client.get(reverse("owner_console"), REMOTE_ADDR="10.0.0.12")

        self.assertEqual(response.status_code, 404)

    def test_owner_console_opens_first_owner_setup_when_no_staff_exists(self):
        with mock.patch("organizer.core.owner_access.owner_mode_enabled", return_value=True):
            response = self.client.get(reverse("owner_console"), REMOTE_ADDR="127.0.0.1")

        self.assertRedirects(response, reverse("owner_setup"), fetch_redirect_response=False)

    def test_owner_setup_page_renders_for_local_owner_mode(self):
        with mock.patch("organizer.core.owner_access.owner_mode_enabled", return_value=True):
            response = self.client.get(reverse("owner_setup"), REMOTE_ADDR="127.0.0.1")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create owner access")
        self.assertContains(response, "Local owner mode")

    def test_owner_setup_creates_real_staff_account(self):
        with mock.patch("organizer.core.owner_access.owner_mode_enabled", return_value=True):
            response = self.client.post(
                reverse("owner_setup"),
                {
                    "username": "owner",
                    "email": "owner@example.com",
                    "password": "OrchOwnerPass2026!",
                    "confirm_password": "OrchOwnerPass2026!",
                },
                REMOTE_ADDR="127.0.0.1",
            )

        self.assertRedirects(response, reverse("admin:index"), fetch_redirect_response=False)
        user = get_user_model().objects.get(username="owner")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_owner_console_redirects_to_admin_after_staff_exists(self):
        get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="OrchOwnerPass2026!",
        )

        with mock.patch("organizer.core.owner_access.owner_mode_enabled", return_value=True):
            response = self.client.get(reverse("owner_console"), REMOTE_ADDR="127.0.0.1")

        self.assertRedirects(response, reverse("admin:index"), fetch_redirect_response=False)
