import hashlib
import json
import urllib.error
from unittest import mock

from django.test import TestCase

from organizer.core import updater


class VersionParsingTests(TestCase):
    def test_recognizes_a_newer_version(self):
        self.assertTrue(updater.is_newer("v1.2.0", current_version="1.1.0"))

    def test_recognizes_an_older_or_equal_version_as_not_newer(self):
        self.assertFalse(updater.is_newer("v1.0.0", current_version="1.1.0"))
        self.assertFalse(updater.is_newer("v1.1.0", current_version="1.1.0"))

    def test_works_without_a_leading_v(self):
        self.assertTrue(updater.is_newer("2.0.0", current_version="1.9.9"))

    def test_an_unparsable_tag_is_never_treated_as_newer(self):
        self.assertFalse(updater.is_newer("nightly-build", current_version="1.0.0"))
        self.assertFalse(updater.is_newer("", current_version="1.0.0"))


class _FakeResponse:
    def __init__(self, body, headers=None):
        self._body = body
        self._offset = 0
        self.headers = headers or {}

    def read(self, size=None):
        if size is None:
            chunk, self._offset = self._body[self._offset:], len(self._body)
            return chunk
        chunk = self._body[self._offset:self._offset + size]
        self._offset += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class CheckForUpdateTests(TestCase):
    def _release_payload(self, tag="v9.9.9", asset_name="Orch-Setup.exe", digest=None):
        asset = {"name": asset_name, "browser_download_url": "https://example.invalid/Orch-Setup.exe"}
        if digest:
            asset["digest"] = digest
        return json.dumps({"tag_name": tag, "assets": [asset]}).encode("utf-8")

    def test_reports_available_when_the_release_is_newer(self):
        with mock.patch(
            "organizer.core.updater.urllib.request.urlopen",
            return_value=_FakeResponse(self._release_payload(tag="v99.0.0")),
        ):
            result = updater.check_for_update()

        self.assertTrue(result["available"])
        self.assertEqual(result["latest_version"], "99.0.0")
        self.assertEqual(result["download_url"], "https://example.invalid/Orch-Setup.exe")
        self.assertIsNone(result["error"])

    def test_reports_unavailable_when_already_current(self):
        with mock.patch(
            "organizer.core.updater.urllib.request.urlopen",
            return_value=_FakeResponse(self._release_payload(tag=f"v{updater.CURRENT_VERSION}")),
        ):
            result = updater.check_for_update()

        self.assertFalse(result["available"])

    def test_extracts_the_sha256_digest_when_github_reports_one(self):
        with mock.patch(
            "organizer.core.updater.urllib.request.urlopen",
            return_value=_FakeResponse(
                self._release_payload(tag="v99.0.0", digest="sha256:" + "ab" * 32)
            ),
        ):
            result = updater.check_for_update()

        self.assertEqual(result["sha256"], "ab" * 32)

    def test_missing_zip_asset_is_reported_as_an_error_not_a_crash(self):
        with mock.patch(
            "organizer.core.updater.urllib.request.urlopen",
            return_value=_FakeResponse(self._release_payload(asset_name="Orch-linux.tar.gz")),
        ):
            result = updater.check_for_update()

        self.assertFalse(result["available"])
        self.assertIn(updater.ASSET_NAME, result["error"])

    def test_a_network_failure_never_raises(self):
        with mock.patch(
            "organizer.core.updater.urllib.request.urlopen",
            side_effect=urllib.error.URLError("offline"),
        ):
            result = updater.check_for_update()

        self.assertFalse(result["available"])
        self.assertIsNotNone(result["error"])

    def test_malformed_json_never_raises(self):
        with mock.patch(
            "organizer.core.updater.urllib.request.urlopen",
            return_value=_FakeResponse(b"not json"),
        ):
            result = updater.check_for_update()

        self.assertFalse(result["available"])
        self.assertIsNotNone(result["error"])


class RememberCheckResultTests(TestCase):
    def test_round_trips_through_the_cache(self):
        self.assertIsNone(updater.get_last_check())

        payload = {"available": True, "latest_version": "2.0.0"}
        updater.remember_check_result(payload)

        self.assertEqual(updater.get_last_check(), payload)


class DownloadUpdateTests(TestCase):
    def test_writes_the_downloaded_bytes_to_disk(self, tmp_name="orch_test_download.zip"):
        import tempfile
        from pathlib import Path

        destination = Path(tempfile.gettempdir()) / tmp_name
        self.addCleanup(lambda: destination.unlink(missing_ok=True))
        body = b"fake-zip-bytes"

        with mock.patch(
            "organizer.core.updater.urllib.request.urlopen",
            return_value=_FakeResponse(body, headers={"Content-Length": str(len(body))}),
        ):
            success, error = updater.download_update("https://example.invalid/Orch-windows.zip", destination)

        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertEqual(destination.read_bytes(), body)

    def test_rejects_and_deletes_a_file_that_fails_the_checksum(self):
        import tempfile
        from pathlib import Path

        destination = Path(tempfile.gettempdir()) / "orch_test_bad_checksum.zip"
        self.addCleanup(lambda: destination.unlink(missing_ok=True))
        body = b"fake-zip-bytes"
        wrong_hash = "0" * 64

        with mock.patch(
            "organizer.core.updater.urllib.request.urlopen",
            return_value=_FakeResponse(body),
        ):
            success, error = updater.download_update(
                "https://example.invalid/Orch-windows.zip", destination, expected_sha256=wrong_hash
            )

        self.assertFalse(success)
        self.assertIn("checksum", error)
        self.assertFalse(destination.exists())

    def test_accepts_a_file_that_matches_the_checksum(self):
        import tempfile
        from pathlib import Path

        destination = Path(tempfile.gettempdir()) / "orch_test_good_checksum.zip"
        self.addCleanup(lambda: destination.unlink(missing_ok=True))
        body = b"fake-zip-bytes"
        correct_hash = hashlib.sha256(body).hexdigest()

        with mock.patch(
            "organizer.core.updater.urllib.request.urlopen",
            return_value=_FakeResponse(body),
        ):
            success, error = updater.download_update(
                "https://example.invalid/Orch-windows.zip", destination, expected_sha256=correct_hash
            )

        self.assertTrue(success)
        self.assertIsNone(error)

    def test_a_network_failure_cleans_up_and_reports_an_error(self):
        import tempfile
        from pathlib import Path

        destination = Path(tempfile.gettempdir()) / "orch_test_network_fail.zip"
        destination.write_bytes(b"partial")
        self.addCleanup(lambda: destination.unlink(missing_ok=True))

        with mock.patch(
            "organizer.core.updater.urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection reset"),
        ):
            success, error = updater.download_update("https://example.invalid/Orch-windows.zip", destination)

        self.assertFalse(success)
        self.assertIsNotNone(error)
        self.assertFalse(destination.exists())


class RelaunchScriptTests(TestCase):
    def test_script_waits_for_the_old_pid_then_installs_silently_and_relaunches(self):
        script = updater.build_relaunch_script(
            4242, r"C:\Temp\Orch-Setup.exe", r"C:\Orch", r"C:\Orch\Orch.exe"
        )

        self.assertIn('"PID eq 4242"', script)
        self.assertIn(
            r'"C:\Temp\Orch-Setup.exe" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR="C:\Orch"',
            script,
        )
        self.assertIn(r'start "" "C:\Orch\Orch.exe"', script)
        self.assertTrue(script.startswith("@echo off"))


class ApplyUpdateAndRestartTests(TestCase):
    def test_writes_the_script_launches_it_detached_then_exits(self):
        from pathlib import Path

        popen_calls = []
        exit_calls = []

        updater.apply_update_and_restart(
            r"C:\Temp\Orch-Setup.exe",
            r"C:\Orch",
            r"C:\Orch\Orch.exe",
            exit_func=lambda: exit_calls.append(True),
            popen_func=lambda *args, **kwargs: popen_calls.append((args, kwargs)),
        )

        self.assertEqual(len(popen_calls), 1)
        self.assertEqual(len(exit_calls), 1)

        args, kwargs = popen_calls[0]
        command = args[0]
        self.assertEqual(command[:2], ["cmd.exe", "/c"])
        script_path = Path(command[2])
        self.assertTrue(script_path.exists())
        self.addCleanup(lambda: script_path.unlink(missing_ok=True))
        content = script_path.read_text(encoding="utf-8")
        self.assertIn("/VERYSILENT", content)
        self.assertIn(r'start "" "C:\Orch\Orch.exe"', content)


class DownloadAndApplyTests(TestCase):
    def test_returns_the_download_error_without_applying_anything_on_failure(self):
        result = {"download_url": "https://example.invalid/Orch-Setup.exe", "sha256": None}
        exit_calls = []

        with mock.patch(
            "organizer.core.updater.download_update", return_value=(False, "network down")
        ):
            success, error = updater.download_and_apply(
                result, exit_func=lambda: exit_calls.append(True)
            )

        self.assertFalse(success)
        self.assertEqual(error, "network down")
        self.assertEqual(exit_calls, [])

    def test_applies_and_exits_on_a_successful_download(self):
        result = {"download_url": "https://example.invalid/Orch-Setup.exe", "sha256": None}
        exit_calls = []
        popen_calls = []

        with mock.patch("organizer.core.updater.download_update", return_value=(True, None)):
            success, error = updater.download_and_apply(
                result,
                exit_func=lambda: exit_calls.append(True),
                popen_func=lambda *args, **kwargs: popen_calls.append((args, kwargs)),
            )

        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertEqual(len(exit_calls), 1)
        self.assertEqual(len(popen_calls), 1)
