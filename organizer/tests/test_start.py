import json

from django.urls import reverse

from organizer.core import paths
from organizer.models import CourseConfig, Profile

from .helpers import SandboxedPathsTestCase


class StartViewTests(SandboxedPathsTestCase):
    def test_offers_both_paths(self):
        response = self.client.get(reverse("start"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Makerere")
        self.assertContains(response, reverse("makerere_wizard"))
        self.assertContains(response, reverse("profile_wizard"))

    def test_mentions_setting_the_default_download_folder(self):
        response = self.client.get(reverse("start"))
        self.assertContains(response, "Chrome")
        self.assertContains(response, "WhatsApp")


class MakerereWizardViewTests(SandboxedPathsTestCase):
    def test_get_renders_form(self):
        response = self.client.get(reverse("makerere_wizard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "College of Computing and Information Sciences")

    def test_creates_an_active_profile_with_config_and_json_file(self):
        response = self.client.post(reverse("makerere_wizard"), {
            "college": "College of Computing and Information Sciences",
            "school": "School of Computing and Informatics Technology",
            "program": "Bachelor of Science in Computer Science",
            "year_value": "2",
            "semester_value": "1",
            "root_path": str(self.profile_root),
            "groups": "CSC2100, BIT2202",
        })

        self.assertRedirects(response, reverse("dashboard"))

        profile = Profile.objects.get()
        self.assertTrue(profile.is_active)
        self.assertIn("Bachelor of Science in Computer Science", profile.name)
        self.assertIn("COCIS", profile.name)
        self.assertEqual(profile.primary_label, "Year")
        self.assertEqual(profile.secondary_label, "Semester")

        config = CourseConfig.objects.get(profile=profile)
        self.assertEqual(config.primary_value, "Year 2")
        self.assertEqual(config.secondary_value, "Semester 1")
        self.assertEqual(config.groups, ["CSC2100", "BIT2202"])

        written = json.loads(paths.config_path(profile.root_path).read_text())
        self.assertEqual(written["groups"], ["CSC2100", "BIT2202"])

    def test_program_not_in_the_verified_list_is_still_accepted(self):
        # The wizard must accept a typed program even when it isn't one
        # Orch has a verified list for -- honesty about what's verified
        # doesn't mean blocking students whose program isn't in it yet.
        response = self.client.post(reverse("makerere_wizard"), {
            "college": "College of Computing and Information Sciences",
            "school": "School of Computing and Informatics Technology",
            "program": "Some Brand New Program Not Yet Listed",
            "year_value": "1",
            "semester_value": "1",
            "root_path": str(self.profile_root),
            "groups": "",
        })

        self.assertRedirects(response, reverse("dashboard"))
        self.assertIn("Some Brand New Program Not Yet Listed", Profile.objects.get().name)

    def test_unknown_college_is_rejected(self):
        response = self.client.post(reverse("makerere_wizard"), {
            "college": "Not A Real College",
            "school": "Whatever",
            "program": "Whatever",
            "year_value": "1",
            "semester_value": "1",
            "root_path": str(self.profile_root),
            "groups": "",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Profile.objects.count(), 0)

    def test_missing_required_field_is_rejected(self):
        response = self.client.post(reverse("makerere_wizard"), {
            "college": "College of Computing and Information Sciences",
            "school": "",
            "program": "",
            "year_value": "",
            "semester_value": "",
            "root_path": "",
            "groups": "",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Profile.objects.count(), 0)
