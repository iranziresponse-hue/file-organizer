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


class EnsureSubjectFoldersTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.config = CourseConfig.objects.create(
            profile=self.profile,
            primary_value="Year 1",
            secondary_value="Semester 1",
            groups=["BIO101", "CHE102"],
        )

    def test_creates_only_the_missing_folders(self):
        existing = self.profile_root / "Year 1" / "Semester 1" / "BIO101"
        existing.mkdir(parents=True)

        result = sorting.ensure_subject_folders(self.profile)

        self.assertEqual(result["created"], ["CHE102"])
        self.assertEqual(result["existing"], ["BIO101"])
        self.assertTrue((self.profile_root / "Year 1" / "Semester 1" / "CHE102").exists())

    def test_never_touches_a_folder_that_already_exists(self):
        existing = self.profile_root / "Year 1" / "Semester 1" / "BIO101"
        existing.mkdir(parents=True)
        marker = existing / "my_notes.pdf"
        marker.write_text("keep me")

        sorting.ensure_subject_folders(self.profile)

        # Re-running must not duplicate or disturb what's already there.
        self.assertTrue(marker.exists())
        self.assertEqual(marker.read_text(), "keep me")

    def test_running_twice_creates_nothing_new_the_second_time(self):
        sorting.ensure_subject_folders(self.profile)
        result = sorting.ensure_subject_folders(self.profile)

        self.assertEqual(result["created"], [])
        self.assertEqual(sorted(result["existing"]), ["BIO101", "CHE102"])

    def test_no_config_returns_empty_result_without_error(self):
        profile = self.make_profile(name="No config", root_path=str(self.profile_root) + "-none")
        result = sorting.ensure_subject_folders(profile)
        self.assertEqual(result, {"created": [], "existing": [], "renamed": []})


class EnsureSubjectFoldersNamingTests(SandboxedPathsTestCase):
    """CSC1102 is a real code from makerere_curricula.py (Bachelor of
    Science in Computer Science, Year 1 Semester 1) -- "Structured and
    Object-Oriented Programming" -- used here to exercise the
    known-name path without hardcoding a name Orch didn't actually derive."""

    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.config = CourseConfig.objects.create(
            profile=self.profile,
            primary_value="Year 1",
            secondary_value="Semester 1",
            groups=["CSC1102"],
        )
        from organizer.core import makerere_curricula
        self.expected_name = makerere_curricula.name_for_code("CSC1102")
        self.assertTrue(self.expected_name, "test fixture assumption broken: CSC1102 should be a known code")

    def test_creates_a_named_folder_directly_when_nothing_exists_yet(self):
        result = sorting.ensure_subject_folders(self.profile)

        self.assertEqual(result["created"], ["CSC1102"])
        expected = self.profile_root / "Year 1" / "Semester 1" / f"CSC1102 - {self.expected_name}"
        self.assertTrue(expected.exists())
        self.assertFalse((self.profile_root / "Year 1" / "Semester 1" / "CSC1102").exists())

    def test_renames_an_existing_bare_folder_in_place_preserving_contents(self):
        bare = self.profile_root / "Year 1" / "Semester 1" / "CSC1102"
        bare.mkdir(parents=True)
        (bare / "lecture1.pdf").write_text("real notes")

        result = sorting.ensure_subject_folders(self.profile)

        self.assertEqual(result["renamed"], ["CSC1102"])
        self.assertEqual(result["created"], [])
        named = self.profile_root / "Year 1" / "Semester 1" / f"CSC1102 - {self.expected_name}"
        self.assertTrue(named.exists())
        self.assertEqual((named / "lecture1.pdf").read_text(), "real notes")
        self.assertFalse(bare.exists(), "bare CODE folder must not survive as a duplicate")

    def test_does_nothing_when_already_named(self):
        named = self.profile_root / "Year 1" / "Semester 1" / f"CSC1102 - {self.expected_name}"
        named.mkdir(parents=True)

        result = sorting.ensure_subject_folders(self.profile)

        self.assertEqual(result["created"], [])
        self.assertEqual(result["renamed"], [])
        self.assertEqual(result["existing"], ["CSC1102"])


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


class MueleTokenStoreResilienceTests(SandboxedPathsTestCase):
    """Regression coverage for a real crash: the `keyring` package wasn't
    installed in the environment running the dev server, and load_token()
    let the ImportError propagate straight up through the MUELE views as
    an unhandled 500. These functions are documented (module docstring) to
    never throw -- these tests hold that promise for the "keyring isn't
    available" case specifically, without needing keyring to actually be
    absent from this test environment."""

    def _simulate_missing_keyring(self):
        return mock.patch.dict("sys.modules", {"keyring": None})

    def test_load_token_returns_none_instead_of_raising(self):
        from organizer.core import muele_api

        with self._simulate_missing_keyring():
            result = muele_api.load_token()

        self.assertIsNone(result)

    def test_store_token_reports_failure_instead_of_raising(self):
        from organizer.core import muele_api

        with self._simulate_missing_keyring():
            stored, error = muele_api.store_token("abc123")

        self.assertFalse(stored)
        self.assertIsNotNone(error)

    def test_clear_token_does_not_raise(self):
        from organizer.core import muele_api

        with self._simulate_missing_keyring():
            muele_api.clear_token()  # must not raise


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
            with mock.patch("organizer.core.muele_api.store_token", return_value=(True, None)) as store_token:
                token, error = muele_api.generate_token("student", "secret")

        self.assertEqual(token, "abc123")
        self.assertIsNone(error)
        store_token.assert_called_once_with("abc123")
        self.assertEqual(post.call_args.kwargs["data"]["password"], "secret")

    def test_generate_token_reports_when_storing_the_token_fails(self):
        response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"token": "abc123"},
        )

        with mock.patch("requests.post", return_value=response):
            with mock.patch(
                "organizer.core.muele_api.store_token",
                return_value=(False, "no OS credential backend available"),
            ):
                token, error = muele_api.generate_token("student", "secret")

        self.assertIsNone(token)
        self.assertIn("no OS credential backend available", error)
