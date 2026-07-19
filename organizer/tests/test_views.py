import json

from django.urls import reverse

from organizer.core import paths
from organizer.models import CourseConfig, MoveEvent, Profile

from .helpers import SandboxedPathsTestCase


class DashboardViewTests(SandboxedPathsTestCase):
    def test_no_profiles_at_all_prompts_the_wizard(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["has_any_profile"])
        self.assertContains(response, "Create your first profile")

    def test_profiles_exist_but_none_active_prompts_a_choice(self):
        self.make_profile(is_active=False)
        response = self.client.get(reverse("dashboard"))
        self.assertTrue(response.context["has_any_profile"])
        self.assertIsNone(response.context["profile"])
        self.assertContains(response, "Choose a profile")

    def test_shows_recent_moves_and_stats_for_the_active_profile(self):
        profile = self.make_profile()
        other = self.make_profile(name="Other", root_path=str(self.profile_root) + "2", is_active=False)

        MoveEvent.objects.create(
            filename="notes.pdf",
            source_path="C:/Downloads/notes.pdf",
            destination_path=str(self.profile_root / "notes.pdf"),
            method="course_code",
            course_code="CSC2100",
            success=True,
            profile=profile,
        )
        MoveEvent.objects.create(
            filename="other-notes.pdf",
            method="course_code",
            course_code="ZZZ",
            success=True,
            profile=other,
        )

        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, "notes.pdf")
        self.assertNotContains(response, "other-notes.pdf")
        self.assertEqual(response.context["total_moves"], 1)
        self.assertEqual(response.context["method_counts"][0]["method"], "course_code")
        self.assertEqual(response.context["course_counts"][0]["course_code"], "CSC2100")


class ProfilesListViewTests(SandboxedPathsTestCase):
    def test_empty_state(self):
        response = self.client.get(reverse("profiles_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No profiles yet")

    def test_lists_existing_profiles(self):
        self.make_profile(name="University")
        response = self.client.get(reverse("profiles_list"))
        self.assertContains(response, "University")


class ProfileWizardViewTests(SandboxedPathsTestCase):
    def test_get_renders_form(self):
        response = self.client.get(reverse("profile_wizard"))
        self.assertEqual(response.status_code, 200)

    def test_creates_an_active_profile_with_config_and_json_file(self):
        response = self.client.post(reverse("profile_wizard"), {
            "name": "University",
            "purpose": "school",
            "primary_label": "Year",
            "secondary_label": "Semester",
            "root_path": str(self.profile_root),
            "primary_value": "Year 2",
            "secondary_value": "Semester 1",
            "groups": "CSC2100, BSE2105",
        })

        self.assertRedirects(response, reverse("dashboard"))

        profile = Profile.objects.get(name="University")
        self.assertTrue(profile.is_active)
        self.assertEqual(profile.setup_path, "manual")
        self.assertEqual(profile.root_path, str(self.profile_root))

        config = CourseConfig.objects.get(profile=profile)
        self.assertEqual(config.groups, ["CSC2100", "BSE2105"])

        written = json.loads(paths.config_path(profile.root_path).read_text())
        self.assertEqual(written["groups"], ["CSC2100", "BSE2105"])

    def test_creating_a_second_profile_deactivates_the_first(self):
        first = self.make_profile(name="School")

        self.client.post(reverse("profile_wizard"), {
            "name": "Online",
            "purpose": "online",
            "primary_label": "Year",
            "secondary_label": "Course",
            "root_path": str(self.profile_root) + "-online",
            "primary_value": "2026",
            "secondary_value": "Python Bootcamp",
            "groups": "",
        })

        first.refresh_from_db()
        self.assertFalse(first.is_active)
        self.assertTrue(Profile.objects.get(name="Online").is_active)

    def test_missing_required_fields_reshows_the_form(self):
        response = self.client.post(reverse("profile_wizard"), {"name": "", "root_path": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Profile.objects.count(), 0)


class ProfileEditViewTests(SandboxedPathsTestCase):
    def test_updates_profile_and_config(self):
        profile = self.make_profile()

        response = self.client.post(reverse("profile_edit", args=[profile.pk]), {
            "name": "University (updated)",
            "primary_label": "Year",
            "secondary_label": "Semester",
            "root_path": str(self.profile_root),
            "primary_value": "Year 3",
            "secondary_value": "Semester 2",
            "groups": "CSC3100",
        })

        self.assertRedirects(response, reverse("profile_edit", args=[profile.pk]))

        profile.refresh_from_db()
        self.assertEqual(profile.name, "University (updated)")
        self.assertFalse(profile.ai_fallback_enabled)

        config = CourseConfig.objects.get(profile=profile)
        self.assertEqual(config.primary_value, "Year 3")
        self.assertEqual(config.groups, ["CSC3100"])

    def test_ai_fallback_checkbox_round_trips(self):
        profile = self.make_profile()

        self.client.post(reverse("profile_edit", args=[profile.pk]), {
            "name": profile.name,
            "primary_label": profile.primary_label,
            "secondary_label": profile.secondary_label,
            "root_path": profile.root_path,
            "primary_value": "Year 2",
            "secondary_value": "Semester 1",
            "groups": "",
            "ai_fallback_enabled": "on",
        })

        profile.refresh_from_db()
        self.assertTrue(profile.ai_fallback_enabled)


class ProfileActivateDeleteViewTests(SandboxedPathsTestCase):
    def test_activate_switches_active_profile(self):
        first = self.make_profile(name="School")
        second = self.make_profile(name="Online", root_path=str(self.profile_root) + "2", is_active=False)

        self.client.post(reverse("profile_activate", args=[second.pk]))

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_active)
        self.assertTrue(second.is_active)

    def test_delete_removes_the_profile(self):
        profile = self.make_profile()
        self.client.post(reverse("profile_delete", args=[profile.pk]))
        self.assertFalse(Profile.objects.filter(pk=profile.pk).exists())

    def test_get_does_not_delete(self):
        profile = self.make_profile()
        self.client.get(reverse("profile_delete", args=[profile.pk]))
        self.assertTrue(Profile.objects.filter(pk=profile.pk).exists())
