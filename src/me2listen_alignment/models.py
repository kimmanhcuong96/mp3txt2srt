from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True, slots=True)
class ScriptLine:
    index: int
    source_line_number: int
    original: str
    alignment_text: str
    tokens: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AlignedWord:
    text: str
    normalized: str
    start: float
    end: float
    score: float | None = None


@dataclass(frozen=True, slots=True)
class SubtitleCue:
    index: int
    start: float
    end: float
    text: str
    matched_words: int
    expected_words: int
    average_score: float | None = None


@dataclass(slots=True)
class QualityReport:
    lesson_name: str
    status: str
    total_script_lines: int
    successfully_aligned: int
    expected_words: int
    aligned_words: int
    alignment_coverage: float
    timing_issues: list[str] = field(default_factory=list)
    suspicious_lines: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    leading_silence_seconds: float | None = None
    audio_duration_seconds: float | None = None
    generated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LessonPair:
    name: str
    audio_path: Path
    script_path: Path
    srt_path: Path
    output_audio_path: Path

