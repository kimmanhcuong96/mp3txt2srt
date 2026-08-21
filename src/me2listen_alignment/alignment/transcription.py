from __future__ import annotations

import gc
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import TranscriptionConfig


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    text: str
    segments: tuple[dict[str, Any], ...]


class WhisperXTranscriptionEngine:
    """Temporary local ASR model used for MP3-only lessons.

    It is intentionally separate from ``WhisperXEngine`` so ASR and forced
    alignment models can never occupy GPU memory at the same time.
    """

    def __init__(self, config: TranscriptionConfig):
        if sys.version_info >= (3, 14):
            raise RuntimeError("WhisperX requires Python 3.10-3.13; use the documented Python 3.12 environment")
        try:
            import torch
            import whisperx
        except ImportError as exc:
            raise RuntimeError("WhisperX dependencies are missing. Activate the project virtual environment and follow README.md") from exc
        if config.device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested for transcription but PyTorch cannot access an NVIDIA GPU; set transcription.device: cpu")
        self.config = config
        self.torch = torch
        self.whisperx = whisperx
        config.model_dir.mkdir(parents=True, exist_ok=True)
        self.model = whisperx.load_model(
            config.model_name,
            device=config.device,
            compute_type=config.compute_type,
            language=config.language,
            download_root=str(config.model_dir),
            local_files_only=config.model_cache_only,
            vad_method=config.vad_method,
        )

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        try:
            audio = self.whisperx.load_audio(str(audio_path))
        except (OSError, RuntimeError, ValueError) as exc:
            raise RuntimeError(f"audio load failed: {audio_path}: {exc}") from exc
        try:
            raw = self.model.transcribe(audio, batch_size=self.config.batch_size)
        except RuntimeError as exc:
            message = str(exc)
            if "out of memory" in message.casefold():
                raise RuntimeError(f"CUDA OOM during transcription: {audio_path}") from exc
            raise RuntimeError(f"transcription failed: {audio_path}: {message}") from exc
        finally:
            del audio
        raw_segments = raw.get("segments", []) if isinstance(raw, dict) else []
        segments = tuple(
            {"start": segment.get("start"), "end": segment.get("end"), "text": str(segment.get("text", "")).strip()}
            for segment in raw_segments
            if isinstance(segment, dict)
            and str(segment.get("text", "")).strip()
            and _is_confident(segment, self.config.min_avg_logprob)
        )
        text = " ".join(segment["text"] for segment in segments).strip()
        if not text or not segments:
            raise RuntimeError(f"transcription failed: no confident spoken English text found in {audio_path}")
        return TranscriptionResult(text=text, segments=segments)

    def close(self) -> None:
        if hasattr(self, "model"):
            del self.model
        gc.collect()
        if self.config.device == "cuda":
            self.torch.cuda.empty_cache()


def _is_confident(segment: dict[str, Any], min_avg_logprob: float) -> bool:
    """Reject segments faster-whisper itself would treat as no-speech/hallucinated.

    WhisperX's batched pipeline skips faster-whisper's own ``logprob_threshold``
    safety check, so a long low-confidence window (background music, silence, an
    unclear voice) can decode into a single confident-sounding boilerplate phrase
    (e.g. "We'll see you next time.") repeated for every chunk. ``avg_logprob`` is
    still present on each segment and is what that check would have used.
    """
    avg_logprob = segment.get("avg_logprob")
    return avg_logprob is None or float(avg_logprob) >= min_avg_logprob
