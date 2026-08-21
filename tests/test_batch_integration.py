import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from me2listen_alignment.alignment.whisperx_engine import EngineResult
from me2listen_alignment.alignment.transcription import TranscriptionResult
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


class _FakeAutoEngine:
    transcript_called = False

    def __init__(self, *_args):
        pass

    def align_transcript(self, _audio_path, segments):
        self.__class__.transcript_called = bool(segments)
        words = (
            AlignedWord("Hello", "hello", 0.1, 0.3),
            AlignedWord("world", "world", 0.3, 0.6),
            AlignedWord("How", "how", 1.0, 1.2),
            AlignedWord("are", "are", 1.2, 1.4),
            AlignedWord("you", "you", 1.4, 1.7),
            AlignedWord("I", "i", 2.0, 2.1),
            AlignedWord("am", "am", 2.1, 2.3),
            AlignedWord("fine", "fine", 2.3, 2.6),
        )
        return EngineResult(words=words, duration_seconds=3.0, leading_silence_seconds=0.0)

    def close(self):
        pass


class _FakeTranscriber:
    called = False

    def __init__(self, *_args):
        pass

    def transcribe(self, _audio_path):
        self.__class__.called = True
        return TranscriptionResult(
            text="Hello world. How are you? I am fine!",
            segments=(
                {"start": 0.0, "end": 0.8, "text": "Hello world."},
                {"start": 0.9, "end": 1.8, "text": "How are you?"},
                {"start": 1.9, "end": 2.7, "text": "I am fine!"},
            ),
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

    def test_mp3_only_uses_transcription_then_generates_sentence_srt(self):
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
            config.input_dir.mkdir(parents=True)
            (config.input_dir / "lesson.mp3").write_bytes(b"original-mp3-bytes")
            pairs = discover_pairs(config)
            store = JobStore(config.state_db)
            _FakeAutoEngine.transcript_called = False
            _FakeTranscriber.called = False
            try:
                store.sync(pairs)
                with patch("me2listen_alignment.batch.WhisperXTranscriptionEngine", _FakeTranscriber), patch(
                    "me2listen_alignment.batch.WhisperXEngine", _FakeAutoEngine
                ):
                    success = BatchProcessor(config, store, printer=lambda _message: None).run()
                self.assertTrue(success)
                self.assertTrue(_FakeTranscriber.called)
                self.assertTrue(_FakeAutoEngine.transcript_called)
                srt = (config.output_dir / "lesson.srt").read_text(encoding="utf-8")
                self.assertEqual(srt.count(" --> "), 3)
                self.assertIn("Hello world.", srt)
                self.assertIn("How are you?", srt)
                self.assertIn("I am fine!", srt)
            finally:
                store.close()
