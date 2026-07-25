from django.test import SimpleTestCase
from django.urls import reverse

from organizer.core import grade_planner
from organizer.models import GradeTarget

from .helpers import SandboxedPathsTestCase


class RequiredExamScoreTests(SimpleTestCase):
    def test_achievable_target_computes_required_score(self):
        result = grade_planner.required_exam_score(
            coursework_weight=30, coursework_score=60,
            test_weight=0, test_score=None,
            exam_weight=70, target_percent=70,
        )
        # contributed = 0.3 * 60 = 18; required = (70 - 18) / 0.7 = 74.28..
        self.assertAlmostEqual(result["required"], 74.3, places=1)
        self.assertTrue(result["achievable"])
        self.assertIn("74%", result["message"])

    def test_not_achievable_even_with_full_marks(self):
        result = grade_planner.required_exam_score(
            coursework_weight=30, coursework_score=20,
            test_weight=0, test_score=None,
            exam_weight=70, target_percent=90,
        )
        self.assertFalse(result["achievable"])
        self.assertIn("Even 100%", result["message"])

    def test_already_secured_target(self):
        result = grade_planner.required_exam_score(
            coursework_weight=30, coursework_score=90,
            test_weight=0, test_score=None,
            exam_weight=70, target_percent=20,
        )
        self.assertTrue(result["achievable"])
        self.assertLessEqual(result["required"], 0)
        self.assertIn("already secured", result["message"])

    def test_missing_score_is_provisional_and_says_so(self):
        result = grade_planner.required_exam_score(
            coursework_weight=30, coursework_score=None,
            test_weight=0, test_score=None,
            exam_weight=70, target_percent=70,
        )
        self.assertTrue(result["provisional"])
        self.assertIn("assumes 0", result["message"])

    def test_fully_scored_components_are_not_provisional(self):
        result = grade_planner.required_exam_score(
            coursework_weight=30, coursework_score=60,
            test_weight=20, test_score=50,
            exam_weight=50, target_percent=70,
        )
        self.assertFalse(result["provisional"])
        self.assertNotIn("assumes 0", result["message"])

    def test_zero_exam_weight_cannot_be_solved(self):
        result = grade_planner.required_exam_score(
            coursework_weight=50, coursework_score=60,
            test_weight=50, test_score=60,
            exam_weight=0, target_percent=70,
        )
        self.assertIsNone(result["required"])
        self.assertIsNone(result["achievable"])
        self.assertIn("no exam weight", result["message"])

    def test_all_three_components_combine(self):
        result = grade_planner.required_exam_score(
            coursework_weight=20, coursework_score=80,
            test_weight=20, test_score=60,
            exam_weight=60, target_percent=65,
        )
        # contributed = 0.2*80 + 0.2*60 = 16 + 12 = 28; required = (65-28)/0.6 = 61.67
        self.assertAlmostEqual(result["required"], 61.7, places=1)
        self.assertTrue(result["achievable"])


class GradeTargetPlannerViewTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_requires_active_profile(self):
        self.profile.is_active = False
        self.profile.save()

        response = self.client.get(reverse("grade_target_planner"))

        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_empty_state(self):
        response = self.client.get(reverse("grade_target_planner"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No targets set yet")

    def test_creates_a_target(self):
        response = self.client.post(reverse("grade_target_planner"), {
            "subject_code": "CSC2100",
            "coursework_weight": "30",
            "coursework_score": "60",
            "test_weight": "0",
            "test_score": "",
            "exam_weight": "70",
            "target_percent": "70",
        })

        self.assertRedirects(response, reverse("grade_target_planner"))
        target = GradeTarget.objects.get(profile=self.profile, subject_code="CSC2100")
        self.assertEqual(target.coursework_score, 60)
        self.assertIsNone(target.test_score)

    def test_saving_again_for_the_same_subject_updates_in_place(self):
        GradeTarget.objects.create(profile=self.profile, subject_code="CSC2100", target_percent=70)

        self.client.post(reverse("grade_target_planner"), {
            "subject_code": "CSC2100",
            "coursework_weight": "30",
            "coursework_score": "",
            "test_weight": "0",
            "test_score": "",
            "exam_weight": "70",
            "target_percent": "80",
        })

        self.assertEqual(GradeTarget.objects.filter(profile=self.profile, subject_code="CSC2100").count(), 1)
        self.assertEqual(GradeTarget.objects.get(profile=self.profile, subject_code="CSC2100").target_percent, 80)

    def test_blank_subject_code_is_rejected(self):
        response = self.client.post(reverse("grade_target_planner"), {"subject_code": ""})

        self.assertRedirects(response, reverse("grade_target_planner"))
        self.assertEqual(GradeTarget.objects.count(), 0)

    def test_list_page_shows_the_computed_message(self):
        GradeTarget.objects.create(
            profile=self.profile, subject_code="CSC2100",
            coursework_weight=30, coursework_score=60,
            exam_weight=70, target_percent=70,
        )

        response = self.client.get(reverse("grade_target_planner"))

        self.assertContains(response, "CSC2100")
        self.assertContains(response, "exam")

    def test_delete_removes_the_target(self):
        target = GradeTarget.objects.create(profile=self.profile, subject_code="CSC2100", target_percent=70)

        response = self.client.post(reverse("grade_target_delete", args=[target.pk]))

        self.assertRedirects(response, reverse("grade_target_planner"))
        self.assertFalse(GradeTarget.objects.filter(pk=target.pk).exists())
