from django.test import TestCase

from organizer.models import CourseConfig, MoveEvent, Profile


class ProfileTests(TestCase):
    def test_str(self):
        profile = Profile(name="University")
        self.assertEqual(str(profile), "University")

    def test_only_one_profile_can_be_active(self):
        first = Profile.objects.create(name="School", root_path="C:/School", is_active=True)
        second = Profile.objects.create(name="Online", root_path="C:/Online", is_active=True)

        first.refresh_from_db()
        second.refresh_from_db()

        self.assertFalse(first.is_active)
        self.assertTrue(second.is_active)
        self.assertEqual(Profile.get_active(), second)

    def test_saving_inactive_profile_does_not_disturb_the_active_one(self):
        active = Profile.objects.create(name="School", root_path="C:/School", is_active=True)
        other = Profile.objects.create(name="Online", root_path="C:/Online", is_active=False)

        other.name = "Online Courses"
        other.save()

        active.refresh_from_db()
        self.assertTrue(active.is_active)

    def test_get_active_with_no_active_profile(self):
        Profile.objects.create(name="School", root_path="C:/School", is_active=False)
        self.assertIsNone(Profile.get_active())


class CourseConfigTests(TestCase):
    def test_str(self):
        profile = Profile.objects.create(name="School", root_path="C:/School")
        config = CourseConfig(profile=profile, primary_value="Year 2", secondary_value="Semester 1")
        self.assertEqual(str(config), "Year 2 / Semester 1")


class MoveEventTests(TestCase):
    def test_str(self):
        event = MoveEvent(filename="a.pdf", destination_path="D:/School/a.pdf", method="media")
        self.assertEqual(str(event), "a.pdf -> D:/School/a.pdf")

    def test_default_ordering_is_newest_first(self):
        older = MoveEvent.objects.create(filename="old.pdf", method="media")
        newer = MoveEvent.objects.create(filename="new.pdf", method="media")

        self.assertEqual(list(MoveEvent.objects.all()), [newer, older])

    def test_survives_profile_deletion(self):
        profile = Profile.objects.create(name="School", root_path="C:/School")
        event = MoveEvent.objects.create(filename="a.pdf", method="media", profile=profile)

        profile.delete()
        event.refresh_from_db()

        self.assertIsNone(event.profile)
