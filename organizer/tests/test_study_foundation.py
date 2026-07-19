from django.urls import reverse

from organizer.core import study
from organizer.models import (
    CourseConfig,
    FolderImportPlan,
    FolderRule,
    IntegrationConnection,
    LearningDigest,
    MoveEvent,
    ReviewItem,
    SubjectMemory,
    SubjectTheme,
)

from .helpers import SandboxedPathsTestCase


class StudyFoundationTests(SandboxedPathsTestCase):
    def test_subject_memory_and_review_queue_are_seeded_from_profile_activity(self):
        profile = self.make_profile()
        CourseConfig.objects.create(
            profile=profile,
            primary_value="Year 2",
            secondary_value="Semester 1",
            groups=["CSC2100", "BSE2105"],
        )
        event = MoveEvent.objects.create(
            profile=profile,
            filename="CSC2100 arrays.pdf",
            source_path="C:/Downloads/CSC2100 arrays.pdf",
            destination_path=str(self.profile_root / "CSC2100 arrays.pdf"),
            method="course_code",
            course_code="CSC2100",
            success=True,
        )

        foundation = study.ensure_learning_foundation(profile)

        self.assertEqual({m.code for m in foundation["memories"]}, {"BSE2105", "CSC2100"})
        self.assertTrue(foundation["goal"])
        self.assertEqual({r.subject_code for r in foundation["rules"]}, {"BSE2105", "CSC2100"})
        memory = SubjectMemory.objects.get(profile=profile, code="CSC2100")
        self.assertEqual(memory.resource_count, 1)
        self.assertTrue(SubjectTheme.objects.filter(profile=profile, subject_code="CSC2100").exists())

        review = ReviewItem.objects.get(profile=profile, move_event=event)
        self.assertEqual(review.subject_code, "CSC2100")
        self.assertEqual(review.status, "queued")

    def test_weekly_digest_records_metrics(self):
        profile = self.make_profile()
        MoveEvent.objects.create(
            profile=profile,
            filename="notes.pdf",
            method="course_code",
            course_code="CSC2100",
            success=True,
        )

        digest = study.create_weekly_digest(profile)

        self.assertEqual(digest.metrics["files_sorted"], 1)
        self.assertIn("files sorted", digest.content)

    def test_makerere_profiles_get_muele_connection_foundation(self):
        profile = self.make_profile(name="Computer Science - Makerere University")

        connection = study.ensure_makerere_connection(profile)

        self.assertIsNotNone(connection)
        self.assertEqual(connection.provider, "muele")
        self.assertEqual(connection.base_url, study.MUELE_BASE_URL)
        self.assertEqual(connection.status, "planned")

    def test_manual_profile_does_not_get_muele_connection(self):
        profile = self.make_profile(setup_path="manual")

        foundation = study.ensure_learning_foundation(profile)

        self.assertIsNone(foundation["muele_connection"])
        self.assertFalse(IntegrationConnection.objects.filter(profile=profile, provider="muele").exists())

    def test_folder_import_plan_scans_without_changing_files(self):
        root = self.profile_root / "Messy"
        (root / "BIO101").mkdir(parents=True)
        (root / "BIO101" / "cells.pdf").write_text("notes", encoding="utf-8")

        plan = study.create_import_plan(root, profile=self.make_profile())

        self.assertEqual(plan.status, "scanned")
        self.assertIn("BIO101", plan.proposed_subjects)
        self.assertTrue(FolderImportPlan.objects.filter(pk=plan.pk).exists())

    def test_rule_builder_foundation_records_visual_rule(self):
        profile = self.make_profile()

        rule = study.create_rule_from_subject(profile, "BIO101", extensions=["pdf"])

        self.assertEqual(rule.match_field, "filename")
        self.assertEqual(rule.operator, "contains")
        self.assertEqual(rule.pattern, "BIO101")
        self.assertEqual(rule.file_extensions, ["pdf"])
        self.assertEqual(FolderRule.objects.get(pk=rule.pk).subject_code, "BIO101")


class StudyViewsTests(SandboxedPathsTestCase):
    def test_study_page_requires_active_profile_foundation(self):
        response = self.client.get(reverse("study_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No active profile")

    def test_study_page_renders_active_profile_foundation(self):
        profile = self.make_profile()
        CourseConfig.objects.create(
            profile=profile,
            primary_value="Year 2",
            secondary_value="Semester 1",
            groups=["CSC2100"],
        )

        response = self.client.get(reverse("study_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Subject memory")
        self.assertContains(response, "Folder rules")
        self.assertContains(response, "Folder imports")
        self.assertContains(response, "CSC2100")

    def test_create_digest_from_study_page(self):
        profile = self.make_profile()
        MoveEvent.objects.create(profile=profile, filename="notes.pdf", method="media", success=True)

        response = self.client.post(reverse("study_home"), {"action": "create_digest"})

        self.assertRedirects(response, reverse("study_home"))
        self.assertEqual(LearningDigest.objects.filter(profile=profile).count(), 1)

    def test_makerere_wizard_creates_muele_connection(self):
        response = self.client.post(reverse("makerere_wizard"), {
            "college": "College of Computing and Information Sciences",
            "school": "School of Computing and Informatics Technology",
            "program": "Bachelor of Science in Computer Science",
            "year_value": "2",
            "semester_value": "1",
            "root_path": str(self.profile_root),
            "groups": "CSC2100",
        })

        self.assertRedirects(response, reverse("dashboard"))
        connection = IntegrationConnection.objects.get()
        self.assertEqual(connection.provider, "muele")
        self.assertEqual(connection.base_url, study.MUELE_BASE_URL)

    def test_muele_connection_page_saves_metadata_without_secret(self):
        profile = self.make_profile(name="Computer Science - Makerere University")
        study.ensure_makerere_connection(profile)

        response = self.client.post(reverse("muele_connection"), {
            "base_url": study.MUELE_BASE_URL,
            "username": "student@mak.ac.ug",
            "college": "COCIS",
            "sync_targets": ["course_files", "assignments"],
        })

        self.assertRedirects(response, reverse("study_home"))
        connection = IntegrationConnection.objects.get(profile=profile, provider="muele")
        self.assertEqual(connection.username, "student@mak.ac.ug")
        self.assertEqual(connection.token_reference, "")
        self.assertEqual(connection.config["college"], "COCIS")
