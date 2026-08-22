import tempfile
import unittest
from pathlib import Path

from me2listen_alignment.config import load_config


class ConfigTests(unittest.TestCase):
    def test_rejects_timestamp_interpolation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text("alignment:\n  interpolate_method: nearest\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ignore"):
                load_config(path)

    def test_loads_nested_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(
                "alignment:\n  device: cpu\n  batch_size: 1\nquality:\n  pass_coverage: 0.98\n",
                encoding="utf-8",
            )
            config = load_config(path)
            self.assertEqual(config.alignment.device, "cpu")
            self.assertEqual(config.quality.pass_coverage, 0.98)

    def test_loads_transcription_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(
                "transcription:\n  model_name: small.en\n  device: cpu\n"
                "  compute_type: int8\n  batch_size: 2\n  language: en\n",
                encoding="utf-8",
            )
            config = load_config(path)
            self.assertEqual(config.transcription.model_name, "small.en")
            self.assertEqual(config.transcription.batch_size, 2)

    def test_rejects_non_negative_transcription_confidence_floor(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text("transcription:\n  min_avg_logprob: 0.0\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "min_avg_logprob"):
                load_config(path)

    def test_loads_and_validates_the_sentence_word_minimum(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text("transcription:\n  min_sentence_words: 8\n", encoding="utf-8")
            self.assertEqual(load_config(path).transcription.min_sentence_words, 8)
            path.write_text("transcription:\n  min_sentence_words: 0\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "min_sentence_words"):
                load_config(path)
