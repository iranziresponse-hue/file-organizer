from django.urls import reverse
from django.utils import timezone

from organizer.models import AssignmentItem, MoveEvent, ReviewItem, SubjectMemory, SubjectTheme

from .helpers import SandboxedPathsTestCase


class CourseUnitBrainTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.memory = SubjectMemory.objects.create(profile=self.profile, code="CSC2100")

    def _resource(self, filename, category_folder, **overrides):
        fields = {
            "profile": self.profile,
            "filename": filename,
            "source_path": f"C:/Downloads/{filename}",
            "destination_path": f"C:/School/CSC2100/{category_folder}/{filename}",
            "method": "course_code",
            "course_code": "CSC2100",
            "success": True,
        }
        fields.update(overrides)
        return MoveEvent.objects.create(**fields)

    def test_resources_are_bucketed_by_category(self):
        self._resource("notes.pdf", "01 Lecture Notes and Slides")
        self._resource("assignment1.docx", "02 Assignments and Coursework")
        self._resource("2023 exam.pdf", "03 Past Papers and Tests")

        response = self.client.get(reverse("subject_memory_detail", args=["CSC2100"]))

        self.assertEqual(response.status_code, 200)
        buckets = response.context["resource_buckets"]
        self.assertEqual(len(buckets["Lecture Notes"]), 1)
        self.assertEqual(len(buckets["Assignments & Coursework"]), 1)
        self.assertEqual(len(buckets["Past Papers & Tests"]), 1)
        self.assertEqual(response.context["lecture_notes_count"], 1)
        self.assertEqual(response.context["past_papers_count"], 1)

    def test_unrecognized_destination_lands_in_other_bucket(self):
        self._resource("photo.png", "does-not-exist")

        response = self.client.get(reverse("subject_memory_detail", args=["CSC2100"]))

        self.assertEqual(len(response.context["resource_buckets"]["Other"]), 1)

    def test_revision_status_reflects_queued_and_done_reviews(self):
        ReviewItem.objects.create(
            profile=self.profile, subject_code="CSC2100", title="Done one",
            due_at=timezone.now(), status="done",
        )
        ReviewItem.objects.create(
            profile=self.profile, subject_code="CSC2100", title="Queued one",
            due_at=timezone.now(), status="queued",
        )

        response = self.client.get(reverse("subject_memory_detail", args=["CSC2100"]))

        self.assertEqual(response.context["reviews_done_count"], 1)
        self.assertEqual(response.context["reviews_queued_count"], 1)
        self.assertContains(response, "1 / 2")

    def test_weak_areas_render_when_present(self):
        self.memory.weak_areas = ["Recursion", "Big-O notation"]
        self.memory.save()

        response = self.client.get(reverse("subject_memory_detail", args=["CSC2100"]))

        self.assertEqual(response.context["weak_topics_count"], 2)
        self.assertContains(response, "Recursion")
        self.assertContains(response, "Big-O notation")

    def test_weak_areas_empty_state(self):
        response = self.client.get(reverse("subject_memory_detail", args=["CSC2100"]))

        self.assertEqual(response.context["weak_topics_count"], 0)
        self.assertContains(response, "Nothing flagged yet")

    def test_open_assignments_count_excludes_non_open(self):
        AssignmentItem.objects.create(profile=self.profile, subject_code="CSC2100", title="Open", status="open")
        AssignmentItem.objects.create(profile=self.profile, subject_code="CSC2100", title="Done", status="submitted")

        response = self.client.get(reverse("subject_memory_detail", args=["CSC2100"]))

        self.assertEqual(response.context["open_assignments_count"], 1)

    def test_top_themes_is_capped_at_five(self):
        for i in range(8):
            SubjectTheme.objects.create(
                profile=self.profile, subject_code="CSC2100", name=f"topic{i}", weight=i,
            )

        response = self.client.get(reverse("subject_memory_detail", args=["CSC2100"]))

        self.assertEqual(len(response.context["top_themes"]), 5)

    def test_assignments_card_links_to_the_tracker(self):
        response = self.client.get(reverse("subject_memory_detail", args=["CSC2100"]))

        self.assertContains(response, reverse("assignment_tracker"))
