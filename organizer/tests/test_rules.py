import json

from organizer.core import paths, rules

from .helpers import SandboxedPathsTestCase


class IsEbookTests(SandboxedPathsTestCase):
    def test_epub_extension_is_always_an_ebook(self):
        self.assertTrue(rules.is_ebook("random.epub", "epub"))

    def test_marker_in_filename(self):
        self.assertTrue(rules.is_ebook("Some Book [Z-Library].pdf", "pdf"))

    def test_isbn13_in_filename(self):
        self.assertTrue(rules.is_ebook("9781234567897.pdf", "pdf"))

    def test_ordinary_pdf_is_not_an_ebook(self):
        self.assertFalse(rules.is_ebook("Assignment 1.pdf", "pdf"))


class ContentCategoryTests(SandboxedPathsTestCase):
    def test_past_paper(self):
        self.assertEqual(rules.get_content_category("CSC2100 Past Paper 2024.pdf"), "03 Past Papers and Tests")

    def test_assignment(self):
        self.assertEqual(rules.get_content_category("Assignment 3.docx"), "02 Assignments and Coursework")

    def test_lecture_notes(self):
        self.assertEqual(rules.get_content_category("Week 4 Lecture Slides.pptx"), "01 Lecture Notes and Slides")

    def test_report(self):
        self.assertEqual(rules.get_content_category("Final Year Project Report.docx"), "04 Reports and Projects")

    def test_falls_back_to_reference(self):
        self.assertEqual(rules.get_content_category("Untitled document.docx"), "05 Reference and Extra Reading")


class GetDestinationTests(SandboxedPathsTestCase):
    def _write_config(self, courses=("CSC2100", "BSE2105"), year="Year 2", semester="Semester 1"):
        paths.CONFIG_PATH.write_text(json.dumps({
            "current_year": year,
            "current_semester": semester,
            "courses": list(courses),
        }))

    def _write_curriculum(self, archived=False):
        paths.CURRICULUM_PATH.write_text(json.dumps({
            "courses": [
                {
                    "code": "CSC2100",
                    "year": "Year 2",
                    "semester": "Semester 1",
                    "archived": archived,
                    "keywords": ["data structures"],
                }
            ]
        }))

    def test_in_progress_downloads_are_skipped(self):
        self.assertIsNone(rules.get_destination("movie.mp4.crdownload"))
        self.assertIsNone(rules.get_destination("movie.mp4.part"))
        self.assertIsNone(rules.get_destination("movie.mp4.tmp"))

    def test_sensitive_keyword_wins_over_everything(self):
        dest = rules.get_destination("Netflix password reset.pdf")
        self.assertEqual(dest.method, "sensitive")
        self.assertEqual(dest.path, self.personal_root / "Important")

    def test_cert_extension_is_sensitive(self):
        dest = rules.get_destination("server.pem")
        self.assertEqual(dest.method, "sensitive")

    def test_ebook_wins_over_course_match(self):
        self._write_config()
        dest = rules.get_destination("CSC2100 Data Structures [Z-Library].pdf")
        self.assertEqual(dest.method, "ebook")
        self.assertEqual(dest.path, paths.LIBRARY_INBOX)

    def test_image_goes_to_media(self):
        dest = rules.get_destination("screenshot.png")
        self.assertEqual(dest.method, "media")
        self.assertEqual(dest.path, self.personal_root / "Media" / "Images")

    def test_music_goes_to_media(self):
        dest = rules.get_destination("track.mp3")
        self.assertEqual(dest.path, self.personal_root / "Media" / "Music")

    def test_video_goes_to_media(self):
        dest = rules.get_destination("clip.mp4")
        self.assertEqual(dest.path, self.personal_root / "Media" / "Videos")

    def test_installer(self):
        dest = rules.get_destination("setup.exe")
        self.assertEqual(dest.method, "installer")
        self.assertEqual(dest.path, self.personal_root / "Installers")

    def test_archive(self):
        dest = rules.get_destination("notes.zip")
        self.assertEqual(dest.method, "archive")
        self.assertEqual(dest.path, self.personal_root / "Archives")

    def test_code_file_goes_to_work_unsorted(self):
        dest = rules.get_destination("script.py")
        self.assertEqual(dest.method, "work_unsorted")
        self.assertEqual(dest.path, self.work_unsorted)

    def test_unrecognized_extension_needs_sorting(self):
        dest = rules.get_destination("mystery.xyz")
        self.assertEqual(dest.method, "needs_sorting")
        self.assertEqual(dest.path, self.personal_root / "Documents" / "_NeedsSorting")

    def test_course_code_in_filename_matches_current_semester(self):
        self._write_config()
        dest = rules.get_destination("CSC2100 Assignment 2.docx")
        self.assertEqual(dest.method, "course_code")
        self.assertEqual(dest.course_code, "CSC2100")
        self.assertEqual(
            dest.path,
            self.school_root / "Year 2" / "Semester 1" / "CSC2100" / "02 Assignments and Coursework",
        )

    def test_topic_keyword_routes_with_no_course_code_in_name(self):
        self._write_curriculum()
        dest = rules.get_destination("Data Structures Notes.pdf")
        self.assertEqual(dest.method, "topic")
        self.assertEqual(dest.course_code, "CSC2100")
        self.assertEqual(
            dest.path,
            self.school_root / "Year 2" / "Semester 1" / "CSC2100" / "01 Lecture Notes and Slides",
        )

    def test_archived_topic_match_goes_under_archive(self):
        self._write_curriculum(archived=True)
        dest = rules.get_destination("Data Structures Notes.pdf")
        self.assertEqual(dest.method, "topic")
        self.assertEqual(
            dest.path,
            self.school_root / "_Archive" / "Year 2" / "Semester 1" / "CSC2100" / "01 Lecture Notes and Slides",
        )

    def test_course_code_wins_over_topic_match(self):
        self._write_config()
        self._write_curriculum()
        # Course code check runs before the topic-keyword check, so this
        # must resolve via course_code even though "revision" would also
        # steer get_content_category, and the curriculum has a topic match.
        dest = rules.get_destination("CSC2100 revision notes.pdf")
        self.assertEqual(dest.method, "course_code")

    def test_ai_fallback_used_when_nothing_else_matches(self):
        self._write_config()
        self._write_curriculum()
        seen = {}

        def fake_ai_classify(name, curriculum):
            seen["name"] = name
            seen["curriculum"] = curriculum
            return {"code": "CSC2100", "year": "Year 2", "semester": "Semester 1"}

        dest = rules.get_destination("mysterious file.docx", ai_classify=fake_ai_classify)

        self.assertEqual(dest.method, "ai")
        self.assertEqual(dest.course_code, "CSC2100")
        self.assertEqual(seen["name"], "mysterious file.docx")

    def test_ai_fallback_not_consulted_when_disabled(self):
        self._write_config()
        dest = rules.get_destination("mysterious file.docx", ai_classify=None)
        self.assertEqual(dest.method, "unsorted")

    def test_no_match_falls_back_to_unsorted_when_config_exists(self):
        self._write_config()
        dest = rules.get_destination("mysterious file.docx")
        self.assertEqual(dest.method, "unsorted")
        self.assertEqual(
            dest.path,
            self.school_root / "Year 2" / "Semester 1" / "_Unsorted" / "05 Reference and Extra Reading",
        )

    def test_no_match_and_no_config_falls_back_to_needs_sorting(self):
        dest = rules.get_destination("mysterious file.docx")
        self.assertEqual(dest.method, "needs_sorting")
        self.assertEqual(
            dest.path,
            self.personal_root / "Documents" / "_NeedsSorting" / "05 Reference and Extra Reading",
        )
