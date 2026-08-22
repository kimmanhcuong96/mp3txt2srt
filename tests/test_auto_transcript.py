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
        lines = transcript_to_script_lines("Hello there my dear world. How are you doing today?")
        self.assertEqual(
            [line.original for line in lines],
            ["Hello there my dear world.", "How are you doing today?"],
        )
        self.assertEqual(lines[0].tokens, ("hello", "there", "my", "dear", "world"))

    def test_merges_a_short_sentence_into_the_next_sentence(self):
        lines = transcript_to_script_lines("Hello world. How are you today?")
        self.assertEqual(
            [line.original for line in lines],
            ["Hello world. How are you today?"],
        )

    def test_chains_merge_across_multiple_short_sentences(self):
        lines = transcript_to_script_lines("Yes. OK. I understand completely.")
        self.assertEqual(
            [line.original for line in lines],
            ["Yes. OK. I understand completely."],
        )

    def test_merges_trailing_short_sentence_into_the_previous_one(self):
        lines = transcript_to_script_lines("How are you feeling today? Fine.")
        self.assertEqual(
            [line.original for line in lines],
            ["How are you feeling today? Fine."],
        )

    def test_does_not_merge_sentences_already_at_the_word_minimum(self):
        lines = transcript_to_script_lines("I am feeling very fine. How are you doing today?")
        self.assertEqual(
            [line.original for line in lines],
            ["I am feeling very fine.", "How are you doing today?"],
        )

    def test_discards_wordless_fragments_instead_of_merging_them_into_a_cue(self):
        for text in (
            "... Hello there my dear world.",
            "Hello there my dear world. ...",
        ):
            with self.subTest(text=text):
                lines = transcript_to_script_lines(text)
                self.assertEqual(
                    [line.original for line in lines],
                    ["Hello there my dear world."],
                )

    def test_honors_a_configured_word_minimum(self):
        text = "Hello world. How are you today?"
        self.assertEqual(
            [line.original for line in transcript_to_script_lines(text, 2)],
            ["Hello world.", "How are you today?"],
        )
        self.assertEqual(
            [line.original for line in transcript_to_script_lines(text, 5)],
            ["Hello world. How are you today?"],
        )
