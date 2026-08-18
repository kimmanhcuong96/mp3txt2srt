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

    def test_rejects_numbering_and_speaker_labels(self):
        with self.assertRaisesRegex(ValueError, "numbering"):
            parse_script(self._write("1. Hello.\n"))
        self.directory.cleanup()
        del self.directory
        with self.assertRaisesRegex(ValueError, "speaker"):
            parse_script(self._write("John: Hello.\n"))

    def test_rejects_non_utf8(self):
        self.directory = tempfile.TemporaryDirectory()
        path = Path(self.directory.name) / "lesson.txt"
        path.write_bytes(b"\xff\xfe")
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            parse_script(path)
