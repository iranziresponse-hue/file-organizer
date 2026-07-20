from django.test import SimpleTestCase

from organizer.core import makerere, makerere_curricula


class MakerereCurriculaIntegrityTests(SimpleTestCase):
    def test_every_curriculum_key_matches_a_real_programme_name(self):
        # Guards against a typo silently orphaning a curriculum entry --
        # every key here must match a programme name that actually exists
        # somewhere in makerere.py's verified COLLEGES data.
        all_programmes = {
            programme
            for college in makerere.COLLEGES
            for school in college["schools"]
            for programme in school["programmes"]
        }
        for name in makerere_curricula.CURRICULA:
            self.assertIn(name, all_programmes, f"'{name}' is not a known programme name")

    def test_every_entry_has_a_source_and_at_least_one_year(self):
        for name, data in makerere_curricula.CURRICULA.items():
            self.assertIn("source", data, name)
            self.assertTrue(data["source"].startswith("https://"), name)
            self.assertTrue(data["years"], name)

    def test_every_semester_is_a_list_of_strings(self):
        for name, data in makerere_curricula.CURRICULA.items():
            for year, semesters in data["years"].items():
                for semester, units in semesters.items():
                    self.assertIsInstance(units, list, f"{name} {year} {semester}")
                    for unit in units:
                        self.assertIsInstance(unit, str)


class GetCourseUnitsTests(SimpleTestCase):
    def test_known_programme_year_and_semester(self):
        units = makerere_curricula.get_course_units("Bachelor of Laws", "Year 1", "Semester 1")
        self.assertIn("LAW1106 - Introducing Law", units)

    def test_unknown_programme_returns_empty_list(self):
        self.assertEqual(makerere_curricula.get_course_units("Not A Real Programme", "Year 1", "Semester 1"), [])

    def test_known_programme_unknown_year_returns_empty_list(self):
        self.assertEqual(makerere_curricula.get_course_units("Bachelor of Laws", "Year 9", "Semester 1"), [])

    def test_known_programme_unknown_semester_returns_empty_list(self):
        self.assertEqual(makerere_curricula.get_course_units("Bachelor of Laws", "Year 1", "Semester 9"), [])

    def test_get_curriculum_returns_none_for_unknown_programme(self):
        self.assertIsNone(makerere_curricula.get_curriculum("Not A Real Programme"))
