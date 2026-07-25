from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from organizer.core import resource_cache
from organizer.models import LearningActivity, ResourceRecommendation

from .helpers import SandboxedPathsTestCase


class GenerationCounterCacheTests(TestCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(cache.clear)

    def test_a_cache_miss_calls_compute_and_caches_the_result(self):
        calls = []

        def compute():
            calls.append(1)
            return ["item"]

        first = resource_cache.get_or_set_resource_recommendations(1, None, compute)
        second = resource_cache.get_or_set_resource_recommendations(1, None, compute)

        self.assertEqual(first, ["item"])
        self.assertEqual(second, ["item"])
        self.assertEqual(len(calls), 1)  # compute only ran once -- the second call was a cache hit

    def test_invalidate_forces_the_next_read_to_recompute(self):
        calls = []

        def compute():
            calls.append(1)
            return len(calls)

        first = resource_cache.get_or_set_resource_recommendations(1, None, compute)
        resource_cache.invalidate_resource_recommendations(1)
        second = resource_cache.get_or_set_resource_recommendations(1, None, compute)

        self.assertEqual(first, 1)
        self.assertEqual(second, 2)  # invalidation forced a real recompute, not a stale hit

    def test_different_subject_codes_are_cached_separately(self):
        def compute_for(tag):
            return lambda: tag

        a = resource_cache.get_or_set_resource_recommendations(1, "BIO101", compute_for("bio"))
        b = resource_cache.get_or_set_resource_recommendations(1, "CSC2100", compute_for("csc"))

        self.assertEqual(a, "bio")
        self.assertEqual(b, "csc")

    def test_different_profiles_are_cached_separately(self):
        def compute_for(tag):
            return lambda: tag

        a = resource_cache.get_or_set_resource_recommendations(1, None, compute_for("profile1"))
        b = resource_cache.get_or_set_resource_recommendations(2, None, compute_for("profile2"))

        self.assertEqual(a, "profile1")
        self.assertEqual(b, "profile2")

    def test_invalidating_one_profile_does_not_affect_another(self):
        calls_for_2 = []

        resource_cache.get_or_set_resource_recommendations(1, None, lambda: "x")
        resource_cache.get_or_set_resource_recommendations(2, None, lambda: calls_for_2.append(1) or "y")

        resource_cache.invalidate_resource_recommendations(1)

        # Profile 2's cached value survives profile 1's invalidation.
        result = resource_cache.get_or_set_resource_recommendations(
            2, None, lambda: calls_for_2.append(1) or "y",
        )
        self.assertEqual(result, "y")
        self.assertEqual(len(calls_for_2), 1)  # still just the original compute, no second call

    def test_invalidating_resource_recommendations_clears_every_subject_variant(self):
        # This is the bug this generation-counter design exists to avoid:
        # a single cache.delete() on one key wouldn't reach every
        # subject_code variant that's been cached for this profile.
        resource_cache.get_or_set_resource_recommendations(1, "BIO101", lambda: "old-bio")
        resource_cache.get_or_set_resource_recommendations(1, "CSC2100", lambda: "old-csc")

        resource_cache.invalidate_resource_recommendations(1)

        self.assertEqual(
            resource_cache.get_or_set_resource_recommendations(1, "BIO101", lambda: "new-bio"), "new-bio",
        )
        self.assertEqual(
            resource_cache.get_or_set_resource_recommendations(1, "CSC2100", lambda: "new-csc"), "new-csc",
        )

    def test_timeline_cache_separates_by_days_and_type(self):
        a = resource_cache.get_or_set_timeline(1, 7, "", lambda: "week")
        b = resource_cache.get_or_set_timeline(1, 30, "", lambda: "month")
        c = resource_cache.get_or_set_timeline(1, 7, "file_sorted", lambda: "week-filtered")

        self.assertEqual(a, "week")
        self.assertEqual(b, "month")
        self.assertEqual(c, "week-filtered")

    def test_invalidating_timeline_clears_every_days_type_variant(self):
        resource_cache.get_or_set_timeline(1, 7, "", lambda: "old-week")
        resource_cache.get_or_set_timeline(1, 30, "", lambda: "old-month")

        resource_cache.invalidate_timeline(1)

        self.assertEqual(resource_cache.get_or_set_timeline(1, 7, "", lambda: "new-week"), "new-week")
        self.assertEqual(resource_cache.get_or_set_timeline(1, 30, "", lambda: "new-month"), "new-month")


class ResourceRecommendationSignalInvalidatesCacheTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(cache.clear)

    def test_creating_a_recommendation_invalidates_that_profiles_cache(self):
        profile = self.make_profile()
        resource_cache.get_or_set_resource_recommendations(profile.pk, None, lambda: "stale")

        ResourceRecommendation.objects.create(
            profile=profile, source_type="youtube", subject_code="BIO101", theme="cells",
            title="A video", query="cells", url="https://example.com", reason="test",
        )

        fresh = resource_cache.get_or_set_resource_recommendations(profile.pk, None, lambda: "fresh")
        self.assertEqual(fresh, "fresh")

    def test_the_resource_radar_view_reflects_a_newly_generated_recommendation(self):
        profile = self.make_profile()
        # Prime the cache the same way the view would on a first GET.
        self.client.get(reverse("resource_radar"))

        ResourceRecommendation.objects.create(
            profile=profile, source_type="youtube", subject_code="BIO101", theme="cells",
            title="Freshly added video", query="cells2", url="https://example.com", reason="test",
        )

        response = self.client.get(reverse("resource_radar"))
        self.assertContains(response, "Freshly added video")


class TimelineSignalInvalidatesCacheTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(cache.clear)

    def test_the_timeline_view_reflects_a_newly_created_activity(self):
        profile = self.make_profile()
        self.client.get(reverse("timeline"))

        LearningActivity.objects.create(
            profile=profile, activity_type="manual_note", title="Just happened",
        )

        response = self.client.get(reverse("timeline"))
        self.assertContains(response, "Just happened")

    def test_deleting_an_activity_removes_it_from_a_later_render(self):
        profile = self.make_profile()
        activity = LearningActivity.objects.create(
            profile=profile, activity_type="manual_note", title="Temporary",
        )
        first = self.client.get(reverse("timeline"))
        self.assertContains(first, "Temporary")

        activity.delete()

        second = self.client.get(reverse("timeline"))
        self.assertNotContains(second, "Temporary")
