from __future__ import annotations

import os
import zipfile
from pathlib import Path


def create_package(rows: list, destination: Path, output_dir: Path) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    count = 0
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for row in rows:
                audio = Path(row["output_audio_path"])
                srt = Path(row["srt_path"])
                if not audio.is_file() or not srt.is_file():
                    raise FileNotFoundError(f"Completed lesson output is missing: {row['lesson_name']}")
                if audio.stem.casefold() != srt.stem.casefold():
                    raise ValueError(f"Output basenames do not match for {row['lesson_name']}")
                try:
                    audio_name = audio.relative_to(output_dir).as_posix()
                    srt_name = srt.relative_to(output_dir).as_posix()
                except ValueError as exc:
                    raise ValueError(f"Package asset is outside output directory: {row['lesson_name']}") from exc
                archive.write(audio, arcname=audio_name)
                archive.write(srt, arcname=srt_name)
                count += 1
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return count
