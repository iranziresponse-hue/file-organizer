from django.test import SimpleTestCase

from organizer.core import makerere


class MakerereDataIntegrityTests(SimpleTestCase):
    def test_ten_colleges_are_present(self):
        self.assertEqual(len(makerere.COLLEGES), 10)

    def test_no_duplicate_college_codes(self):
        codes = [c["code"] for c in makerere.COLLEGES]
        self.assertEqual(len(codes), len(set(codes)))

    def test_mubs_is_not_included(self):
        # MUBS is a separate, affiliated institution, not a Makerere college.
        names = [c["name"] for c in makerere.COLLEGES]
        self.assertFalse(any("business school" in n.lower() for n in names))

    def test_every_college_has_at_least_one_school(self):
        for college in makerere.COLLEGES:
            self.assertTrue(college["schools"], f"{college['code']} has no schools")

    def test_every_school_has_a_name_and_a_programmes_list(self):
        for college in makerere.COLLEGES:
            for school in college["schools"]:
                self.assertIn("name", school)
                self.assertIsInstance(school["programmes"], list)

    def test_no_duplicate_school_names_within_a_college(self):
        for college in makerere.COLLEGES:
            names = [s["name"] for s in college["schools"]]
            self.assertEqual(len(names), len(set(names)), college["code"])

    def test_known_colleges_present_by_code(self):
        codes = {c["code"] for c in makerere.COLLEGES}
        for expected in ("CAES", "COBAMS", "COCIS", "CEES", "CEDAT", "CHS", "CHUSS", "CONAS", "COVAB", "LAW"):
            self.assertIn(expected, codes)


class MakerereHelperTests(SimpleTestCase):
    def test_get_college_by_code(self):
        college = makerere.get_college("COCIS")
        self.assertEqual(college["name"], "College of Computing and Information Sciences")

    def test_get_college_unknown_code_returns_none(self):
        self.assertIsNone(makerere.get_college("NOPE"))

    def test_get_college_by_name(self):
        college = makerere.get_college_by_name("College of Computing and Information Sciences")
        self.assertEqual(college["code"], "COCIS")

    def test_get_college_by_name_unknown_returns_none(self):
        self.assertIsNone(makerere.get_college_by_name("Not A Real College"))

    def test_schools_for_known_college(self):
        schools = makerere.schools_for("COCIS")
        names = [s["name"] for s in schools]
        self.assertIn("School of Computing and Informatics Technology", names)
        self.assertIn("East African School of Library and Information Science", names)

    def test_schools_for_unknown_college_is_empty(self):
        self.assertEqual(makerere.schools_for("NOPE"), [])

    def test_get_school(self):
        school = makerere.get_school("COCIS", "School of Computing and Informatics Technology")
        self.assertIn("Bachelor of Science in Computer Science", school["programmes"])

    def test_get_school_unknown_returns_none(self):
        self.assertIsNone(makerere.get_school("COCIS", "Not A Real School"))

    def test_as_json_shape(self):
        data = makerere.as_json()
        self.assertIn("COCIS", data)
        self.assertEqual(data["COCIS"]["name"], "College of Computing and Information Sciences")
        self.assertIsInstance(data["COCIS"]["schools"], list)
