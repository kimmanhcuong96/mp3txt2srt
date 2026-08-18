from __future__ import annotations

import re

from ..models import SubtitleCue

TIMING_LINE = re.compile(
    r"^(\d{2,}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2,}):(\d{2}):(\d{2}),(\d{3})$"
)


def _seconds(groups: tuple[str, ...]) -> float:
    hours, minutes, seconds, milliseconds = map(int, groups)
    if minutes >= 60 or seconds >= 60:
        raise ValueError("Invalid SRT timestamp component")
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000


def validate_srt_text(content: str, expected: tuple[SubtitleCue, ...], duration: float) -> None:
    blocks = re.split(r"\r?\n\r?\n", content.strip()) if content.strip() else []
    if len(blocks) != len(expected):
        raise ValueError(f"SRT cue count {len(blocks)} does not match script line count {len(expected)}")
    previous_end = -1.0
    for position, (block, cue) in enumerate(zip(blocks, expected), 1):
        parts = block.splitlines()
        if len(parts) != 3:
            raise ValueError(f"SRT cue {position} must contain exactly three lines")
        if parts[0] != str(position) or cue.index != position:
            raise ValueError(f"SRT sequence number {position} is invalid")
        match = TIMING_LINE.fullmatch(parts[1])
        if not match:
            raise ValueError(f"SRT cue {position} has invalid timestamp syntax")
        start = _seconds(match.groups()[:4])
        end = _seconds(match.groups()[4:])
        if start >= end:
            raise ValueError(f"SRT cue {position} must satisfy start < end")
        if start < previous_end:
            raise ValueError(f"SRT cue {position} overlaps the previous cue")
        if end > duration + 0.051:
            raise ValueError(f"SRT cue {position} extends beyond audio duration")
        if not parts[2] or parts[2] != cue.text:
            raise ValueError(f"SRT cue {position} text does not exactly match the original script")
        previous_end = end

