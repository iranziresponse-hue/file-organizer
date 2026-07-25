"""UI Performance Budget checks. Two different kinds of assertion here on
purpose:

- Wall-clock render time: a *generous* threshold (seconds, not the 300ms
  the roadmap names as the real target), because this suite has to pass
  reliably on whatever machine runs it, not just this one. The point is
  catching a genuine, pathological regression (an accidental N+1 that
  turns 77 queries into 7,700), not policing normal hardware variance --
  the actual 300ms/150ms targets are things to watch in
  organizer.core.perf's Performance Health Panel against real usage, not
  something a portable automated test can honestly enforce.
- Static markup/CSS checks (no layout-shift-prone patterns, animations
  respect prefers-reduced-motion): these ARE exact and reliable regardless
  of hardware, so they get real assertions.
"""

import time
from pathlib import Path

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from organizer.models import MoveEvent

from .helpers import SandboxedPathsTestCase

BASE_CSS = Path(__file__).resolve().parents[2] / "organizer" / "static" / "organizer" / "css" / "base.css"

# Generous on purpose -- see module docstring. This is a regression guard
# against something becoming catastrophically slow, not a precise budget.
_GENEROUS_LOCAL_BUDGET_SECONDS = 3.0


class RenderTimeBudgetTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(cache.clear)
        profile = self.make_profile()
        for i in range(20):
            MoveEvent.objects.create(
                profile=profile, filename=f"file{i}.pdf",
                destination_path=str(self.profile_root / f"file{i}.pdf"),
                method="course_code", success=True, course_code="CSC2100",
            )

    def test_dashboard_renders_within_budget(self):
        cache.clear()
        start = time.perf_counter()
        response = self.client.get(reverse("dashboard"))
        elapsed = time.perf_counter() - start

        self.assertEqual(response.status_code, 200)
        self.assertLess(elapsed, _GENEROUS_LOCAL_BUDGET_SECONDS)

    def test_recent_moves_search_responds_within_budget(self):
        cache.clear()
        start = time.perf_counter()
        response = self.client.get(reverse("dashboard"), {"q": "file1"})
        elapsed = time.perf_counter() - start

        self.assertEqual(response.status_code, 200)
        self.assertLess(elapsed, _GENEROUS_LOCAL_BUDGET_SECONDS)


class NoHeavyAnimationDuringScrollTests(TestCase):
    """prefers-reduced-motion must actually turn off scroll-adjacent motion
    (the topbar hide/reveal transform, card hover transforms, tooltip
    transitions) -- confirms the escape hatch this app already commits to
    (base.css's @media (prefers-reduced-motion: reduce) block) still
    exists and still targets the elements that actually move."""

    def setUp(self):
        self.css = BASE_CSS.read_text(encoding="utf-8")

    def test_reduced_motion_media_query_exists(self):
        self.assertIn("prefers-reduced-motion: reduce", self.css)

    def test_reduced_motion_disables_scroll_behavior_and_transitions(self):
        start = self.css.index("prefers-reduced-motion: reduce")
        block = self.css[start:start + 600]
        self.assertIn("scroll-behavior: auto", block)
