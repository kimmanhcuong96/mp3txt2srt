from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class AlignmentConfig:
    language: str = "en"
    device: str = "cuda"
    batch_size: int = 1
    model_name: str | None = None
    model_dir: Path = Path("state/models")
    model_cache_only: bool = False
    interpolate_method: str = "ignore"
    boundary_refinement_enabled: bool = True
    boundary_silence_threshold_db: float = -38.0
    boundary_silence_minimum: float = 0.08
    boundary_search_radius: float = 0.75
    boundary_speech_padding: float = 0.02
    boundary_embedded_silence_minimum: float = 0.30


@dataclass(slots=True)
class TranscriptionConfig:
    """Local English ASR settings used only when an `.en.txt` file is absent."""

    model_name: str = "large-v3-turbo"
    device: str = "cuda"
    compute_type: str = "int8"
    batch_size: int = 1
    language: str = "en"
    model_dir: Path = Path("state/models")
    model_cache_only: bool = False
    vad_method: str = "silero"
    min_avg_logprob: float = -1.0
    min_sentence_words: int = 5


@dataclass(slots=True)
class QualityConfig:
    pass_coverage: float = 0.99
    warning_coverage: float = 0.95
    long_line_characters: int = 84
    long_line_words: int = 20
    suspicious_line_coverage: float = 0.90
    low_word_score: float = 0.50
    leading_silence_minimum: float = 0.5
    leading_silence_maximum: float = 1.0
    silence_threshold_db: float = -45.0


@dataclass(slots=True)
class AppConfig:
    input_dir: Path = Path("input")
    output_dir: Path = Path("output")
    state_db: Path = Path("state/jobs.sqlite")
    report_dir: Path = Path("state/reports")
    log_file: Path = Path("logs/alignment.log")
    alignment: AlignmentConfig = field(default_factory=AlignmentConfig)
    transcription: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    retry_count: int = 2
    copy_audio_to_output: bool = True
    package_name: str = "me2listen-batch-001.zip"

    def validate(self) -> None:
        if self.retry_count < 1:
            raise ValueError("retry_count must be at least 1")
        if self.alignment.batch_size != 1:
            raise ValueError("alignment.batch_size must be 1 for the sequential v1 pipeline")
        if self.alignment.device not in {"cuda", "cpu"}:
            raise ValueError("alignment.device must be 'cuda' or 'cpu'")
        if self.transcription.device not in {"cuda", "cpu"}:
            raise ValueError("transcription.device must be 'cuda' or 'cpu'")
        if self.transcription.language != "en":
            raise ValueError("transcription.language must be 'en' in this version")
        if self.transcription.batch_size < 1:
            raise ValueError("transcription.batch_size must be at least 1")
        if not self.transcription.model_name:
            raise ValueError("transcription.model_name must not be empty")
        if not self.transcription.compute_type:
            raise ValueError("transcription.compute_type must not be empty")
        if self.transcription.min_avg_logprob >= 0:
            raise ValueError("transcription.min_avg_logprob must be negative")
        if self.transcription.min_sentence_words < 1:
            raise ValueError("transcription.min_sentence_words must be at least 1")
        if self.alignment.interpolate_method != "ignore":
            raise ValueError("alignment.interpolate_method must be 'ignore' so missing timing is never invented")
        if (
            self.alignment.boundary_silence_minimum <= 0
            or self.alignment.boundary_search_radius <= 0
            or self.alignment.boundary_embedded_silence_minimum <= 0
        ):
            raise ValueError("alignment boundary duration and search radius must be positive")
        if self.alignment.boundary_speech_padding < 0:
            raise ValueError("alignment.boundary_speech_padding cannot be negative")
        if not 0 <= self.quality.warning_coverage <= self.quality.pass_coverage <= 1:
            raise ValueError("quality coverage thresholds must satisfy 0 <= warning <= pass <= 1")
        if not 0 <= self.quality.suspicious_line_coverage <= 1 or not 0 <= self.quality.low_word_score <= 1:
            raise ValueError("line coverage and word score thresholds must be between 0 and 1")
        if self.quality.leading_silence_minimum > self.quality.leading_silence_maximum:
            raise ValueError("leading silence minimum cannot exceed maximum")
        if Path(self.package_name).name != self.package_name or not self.package_name.lower().endswith(".zip"):
            raise ValueError("package_name must be a plain .zip filename")


def _path(value: Any) -> Path:
    return value if isinstance(value, Path) else Path(str(value))


def load_config(path: Path | None = None, overrides: dict[str, Any] | None = None) -> AppConfig:
    default_path = Path(__file__).resolve().parents[2] / "config" / "default.yaml"
    selected = path or (default_path if default_path.is_file() else None)
    raw: dict[str, Any] = {}
    if selected:
        if not selected.is_file():
            raise FileNotFoundError(f"Configuration file not found: {selected}")
        loaded = yaml.safe_load(selected.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError("Configuration root must be a mapping")
        raw.update(loaded)
    if overrides:
        raw.update({key: value for key, value in overrides.items() if value is not None})

    allowed = {
        "input_dir", "output_dir", "state_db", "report_dir",
        "log_file", "alignment", "transcription", "quality", "retry_count", "copy_audio_to_output", "package_name",
    }
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"Unknown configuration keys: {', '.join(sorted(unknown))}")
    alignment_raw = raw.pop("alignment", {}) or {}
    transcription_raw = raw.pop("transcription", {}) or {}
    quality_raw = raw.pop("quality", {}) or {}
    if not isinstance(alignment_raw, dict) or not isinstance(transcription_raw, dict) or not isinstance(quality_raw, dict):
        raise ValueError("alignment, transcription, and quality configuration must be mappings")
    alignment_allowed = set(AlignmentConfig.__dataclass_fields__)
    transcription_allowed = set(TranscriptionConfig.__dataclass_fields__)
    quality_allowed = set(QualityConfig.__dataclass_fields__)
    if set(alignment_raw) - alignment_allowed:
        raise ValueError(f"Unknown alignment keys: {', '.join(sorted(set(alignment_raw) - alignment_allowed))}")
    if set(transcription_raw) - transcription_allowed:
        raise ValueError(f"Unknown transcription keys: {', '.join(sorted(set(transcription_raw) - transcription_allowed))}")
    if set(quality_raw) - quality_allowed:
        raise ValueError(f"Unknown quality keys: {', '.join(sorted(set(quality_raw) - quality_allowed))}")
    if "model_dir" in alignment_raw:
        alignment_raw["model_dir"] = _path(alignment_raw["model_dir"])
    if "model_dir" in transcription_raw:
        transcription_raw["model_dir"] = _path(transcription_raw["model_dir"])
    for key in ("input_dir", "output_dir", "state_db", "report_dir", "log_file"):
        if key in raw:
            raw[key] = _path(raw[key])
    config = AppConfig(
        **raw,
        alignment=AlignmentConfig(**alignment_raw),
        transcription=TranscriptionConfig(**transcription_raw),
        quality=QualityConfig(**quality_raw),
    )
    config.validate()
    return config
