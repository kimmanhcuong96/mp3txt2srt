import unittest

from me2listen_alignment.script.auto_transcript import (
    split_english_sentences,
    transcript_to_script_lines,
)


class AutoTranscriptTests(unittest.TestCase):
    def test_splits_punctuated_transcript_without_changing_sentence_text(self):
        text = "Hello world. How are you? I am fine!"
        self.assertEqual(
            split_english_sentences(text),
            ["Hello world.", "How are you?", "I am fine!"],
        )

    def test_creates_one_script_line_per_sentence(self):
        lines = transcript_to_script_lines("Hello world. How are you?")
        self.assertEqual([line.original for line in lines], ["Hello world.", "How are you?"])
        self.assertEqual(lines[0].tokens, ("hello", "world"))
