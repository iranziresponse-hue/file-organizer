from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from organizer.core import weakness_radar
from organizer.models import MoveEvent, ReviewItem, SubjectMemory

from .helpers import SandboxedPathsTestCase


class BuildRadarTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_empty_state_when_nothing_flagged(self):
        radar = weakness_radar.build_radar(self.profile)

        self.assertEqual(radar["subject_weak_areas"], [])
        self.assertEqual(radar["repeated_topics"], [])
        self.assertIsNone(radar["headline"])

    def test_subject_with_weak_areas_is_flagged(self):
        SubjectMemory.objects.create(profile=self.profile, code="CSC2100", weak_areas=["recursion"])
        SubjectMemory.objects.create(profile=self.profile, code="BIO101", weak_areas=[])

        radar = weakness_radar.build_radar(self.profile)

        codes = [row["code"] for row in radar["subject_weak_areas"]]
        self.assertEqual(codes, ["CSC2100"])

    def test_repeated_topic_needs_two_or_more_subjects(self):
        SubjectMemory.objects.create(profile=self.profile, code="CSC2100", weak_areas=["Recursion", "Trees"])
        SubjectMemory.objects.create(profile=self.profile, code="BSE2106", weak_areas=["recursion"])

        radar = weakness_radar.build_radar(self.profile)

        topics = {row["topic"]: row["subjects"] for row in radar["repeated_topics"]}
        self.assertIn("recursion", topics)
        self.assertEqual(sorted(topics["recursion"]), ["BSE2106", "CSC2100"])
        self.assertNotIn("trees", topics)

    def test_neglected_subjects_ordered_oldest_first(self):
        old = SubjectMemory.objects.create(
            profile=self.profile, code="OLD", last_touched_at=timezone.now() - timedelta(days=40),
        )
        never = SubjectMemory.objects.create(profile=self.profile, code="NEVER", last_touched_at=None)
        recent = SubjectMemory.objects.create(
            profile=self.profile, code="RECENT", last_touched_at=timezone.now() - timedelta(days=1),
        )

        radar = weakness_radar.build_radar(self.profile)

        neglected_codes = [m.code for m in radar["neglected_subjects"]]
        self.assertNotIn("RECENT", neglected_codes)
        self.assertIn("OLD", neglected_codes)
        self.assertIn("NEVER", neglected_codes)
        # Never-touched is treated as more urgent than a known old date.
        self.assertEqual(neglected_codes[0], "NEVER")

    def test_unreviewed_resources_excludes_files_with_any_review_item(self):
        reviewed_event = MoveEvent.objects.create(
            profile=self.profile, filename="reviewed.pdf", source_path="C:/Downloads/reviewed.pdf",
            destination_path="C:/School/CSC2100/reviewed.pdf", method="course_code",
            course_code="CSC2100", success=True,
        )
        ReviewItem.objects.create(
            profile=self.profile, move_event=reviewed_event, subject_code="CSC2100",
            title="Review it", due_at=timezone.now(), status="queued",
        )
        MoveEvent.objects.create(
            profile=self.profile, filename="unreviewed.pdf", source_path="C:/Downloads/unreviewed.pdf",
            destination_path="C:/School/CSC2100/unreviewed.pdf", method="course_code",
            course_code="CSC2100", success=True,
        )

        radar = weakness_radar.build_radar(self.profile)

        filenames = [e.filename for e in radar["unreviewed_resources"]]
        self.assertIn("unreviewed.pdf", filenames)
        self.assertNotIn("reviewed.pdf", filenames)

    def test_files_with_no_subject_code_are_not_counted(self):
        MoveEvent.objects.create(
            profile=self.profile, filename="media.png", source_path="C:/Downloads/media.png",
            destination_path="C:/Personal/Media/media.png", method="media",
            course_code="", success=True,
        )

        radar = weakness_radar.build_radar(self.profile)

        self.assertEqual(radar["unreviewed_resources"], [])

    def test_headline_picks_the_most_neglected_flagged_subject(self):
        SubjectMemory.objects.create(
            profile=self.profile, code="RECENT", weak_areas=["topic a"],
            last_touched_at=timezone.now() - timedelta(days=1),
        )
        SubjectMemory.objects.create(
            profile=self.profile, code="STALE", weak_areas=["topic b"],
            last_touched_at=timezone.now() - timedelta(days=60),
        )

        radar = weakness_radar.build_radar(self.profile)

        self.assertEqual(radar["headline"]["subject_code"], "STALE")
        self.assertEqual(radar["headline"]["topic"], "topic b")


class WeaknessRadarPageTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_requires_active_profile(self):
        self.profile.is_active = False
        self.profile.save()

        response = self.client.get(reverse("weakness_radar"))

        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_empty_state(self):
        response = self.client.get(reverse("weakness_radar"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nothing flagged yet")

    def test_headline_and_flagged_subject_render(self):
        SubjectMemory.objects.create(profile=self.profile, code="CSC2100", weak_areas=["recursion"])

        response = self.client.get(reverse("weakness_radar"))

        self.assertContains(response, "This week's weakest area")
        self.assertContains(response, "recursion")
