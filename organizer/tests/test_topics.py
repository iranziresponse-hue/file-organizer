"""Tests for the intelligent topic extraction module.

Runs the NLP components independently (no Django DB needed).
AI-powered extraction is tested for graceful failure handling.
"""

import os
import sys
import unittest

# Ensure Django settings are configured before importing models
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from organizer.core.topics import (
    _tokenize,
    _extract_keywords,
    _extract_bigrams,
    _tfidf_keywords,
    extract_topics_from_filenames,
    extract_topics_from_summaries,
    _ai_extract_topics,
)


class TestTokenize(unittest.TestCase):
    def test_basic_split(self):
        tokens = _tokenize("CSC2100_Databases_Assignment_1_Final.pdf")
        self.assertIn("csc2100", tokens)
        self.assertIn("databases", tokens)
        self.assertIn("assignment", tokens)
        self.assertIn("final", tokens)
        # '1' is a digit, should be removed
        self.assertNotIn("1", tokens)

    def test_extension_stripping(self):
        tokens = _tokenize("Lecture_Notes.docx")
        self.assertIn("lecture", tokens)
        self.assertIn("notes", tokens)
        # .docx should be stripped
        self.assertNotIn("docx", tokens)

    def test_hyphens_and_underscores(self):
        tokens = _tokenize("data-structures_and-algorithms")
        self.assertIn("data", tokens)
        self.assertIn("structures", tokens)
        self.assertIn("algorithms", tokens)


class TestExtractKeywords(unittest.TestCase):
    def test_simple_keywords(self):
        kws = _extract_keywords("CSC2100 Database Management Systems Lecture Notes Week 3", top_n=5)
        self.assertTrue(len(kws) > 0)
        self.assertTrue(len(kws) <= 5)

    def test_empty_input(self):
        kws = _extract_keywords("")
        self.assertEqual(kws, [])

    def test_stop_words_only(self):
        kws = _extract_keywords("the and for with from")
        self.assertEqual(kws, [])

    def test_frequency_ranking(self):
        kws = _extract_keywords("sql sql sql database database normalization", top_n=5)
        self.assertEqual(kws[0], "sql")
        self.assertEqual(kws[1], "database")


class TestExtractBigrams(unittest.TestCase):
    def test_bigrams_found(self):
        bgs = _extract_bigrams("Introduction to Database Management Systems")
        self.assertTrue(len(bgs) > 0)

    def test_empty_input(self):
        bgs = _extract_bigrams("")
        self.assertEqual(bgs, [])


class TestTfidfKeywords(unittest.TestCase):
    def test_multiple_texts(self):
        texts = [
            "Database normalization SQL queries indexing strategies",
            "ER diagrams schema design database modeling techniques",
            "Normalization forms functional dependencies database theory",
        ]
        kws = _tfidf_keywords(texts, top_n=6)
        self.assertTrue(len(kws) > 0)
        # Should have meaningful terms
        self.assertTrue(any(kw in str(texts).lower() for kw in kws))

    def test_single_text(self):
        kws = _tfidf_keywords(["Database normalization SQL queries"])
        self.assertTrue(len(kws) > 0)

    def test_empty_list(self):
        kws = _tfidf_keywords([])
        self.assertEqual(kws, [])


class TestExtractTopicsFromFilenames(unittest.TestCase):
    def setUp(self):
        self.filenames = [
            "CSC2100_Databases_Week3_ER_Diagrams.pdf",
            "CSC2100_SQL_Queries_Assignment.pdf",
            "CSC2100_Normalization_Notes.pdf",
            "CSC2100_Indexing_and_Performance.pdf",
            "CSC2100_Transaction_Management.pdf",
        ]

    def test_extracts_topics(self):
        topics = extract_topics_from_filenames(self.filenames, "CSC2100")
        self.assertTrue(len(topics) > 0)
        # Check structure
        topic = topics[0]
        self.assertIn("name", topic)
        self.assertIn("weight", topic)
        self.assertIn("source", topic)
        self.assertIn("evidence", topic)

    def test_topics_have_evidence(self):
        topics = extract_topics_from_filenames(self.filenames, "CSC2100")
        for t in topics:
            self.assertTrue(len(t["evidence"]) > 0)

    def test_weights_are_positive(self):
        topics = extract_topics_from_filenames(self.filenames, "CSC2100")
        for t in topics:
            self.assertGreaterEqual(t["weight"], 1)

    def test_empty_filenames(self):
        topics = extract_topics_from_filenames([], "TEST")
        self.assertEqual(topics, [])


class TestExtractTopicsFromSummaries(unittest.TestCase):
    def test_extracts_from_summaries(self):
        summaries = [
            "This document covers the principles of database normalization "
            "including first second and third normal forms",
            "SQL query optimization covering index usage query planning "
            "and execution strategies for better performance",
        ]
        filenames = ["normalization.pdf", "sql_optimization.pdf"]
        topics = extract_topics_from_summaries(summaries, filenames)
        self.assertTrue(len(topics) > 0)

    def test_empty_summaries(self):
        topics = extract_topics_from_summaries([], ["file.pdf"])
        self.assertEqual(topics, [])


class TestAiExtractTopicsFallback(unittest.TestCase):
    def test_empty_input_returns_empty(self):
        """Empty input should always return empty regardless of config."""
        topics = _ai_extract_topics("", "")
        self.assertEqual(topics, [])

    def test_ai_called_safely(self):
        """Should not crash when called (config present or not)."""
        topics = _ai_extract_topics("test.pdf", "test summary text")
        # Should either be empty (no valid config) or list of topics
        self.assertIsInstance(topics, list)


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)