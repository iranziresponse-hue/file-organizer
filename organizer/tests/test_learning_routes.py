import re

from django.db import IntegrityError, transaction
from django.urls import reverse

from organizer.core import learning_route, resources
from organizer.models import LearningRoute, ResourceRecommendation, SubjectMemory, SubjectTheme

from .helpers import SandboxedPathsTestCase


class LearningRouteLogicTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        self.memory = SubjectMemory.objects.create(
            profile=self.profile,
            code="CSC2100",
            title="Data Structures",
            weak_areas=["recursion"],
            current_focus=["trees"],
            resource_count=3,
        )
        SubjectTheme.objects.create(
            profile=self.profile,
            subject_memory=self.memory,
            subject_code="CSC2100",
            name="binary trees",
            weight=10,
            source="filename",
        )

    def test_route_uses_weak_area_before_general_theme(self):
        route = learning_route.create_or_refresh_route(self.profile)

        self.assertEqual(route.subject_code, "CSC2100")
        self.assertEqual(route.theme, "recursion")
        self.assertEqual(route.status, "active")

    def test_route_has_resource_summary_review_and_check_steps(self):
        route = learning_route.create_or_refresh_route(self.profile)

        self.assertEqual([step["type"] for step in route.steps], ["resource", "summary", "review", "check"])
        self.assertTrue(route.steps[0]["url"])
        self.assertIn("summary", route.steps[1]["title"].lower())
        self.assertIn("review", route.steps[2]["title"].lower())
        self.assertIn("confidence", route.steps[3]["title"].lower())

    def test_mark_step_done_advances_route_and_completes_after_all_steps(self):
        route = learning_route.create_or_refresh_route(self.profile)

        for index in range(len(route.steps)):
            route = learning_route.mark_step_done(route, index)

        self.assertEqual(route.status, "done")
        self.assertTrue(all(step["done"] for step in route.steps))

    def test_mark_step_done_rejects_invalid_index(self):
        route = learning_route.create_or_refresh_route(self.profile)

        with self.assertRaises(IndexError):
            learning_route.mark_step_done(route, 99)

    def test_route_links_existing_recommendation_when_available(self):
        recommendation = resources.sync_recommendations(self.profile, limit=1)[0]

        route = learning_route.create_or_refresh_route(
            self.profile,
            subject_code=recommendation.subject_code,
            theme=recommendation.theme,
        )

        self.assertEqual(route.recommendation, recommendation)


class LearningRouteDatabaseTests(SandboxedPathsTestCase):
    def test_profile_subject_theme_is_unique(self):
        profile = self.make_profile()
        payload = {
            "profile": profile,
            "subject_code": "BIO101",
            "theme": "cells",
            "title": "BIO101: cells",
            "steps": [],
        }
        LearningRoute.objects.create(**payload)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                LearningRoute.objects.create(**payload)

    def test_route_survives_deleted_recommendation(self):
        profile = self.make_profile()
        recommendation = ResourceRecommendation.objects.create(
            profile=profile,
            subject_code="BIO101",
            theme="cells",
            source_type="youtube",
            title="Find strong video lessons for BIO101: cells",
            query="BIO101 cells lecture tutorial",
            url="https://www.youtube.com/results?search_query=BIO101+cells",
        )
        route = LearningRoute.objects.create(
            profile=profile,
            subject_code="BIO101",
            theme="cells",
            title="BIO101: cells",
            recommendation=recommendation,
            steps=[],
        )

        recommendation.delete()
        route.refresh_from_db()

        self.assertIsNone(route.recommendation)


class LearningRouteViewTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()
        SubjectMemory.objects.create(
            profile=self.profile,
            code="MTH100",
            weak_areas=["limits"],
            resource_count=2,
        )

    def test_learning_routes_page_renders(self):
        response = self.client.get(reverse("learning_routes"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Learning Route")
        self.assertContains(response, "Build route")

    def test_generate_route_from_page(self):
        response = self.client.post(reverse("learning_routes"), {
            "action": "generate",
            "subject_code": "MTH100",
            "theme": "limits",
        })

        self.assertRedirects(response, reverse("learning_routes"))
        self.assertTrue(LearningRoute.objects.filter(profile=self.profile, subject_code="MTH100").exists())

    def test_route_renders_with_stable_hooks_for_the_ajax_layer(self):
        route = learning_route.create_or_refresh_route(self.profile, subject_code="MTH100", theme="limits")

        response = self.client.get(reverse("learning_routes"))
        content = response.content.decode()

        # Hooks learning-route-actions.js depends on to find a step, submit
        # it, and patch in the server's own response without a page reload.
        self.assertIn('data-route-pk="%d"' % route.pk, content)
        self.assertIn('data-step-index="0"', content)
        self.assertIn('id="step-actions-%d-0"' % route.pk, content)
        self.assertIn('id="route-summary-%d"' % route.pk, content)
        self.assertIn('data-learning-action', content)

    def test_mark_step_done_from_page(self):
        route = learning_route.create_or_refresh_route(self.profile, subject_code="MTH100", theme="limits")

        response = self.client.post(reverse("learning_routes"), {
            "action": "step_done",
            "route_pk": route.pk,
            "step_index": "0",
        })

        self.assertRedirects(response, reverse("learning_routes"))
        route.refresh_from_db()
        self.assertTrue(route.steps[0]["done"])

    def test_mark_step_done_response_shows_the_step_as_done(self):
        # This is exactly what learning-route-actions.js checks to decide
        # whether the action actually succeeded server-side: it reads the
        # step-actions block for this route/step and looks for the
        # "Mark done" form to be gone.
        route = learning_route.create_or_refresh_route(self.profile, subject_code="MTH100", theme="limits")

        response = self.client.post(reverse("learning_routes"), {
            "action": "step_done",
            "route_pk": route.pk,
            "step_index": "0",
        }, follow=True)

        match = re.search(
            r'id="step-actions-%d-0">(.*?)</div>' % route.pk,
            response.content.decode(),
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        self.assertNotIn("data-learning-action", match.group(1))
        self.assertIn("Done", match.group(1))

    def test_mark_step_done_with_bad_index_leaves_page_showing_the_error(self):
        route = learning_route.create_or_refresh_route(self.profile, subject_code="MTH100", theme="limits")

        response = self.client.post(reverse("learning_routes"), {
            "action": "step_done",
            "route_pk": route.pk,
            "step_index": "99",
        }, follow=True)

        self.assertContains(response, "no longer exists")

    def test_learning_routes_requires_active_profile(self):
        self.profile.is_active = False
        self.profile.save()

        response = self.client.get(reverse("learning_routes"))

        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
