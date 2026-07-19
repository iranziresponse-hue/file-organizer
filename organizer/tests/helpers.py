"""Shared test infrastructure. organizer.core.paths hardcodes real locations
on this machine (D:\\myDownloads, Documents\\Personal, ...), and several code
paths write to them. SandboxedPathsTestCase redirects every one of those
constants into a throwaway temp directory for the life of the test, so
nothing under test can ever touch the real filesystem. profile_root is a
ready-to-use folder for tests that need an active Profile's root_path.
"""

import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase

from organizer.core import paths


class SandboxedPathsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)

        self.profile_root = root / "Profile"
        self.personal_root = root / "Personal"
        self.downloads = root / "Downloads"
        self.downloads2 = root / "Downloads2"
        self.work_unsorted = root / "Work" / "_Unsorted"
        self.library_inbox = root / "Library" / "00 New - Sort Me"
        self.log_path = root / "organize-log.txt"

        # A profile's root and Documents\Personal already exist for real
        # users -- mirror that here so code that assumes the parent exists
        # (e.g. the config-writing views, which write _config.json without
        # mkdir'ing first) behaves the same in tests as in production.
        self.profile_root.mkdir(parents=True, exist_ok=True)
        self.personal_root.mkdir(parents=True, exist_ok=True)

        overrides = {
            "WORK_UNSORTED": self.work_unsorted,
            "PERSONAL_ROOT": self.personal_root,
            "IMPORTANT_ROOT": self.personal_root / "Important",
            "LIBRARY_INBOX": self.library_inbox,
            "LOG_PATH": self.log_path,
            "DOWNLOADS": self.downloads,
            "DOWNLOADS2": self.downloads2,
        }
        for name, value in overrides.items():
            self.enterContext(mock.patch.object(paths, name, value))

    def make_profile(self, **overrides):
        from organizer.models import Profile

        fields = {
            "name": "Test Profile",
            "purpose": "school",
            "primary_label": "Year",
            "secondary_label": "Semester",
            "root_path": str(self.profile_root),
            "is_active": True,
        }
        fields.update(overrides)
        return Profile.objects.create(**fields)
