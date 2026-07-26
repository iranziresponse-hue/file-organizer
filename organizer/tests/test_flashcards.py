from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from organizer.core import flashcards
from organizer.models import FileSummary, Flashcard, MoveEvent, PastPaperAnalysis

from .helpers import SandboxedPathsTestCase


class GenerateFromPastPapersTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_creates_one_card_per_question_with_blank_back(self):
        PastPaperAnalysis.objects.create(
            profile=self.profile, subject_code="CSC2100",
            questions=[
                {"text": "Explain recursion.", "marks": 10, "source_file": "2023.pdf"},
                {"text": "Define Big-O notation.", "marks": 5, "source_file": "2023.pdf"},
            ],
        )

        created = flashcards.generate_from_past_papers(self.profile, "CSC2100")

        self.assertEqual(created, 2)
        cards = Flashcard.objects.filter(profile=self.profile, card_type="past_paper_question")
        self.assertEqual(cards.count(), 2)
        for card in cards:
            self.assertEqual(card.back, "")
            self.assertEqual(card.source_label, "2023.pdf")

    def test_no_analysis_creates_nothing(self):
        created = flashcards.generate_from_past_papers(self.profile, "CSC2100")
        self.assertEqual(created, 0)
        self.assertEqual(Flashcard.objects.count(), 0)

    def test_second_run_does_not_duplicate(self):
        PastPaperAnalysis.objects.create(
            profile=self.profile, subject_code="CSC2100",
            questions=[{"text": "Explain recursion.", "marks": 10, "source_file": "2023.pdf"}],
        )

        flashcards.generate_from_past_papers(self.profile, "CSC2100")
        second_run_created = flashcards.generate_from_past_papers(self.profile, "CSC2100")

        self.assertEqual(second_run_created, 0)
        self.assertEqual(Flashcard.objects.count(), 1)


class GenerateFromSummariesTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.event = MoveEvent.objects.create(
            profile=self.profile, filename="notes.pdf",
            source_path="C:/Downloads/notes.pdf",
            destination_path="C:/School/CSC2100/notes.pdf",
            method="course_code", course_code="CSC2100", success=True,
        )

    def _summary(self, content):
        return FileSummary.objects.create(move_event=self.event, content=content)

    def test_bold_definition_creates_a_definition_card(self):
        self._summary("Some intro text.\n\n**Recursion**: a function calling itself.\n")

        created = flashcards.generate_from_summaries(self.profile, "CSC2100")

        card = Flashcard.objects.get(card_type="definition")
        self.assertEqual(card.front, "Define: Recursion")
        self.assertEqual(card.back, "a function calling itself.")
        self.assertEqual(card.source_label, "notes.pdf")
        self.assertGreaterEqual(created, 1)

    def test_heading_with_body_creates_a_concept_card(self):
        self._summary("# Overview\n\n## Binary Search Trees\n\nA binary search tree keeps its keys ordered.\n")

        flashcards.generate_from_summaries(self.profile, "CSC2100")

        card = Flashcard.objects.get(card_type="concept")
        self.assertEqual(card.front, "Explain: Binary Search Trees")
        self.assertIn("binary search tree", card.back.lower())

    def test_heading_with_no_body_creates_no_concept_card(self):
        self._summary("## Empty Heading\n\n## Next Heading\n\nSome real content here.\n")

        flashcards.generate_from_summaries(self.profile, "CSC2100")

        fronts = set(Flashcard.objects.filter(card_type="concept").values_list("front", flat=True))
        self.assertNotIn("Explain: Empty Heading", fronts)
        self.assertIn("Explain: Next Heading", fronts)

    def test_second_run_does_not_duplicate(self):
        self._summary("**Recursion**: a function calling itself.\n\n## Trees\n\nA tree has nodes.\n")

        flashcards.generate_from_summaries(self.profile, "CSC2100")
        first_count = Flashcard.objects.count()
        second_run_created = flashcards.generate_from_summaries(self.profile, "CSC2100")

        self.assertEqual(second_run_created, 0)
        self.assertEqual(Flashcard.objects.count(), first_count)

    def test_no_summaries_creates_nothing(self):
        created = flashcards.generate_from_summaries(self.profile, "BIO101")
        self.assertEqual(created, 0)


class GradeFlashcardTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.card = Flashcard.objects.create(profile=self.profile, subject_code="CSC2100", front="Q")

    def test_remembering_advances_interval_and_pushes_due_at_out(self):
        before = timezone.now()

        flashcards.grade_flashcard(self.card, remembered=True)

        self.card.refresh_from_db()
        self.assertEqual(self.card.interval_index, 1)
        self.assertEqual(self.card.times_seen, 1)
        self.assertEqual(self.card.times_correct, 1)
        self.assertGreater(self.card.due_at, before + timedelta(days=2))

    def test_forgetting_regresses_interval_with_a_floor_of_zero(self):
        self.card.interval_index = 0
        self.card.save()

        flashcards.grade_flashcard(self.card, remembered=False)

        self.card.refresh_from_db()
        self.assertEqual(self.card.interval_index, 0)
        self.assertEqual(self.card.times_seen, 1)
        self.assertEqual(self.card.times_correct, 0)

    def test_interval_index_caps_at_the_top_of_the_ladder(self):
        self.card.interval_index = len(flashcards.INTERVALS) - 1
        self.card.save()

        flashcards.grade_flashcard(self.card, remembered=True)

        self.card.refresh_from_db()
        self.assertEqual(self.card.interval_index, len(flashcards.INTERVALS) - 1)


class GetDueCardsTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_excludes_future_due_cards(self):
        Flashcard.objects.create(profile=self.profile, subject_code="CSC2100", front="due now")
        Flashcard.objects.create(
            profile=self.profile, subject_code="CSC2100", front="due later",
            due_at=timezone.now() + timedelta(days=5),
        )

        due = flashcards.get_due_cards(self.profile)

        fronts = [c.front for c in due]
        self.assertIn("due now", fronts)
        self.assertNotIn("due later", fronts)

    def test_excludes_archived_cards(self):
        Flashcard.objects.create(profile=self.profile, subject_code="CSC2100", front="archived", status="archived")

        due = flashcards.get_due_cards(self.profile)

        self.assertEqual(list(due), [])

    def test_respects_subject_filter(self):
        Flashcard.objects.create(profile=self.profile, subject_code="CSC2100", front="a")
        Flashcard.objects.create(profile=self.profile, subject_code="BIO101", front="b")

        due = flashcards.get_due_cards(self.profile, subject_code="CSC2100")

        self.assertEqual([c.front for c in due], ["a"])


class FlashcardsPageTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_requires_active_profile(self):
        self.profile.is_active = False
        self.profile.save()

        response = self.client.get(reverse("flashcards"))

        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_empty_state(self):
        response = self.client.get(reverse("flashcards"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "All caught up")

    def test_practice_flow_grading_removes_it_as_next_due(self):
        card = Flashcard.objects.create(profile=self.profile, subject_code="CSC2100", front="What is recursion?")

        response = self.client.get(reverse("flashcards"))
        self.assertEqual(response.context["next_card"].pk, card.pk)

        self.client.post(reverse("flashcard_grade", args=[card.pk]), {"remembered": "1"})

        card.refresh_from_db()
        self.assertEqual(card.times_seen, 1)
        response = self.client.get(reverse("flashcards"))
        self.assertIsNone(response.context["next_card"])

    def test_generate_past_papers_action_creates_cards_and_messages_count(self):
        PastPaperAnalysis.objects.create(
            profile=self.profile, subject_code="CSC2100",
            questions=[{"text": "Explain recursion.", "marks": 10, "source_file": "2023.pdf"}],
        )

        response = self.client.post(reverse("flashcards"), {
            "action": "generate_past_papers", "subject_code": "CSC2100",
        }, follow=True)

        self.assertContains(response, "Created 1 new card")
        self.assertEqual(Flashcard.objects.filter(card_type="past_paper_question").count(), 1)

    def test_generate_summaries_action_creates_cards(self):
        event = MoveEvent.objects.create(
            profile=self.profile, filename="notes.pdf", source_path="C:/Downloads/notes.pdf",
            destination_path="C:/School/CSC2100/notes.pdf", method="course_code",
            course_code="CSC2100", success=True,
        )
        FileSummary.objects.create(move_event=event, content="**Recursion**: a function calling itself.\n")

        response = self.client.post(reverse("flashcards"), {
            "action": "generate_summaries", "subject_code": "CSC2100",
        }, follow=True)

        self.assertContains(response, "Created 1 new card")
        self.assertEqual(Flashcard.objects.filter(card_type="definition").count(), 1)

    def test_create_manual_card(self):
        response = self.client.post(reverse("flashcards"), {
            "action": "create_manual", "subject_code": "CSC2100",
            "front": "What is Big-O?", "back": "A growth-rate notation.",
        })

        self.assertRedirects(response, reverse("flashcards"))
        card = Flashcard.objects.get(card_type="manual")
        self.assertEqual(card.front, "What is Big-O?")
        self.assertEqual(card.back, "A growth-rate notation.")

    def test_blank_manual_front_is_rejected(self):
        response = self.client.post(reverse("flashcards"), {"action": "create_manual", "front": ""})

        self.assertRedirects(response, reverse("flashcards"))

    def test_delete_subject_cards_removes_only_that_subject(self):
        Flashcard.objects.create(profile=self.profile, subject_code="CSC2100", front="Q1")
        Flashcard.objects.create(profile=self.profile, subject_code="CSC2100", front="Q2")
        other = Flashcard.objects.create(profile=self.profile, subject_code="BIO101", front="Q3")

        response = self.client.post(reverse("flashcards"), {
            "action": "delete_subject_cards", "subject_code": "CSC2100",
        }, follow=True)

        self.assertContains(response, "Deleted 2 card")
        self.assertEqual(Flashcard.objects.filter(subject_code="CSC2100").count(), 0)
        self.assertTrue(Flashcard.objects.filter(pk=other.pk).exists())

    def test_delete_subject_cards_handles_the_unassigned_bucket(self):
        Flashcard.objects.create(profile=self.profile, subject_code="", front="Q1")

        response = self.client.post(reverse("flashcards"), {
            "action": "delete_subject_cards", "subject_code": "Unassigned",
        }, follow=True)

        self.assertContains(response, "Deleted 1 card")
        self.assertEqual(Flashcard.objects.filter(status="active").count(), 0)
        self.assertEqual(Flashcard.objects.count(), 0)

    def test_delete_removes_the_card(self):
        card = Flashcard.objects.create(profile=self.profile, subject_code="CSC2100", front="Q")

        response = self.client.post(reverse("flashcard_delete", args=[card.pk]))

        self.assertRedirects(response, reverse("flashcards"))
        self.assertFalse(Flashcard.objects.filter(pk=card.pk).exists())

    def test_generation_sources_only_list_subjects_with_real_content(self):
        PastPaperAnalysis.objects.create(profile=self.profile, subject_code="CSC2100", questions=[{"text": "Q"}])

        response = self.client.get(reverse("flashcards"))

        self.assertIn("CSC2100", response.context["generation_sources"])
        self.assertContains(response, "CSC2100")
