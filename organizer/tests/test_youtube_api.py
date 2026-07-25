import json
from unittest import mock

import requests

from organizer.core import youtube_api

from .helpers import SandboxedPathsTestCase


class LoadYoutubeConfigTests(SandboxedPathsTestCase):
    def test_returns_none_when_no_config_file_exists(self):
        self.assertIsNone(youtube_api.load_youtube_config())

    def test_reads_a_saved_config(self):
        self.youtube_config_path.write_text(
            json.dumps({"enabled": True, "api_key": "test-key"}), encoding="utf-8"
        )

        config = youtube_api.load_youtube_config()

        self.assertEqual(config["api_key"], "test-key")

    def test_corrupted_config_file_is_treated_as_missing(self):
        self.youtube_config_path.write_text("not valid json", encoding="utf-8")

        self.assertIsNone(youtube_api.load_youtube_config())


class SearchVideosTests(SandboxedPathsTestCase):
    def test_returns_empty_list_when_not_configured(self):
        self.assertEqual(youtube_api.search_videos("anything"), [])

    def test_returns_empty_list_when_enabled_but_no_key(self):
        self.youtube_config_path.write_text(json.dumps({"enabled": True}), encoding="utf-8")

        self.assertEqual(youtube_api.search_videos("anything"), [])

    def test_parses_a_successful_response_into_plain_dicts(self):
        self.youtube_config_path.write_text(
            json.dumps({"enabled": True, "api_key": "test-key"}), encoding="utf-8"
        )
        fake_response = mock.Mock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {
            "items": [{
                "id": {"videoId": "xyz"},
                "snippet": {
                    "title": "Trees 101",
                    "channelTitle": "CS Dojo",
                    "thumbnails": {"medium": {"url": "https://example.com/thumb.jpg"}},
                },
            }]
        }

        with mock.patch("organizer.core.youtube_api.requests.get", return_value=fake_response):
            results = youtube_api.search_videos("binary trees")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Trees 101")
        self.assertEqual(results[0]["video_id"], "xyz")
        self.assertEqual(results[0]["url"], "https://www.youtube.com/watch?v=xyz")
        self.assertEqual(results[0]["channel"], "CS Dojo")

    def test_network_failure_returns_empty_list_never_raises(self):
        self.youtube_config_path.write_text(
            json.dumps({"enabled": True, "api_key": "test-key"}), encoding="utf-8"
        )

        with mock.patch(
            "organizer.core.youtube_api.requests.get",
            side_effect=requests.ConnectionError("no network"),
        ):
            results = youtube_api.search_videos("binary trees")

        self.assertEqual(results, [])

    def test_items_missing_a_video_id_are_skipped(self):
        self.youtube_config_path.write_text(
            json.dumps({"enabled": True, "api_key": "test-key"}), encoding="utf-8"
        )
        fake_response = mock.Mock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {"items": [{"id": {}, "snippet": {"title": "No id"}}]}

        with mock.patch("organizer.core.youtube_api.requests.get", return_value=fake_response):
            results = youtube_api.search_videos("anything")

        self.assertEqual(results, [])
