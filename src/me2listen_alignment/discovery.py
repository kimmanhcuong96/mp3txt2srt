from __future__ import annotations

from pathlib import Path

from .config import AppConfig
from .models import LessonPair


def discover_pairs(config: AppConfig) -> list[LessonPair]:
    config.input_dir.mkdir(parents=True, exist_ok=True)
    audio = _index_files(config.input_dir, ".mp3")
    scripts = _index_files(config.input_dir, ".txt")
    pairs: list[LessonPair] = []
    for key in sorted(set(audio) | set(scripts)):
        audio_path = audio.get(key)
        script_path = scripts.get(key)
        existing = audio_path or script_path
        relative_stem = existing.relative_to(config.input_dir).with_suffix("")  # type: ignore[union-attr]
        name = relative_stem.as_posix()
        output_stem = config.output_dir / relative_stem
        pairs.append(
            LessonPair(
                name=name,
                audio_path=audio_path or (config.input_dir / relative_stem).with_suffix(".mp3"),
                script_path=script_path or (config.input_dir / relative_stem).with_suffix(".txt"),
                srt_path=output_stem.with_suffix(".srt"),
                output_audio_path=output_stem.with_suffix(".mp3"),
            )
        )
    return pairs


def _index_files(directory: Path, suffix: str) -> dict[str, Path]:
    indexed: dict[str, Path] = {}
    for path in directory.rglob("*"):
        if not path.is_file() or path.suffix.casefold() != suffix:
            continue
        key = path.relative_to(directory).with_suffix("").as_posix().casefold()
        if key in indexed:
            raise ValueError(
                f"Duplicate lesson path (case-insensitive) in {directory}: "
                f"{indexed[key].relative_to(directory)}, {path.relative_to(directory)}"
            )
        indexed[key] = path
    return indexed
