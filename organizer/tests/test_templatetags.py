from django.test import SimpleTestCase

from organizer.templatetags.orch_extras import course_label


class CourseLabelFilterTests(SimpleTestCase):
    def test_known_code_gets_its_real_name_appended(self):
        self.assertEqual(course_label("CSC2100"), "CSC2100 - Data Structures and Algorithms")

    def test_unknown_code_is_returned_bare(self):
        self.assertEqual(course_label("made-up-code"), "made-up-code")

    def test_blank_code_passes_through(self):
        self.assertEqual(course_label(""), "")
        self.assertIsNone(course_label(None))
