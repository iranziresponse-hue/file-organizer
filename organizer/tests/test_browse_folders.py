from django.test import TestCase
from django.urls import reverse


class BrowseFoldersViewTests(TestCase):
    def test_no_path_lists_drives(self):
        response = self.client.get(reverse("browse_folders"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data["parent"])
        self.assertIsInstance(data["folders"], list)
        # Whatever drives this machine has, C:\ should be one of them.
        self.assertTrue(any(f["name"] == "C:\\" for f in data["folders"]))

    def test_lists_subfolders_of_a_real_directory(self):
        tmp_path = self._tmp_dir()
        (tmp_path / "Alpha").mkdir()
        (tmp_path / "beta").mkdir()
        (tmp_path / "not_a_dir.txt").write_text("x")

        response = self.client.get(reverse("browse_folders"), {"path": str(tmp_path)})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["path"], str(tmp_path))
        self.assertEqual(data["parent"], str(tmp_path.parent))
        names = [f["name"] for f in data["folders"]]
        # Sorted case-insensitively, and the .txt file never appears.
        self.assertEqual(names, ["Alpha", "beta"])

    def test_hidden_and_system_junk_dirs_are_skipped(self):
        tmp_path = self._tmp_dir()
        (tmp_path / ".git").mkdir()
        (tmp_path / "$RECYCLE.BIN").mkdir()
        (tmp_path / "Visible").mkdir()

        response = self.client.get(reverse("browse_folders"), {"path": str(tmp_path)})

        names = [f["name"] for f in response.json()["folders"]]
        self.assertEqual(names, ["Visible"])

    def test_nonexistent_path_is_a_client_error_not_a_crash(self):
        response = self.client.get(reverse("browse_folders"), {"path": str(self._tmp_dir() / "does-not-exist")})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_root_of_a_drive_has_no_parent(self):
        response = self.client.get(reverse("browse_folders"), {"path": "C:\\"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["parent"])

    def _tmp_dir(self):
        import tempfile
        from pathlib import Path

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)
