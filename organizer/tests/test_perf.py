from unittest import mock

from django.test import TestCase

from organizer.core import diagnostics, perf
from organizer.models import PerformanceMetric, Profile


class MeasureTests(TestCase):
    def test_records_a_successful_operation(self):
        with perf.measure("sort_file", detail="notes.pdf"):
            pass

        metric = PerformanceMetric.objects.get()
        self.assertEqual(metric.operation, "sort_file")
        self.assertEqual(metric.detail, "notes.pdf")
        self.assertTrue(metric.success)
        self.assertGreaterEqual(metric.duration_ms, 0)

    def test_records_a_profile(self):
        profile = Profile.objects.create(name="Test", root_path="C:/x")
        with perf.measure("sort_file", profile=profile):
            pass
        self.assertEqual(PerformanceMetric.objects.get().profile, profile)

    def test_records_failure_and_still_reraises(self):
        with self.assertRaises(ValueError):
            with perf.measure("sort_file"):
                raise ValueError("boom")

        metric = PerformanceMetric.objects.get()
        self.assertFalse(metric.success)

    def test_a_broken_recording_step_never_breaks_the_wrapped_block(self):
        with mock.patch("organizer.models.PerformanceMetric.objects.create", side_effect=Exception("db down")):
            with perf.measure("sort_file"):
                result = 1 + 1

        self.assertEqual(result, 2)
        self.assertFalse(PerformanceMetric.objects.exists())


class MeasureViewTests(TestCase):
    def test_wraps_a_view_records_duration_and_query_count(self):
        @perf.measure_view
        def fake_view(request):
            list(PerformanceMetric.objects.all())
            from django.http import HttpResponse
            return HttpResponse("ok")

        from django.test import RequestFactory
        request = RequestFactory().get("/fake/")

        response = fake_view(request)

        self.assertEqual(response.status_code, 200)
        metric = PerformanceMetric.objects.get()
        self.assertEqual(metric.operation, "page_load")
        self.assertEqual(metric.detail, "fake_view")
        self.assertIsNotNone(metric.query_count)
        self.assertTrue(metric.success)

    def test_a_crashing_view_is_recorded_as_a_failed_page_load_and_still_raises(self):
        @perf.measure_view
        def broken_view(request):
            list(PerformanceMetric.objects.all())
            raise RuntimeError("boom")

        from django.test import RequestFactory
        request = RequestFactory().get("/fake/")

        with self.assertRaises(RuntimeError):
            broken_view(request)

        metric = PerformanceMetric.objects.get()
        self.assertEqual(metric.operation, "page_load")
        self.assertEqual(metric.detail, "broken_view")
        self.assertFalse(metric.success)
        self.assertIsNotNone(metric.query_count)


class PerformanceSummaryTests(TestCase):
    def test_empty_state_has_no_data_placeholders(self):
        summary = diagnostics.get_performance_summary()

        self.assertEqual(summary["files_processed_today"], 0)
        self.assertIsNone(summary["sort_avg_ms"])
        self.assertIsNone(summary["sort_slowest"])
        self.assertEqual(summary["muele_sync"], {"avg_ms": None, "count": 0})
        self.assertEqual(summary["page_loads"], [])

    def test_aggregates_recorded_metrics(self):
        PerformanceMetric.objects.create(operation="sort_file", duration_ms=120, detail="a.pdf")
        PerformanceMetric.objects.create(operation="sort_file", duration_ms=980, detail="slow.pdf")
        PerformanceMetric.objects.create(operation="muele_sync", duration_ms=4000)
        PerformanceMetric.objects.create(
            operation="page_load", duration_ms=250, query_count=12, detail="dashboard"
        )

        summary = diagnostics.get_performance_summary()

        self.assertEqual(summary["sort_avg_ms"], 550)
        self.assertEqual(summary["sort_slowest"]["detail"], "slow.pdf")
        self.assertEqual(summary["muele_sync"], {"avg_ms": 4000, "count": 1})
        self.assertEqual(len(summary["page_loads"]), 1)
        self.assertEqual(summary["page_loads"][0]["view"], "dashboard")
        self.assertEqual(summary["page_loads"][0]["avg_queries"], 12)
