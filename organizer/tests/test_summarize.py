import json
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from organizer.core import paths, summarize


def _write_pdf(path, text):
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path))
    c.drawString(72, 700, text)
    c.save()


def _write_docx(path, text):
    import docx

    document = docx.Document()
    document.add_paragraph(text)
    document.save(str(path))


class ParseStructuredTextTests(SimpleTestCase):
    def test_splits_headings_and_paragraphs(self):
        content = (
            "# The Title\n"
            "\n"
            "## First Section\n"
            "This is one paragraph.\n"
            "Still the same paragraph, wrapped onto a second line.\n"
            "\n"
            "Another paragraph entirely.\n"
        )
        blocks = summarize.parse_structured_text(content)
        self.assertEqual(blocks[0], ("h1", "The Title"))
        self.assertEqual(blocks[1], ("h2", "First Section"))
        self.assertEqual(blocks[2], ("p", "This is one paragraph. Still the same paragraph, wrapped onto a second line."))
        self.assertEqual(blocks[3], ("p", "Another paragraph entirely."))

    def test_empty_content_yields_no_blocks(self):
        self.assertEqual(summarize.parse_structured_text(""), [])

    def test_headings_deeper_than_h2_are_still_recognized_as_headings(self):
        # Models don't always stick to the "# "/"## " convention the prompt
        # asks for -- a stray "### " must become a heading, not leak through
        # as literal "###" text inside a paragraph.
        blocks = summarize.parse_structured_text("# Title\n\n### A Subsection\n\nBody text.\n")
        self.assertEqual(blocks[0], ("h1", "Title"))
        self.assertEqual(blocks[1], ("h2", "A Subsection"))
        self.assertEqual(blocks[2], ("p", "Body text."))

    def test_blank_lines_do_not_create_empty_paragraphs(self):
        blocks = summarize.parse_structured_text("\n\n\n# Title\n\n\n")
        self.assertEqual(blocks, [("h1", "Title")])

    def test_bullet_lines_become_list_items_not_literal_asterisks(self):
        # The prompt asks for plain prose, no lists, but models reach for
        # "* " bullets anyway -- these must become "li" blocks, not leak
        # through as a paragraph starting with a literal asterisk.
        blocks = summarize.parse_structured_text("# Title\n\n* First point\n* Second point\n\nClosing paragraph.\n")
        self.assertEqual(blocks[0], ("h1", "Title"))
        self.assertEqual(blocks[1], ("li", "First point"))
        self.assertEqual(blocks[2], ("li", "Second point"))
        self.assertEqual(blocks[3], ("p", "Closing paragraph."))

    def test_dash_divider_line_is_not_mistaken_for_a_bullet(self):
        # "- " needs a space after the dash to count as a bullet -- a bare
        # run of dashes must not become an empty list item.
        blocks = summarize.parse_structured_text("# Title\n\n----\n\nBody.\n")
        kinds = [kind for kind, _ in blocks]
        self.assertNotIn("li", kinds)


class RenderHtmlTests(SimpleTestCase):
    def test_wraps_consecutive_list_items_in_one_ul(self):
        html = summarize.render_html("# Title\n\n* One\n* Two\n\nAfter.\n")
        self.assertEqual(html, "<h1>Title</h1><ul><li>One</li><li>Two</li></ul><p>After.</p>")

    def test_bold_markdown_becomes_strong_tags(self):
        html = summarize.render_html("This has **bold text** in it.\n")
        self.assertEqual(html, "<p>This has <strong>bold text</strong> in it.</p>")

    def test_html_special_characters_are_escaped(self):
        html = summarize.render_html("Uses <script> and & symbols.\n")
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&amp;", html)
        self.assertNotIn("<script>", html)


class ExtractTextTests(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)

    def test_extracts_real_pdf_text(self):
        pdf_path = self.tmp_path / "notes.pdf"
        _write_pdf(pdf_path, "Data Structures Lecture One")

        text = summarize.extract_text(pdf_path)

        self.assertIn("Data Structures Lecture One", text)

    def test_extracts_real_docx_text(self):
        docx_path = self.tmp_path / "notes.docx"
        _write_docx(docx_path, "Software Engineering Assignment Two")

        text = summarize.extract_text(docx_path)

        self.assertIn("Software Engineering Assignment Two", text)

    def test_unsupported_extension_returns_empty_string(self):
        txt_path = self.tmp_path / "notes.xlsx"
        txt_path.write_bytes(b"not a real spreadsheet")

        self.assertEqual(summarize.extract_text(txt_path), "")

    def test_corrupt_file_never_raises(self):
        pdf_path = self.tmp_path / "corrupt.pdf"
        pdf_path.write_bytes(b"this is not a real pdf")

        self.assertEqual(summarize.extract_text(pdf_path), "")


class FindRelatedFilesTests(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)

    def test_finds_sibling_summarizable_files_excluding_self(self):
        main = self.tmp_path / "main.pdf"
        _write_pdf(main, "main content")
        _write_pdf(self.tmp_path / "sibling.pdf", "sibling content")
        _write_docx(self.tmp_path / "sibling.docx", "sibling docx content")
        (self.tmp_path / "image.png").write_bytes(b"not text")

        related = summarize.find_related_files(main)
        names = sorted(f.name for f in related)

        self.assertEqual(names, ["sibling.docx", "sibling.pdf"])

    def test_respects_the_limit(self):
        main = self.tmp_path / "main.pdf"
        _write_pdf(main, "main content")
        for i in range(10):
            _write_pdf(self.tmp_path / f"sibling{i}.pdf", f"content {i}")

        related = summarize.find_related_files(main, limit=3)

        self.assertEqual(len(related), 3)

    def test_missing_folder_returns_empty_list(self):
        missing = self.tmp_path / "does-not-exist" / "main.pdf"
        self.assertEqual(summarize.find_related_files(missing), [])


class GenerateSummaryTests(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)
        self.config_path = self.tmp_path / "ai_config.json"
        self.enterContext(mock.patch.object(paths, "AI_CONFIG_PATH", self.config_path))

    def _write_ai_config(self, **overrides):
        config = {
            "enabled": True,
            "api_key": "test-key",
            "model": "llama-3.1-8b-instant",
            "base_url": "https://api.groq.com/openai/v1",
        }
        config.update(overrides)
        self.config_path.write_text(json.dumps(config))

    def test_unsupported_extension_is_rejected_before_touching_ai_config(self):
        target = self.tmp_path / "spreadsheet.xlsx"
        target.write_bytes(b"x")

        content, error = summarize.generate_summary(target)

        self.assertIsNone(content)
        self.assertIn("PDF and Word", error)

    def test_missing_file_is_rejected(self):
        content, error = summarize.generate_summary(self.tmp_path / "gone.pdf")
        self.assertIsNone(content)
        self.assertIn("isn't where the log says", error)

    def test_no_ai_config_is_rejected(self):
        target = self.tmp_path / "notes.pdf"
        _write_pdf(target, "x" * 300)

        content, error = summarize.generate_summary(target)

        self.assertIsNone(content)
        self.assertIn("AI isn't configured", error)

    def test_too_little_extracted_text_is_rejected(self):
        self._write_ai_config()
        target = self.tmp_path / "notes.pdf"
        _write_pdf(target, "short")  # a single drawString call, well under MIN_SOURCE_CHARS

        content, error = summarize.generate_summary(target)

        self.assertIsNone(content)
        self.assertIn("Couldn't extract enough readable text", error)

    @mock.patch("organizer.core.summarize.requests.post")
    def test_successful_generation_sanitizes_em_dash_and_divider_lines(self, mock_post):
        self._write_ai_config()
        target = self.tmp_path / "notes.pdf"
        _write_pdf(target, "Data Structures " * 40)

        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": (
                "# Title\n\n"
                "This uses an em dash \u2014 right here.\n\n"
                "----\n\n"
                "## Section\n\nMore text.\n"
            )}}]
        }

        content, error = summarize.generate_summary(target)

        self.assertIsNone(error)
        self.assertNotIn("\u2014", content)
        self.assertNotIn("----", content)
        self.assertIn("Title", content)

    @mock.patch("organizer.core.summarize.requests.post", side_effect=TimeoutError("timed out"))
    def test_network_failure_never_raises(self, mock_post):
        self._write_ai_config()
        target = self.tmp_path / "notes.pdf"
        _write_pdf(target, "Data Structures " * 40)

        content, error = summarize.generate_summary(target)

        self.assertIsNone(content)
        self.assertIn("Couldn't reach the summary service", error)

    @mock.patch("organizer.core.summarize.requests.post")
    def test_related_files_are_included_in_the_prompt(self, mock_post):
        self._write_ai_config()
        target = self.tmp_path / "main.pdf"
        _write_pdf(target, "Main document content " * 20)
        _write_pdf(self.tmp_path / "related.pdf", "Related document content")

        mock_post.return_value.json.return_value = {"choices": [{"message": {"content": "# Title\n\nBody.\n"}}]}

        summarize.generate_summary(target)

        sent_prompt = mock_post.call_args.kwargs["json"]["messages"][0]["content"]
        self.assertIn("related.pdf", sent_prompt)


class RenderPdfTests(SimpleTestCase):
    def test_returns_valid_pdf_bytes(self):
        content = "# Title\n\n## Section\n\nSome body text.\n"
        pdf_bytes = summarize.render_pdf("notes.pdf", content)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_empty_content_still_produces_a_pdf(self):
        pdf_bytes = summarize.render_pdf("notes.pdf", "")
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
