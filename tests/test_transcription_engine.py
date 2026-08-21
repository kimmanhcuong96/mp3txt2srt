import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from me2listen_alignment.alignment.transcription import WhisperXTranscriptionEngine
from me2listen_alignment.config import TranscriptionConfig


class _Cuda:
    @staticmethod
    def is_available():
        return True

    @staticmethod
    def empty_cache():
        return None


class TranscriptionEngineTests(unittest.TestCase):
    def test_loads_configured_local_asr_and_returns_punctuated_segments(self):
        calls = {}
        fake_torch = types.ModuleType("torch")
        fake_torch.cuda = _Cuda()
        fake_whisperx = types.ModuleType("whisperx")

        class FakeModel:
            def transcribe(self, _audio, batch_size):
                calls["batch_size"] = batch_size
                return {"segments": [{"start": 0.0, "end": 1.0, "text": " Hello world."}]}

        def load_model(*args, **kwargs):
            calls["model_args"] = args
            calls["model_kwargs"] = kwargs
            return FakeModel()

        fake_whisperx.load_model = load_model
        fake_whisperx.load_audio = lambda _path: [0.0] * 16_000
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            sys.modules, {"torch": fake_torch, "whisperx": fake_whisperx}
        ), patch(
            "me2listen_alignment.alignment.transcription.sys.version_info", (3, 12, 10)
        ):
            config = TranscriptionConfig(model_dir=Path(directory), batch_size=2)
            engine = WhisperXTranscriptionEngine(config)
            result = engine.transcribe(Path("lesson.mp3"))
            engine.close()
        self.assertEqual(calls["model_args"], ("large-v3-turbo",))
        self.assertEqual(calls["model_kwargs"]["compute_type"], "int8")
        self.assertEqual(calls["model_kwargs"]["language"], "en")
        self.assertEqual(calls["batch_size"], 2)
        self.assertEqual(result.text, "Hello world.")

    def test_rejects_low_confidence_segments_instead_of_hallucinated_boilerplate(self):
        fake_torch = types.ModuleType("torch")
        fake_torch.cuda = _Cuda()
        fake_whisperx = types.ModuleType("whisperx")

        class FakeModel:
            def transcribe(self, _audio, batch_size):
                return {
                    "segments": [
                        {
                            "start": 1.41, "end": 29.05,
                            "text": " We'll see you next time.", "avg_logprob": -1.19,
                        },
                    ]
                }

        fake_whisperx.load_model = lambda *args, **kwargs: FakeModel()
        fake_whisperx.load_audio = lambda _path: [0.0] * 16_000
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            sys.modules, {"torch": fake_torch, "whisperx": fake_whisperx}
        ), patch(
            "me2listen_alignment.alignment.transcription.sys.version_info", (3, 12, 10)
        ):
            config = TranscriptionConfig(model_dir=Path(directory))
            engine = WhisperXTranscriptionEngine(config)
            with self.assertRaises(RuntimeError):
                engine.transcribe(Path("lesson.mp3"))
            engine.close()

    def test_keeps_segments_at_or_above_the_confidence_floor(self):
        fake_torch = types.ModuleType("torch")
        fake_torch.cuda = _Cuda()
        fake_whisperx = types.ModuleType("whisperx")

        class FakeModel:
            def transcribe(self, _audio, batch_size):
                return {
                    "segments": [
                        {"start": 0.0, "end": 1.0, "text": " Hello world.", "avg_logprob": -0.5},
                    ]
                }

        fake_whisperx.load_model = lambda *args, **kwargs: FakeModel()
        fake_whisperx.load_audio = lambda _path: [0.0] * 16_000
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            sys.modules, {"torch": fake_torch, "whisperx": fake_whisperx}
        ), patch(
            "me2listen_alignment.alignment.transcription.sys.version_info", (3, 12, 10)
        ):
            config = TranscriptionConfig(model_dir=Path(directory))
            engine = WhisperXTranscriptionEngine(config)
            result = engine.transcribe(Path("lesson.mp3"))
            engine.close()
        self.assertEqual(result.text, "Hello world.")
