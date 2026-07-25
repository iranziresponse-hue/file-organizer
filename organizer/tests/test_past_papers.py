from unittest import mock

from django.urls import reverse

from organizer.core import past_papers
from organizer.models import MoveEvent, PastPaperAnalysis, SubjectMemory, SubjectTheme

from .helpers import SandboxedPathsTestCase


class ExtractQuestionsTests(SandboxedPathsTestCase):
    def test_splits_numbered_questions(self):
        text = "1. Explain recursion.\n2. Define Big-O notation."
        questions = past_papers.extract_questions(text, source_file="paper.pdf")

        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0]["text"], "Explain recursion.")
        self.assertEqual(questions[1]["text"], "Define Big-O notation.")
        self.assertEqual(questions[0]["source_file"], "paper.pdf")

    def test_extracts_marks_in_square_brackets(self):
        text = "1. Explain recursion. [10 marks]"
        questions = past_papers.extract_questions(text)
        self.assertEqual(questions[0]["marks"], 10)

    def test_extracts_marks_in_parentheses(self):
        text = "1. Define Big-O notation. (5 Marks)"
        questions = past_papers.extract_questions(text)
        self.assertEqual(questions[0]["marks"], 5)

    def test_question_without_marks_is_none(self):
        text = "1. Explain recursion."
        questions = past_papers.extract_questions(text)
        self.assertIsNone(questions[0]["marks"])

    def test_no_question_markers_returns_empty_list(self):
        text = "This is just a paragraph of prose with no numbering at all."
        self.assertEqual(past_papers.extract_questions(text), [])

    def test_blank_text_returns_empty_list(self):
        self.assertEqual(past_papers.extract_questions(""), [])
        self.assertEqual(past_papers.extract_questions("   "), [])

    def test_question_word_form_is_recognized(self):
        text = "Question 1: What is a binary tree?\nQuestion 2: What is a hash table?"
        questions = past_papers.extract_questions(text)
        self.assertEqual(len(questions), 2)


class AnalyzeSubjectTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def _past_paper_event(self, filename, destination_dir="03 Past Papers and Tests"):
        dest_dir = self.profile_root / "CSC2100" / destination_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / filename
        dest_path.write_bytes(b"not a real pdf, but exists")
        return MoveEvent.objects.create(
            profile=self.profile, filename=filename,
            source_path=str(self.downloads / filename),
            destination_path=str(dest_path),
            method="course_code", course_code="CSC2100", success=True,
        )

    def test_no_past_papers_returns_none_and_creates_no_row(self):
        analysis, skipped = past_papers.analyze_subject(self.profile, "CSC2100")

        self.assertIsNone(analysis)
        self.assertEqual(skipped, 0)
        self.assertFalse(PastPaperAnalysis.objects.exists())

    def test_only_files_in_the_past_papers_bucket_are_considered(self):
        self._past_paper_event("2023 exam.pdf")
        self._past_paper_event("notes.pdf", destination_dir="01 Lecture Notes and Slides")

        with mock.patch("organizer.core.summarize.extract_text", return_value="1. Explain recursion. [10 marks]"):
            analysis, skipped = past_papers.analyze_subject(self.profile, "CSC2100")

        self.assertEqual(analysis.paper_count, 1)

    def test_missing_file_on_disk_is_skipped_and_counted(self):
        event = self._past_paper_event("2023 exam.pdf")
        import os
        os.remove(event.destination_path)

        analysis, skipped = past_papers.analyze_subject(self.profile, "CSC2100")

        self.assertIsNone(analysis)
        self.assertEqual(skipped, 1)

    def test_unreadable_file_is_skipped(self):
        self._past_paper_event("2023 exam.pdf")

        with mock.patch("organizer.core.summarize.extract_text", return_value=""):
            analysis, skipped = past_papers.analyze_subject(self.profile, "CSC2100")

        self.assertIsNone(analysis)
        self.assertEqual(skipped, 1)

    def test_topics_come_back_in_the_subject_theme_shape(self):
        self._past_paper_event("2023 exam.pdf")

        with mock.patch(
            "organizer.core.summarize.extract_text",
            return_value="1. Explain recursion and dynamic programming. [10 marks]\n2. Explain recursion again. [8 marks]",
        ):
            analysis, _ = past_papers.analyze_subject(self.profile, "CSC2100")

        self.assertTrue(analysis.topics)
        for topic in analysis.topics:
            self.assertIn("name", topic)
            self.assertIn("weight", topic)
            self.assertIn("evidence", topic)

    def test_marks_annotations_and_exam_command_words_do_not_pollute_topics(self):
        # Every question ends in "[N marks]" and starts with a command verb
        # ("Explain", "Describe") -- both are exam-paper grammar, not a
        # syllabus topic, and would otherwise dominate a naive frequency count.
        self._past_paper_event("2023 exam.pdf")
        self._past_paper_event("2022 exam.pdf")

        texts = iter([
            "1. Explain how a binary search tree performs insertion. [10 marks]\n"
            "2. Describe the time complexity of quicksort. [8 marks]",
            "1. Explain recursion in divide and conquer algorithms. [10 marks]\n"
            "2. Describe how a hash table resolves collisions. [12 marks]",
        ])
        with mock.patch("organizer.core.summarize.extract_text", side_effect=lambda p: next(texts)):
            analysis, _ = past_papers.analyze_subject(self.profile, "CSC2100")

        topic_names = {t["name"] for t in analysis.topics}
        self.assertNotIn("marks", topic_names)
        self.assertNotIn("explain", topic_names)
        self.assertNotIn("describe", topic_names)
        # The questions themselves still keep their marks intact for display.
        self.assertTrue(any(q["marks"] == 10 for q in analysis.questions))

    def test_second_run_overwrites_rather_than_duplicates(self):
        self._past_paper_event("2023 exam.pdf")

        with mock.patch("organizer.core.summarize.extract_text", return_value="1. Explain recursion. [10 marks]"):
            past_papers.analyze_subject(self.profile, "CSC2100")
            past_papers.analyze_subject(self.profile, "CSC2100")

        self.assertEqual(PastPaperAnalysis.objects.filter(profile=self.profile, subject_code="CSC2100").count(), 1)

    def test_analysis_refreshes_weak_areas(self):
        SubjectMemory.objects.create(profile=self.profile, code="CSC2100")
        self._past_paper_event("2023 exam.pdf")

        with mock.patch(
            "organizer.core.summarize.extract_text",
            return_value="1. Explain graph traversal algorithms thoroughly. [10 marks]",
        ):
            past_papers.analyze_subject(self.profile, "CSC2100")

        memory = SubjectMemory.objects.get(profile=self.profile, code="CSC2100")
        self.assertTrue(memory.weak_areas)


class UpdateWeakAreasTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.memory = SubjectMemory.objects.create(profile=self.profile, code="CSC2100")

    def test_no_memory_row_returns_empty(self):
        self.assertEqual(past_papers.update_weak_areas(self.profile, "UNKNOWN"), [])

    def test_past_paper_topic_not_in_own_themes_becomes_weak(self):
        PastPaperAnalysis.objects.create(
            profile=self.profile, subject_code="CSC2100",
            topics=[{"name": "graph traversal", "weight": 80, "evidence": []}],
        )
        SubjectTheme.objects.create(profile=self.profile, subject_code="CSC2100", name="recursion", weight=50)

        weak = past_papers.update_weak_areas(self.profile, "CSC2100")

        self.assertIn("graph traversal", weak)
        self.memory.refresh_from_db()
        self.assertEqual(self.memory.weak_areas, weak)

    def test_topic_already_covered_by_own_themes_is_not_flagged(self):
        PastPaperAnalysis.objects.create(
            profile=self.profile, subject_code="CSC2100",
            topics=[{"name": "recursion", "weight": 80, "evidence": []}],
        )
        SubjectTheme.objects.create(profile=self.profile, subject_code="CSC2100", name="recursion", weight=50)

        weak = past_papers.update_weak_areas(self.profile, "CSC2100")

        self.assertNotIn("recursion", weak)

    def test_falls_back_to_least_covered_own_themes_without_past_papers(self):
        for i in range(8):
            SubjectTheme.objects.create(profile=self.profile, subject_code="CSC2100", name=f"topic{i}", weight=i)

        weak = past_papers.update_weak_areas(self.profile, "CSC2100")

        # Bottom 5 by weight (0-4) should be picked, not the strongest ones.
        self.assertIn("topic0", weak)
        self.assertNotIn("topic7", weak)

    def test_result_is_capped_at_eight(self):
        PastPaperAnalysis.objects.create(
            profile=self.profile, subject_code="CSC2100",
            topics=[{"name": f"topic{i}", "weight": 100 - i, "evidence": []} for i in range(15)],
        )

        weak = past_papers.update_weak_areas(self.profile, "CSC2100")

        self.assertEqual(len(weak), 8)


class PastPaperAnalysisViewTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def _past_paper_event(self, filename):
        dest_dir = self.profile_root / "CSC2100" / "03 Past Papers and Tests"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / filename
        dest_path.write_bytes(b"not a real pdf, but exists")
        return MoveEvent.objects.create(
            profile=self.profile, filename=filename,
            source_path=str(self.downloads / filename),
            destination_path=str(dest_path),
            method="course_code", course_code="CSC2100", success=True,
        )

    def test_requires_active_profile(self):
        self.profile.is_active = False
        self.profile.save()

        response = self.client.get(reverse("past_paper_analysis", args=["CSC2100"]))

        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_empty_state_with_no_past_papers(self):
        response = self.client.get(reverse("past_paper_analysis", args=["CSC2100"]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No analysis yet")
        self.assertContains(response, "No files have landed")

    def test_generate_with_no_past_papers_creates_no_row_and_shows_error(self):
        response = self.client.post(reverse("past_paper_analysis", args=["CSC2100"]))

        self.assertRedirects(response, reverse("past_paper_analysis", args=["CSC2100"]))
        self.assertFalse(PastPaperAnalysis.objects.exists())

    def test_generate_with_a_readable_paper_creates_the_analysis(self):
        self._past_paper_event("2023 exam.pdf")

        with mock.patch(
            "organizer.core.summarize.extract_text",
            return_value="1. Explain recursion thoroughly. [10 marks]",
        ):
            response = self.client.post(reverse("past_paper_analysis", args=["CSC2100"]))

        self.assertRedirects(response, reverse("past_paper_analysis", args=["CSC2100"]))
        analysis = PastPaperAnalysis.objects.get(profile=self.profile, subject_code="CSC2100")
        self.assertEqual(analysis.paper_count, 1)

    def test_page_shows_papers_analyzed_after_generating(self):
        self._past_paper_event("2023 exam.pdf")

        with mock.patch(
            "organizer.core.summarize.extract_text",
            return_value="1. Explain recursion thoroughly. [10 marks]",
        ):
            self.client.post(reverse("past_paper_analysis", args=["CSC2100"]))

        response = self.client.get(reverse("past_paper_analysis", args=["CSC2100"]))

        self.assertContains(response, "Papers analyzed")
        self.assertContains(response, "recursion")
