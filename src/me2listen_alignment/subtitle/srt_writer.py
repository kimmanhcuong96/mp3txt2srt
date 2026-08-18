from __future__ import annotations

import os
from pathlib import Path

from ..models import SubtitleCue
from .validator import validate_srt_text


def format_timestamp(seconds: float) -> str:
    total_ms = round(seconds * 1000)
    if total_ms < 0:
        raise ValueError("SRT timestamp cannot be negative")
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def render_srt(cues: tuple[SubtitleCue, ...]) -> str:
    blocks = [
        f"{cue.index}\n{format_timestamp(cue.start)} --> {format_timestamp(cue.end)}\n{cue.text}"
        for cue in cues
    ]
    return "\n\n".join(blocks) + "\n"


def write_srt(cues: tuple[SubtitleCue, ...], destination: Path, duration: float) -> None:
    content = render_srt(cues)
    validate_srt_text(content, cues, duration)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    os.replace(temporary, destination)

