import unittest

import numpy as np

from me2listen_alignment.alignment.boundary import refine_cue_boundaries
from me2listen_alignment.alignment.whisperx_engine import _detect_silence_intervals
from me2listen_alignment.models import AlignedWord, SubtitleCue


class BoundaryRefinementTests(unittest.TestCase):
    def test_separates_adjacent_cues_at_measured_silence_edges(self):
        cues = (
            SubtitleCue(1, 0.68, 6.362, "First.", 1, 1),
            SubtitleCue(2, 6.362, 9.023, "Second.", 1, 1),
            SubtitleCue(3, 9.023, 11.784, "Third.", 1, 1),
        )
        silences = (
            (0.0, 0.344),
            (1.76, 3.58),
            (5.592, 6.283),
            (8.177, 8.959),
            (10.738, 11.734),
        )

        words_by_line = (
            (AlignedWord("Today", "today", 0.68, 4.061, 0.661),),
            (AlignedWord("Second", "second", 6.362, 8.0, 0.9),),
            (AlignedWord("Third", "third", 9.023, 10.5, 0.9),),
        )
        refined = refine_cue_boundaries(
            cues, silences, 12.0, 0.75, 0.02, words_by_line, 0.30
        )

        self.assertAlmostEqual(refined[0].start, 3.56)
        self.assertAlmostEqual(refined[0].end, 5.612)
        self.assertAlmostEqual(refined[1].start, 6.263)
        self.assertAlmostEqual(refined[1].end, 8.197)
        self.assertAlmostEqual(refined[2].start, 8.939)
        self.assertAlmostEqual(refined[2].end, 11.784)

    def test_keeps_whisperx_timing_when_no_reliable_silence_exists(self):
        cues = (
            SubtitleCue(1, 1.0, 2.0, "First.", 1, 1),
            SubtitleCue(2, 2.0, 3.0, "Second.", 1, 1),
        )
        self.assertEqual(refine_cue_boundaries(cues, (), 4.0, 0.75, 0.02), cues)

    def test_removes_unlisted_outro_when_last_word_spans_a_long_silence(self):
        cues = (SubtitleCue(1, 1.0, 6.0, "Target phrase.", 2, 2),)
        words = ((
            AlignedWord("Target", "target", 1.0, 2.0, 0.9),
            AlignedWord("phrase", "phrase", 2.5, 6.0, 0.7),
        ),)
        refined = refine_cue_boundaries(
            cues, ((3.0, 4.0),), 7.0, 0.75, 0.02, words, 0.30
        )
        self.assertAlmostEqual(refined[0].end, 3.02)

    def test_detects_sustained_low_energy_interval(self):
        sample_rate = 1000
        audio = np.concatenate(
            [
                np.full(200, 0.1, dtype=np.float32),
                np.zeros(300, dtype=np.float32),
                np.full(200, 0.1, dtype=np.float32),
            ]
        )
        self.assertEqual(
            _detect_silence_intervals(audio, sample_rate, -38.0, 0.08),
            ((0.2, 0.5),),
        )
