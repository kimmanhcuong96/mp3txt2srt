import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from me2listen_alignment.alignment.whisperx_engine import WhisperXEngine
from me2listen_alignment.config import AlignmentConfig
from me2listen_alignment.models import ScriptLine


class _Cuda:
    @staticmethod
    def is_available():
        return True

    @staticmethod
    def empty_cache():
        return None


class WhisperXEngineTests(unittest.TestCase):
    def test_uses_known_transcript_alignment_without_asr(self):
        calls = {}
        fake_torch = types.ModuleType("torch")
        fake_torch.cuda = _Cuda()
        fake_whisperx = types.ModuleType("whisperx")

        def load_align_model(**kwargs):
            calls["load"] = kwargs
            return object(), {"language": "en"}

        def load_audio(_path):
            return [0.0] * 32_000

        def align(**kwargs):
            calls["align"] = kwargs
            return {
                "word_segments": [
                    {"word": "Hello", "start": 0.7, "end": 1.0, "score": 0.9}
                ]
            }

        fake_whisperx.load_align_model = load_align_model
        fake_whisperx.load_audio = load_audio
        fake_whisperx.align = align
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            sys.modules, {"torch": fake_torch, "whisperx": fake_whisperx}
        ), patch(
            "me2listen_alignment.alignment.whisperx_engine._detect_leading_silence",
            return_value=0.7,
        ), patch(
            "me2listen_alignment.alignment.whisperx_engine.sys.version_info", (3, 12, 10)
        ):
            config = AlignmentConfig(model_dir=Path(directory))
            engine = WhisperXEngine(config, -45.0)
            line = ScriptLine(1, 1, "Hello.", "Hello.", ("hello",))
            result = engine.align(Path("lesson.mp3"), [line])
            engine.close()
        self.assertEqual(calls["load"]["language_code"], "en")
        self.assertEqual(calls["align"]["transcript"][0]["text"], "Hello.")
        self.assertEqual(calls["align"]["interpolate_method"], "ignore")
        self.assertNotIn("transcribe", calls)
        self.assertEqual(result.words[0].normalized, "hello")

    def test_aligns_whisper_transcription_segments(self):
        calls = {}
        fake_torch = types.ModuleType("torch")
        fake_torch.cuda = _Cuda()
        fake_whisperx = types.ModuleType("whisperx")

        fake_whisperx.load_align_model = lambda **_kwargs: (object(), {"language": "en"})
        fake_whisperx.load_audio = lambda _path: [0.0] * 32_000
        fake_whisperx.align = lambda **kwargs: calls.setdefault("align", kwargs) or {"word_segments": []}
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            sys.modules, {"torch": fake_torch, "whisperx": fake_whisperx}
        ), patch(
            "me2listen_alignment.alignment.whisperx_engine._detect_leading_silence", return_value=0.0
        ), patch(
            "me2listen_alignment.alignment.whisperx_engine.sys.version_info", (3, 12, 10)
        ):
            engine = WhisperXEngine(AlignmentConfig(model_dir=Path(directory)), -45.0)
            engine.align_transcript(
                Path("lesson.mp3"), ({"start": 0.2, "end": 1.5, "text": "Hello world."},)
            )
            engine.close()
        self.assertEqual(calls["align"]["transcript"], [
            {"start": 0.2, "end": 1.5, "text": "Hello world."}
        ])
