"""Shared test infrastructure. organizer.core.paths hardcodes real locations
on this machine (D:\\School, D:\\myDownloads, Documents\\Personal, ...), and
several code paths write to them. SandboxedPathsTestCase redirects every one
of those constants into a throwaway temp directory for the life of the test,
so nothing under test can ever touch the real filesystem.
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

        self.school_root = root / "School"
        self.personal_root = root / "Personal"
        self.downloads = root / "Downloads"
        self.downloads2 = root / "Downloads2"
        self.work_unsorted = root / "Work" / "_Unsorted"
        self.library_inbox = root / "Library" / "00 New - Sort Me"
        self.log_path = root / "organize-log.txt"

        # D:\School and Documents\Personal already exist for real users --
        # mirror that here so code that assumes the parent exists (e.g. the
        # config_edit view, which writes _config.json without mkdir'ing
        # first) behaves the same in tests as it does in production.
        self.school_root.mkdir(parents=True, exist_ok=True)
        self.personal_root.mkdir(parents=True, exist_ok=True)

        overrides = {
            "SCHOOL_ROOT": self.school_root,
            "CONFIG_PATH": self.school_root / "_config.json",
            "CURRICULUM_PATH": self.school_root / "_curriculum_map.json",
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
