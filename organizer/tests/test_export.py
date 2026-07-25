import json
import zipfile
from unittest import mock

from organizer.core import export
from organizer.models import ExportBundle, Flashcard, GradeTarget, MoveEvent, PastPaperAnalysis, SubjectMemory

from .helpers import SandboxedPathsTestCase


class KnowledgePackTestCase(SandboxedPathsTestCase):
    """export._EXPORT_ROOT is derived from paths.BASE_DIR, which
    SandboxedPathsTestCase does not sandbox (it's an install-location
    constant, not a per-profile one) -- patched here directly so these
    tests never write into the real project's _knowledge_packs folder."""

    def setUp(self):
        super().setUp()
        self._export_root = self._tmp_path() / "_knowledge_packs"
        self.enterContext(mock.patch.object(export, "_EXPORT_ROOT", self._export_root))
        self.profile = self.make_profile()

    def _tmp_path(self):
        from pathlib import Path
        return Path(self._tmp.name)

    def _real_file_and_event(self, filename="notes.pdf", subject_code="CSC2100"):
        dest_dir = self.profile_root / "Year 2" / "Semester 1" / subject_code
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / filename
        dest_path.write_bytes(b"%PDF-1.4 fake content for tests")
        return MoveEvent.objects.create(
            profile=self.profile, filename=filename,
            source_path=str(self.downloads / filename),
            destination_path=str(dest_path),
            method="course_code", course_code=subject_code, success=True,
        )

    def _read_zip(self, result):
        return zipfile.ZipFile(result["output_path"])

    def _manifest(self, zf):
        return json.loads(zf.read("manifest.json"))


class BaselineKnowledgePackTests(KnowledgePackTestCase):
    def test_no_files_found_fails_gracefully(self):
        result = export.create_knowledge_pack(self.profile, scope="profile")

        self.assertEqual(result["status"], "failed")
        bundle = ExportBundle.objects.get(pk=result["bundle_id"])
        self.assertEqual(bundle.status, "failed")
        self.assertIn("error", bundle.manifest)

    def test_real_file_produces_a_ready_zip(self):
        self._real_file_and_event()

        result = export.create_knowledge_pack(self.profile, scope="profile")

        self.assertEqual(result["status"], "ready")
        bundle = ExportBundle.objects.get(pk=result["bundle_id"])
        self.assertEqual(bundle.status, "ready")

        zf = self._read_zip(result)
        names = zf.namelist()
        self.assertIn("reading_list.md", names)
        self.assertIn("folder_map.json", names)
        self.assertIn("manifest.json", names)
        self.assertTrue(any(n.endswith("_study_guide.pdf") for n in names))

    def test_manifest_has_expected_baseline_keys(self):
        self._real_file_and_event()

        result = export.create_knowledge_pack(self.profile, scope="profile")
        manifest = self._manifest(self._read_zip(result))

        self.assertTrue(manifest["has_folder_map"])
        self.assertTrue(manifest["has_reading_list"])
        self.assertTrue(manifest["has_study_guide_pdf"])
        self.assertEqual(manifest["total_files"], 1)


class RevisionContentKnowledgePackTests(KnowledgePackTestCase):
    def test_no_revision_content_writes_none_of_the_three_files(self):
        self._real_file_and_event()

        result = export.create_knowledge_pack(self.profile, scope="profile")
        zf = self._read_zip(result)
        manifest = self._manifest(zf)

        names = zf.namelist()
        self.assertNotIn("flashcards.md", names)
        self.assertNotIn("past_paper_analysis.md", names)
        self.assertNotIn("revision_priorities.md", names)
        self.assertFalse(manifest["has_flashcard_sheet"])
        self.assertFalse(manifest["has_past_paper_brief"])
        self.assertFalse(manifest["has_revision_priorities"])

    def test_flashcards_are_included_with_honest_blank_answers(self):
        self._real_file_and_event()
        Flashcard.objects.create(
            profile=self.profile, subject_code="CSC2100", card_type="past_paper_question",
            front="Explain recursion.", back="",
        )
        Flashcard.objects.create(
            profile=self.profile, subject_code="CSC2100", card_type="definition",
            front="Define: Recursion", back="A function calling itself.",
        )

        result = export.create_knowledge_pack(self.profile, scope="profile")
        zf = self._read_zip(result)
        content = zf.read("flashcards.md").decode("utf-8")

        self.assertIn("Explain recursion.", content)
        self.assertIn("answer not recorded", content)
        self.assertIn("A function calling itself.", content)
        self.assertTrue(self._manifest(zf)["has_flashcard_sheet"])

    def test_past_paper_analysis_is_included(self):
        self._real_file_and_event()
        PastPaperAnalysis.objects.create(
            profile=self.profile, subject_code="CSC2100", paper_count=2,
            questions=[{"text": "Q1", "marks": 10, "source_file": "x.pdf"}],
            topics=[{"name": "recursion", "weight": 80, "evidence": []}],
        )

        result = export.create_knowledge_pack(self.profile, scope="profile")
        zf = self._read_zip(result)
        content = zf.read("past_paper_analysis.md").decode("utf-8")

        self.assertIn("CSC2100", content)
        self.assertIn("recursion", content)
        self.assertTrue(self._manifest(zf)["has_past_paper_brief"])

    def test_revision_priorities_include_weak_areas_and_grade_targets(self):
        self._real_file_and_event()
        SubjectMemory.objects.create(profile=self.profile, code="CSC2100", weak_areas=["graph traversal"])
        GradeTarget.objects.create(
            profile=self.profile, subject_code="CSC2100",
            coursework_weight=30, coursework_score=60, exam_weight=70, target_percent=70,
        )

        result = export.create_knowledge_pack(self.profile, scope="profile")
        zf = self._read_zip(result)
        content = zf.read("revision_priorities.md").decode("utf-8")

        self.assertIn("graph traversal", content)
        self.assertIn("CSC2100", content)
        self.assertIn("exam", content)
        self.assertTrue(self._manifest(zf)["has_revision_priorities"])

    def test_subject_scoped_pack_only_includes_that_subjects_content(self):
        self._real_file_and_event(subject_code="CSC2100")
        self._real_file_and_event(filename="bio_notes.pdf", subject_code="BIO101")
        Flashcard.objects.create(profile=self.profile, subject_code="CSC2100", front="CSC card")
        Flashcard.objects.create(profile=self.profile, subject_code="BIO101", front="BIO card")

        result = export.create_knowledge_pack(self.profile, scope="subject", subject_code="CSC2100")
        zf = self._read_zip(result)
        content = zf.read("flashcards.md").decode("utf-8")

        self.assertIn("CSC card", content)
        self.assertNotIn("BIO card", content)
