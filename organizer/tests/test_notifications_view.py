from django.urls import reverse

from organizer.models import Notification

from .helpers import SandboxedPathsTestCase


class NotificationsViewTests(SandboxedPathsTestCase):
    def test_lists_notifications_newest_first(self):
        profile = self.make_profile()
        older = Notification.objects.create(profile=profile, title="Older")
        newer = Notification.objects.create(profile=profile, title="Newer")

        response = self.client.get(reverse("notifications"))

        self.assertEqual(list(response.context["notifications"]), [newer, older])

    def test_mark_all_read_only_touches_the_active_profiles_notifications(self):
        profile = self.make_profile()
        other = self.make_profile(name="Other", is_active=False)
        mine = Notification.objects.create(profile=profile, title="Mine")
        theirs = Notification.objects.create(profile=other, title="Theirs")

        response = self.client.post(reverse("notifications"), {"action": "mark_all_read"})

        self.assertRedirects(response, reverse("notifications"))
        mine.refresh_from_db()
        theirs.refresh_from_db()
        self.assertIsNotNone(mine.read_at)
        self.assertIsNone(theirs.read_at)

    def test_clear_all_deletes_only_the_active_profiles_notifications(self):
        profile = self.make_profile()
        other = self.make_profile(name="Other", is_active=False)
        Notification.objects.create(profile=profile, title="Mine")
        Notification.objects.create(profile=other, title="Theirs")

        response = self.client.post(reverse("notifications"), {"action": "clear_all"})

        self.assertRedirects(response, reverse("notifications"))
        self.assertFalse(Notification.objects.filter(profile=profile).exists())
        self.assertTrue(Notification.objects.filter(profile=other).exists())

    def test_clear_all_button_only_shows_when_there_is_something_to_clear(self):
        response = self.client.get(reverse("notifications"))
        self.assertNotContains(response, 'value="clear_all"')

        profile = self.make_profile()
        Notification.objects.create(profile=profile, title="Mine")
        response = self.client.get(reverse("notifications"))
        self.assertContains(response, 'value="clear_all"')
