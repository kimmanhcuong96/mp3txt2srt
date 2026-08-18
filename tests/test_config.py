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

