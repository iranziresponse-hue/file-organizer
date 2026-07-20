from django.urls import reverse
from django.db import IntegrityError, transaction

from organizer.core import resources
from organizer.models import CourseConfig, MoveEvent, ResourceRecommendation, SubjectMemory, SubjectTheme

from .helpers import SandboxedPathsTestCase


class ResourceRecommendationEngineTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        CourseConfig.objects.create(
            profile=self.profile,
            primary_value="Year 2",
            secondary_value="Semester 1",
            groups=["CSC2100"],
        )
        self.memory = SubjectMemory.objects.create(
            profile=self.profile,
            code="CSC2100",
            title="Data Structures",
            current_focus=["trees"],
            weak_areas=["recursion"],
            resource_count=4,
        )
        SubjectTheme.objects.create(
            profile=self.profile,
            subject_memory=self.memory,
            subject_code="CSC2100",
            name="binary search trees",
            weight=12,
            source="filename",
        )

    def test_builds_youtube_and_book_discovery_links_from_subject_signal(self):
        candidates = resources.build_candidates(self.profile, limit=8)

        self.assertTrue(any(item.source_type == "youtube" for item in candidates))
        self.assertTrue(any(item.source_type == "book" for item in candidates))
        self.assertTrue(any("recursion" in item.query.lower() for item in candidates))
        self.assertTrue(all("youtube.com/results" in item.url or "openlibrary.org/search" in item.url for item in candidates))
        self.assertTrue(all("Based on" in item.reason for item in candidates))

    def test_weak_areas_rank_above_general_themes(self):
        candidates = resources.build_candidates(self.profile, limit=4)

        self.assertIn("recursion", candidates[0].theme.lower())
        self.assertGreaterEqual(candidates[0].score, candidates[-1].score)

    def test_subject_filter_limits_recommendations_to_one_subject(self):
        SubjectMemory.objects.create(
            profile=self.profile,
            code="MTH100",
            weak_areas=["limits"],
            resource_count=1,
        )

        candidates = resources.build_candidates(self.profile, subject_code="MTH100", limit=8)

        self.assertTrue(candidates)
        self.assertEqual({item.subject_code for item in candidates}, {"MTH100"})

    def test_recent_files_create_signal_when_memory_has_no_themes(self):
        empty_memory = SubjectMemory.objects.create(profile=self.profile, code="PHY101")
        MoveEvent.objects.create(
            profile=self.profile,
            filename="PHY101 circular motion notes.pdf",
            source_path="C:/Downloads/PHY101 circular motion notes.pdf",
            destination_path=str(self.profile_root / "PHY101 circular motion notes.pdf"),
            method="course_code",
            course_code="PHY101",
            success=True,
        )

        candidates = resources.build_candidates(self.profile, subject_code=empty_memory.code, limit=4)

        self.assertTrue(any("circular motion" in item.query.lower() for item in candidates))

    def test_sync_persists_without_duplicating_recommendations(self):
        first = resources.sync_recommendations(self.profile, limit=8)
        second = resources.sync_recommendations(self.profile, limit=8)

        self.assertEqual(len(first), len(second))
        self.assertEqual(ResourceRecommendation.objects.filter(profile=self.profile).count(), len(first))

    def test_status_changes_are_validated(self):
        item = resources.sync_recommendations(self.profile, limit=1)[0]

        resources.set_recommendation_status(item, "saved")
        item.refresh_from_db()

        self.assertEqual(item.status, "saved")
        with self.assertRaises(ValueError):
            resources.set_recommendation_status(item, "unknown")

    def test_dismissed_recommendations_are_excluded_from_default_query(self):
        item = resources.sync_recommendations(self.profile, limit=1)[0]
        resources.set_recommendation_status(item, "dismissed")

        visible = list(resources.recommendations_for_profile(self.profile))

        self.assertEqual(visible, [])


class ResourceRecommendationDatabaseTests(SandboxedPathsTestCase):
    def test_unique_query_per_profile_subject_and_source(self):
        profile = self.make_profile()
        payload = {
            "profile": profile,
            "subject_code": "CSC2100",
            "theme": "trees",
            "source_type": "youtube",
            "title": "Find strong video lessons for CSC2100: trees",
            "query": "CSC2100 trees lecture tutorial",
            "url": "https://www.youtube.com/results?search_query=CSC2100+trees",
        }
        ResourceRecommendation.objects.create(**payload)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ResourceRecommendation.objects.create(**payload)

    def test_recommendations_cascade_when_profile_is_deleted(self):
        profile = self.make_profile()
        ResourceRecommendation.objects.create(
            profile=profile,
            subject_code="CSC2100",
            theme="trees",
            source_type="book",
            title="Find books and study guides for CSC2100: trees",
            query="CSC2100 trees textbook",
            url="https://openlibrary.org/search?q=CSC2100+trees",
        )

        profile.delete()

        self.assertEqual(ResourceRecommendation.objects.count(), 0)


class ResourceRadarViewTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        SubjectMemory.objects.create(
            profile=self.profile,
            code="BIO101",
            weak_areas=["cell division"],
            resource_count=2,
        )

    def test_page_renders_empty_state_before_generation(self):
        response = self.client.get(reverse("resource_radar"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resource Radar")
        self.assertContains(response, "No recommendations yet")

    def test_generate_creates_recommendations(self):
        response = self.client.post(reverse("resource_radar"), {"action": "generate"})

        self.assertRedirects(response, reverse("resource_radar"))
        self.assertTrue(ResourceRecommendation.objects.filter(profile=self.profile).exists())

    def test_generate_for_one_subject_keeps_filter_in_redirect(self):
        SubjectMemory.objects.create(
            profile=self.profile,
            code="CHEM101",
            weak_areas=["bonding"],
            resource_count=1,
        )

        response = self.client.post(reverse("resource_radar"), {
            "action": "generate",
            "subject_code": "CHEM101",
        })

        self.assertRedirects(response, f"{reverse('resource_radar')}?subject=CHEM101", fetch_redirect_response=False)
        self.assertEqual(
            set(ResourceRecommendation.objects.values_list("subject_code", flat=True)),
            {"CHEM101"},
        )

    def test_user_can_save_and_dismiss_recommendation(self):
        item = resources.sync_recommendations(self.profile, limit=1)[0]

        response = self.client.post(
            reverse("resource_radar"),
            {"action": "saved", "recommendation_pk": item.pk},
        )
        self.assertRedirects(response, reverse("resource_radar"))
        item.refresh_from_db()
        self.assertEqual(item.status, "saved")

        response = self.client.post(
            reverse("resource_radar"),
            {"action": "dismissed", "recommendation_pk": item.pk},
        )
        self.assertRedirects(response, reverse("resource_radar"))
        item.refresh_from_db()
        self.assertEqual(item.status, "dismissed")

    def test_resource_radar_requires_active_profile(self):
        self.profile.is_active = False
        self.profile.save()

        response = self.client.get(reverse("resource_radar"))

        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_recommendation_renders_with_stable_hooks_for_the_ajax_layer(self):
        item = resources.sync_recommendations(self.profile, limit=1)[0]

        response = self.client.get(reverse("resource_radar"))
        content = response.content.decode()

        # Hooks resource-radar-actions.js depends on to find a row, submit
        # its action, and patch in the server's own response.
        self.assertIn('data-pk="%d"' % item.pk, content)
        self.assertIn('id="rec-actions-%d"' % item.pk, content)
        self.assertIn('data-radar-action', content)
        self.assertIn('id="saved-count"', content)
        self.assertIn('id="visible-count"', content)

    def test_dismiss_response_no_longer_lists_the_item(self):
        # This is exactly what resource-radar-actions.js checks to decide
        # whether the dismiss actually succeeded server-side.
        item = resources.sync_recommendations(self.profile, limit=1)[0]

        response = self.client.post(
            reverse("resource_radar"),
            {"action": "dismissed", "recommendation_pk": item.pk},
            follow=True,
        )

        self.assertNotIn('data-pk="%d"' % item.pk, response.content.decode())

    def test_save_response_still_lists_the_item_with_updated_action(self):
        item = resources.sync_recommendations(self.profile, limit=1)[0]

        response = self.client.post(
            reverse("resource_radar"),
            {"action": "saved", "recommendation_pk": item.pk},
            follow=True,
        )
        content = response.content.decode()

        self.assertIn('data-pk="%d"' % item.pk, content)
        self.assertIn("Unsave", content)
