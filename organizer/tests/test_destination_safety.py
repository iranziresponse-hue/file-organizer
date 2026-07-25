from organizer.core import destination_safety, paths

from .helpers import SandboxedPathsTestCase


class IsWithinTrustedRootsTests(SandboxedPathsTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.make_profile()

    def test_inside_profile_root_is_trusted(self):
        dest = self.profile_root / "Year 2" / "Semester 1" / "CSC2100"
        self.assertTrue(destination_safety.is_within_trusted_roots(str(dest), self.profile))

    def test_profile_root_itself_is_trusted(self):
        self.assertTrue(destination_safety.is_within_trusted_roots(str(self.profile_root), self.profile))

    def test_inside_personal_root_is_trusted(self):
        dest = paths.PERSONAL_ROOT / "Some Folder"
        self.assertTrue(destination_safety.is_within_trusted_roots(str(dest), self.profile))

    def test_inside_important_root_is_trusted(self):
        dest = paths.IMPORTANT_ROOT / "Receipts"
        self.assertTrue(destination_safety.is_within_trusted_roots(str(dest), self.profile))

    def test_sibling_folder_outside_all_roots_is_not_trusted(self):
        dest = self.profile_root.parent / "Somewhere Else Entirely"
        self.assertFalse(destination_safety.is_within_trusted_roots(str(dest), self.profile))

    def test_blank_destination_is_not_trusted(self):
        self.assertFalse(destination_safety.is_within_trusted_roots("", self.profile))

    def test_no_profile_still_checks_personal_and_important_roots(self):
        dest = paths.PERSONAL_ROOT / "Notes"
        self.assertTrue(destination_safety.is_within_trusted_roots(str(dest), None))

    def test_no_profile_and_outside_shared_roots_is_not_trusted(self):
        dest = self.profile_root  # not PERSONAL_ROOT/IMPORTANT_ROOT, and no profile to check its own root
        self.assertFalse(destination_safety.is_within_trusted_roots(str(dest), None))
