from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

from .batch import BatchProcessor
from .config import load_config
from .discovery import discover_pairs
from .jobs import JobStore
from .packaging import create_package


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Align known MP3/TXT lesson pairs with WhisperX and generate Standard SRT."
    )
    parser.add_argument("--config", type=Path, help="YAML configuration file")
    parser.add_argument("--input", type=Path, help="Recursive directory containing colocated MP3/TXT pairs")
    parser.add_argument("--output", type=Path, help="Output directory for MP3/SRT pairs")
    parser.add_argument("--state", type=Path, help="SQLite job-state path")
    parser.add_argument("--device", choices=("cuda", "cpu"), help="Alignment device override")
    parser.add_argument("--lesson", action="append", help="Process one relative lesson path; repeatable")
    parser.add_argument("--resume", action="store_true", help="Resume queued, interrupted, and failed jobs")
    parser.add_argument("--package", action="store_true", help="Create the configured ZIP after processing")
    parser.add_argument("--package-only", action="store_true", help="Package completed outputs without alignment")
    return parser


def configure_logging(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        encoding="utf-8",
    )


def check_audio_runtime() -> None:
    if sys.version_info >= (3, 14):
        raise RuntimeError("Python 3.14 is not supported by WhisperX 3.8.6; create the documented Python 3.12 environment")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg was not found on PATH; install FFmpeg before processing MP3 files")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    overrides = {
        "input_dir": args.input,
        "output_dir": args.output,
        "state_db": args.state,
    }
    jobs: JobStore | None = None
    try:
        config = load_config(args.config, overrides)
        if args.device:
            config.alignment.device = args.device
            config.validate()
        for directory in (config.output_dir, config.report_dir, config.alignment.model_dir):
            directory.mkdir(parents=True, exist_ok=True)
        configure_logging(config.log_file)
        pairs = discover_pairs(config)
        jobs = JobStore(config.state_db)
        jobs.sync(pairs, require_output_audio=config.copy_audio_to_output)
        if not pairs:
            print(
                f"No lesson files found. Put matching MP3/TXT pairs in {config.input_dir}."
            )
        success = True
        if not args.package_only and pairs:
            check_audio_runtime()
            selected = {
                Path(name).with_suffix("").as_posix().removeprefix("./")
                for name in args.lesson
            } if args.lesson else None
            success = BatchProcessor(config, jobs).run(selected)
        if args.package or args.package_only:
            destination = config.output_dir / config.package_name
            count = create_package(jobs.completed(), destination, config.output_dir)
            print(f"Package created: {destination} ({count} lesson(s))")
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\nInterrupted. Run again with --resume to continue.", file=sys.stderr)
        return 130
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    finally:
        if jobs is not None:
            jobs.close()


if __name__ == "__main__":
    raise SystemExit(main())
