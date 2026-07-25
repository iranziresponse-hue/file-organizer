from organizer.core import decision

from .helpers import SandboxedPathsTestCase


class DetectSensitiveTests(SandboxedPathsTestCase):
    def test_password_keyword_is_sensitive(self):
        self.assertTrue(decision.detect_sensitive("banking password.pdf", "pdf"))

    def test_private_key_extension_is_sensitive(self):
        self.assertTrue(decision.detect_sensitive("id_rsa.pem", "pem"))

    def test_kdbx_extension_is_sensitive(self):
        self.assertTrue(decision.detect_sensitive("vault.kdbx", "kdbx"))

    def test_ordinary_document_is_not_sensitive(self):
        self.assertFalse(decision.detect_sensitive("Assignment 1.docx", "docx"))


class ClassifyGlobalCategoryTests(SandboxedPathsTestCase):
    def test_image_is_media(self):
        self.assertEqual(decision.classify_global_category("photo.png", "png"), "media")

    def test_zip_is_archive(self):
        self.assertEqual(decision.classify_global_category("bundle.zip", "zip"), "archives")

    def test_exe_is_installer(self):
        self.assertEqual(decision.classify_global_category("setup.exe", "exe"), "installers")

    def test_python_file_is_code(self):
        self.assertEqual(decision.classify_global_category("script.py", "py"), "code")

    def test_epub_is_ebook(self):
        self.assertEqual(decision.classify_global_category("novel.epub", "epub"), "ebooks")

    def test_ebook_marker_wins_over_extension(self):
        # A PDF from a known ebook source is an ebook, not a generic document.
        self.assertEqual(decision.classify_global_category("Some Book [Z-Library].pdf", "pdf"), "ebooks")

    def test_ordinary_document_matches_no_category(self):
        self.assertIsNone(decision.classify_global_category("Assignment 1.docx", "docx"))


class ScoreConfidenceTests(SandboxedPathsTestCase):
    def test_no_signals_scores_zero(self):
        self.assertEqual(decision.score_confidence(), 0)

    def test_explicit_rule_match_scores_fifty(self):
        self.assertEqual(decision.score_confidence(explicit_rule_match=True), 50)

    def test_signals_stack_additively(self):
        score = decision.score_confidence(
            extension_category_match=True,  # +20
            filename_keyword_match=True,  # +15
            destination_exists=True,  # +10
        )
        self.assertEqual(score, 45)

    def test_prior_rejection_lowers_a_previously_high_score(self):
        without_rejection = decision.score_confidence(extension_category_match=True, destination_exists=True)
        with_rejection = decision.score_confidence(
            extension_category_match=True, destination_exists=True, prior_rejected=True
        )
        self.assertEqual(without_rejection, 30)
        self.assertEqual(with_rejection, 0)  # clamped at zero, not negative

    def test_prior_approved_boost_uses_the_rules_own_value_not_a_fixed_constant(self):
        self.assertEqual(decision.score_confidence(prior_approved_boost=40), 40)

    def test_score_never_exceeds_one_hundred(self):
        score = decision.score_confidence(
            explicit_rule_match=True,  # 50
            exact_subject_match=True,  # 45
            prior_approved_boost=25,  # 25
            extension_category_match=True,  # 20
        )
        self.assertEqual(score, 100)
