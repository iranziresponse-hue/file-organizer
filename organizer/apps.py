from django.apps import AppConfig


class OrganizerConfig(AppConfig):
    name = 'organizer'

    def ready(self):
        from . import signals  # noqa: F401 -- registers the search-index post_save/post_delete receivers
