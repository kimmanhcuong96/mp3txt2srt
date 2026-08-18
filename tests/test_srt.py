import tempfile
import unittest
from pathlib import Path

from me2listen_alignment.models import SubtitleCue
from me2listen_alignment.subtitle.srt_writer import render_srt, write_srt
from me2listen_alignment.subtitle.validator import validate_srt_text


class SrtTests(unittest.TestCase):
    def setUp(self):
        self.cues = (
            SubtitleCue(1, 1.02, 2.34, "Hello, how are you?", 4, 4),
            SubtitleCue(2, 3.1, 4.62, "I'm fine.", 2, 2),
        )

    def test_standard_srt_exact_text(self):
        text = render_srt(self.cues)
        self.assertIn("00:00:01,020 --> 00:00:02,340", text)
        self.assertIn("\nI'm fine.\n", text)
        validate_srt_text(text, self.cues, 5.0)

    def test_atomic_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lesson.srt"
            write_srt(self.cues, path, 5.0)
            self.assertEqual(path.read_text(encoding="utf-8"), render_srt(self.cues))
            self.assertFalse(path.with_suffix(".srt.tmp").exists())

    def test_rejects_overlap(self):
        overlapping = (
            self.cues[0],
            SubtitleCue(2, 2.0, 4.0, "I'm fine.", 2, 2),
        )
        with self.assertRaisesRegex(ValueError, "overlaps"):
            validate_srt_text(render_srt(overlapping), overlapping, 5.0)

