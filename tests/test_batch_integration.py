import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from me2listen_alignment.alignment.whisperx_engine import EngineResult
from me2listen_alignment.batch import BatchProcessor
from me2listen_alignment.config import AppConfig
from me2listen_alignment.discovery import discover_pairs
from me2listen_alignment.jobs import JobStore
from me2listen_alignment.models import AlignedWord


class _FakeEngine:
    def __init__(self, *_args):
        pass

    def align(self, _audio_path, _lines):
        return EngineResult(
            words=(
                AlignedWord("Hello", "hello", 0.7, 1.0, 0.95),
                AlignedWord("world", "world", 1.1, 1.4, 0.95),
            ),
            duration_seconds=2.0,
            leading_silence_seconds=0.7,
        )

    def close(self):
        pass


class BatchIntegrationTests(unittest.TestCase):
    def test_pair_to_exact_srt_audio_copy_report_and_completed_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = AppConfig(
                input_dir=root / "input",
                output_dir=root / "output",
                state_db=root / "state/jobs.sqlite",
                report_dir=root / "state/reports",
                log_file=root / "logs/test.log",
                retry_count=1,
            )
            lesson_dir = config.input_dir / "course/unit-01"
            lesson_dir.mkdir(parents=True)
            source_bytes = b"original-mp3-bytes"
            (lesson_dir / "lesson.mp3").write_bytes(source_bytes)
            (lesson_dir / "lesson.en.txt").write_text("Hello, world!\n", encoding="utf-8")
            pairs = discover_pairs(config)
            store = JobStore(config.state_db)
            try:
                store.sync(pairs)
                with patch("me2listen_alignment.batch.WhisperXEngine", _FakeEngine):
                    success = BatchProcessor(config, store, printer=lambda _message: None).run()
                self.assertTrue(success)
                output_dir = config.output_dir / "course/unit-01"
                self.assertEqual((output_dir / "lesson.mp3").read_bytes(), source_bytes)
                srt = (output_dir / "lesson.srt").read_text(encoding="utf-8")
                self.assertIn("00:00:00,700 --> 00:00:01,400", srt)
                self.assertTrue(srt.endswith("Hello, world!\n"))
                report = json.loads(
                    (config.report_dir / "course/unit-01/lesson.quality.json").read_text(encoding="utf-8")
                )
                self.assertEqual(report["status"], "PASS")
                self.assertEqual(store.counts()["completed"], 1)
            finally:
                store.close()
