import tempfile
import unittest
from pathlib import Path

from me2listen_alignment.script.parser import parse_script


class ScriptTests(unittest.TestCase):
    def _write(self, text: str) -> Path:
        self.directory = tempfile.TemporaryDirectory()
        path = Path(self.directory.name) / "lesson.txt"
        path.write_text(text, encoding="utf-8")
        return path

    def tearDown(self):
        if hasattr(self, "directory"):
            self.directory.cleanup()

    def test_preserves_original_lines_and_ignores_blanks(self):
        lines = parse_script(self._write("Hello, world!\n\nI’m fine.\n"))
        self.assertEqual([line.original for line in lines], ["Hello, world!", "I’m fine."])
        self.assertEqual(lines[1].tokens, ("i'm", "fine"))

    def test_trims_leading_and_trailing_whitespace(self):
        lines = parse_script(self._write("   Hello, world!   \n\tI'm fine.\t\n   \n"))
        self.assertEqual(
            [line.original for line in lines],
            ["Hello, world!", "I'm fine."],
        )

    def test_rejects_timestamps(self):
        with self.assertRaisesRegex(ValueError, "timestamps"):
            parse_script(self._write("[00:01.500] Hello.\n"))

    def test_allows_spoken_clock_times(self):
        lines = parse_script(
            self._write(
                "At 10:15 A.M. the students have recess.\n"
                "At 10:30 A.M. the students go to gym class.\n"
                "At 11:15 A.M. the students return to class.\n"
            )
        )
        self.assertEqual(len(lines), 3)

    def test_rejects_srt_timing_line(self):
        with self.assertRaisesRegex(ValueError, "timestamps"):
            parse_script(
                self._write("00:00:01,500 --> 00:00:03,000\nHello.\n")
            )

    def test_rejects_numbering_and_speaker_labels(self):
        with self.assertRaisesRegex(ValueError, "numbering"):
            parse_script(self._write("1. Hello.\n"))
        self.directory.cleanup()
        del self.directory
        with self.assertRaisesRegex(ValueError, "speaker"):
            parse_script(self._write("John: Hello.\n"))

    def test_allows_colon_inside_natural_sentence(self):
        text = "My grandparents have two sons: my father and my Uncle Bill."
        lines = parse_script(self._write(text + "\n"))
        self.assertEqual(lines[0].original, text)

    def test_rejects_explicit_metadata(self):
        with self.assertRaisesRegex(ValueError, "metadata"):
            parse_script(self._write("lesson title: My Family\n"))

    def test_rejects_non_utf8(self):
        self.directory = tempfile.TemporaryDirectory()
        path = Path(self.directory.name) / "lesson.txt"
        path.write_bytes(b"\xff\xfe")
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            parse_script(path)
