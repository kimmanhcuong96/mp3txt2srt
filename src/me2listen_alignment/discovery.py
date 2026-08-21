from __future__ import annotations

from pathlib import Path

from .config import AppConfig
from .models import LessonPair

SCRIPT_SUFFIX = ".en.txt"


def discover_pairs(config: AppConfig) -> list[LessonPair]:
    config.input_dir.mkdir(parents=True, exist_ok=True)
    audio = _index_audio_files(config.input_dir)
    scripts = _index_files(config.input_dir, SCRIPT_SUFFIX)
    pairs: list[LessonPair] = []
    for key in sorted(set(audio) | set(scripts)):
        audio_path = audio.get(key)
        script_path = scripts.get(key)
        existing = audio_path or script_path
        relative_stem = _relative_lesson_stem(existing, config.input_dir)  # type: ignore[arg-type]
        name = relative_stem.as_posix()
        output_stem = config.output_dir / relative_stem
        pairs.append(
            LessonPair(
                name=name,
                audio_path=audio_path or (config.input_dir / relative_stem).with_suffix(".mp3"),
                script_path=script_path or _script_path(config.input_dir / relative_stem),
                srt_path=output_stem.with_suffix(".srt"),
                output_audio_path=output_stem.with_suffix(audio_path.suffix if audio_path else ".mp3"),
            )
        )
    return pairs


def _index_files(directory: Path, suffix: str) -> dict[str, Path]:
    indexed: dict[str, Path] = {}
    for path in directory.rglob("*"):
        if not path.is_file() or not path.name.casefold().endswith(suffix.casefold()):
            continue
        key = _relative_lesson_stem(path, directory).as_posix().casefold()
        if key in indexed:
            raise ValueError(
                f"Duplicate lesson path (case-insensitive) in {directory}: "
                f"{indexed[key].relative_to(directory)}, {path.relative_to(directory)}"
            )
        indexed[key] = path
    return indexed


def _index_audio_files(directory: Path) -> dict[str, Path]:
    indexed: dict[str, Path] = {}
    for path in directory.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in {".mp3", ".wav"}:
            continue
        key = _relative_lesson_stem(path, directory).as_posix().casefold()
        if key in indexed:
            raise ValueError(
                f"Duplicate lesson path (case-insensitive) in {directory}: "
                f"{indexed[key].relative_to(directory)}, {path.relative_to(directory)}"
            )
        indexed[key] = path
    return indexed


def _relative_lesson_stem(path: Path, directory: Path) -> Path:
    relative = path.relative_to(directory)
    name = relative.name
    if name.casefold().endswith(SCRIPT_SUFFIX):
        return relative.parent / name[:-len(SCRIPT_SUFFIX)]
    return relative.with_suffix("")


def _script_path(stem: Path) -> Path:
    return stem.parent / f"{stem.name}{SCRIPT_SUFFIX}"
