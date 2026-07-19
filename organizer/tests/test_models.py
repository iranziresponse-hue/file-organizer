from django.test import TestCase

from organizer.models import CourseConfig, MoveEvent


class CourseConfigTests(TestCase):
    def test_str(self):
        config = CourseConfig(current_year="Year 2", current_semester="Semester 1")
        self.assertEqual(str(config), "Year 2 / Semester 1")


class MoveEventTests(TestCase):
    def test_str(self):
        event = MoveEvent(filename="a.pdf", destination_path="D:/School/a.pdf", method="media")
        self.assertEqual(str(event), "a.pdf -> D:/School/a.pdf")

    def test_default_ordering_is_newest_first(self):
        older = MoveEvent.objects.create(filename="old.pdf", method="media")
        newer = MoveEvent.objects.create(filename="new.pdf", method="media")

        self.assertEqual(list(MoveEvent.objects.all()), [newer, older])
