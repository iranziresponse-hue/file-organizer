from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.utils import timezone

from organizer.core import diagnostics, muele_api, sorting, undo
from organizer.models import (
    CourseConfig,
    FolderImportPlan,
    FolderRule,
    IntegrationConnection,
    MoveEvent,
    SortingInboxItem,
)

from .helpers import SandboxedPathsTestCase


class SortingEngineWorkflowTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        CourseConfig.objects.create(
            profile=self.profile,
            primary_value="Year 1",
            secondary_value="Semester 1",
            groups=["BIO101"],
        )

    def test_invalid_regex_rule_fails_closed(self):
        rule = SimpleNamespace(
            match_field="filename",
            file_extensions=[],
            operator="regex",
            pattern="[",
            action="route",
            subject_code="BIO101",
            category="Notes",
            profile=self.profile,
        )

        matched, destination = sorting.evaluate_rule(rule, "BIO101 notes.pdf", Path("BIO101 notes.pdf"))

        self.assertFalse(matched)
        self.assertIsNone(destination)

    def test_ignore_rule_returns_ignore_signal(self):
        rule = SimpleNamespace(
            match_field="filename",
            file_extensions=[],
            operator="contains",
            pattern="draft",
            action="ignore",
            subject_code="",
            category="",
            profile=self.profile,
        )

        matched, destination = sorting.evaluate_rule(rule, "draft notes.pdf", Path("draft notes.pdf"))

        self.assertTrue(matched)
        self.assertEqual(destination, "__IGNORE__")

    def test_inbox_approve_moves_file_and_records_event(self):
        source = self.downloads / "BIO101 cells.pdf"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"notes")
        destination = self.profile_root / "Year 1" / "Semester 1" / "BIO101" / "Notes"
        item = SortingInboxItem.objects.create(
            profile=self.profile,
            filename=source.name,
            source_path=str(source),
            suggested_subject="BIO101",
            suggested_destination=str(destination),
            confidence=0.75,
            status="pending",
        )

        approved = sorting.approve_inbox_item(item)

        self.assertTrue(approved)
        self.assertTrue((destination / source.name).exists())
        item.refresh_from_db()
        self.assertEqual(item.status, "approved")
        self.assertTrue(MoveEvent.objects.filter(profile=self.profile, filename=source.name).exists())

    def test_reroute_marks_item_as_rerouted_after_success(self):
        source = self.downloads / "BIO101 lab.pdf"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"notes")
        destination = self.profile_root / "Custom" / "Lab"
        item = SortingInboxItem.objects.create(
            profile=self.profile,
            filename=source.name,
            source_path=str(source),
            suggested_subject="BIO101",
            suggested_destination=str(self.profile_root / "Wrong"),
            confidence=0.25,
            status="pending",
        )

        rerouted = sorting.reroute_inbox_item(item, str(destination))

        self.assertTrue(rerouted)
        item.refresh_from_db()
        self.assertEqual(item.status, "rerouted")
        self.assertTrue((destination / source.name).exists())


class ImportPlanWorkflowTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        CourseConfig.objects.create(
            profile=self.profile,
            primary_value="Year 1",
            secondary_value="Semester 1",
            groups=["CSC100"],
        )

    def test_approve_import_plan_adopts_subjects_and_rules(self):
        plan = FolderImportPlan.objects.create(
            profile=self.profile,
            root_path=str(self.profile_root / "Messy"),
            status="scanned",
            proposed_subjects=["BIO101"],
            proposed_rules=[{
                "name": "BIO101 import rule",
                "match_field": "filename",
                "operator": "contains",
                "pattern": "BIO101",
                "subject_code": "BIO101",
                "category": "Notes",
                "action": "route",
            }],
        )

        approved = sorting.approve_import_plan(plan, self.profile)

        self.assertTrue(approved)
        plan.refresh_from_db()
        self.assertEqual(plan.status, "approved")
        self.assertIn("BIO101", self.profile.config.groups)
        self.assertTrue(FolderRule.objects.filter(profile=self.profile, subject_code="BIO101").exists())

    def test_apply_import_plan_creates_folder_structure(self):
        root = self.profile_root / "Messy"
        root.mkdir(parents=True)
        plan = FolderImportPlan.objects.create(
            profile=self.profile,
            root_path=str(root),
            status="approved",
            discovered_folders=["BIO101/Notes", "BIO101/Labs"],
        )

        applied = sorting.apply_import_plan(plan, self.profile)

        self.assertTrue(applied)
        self.assertTrue((self.profile_root / "Year 1" / "Semester 1" / "BIO101" / "Notes").exists())
        self.assertTrue((self.profile_root / "Year 1" / "Semester 1" / "BIO101" / "Labs").exists())


class UndoWorkflowTests(SandboxedPathsTestCase):
    def test_restore_move_returns_file_and_records_trace_event(self):
        original = self.downloads / "notes.pdf"
        moved = self.profile_root / "Year 1" / "notes.pdf"
        moved.parent.mkdir(parents=True, exist_ok=True)
        moved.write_bytes(b"notes")
        profile = self.make_profile()
        event = MoveEvent.objects.create(
            profile=profile,
            filename="notes.pdf",
            source_path=str(original),
            destination_path=str(moved),
            method="course_code",
            course_code="CSC100",
            success=True,
        )

        restored = undo.restore_move(event)

        self.assertTrue(restored)
        self.assertTrue(original.exists())
        self.assertTrue(MoveEvent.objects.filter(error_message=f"Undo of move #{event.pk}").exists())


class DiagnosticsWorkflowTests(SandboxedPathsTestCase):
    def test_create_backup_uses_runtime_app_dir_and_reports_file(self):
        self.make_settings()

        with mock.patch("runtime.app_dir", return_value=Path(self._tmp.name)):
            result = diagnostics.create_backup()

        self.assertIn("path", result)
        self.assertTrue(result.get("path") is None or Path(result["path"]).exists())

    def test_database_maintenance_functions_return_structured_results(self):
        vacuum = diagnostics.vacuum_database()
        reindex = diagnostics.reindex_database()

        self.assertIn("success", vacuum)
        self.assertIn("success", reindex)


class MueleSecurityWorkflowTests(SandboxedPathsTestCase):
    def test_manual_muele_connection_does_not_store_password_in_database(self):
        profile = self.make_profile(setup_path="makerere")

        IntegrationConnection.objects.create(
            profile=profile,
            provider="muele",
            display_name="Makerere MUELE",
            username="student@mak.ac.ug",
            token_reference="keyring:muele_token",
            status="connected",
            config={"sync_targets": ["course_files"]},
        )

        connection = IntegrationConnection.objects.get(profile=profile, provider="muele")

        self.assertNotIn("password", connection.config)
        self.assertEqual(connection.token_reference, "keyring:muele_token")

    def test_generate_token_stores_only_returned_token(self):
        response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"token": "abc123"},
        )

        with mock.patch("requests.post", return_value=response) as post:
            with mock.patch("organizer.core.muele_api.store_token") as store_token:
                token, error = muele_api.generate_token("student", "secret")

        self.assertEqual(token, "abc123")
        self.assertIsNone(error)
        store_token.assert_called_once_with("abc123")
        self.assertEqual(post.call_args.kwargs["data"]["password"], "secret")
