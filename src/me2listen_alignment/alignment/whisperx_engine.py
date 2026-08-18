from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import AlignmentConfig
from ..models import AlignedWord, ScriptLine
from ..script.normalizer import tokenize


@dataclass(frozen=True, slots=True)
class EngineResult:
    words: tuple[AlignedWord, ...]
    duration_seconds: float
    leading_silence_seconds: float
    silence_intervals: tuple[tuple[float, float], ...] = ()


class WhisperXEngine:
    """Load one language-specific aligner and reuse it for the whole batch."""

    sample_rate = 16_000

    def __init__(self, config: AlignmentConfig, silence_threshold_db: float):
        if sys.version_info >= (3, 14):
            raise RuntimeError("WhisperX requires Python 3.10-3.13; use the documented Python 3.12 environment")
        try:
            import torch
            import whisperx
        except ImportError as exc:
            raise RuntimeError(
                "WhisperX dependencies are missing. Activate the project virtual environment and follow README.md"
            ) from exc
        if config.device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA was requested but PyTorch cannot access an NVIDIA GPU; "
                "install the CUDA PyTorch build or set device: cpu"
            )
        self.config = config
        self.silence_threshold_db = silence_threshold_db
        self.torch = torch
        self.whisperx = whisperx
        config.model_dir.mkdir(parents=True, exist_ok=True)
        self.model, self.metadata = whisperx.load_align_model(
            language_code=config.language,
            device=config.device,
            model_name=config.model_name,
            model_dir=str(config.model_dir),
            model_cache_only=config.model_cache_only,
        )

    def align(self, audio_path: Path, lines: list[ScriptLine]) -> EngineResult:
        audio = self.whisperx.load_audio(str(audio_path))
        duration = float(len(audio) / self.sample_rate)
        if not math.isfinite(duration) or duration <= 0:
            raise RuntimeError("Audio duration must be positive")
        known_text = "\n".join(line.alignment_text for line in lines)
        transcript = [{"start": 0.0, "end": duration, "text": known_text}]
        aligned = self.whisperx.align(
            transcript=transcript,
            model=self.model,
            align_model_metadata=self.metadata,
            audio=audio,
            device=self.config.device,
            interpolate_method=self.config.interpolate_method,
            return_char_alignments=False,
            print_progress=False,
        )
        words: list[AlignedWord] = []
        for raw in aligned.get("word_segments", []):
            if raw.get("start") is None or raw.get("end") is None:
                continue
            start, end = float(raw["start"]), float(raw["end"])
            if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= duration + 0.1):
                continue
            raw_text = str(raw.get("word", ""))
            pieces = tokenize(raw_text)
            score = float(raw["score"]) if raw.get("score") is not None else None
            for piece in pieces:
                words.append(AlignedWord(raw_text.strip(), piece, start, end, score))
        leading = _detect_leading_silence(audio, self.sample_rate, self.silence_threshold_db)
        silence_intervals = _detect_silence_intervals(
            audio,
            self.sample_rate,
            self.config.boundary_silence_threshold_db,
            self.config.boundary_silence_minimum,
        ) if self.config.boundary_refinement_enabled else ()
        del audio, aligned
        if self.config.device == "cuda":
            self.torch.cuda.empty_cache()
        return EngineResult(tuple(words), duration, leading, silence_intervals)

    def close(self) -> None:
        if hasattr(self, "model"):
            del self.model
        if self.config.device == "cuda":
            self.torch.cuda.empty_cache()


def _detect_leading_silence(audio: Any, sample_rate: int, threshold_db: float) -> float:
    """Return the first sustained non-silent frame; never modify audio."""
    import numpy as np

    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if not len(values):
        return 0.0
    frame_size = max(1, round(sample_rate * 0.02))
    threshold = 10 ** (threshold_db / 20.0)
    frame_count = len(values) // frame_size
    if frame_count == 0:
        return 0.0
    frames = values[: frame_count * frame_size].reshape(frame_count, frame_size)
    rms = np.sqrt(np.mean(frames * frames, axis=1))
    active = rms >= threshold
    sustained_frames = 3
    for index in range(max(0, len(active) - sustained_frames + 1)):
        if bool(active[index : index + sustained_frames].all()):
            return round(index * frame_size / sample_rate, 3)
    return round(len(values) / sample_rate, 3)


def _detect_silence_intervals(
    audio: Any,
    sample_rate: int,
    threshold_db: float,
    minimum_duration: float,
) -> tuple[tuple[float, float], ...]:
    """Detect sustained low-energy ranges used only to tighten cue boundaries."""
    import numpy as np

    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if not len(values):
        return ()
    frame_size = max(1, round(sample_rate * 0.01))
    frame_count = len(values) // frame_size
    if frame_count == 0:
        return ()
    frames = values[: frame_count * frame_size].reshape(frame_count, frame_size)
    rms = np.sqrt(np.mean(frames * frames, axis=1))
    quiet = rms < 10 ** (threshold_db / 20.0)
    minimum_frames = max(1, math.ceil(minimum_duration * sample_rate / frame_size))
    intervals: list[tuple[float, float]] = []
    start: int | None = None
    for index, is_quiet in enumerate(quiet):
        if bool(is_quiet) and start is None:
            start = index
        if start is not None and (not bool(is_quiet) or index == len(quiet) - 1):
            end = index if not bool(is_quiet) else index + 1
            if end - start >= minimum_frames:
                intervals.append(
                    (round(start * frame_size / sample_rate, 3), round(end * frame_size / sample_rate, 3))
                )
            start = None
    return tuple(intervals)
