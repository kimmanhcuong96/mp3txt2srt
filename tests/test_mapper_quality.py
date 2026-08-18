import unittest

from me2listen_alignment.alignment.mapper import map_words_to_lines
from me2listen_alignment.config import QualityConfig
from me2listen_alignment.models import AlignedWord, ScriptLine
from me2listen_alignment.quality.analyzer import analyze_quality


class MapperQualityTests(unittest.TestCase):
    def setUp(self):
        self.lines = [
            ScriptLine(1, 1, "Hello, world!", "Hello, world!", ("hello", "world")),
            ScriptLine(2, 2, "I'm fine.", "I'm fine.", ("i'm", "fine")),
        ]
        self.words = (
            AlignedWord("Hello", "hello", 0.7, 1.0, 0.9),
            AlignedWord("world", "world", 1.1, 1.4, 0.9),
            AlignedWord("I'm", "i'm", 2.0, 2.2, 0.8),
            AlignedWord("fine", "fine", 2.3, 2.7, 0.8),
        )

    def test_maps_one_cue_per_line_from_real_words(self):
        result = map_words_to_lines(self.lines, self.words)
        self.assertEqual(len(result.cues), 2)
        self.assertEqual((result.cues[0].start, result.cues[0].end), (0.7, 1.4))
        self.assertEqual(result.cues[1].text, "I'm fine.")
        self.assertEqual(result.coverage, 1.0)

    def test_missing_line_fails_quality_without_inventing_timing(self):
        result = map_words_to_lines(self.lines, self.words[:2])
        report = analyze_quality("lesson", self.lines, result, 3.0, 0.7, QualityConfig())
        self.assertEqual(report.status, "FAIL")
        self.assertEqual(report.successfully_aligned, 1)
        self.assertIn("no aligned words", report.timing_issues[0])

    def test_long_line_is_warning_not_split(self):
        result = map_words_to_lines(self.lines, self.words)
        config = QualityConfig(long_line_characters=5)
        report = analyze_quality("lesson", self.lines, result, 3.0, 0.7, config)
        self.assertEqual(report.status, "WARNING")
        self.assertEqual(len(result.cues), len(self.lines))

