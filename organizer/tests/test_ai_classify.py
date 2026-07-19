import json
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from organizer.core import ai_classify, paths

CURRICULUM = [
    {"code": "CSC2100", "keywords": ["data structures"]},
    {"code": "BSE2105", "keywords": ["software engineering"]},
]


class AiClassifyTestCase(SimpleTestCase):
    """Base class: points paths.AI_CONFIG_PATH at a throwaway file instead
    of the real, gitignored ai_config.json in the project root."""

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.config_path = Path(self._tmp.name) / "ai_config.json"
        self.enterContext(mock.patch.object(paths, "AI_CONFIG_PATH", self.config_path))

    def _write_config(self, **overrides):
        config = {
            "enabled": True,
            "api_key": "test-key",
            "model": "llama-3.1-8b-instant",
            "base_url": "https://api.groq.com/openai/v1",
        }
        config.update(overrides)
        self.config_path.write_text(json.dumps(config))


class LoadAiConfigTests(AiClassifyTestCase):
    def test_missing_file_returns_none(self):
        self.assertIsNone(ai_classify.load_ai_config())

    def test_malformed_json_returns_none(self):
        self.config_path.write_text("{not valid json")
        self.assertIsNone(ai_classify.load_ai_config())

    def test_valid_file_is_loaded(self):
        self._write_config()
        config = ai_classify.load_ai_config()
        self.assertEqual(config["model"], "llama-3.1-8b-instant")


class ClassifyTests(AiClassifyTestCase):
    def test_returns_none_when_no_config_file(self):
        self.assertIsNone(ai_classify.classify("some file.pdf", CURRICULUM))

    def test_returns_none_when_disabled(self):
        self._write_config(enabled=False)
        self.assertIsNone(ai_classify.classify("some file.pdf", CURRICULUM))

    def test_returns_none_without_api_key(self):
        self._write_config(api_key="")
        self.assertIsNone(ai_classify.classify("some file.pdf", CURRICULUM))

    def test_returns_none_without_curriculum(self):
        self._write_config()
        self.assertIsNone(ai_classify.classify("some file.pdf", []))
        self.assertIsNone(ai_classify.classify("some file.pdf", None))

    @mock.patch("organizer.core.ai_classify.requests.post")
    def test_matches_returned_course_code(self, mock_post):
        self._write_config()
        mock_post.return_value.json.return_value = {"choices": [{"message": {"content": "CSC2100"}}]}

        result = ai_classify.classify("mystery file.pdf", CURRICULUM)

        self.assertEqual(result["code"], "CSC2100")
        sent_body = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent_body["model"], "llama-3.1-8b-instant")
        self.assertIn("mystery file.pdf", sent_body["messages"][0]["content"])
        self.assertEqual(mock_post.call_args.kwargs["headers"]["Authorization"], "Bearer test-key")

    @mock.patch("organizer.core.ai_classify.requests.post")
    def test_none_response_means_no_match(self, mock_post):
        self._write_config()
        mock_post.return_value.json.return_value = {"choices": [{"message": {"content": "NONE"}}]}

        self.assertIsNone(ai_classify.classify("mystery file.pdf", CURRICULUM))

    @mock.patch("organizer.core.ai_classify.requests.post")
    def test_unknown_course_code_returns_none(self, mock_post):
        self._write_config()
        mock_post.return_value.json.return_value = {"choices": [{"message": {"content": "ZZZ9999"}}]}

        self.assertIsNone(ai_classify.classify("mystery file.pdf", CURRICULUM))

    @mock.patch("organizer.core.ai_classify.requests.post", side_effect=TimeoutError("timed out"))
    def test_network_failure_never_raises(self, mock_post):
        self._write_config()
        logged = []

        result = ai_classify.classify("mystery file.pdf", CURRICULUM, log=logged.append)

        self.assertIsNone(result)
        self.assertTrue(logged)
        self.assertIn("mystery file.pdf", logged[0])

    @mock.patch("organizer.core.ai_classify.requests.post")
    def test_malformed_response_never_raises(self, mock_post):
        self._write_config()
        mock_post.return_value.json.return_value = {"unexpected": "shape"}

        self.assertIsNone(ai_classify.classify("mystery file.pdf", CURRICULUM))
