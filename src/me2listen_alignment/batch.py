from __future__ import annotations

import hashlib
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Callable

from .alignment.mapper import map_words_to_lines
from .alignment.boundary import refine_cue_boundaries
from .alignment.whisperx_engine import WhisperXEngine
from .config import AppConfig
from .jobs import JobStore
from .models import LessonPair, QualityReport
from .quality.analyzer import analyze_quality, write_report
from .script.parser import parse_script
from .subtitle.srt_writer import write_srt


class PermanentJobError(RuntimeError):
    def __init__(self, message: str, report_written: bool = False):
        super().__init__(message)
        self.report_written = report_written


class BatchProcessor:
    def __init__(self, config: AppConfig, jobs: JobStore, printer: Callable[[str], None] = print):
        self.config = config
        self.jobs = jobs
        self.print = printer
        self.logger = logging.getLogger("me2listen_alignment")
        self.engine: WhisperXEngine | None = None

    def run(self, selected: set[str] | None = None) -> bool:
        rows = self.jobs.pending(selected)
        if not rows:
            self.print("No pending or failed lessons to process.")
            return self.jobs.counts()["failed"] == 0
        try:
            for position, row in enumerate(rows, 1):
                self._show_progress(row["lesson_name"])
                self._process_with_retries(row, position, len(rows))
        finally:
            if self.engine is not None:
                self.engine.close()
        counts = self.jobs.counts()
        self.print(
            f"\nFinished. Completed: {counts['completed']} | Failed: {counts['failed']} "
            f"| Total: {sum(counts.values())}"
        )
        return counts["failed"] == 0

    def _show_progress(self, lesson_name: str) -> None:
        counts = self.jobs.counts()
        remaining = counts["queued"] + counts["processing"] + counts["failed"]
        self.print(
            f"\nTotal: {sum(counts.values())} | Completed: {counts['completed']} | Processing: 1 "
            f"| Failed: {counts['failed']} | Remaining: {remaining}\nLesson: {lesson_name}"
        )

    def _process_with_retries(self, row, position: int, total: int) -> None:
        pair = _pair_from_row(row)
        started = time.monotonic()
        pair.srt_path.unlink(missing_ok=True)
        report_written = False
        last_error = "Unknown processing error"
        for attempt in range(1, self.config.retry_count + 1):
            self.jobs.mark_processing(row["job_id"])
            self.print(f"[{position}/{total}] attempt {attempt}/{self.config.retry_count}")
            try:
                report = self._process_one(pair)
                report_written = True
                elapsed = time.monotonic() - started
                self.jobs.mark_completed(
                    row["job_id"], report.status, report.alignment_coverage, elapsed
                )
                self.logger.info(
                    "lesson=%s completed quality=%s coverage=%.2f%% duration=%.2fs",
                    pair.name, report.status, report.alignment_coverage * 100, elapsed,
                )
                self.print(
                    f"Completed: {pair.srt_path} | {report.status} | "
                    f"coverage {report.alignment_coverage:.1%}"
                )
                return
            except PermanentJobError as exc:
                last_error = str(exc)
                report_written = exc.report_written
                break
            except (OSError, RuntimeError, ValueError) as exc:
                last_error = str(exc) or exc.__class__.__name__
                self.logger.exception("lesson=%s attempt=%d failed", pair.name, attempt)
                self.print(f"Attempt failed: {last_error}")
                if attempt < self.config.retry_count:
                    self.print("Retrying...")
        elapsed = time.monotonic() - started
        pair.srt_path.unlink(missing_ok=True)
        if not report_written:
            failure = QualityReport(
                lesson_name=pair.name,
                status="FAIL",
                total_script_lines=0,
                successfully_aligned=0,
                expected_words=0,
                aligned_words=0,
                alignment_coverage=0.0,
                timing_issues=[last_error],
            )
            write_report(failure, self.config.report_dir)
        self.jobs.mark_failed(row["job_id"], last_error, elapsed)
        self.print(f"FAILED: {pair.name}\nReason: {last_error}")

    def _process_one(self, pair: LessonPair) -> QualityReport:
        self.logger.info(
            "lesson=%s started device=%s language=%s model=%s batch_size=%d",
            pair.name, self.config.alignment.device, self.config.alignment.language,
            self.config.alignment.model_name or "default", self.config.alignment.batch_size,
        )
        _validate_pair(pair)
        self.print("Validating script...")
        try:
            lines = parse_script(pair.script_path)
        except (OSError, ValueError) as exc:
            raise PermanentJobError(str(exc)) from exc
        if self.engine is None:
            self.print("Loading WhisperX alignment model once for this batch...")
            self.engine = WhisperXEngine(
                self.config.alignment, self.config.quality.silence_threshold_db
            )
        self.print("Running WhisperX forced alignment...")
        engine_result = self.engine.align(pair.audio_path, lines)
        self.print("Mapping aligned words to original script lines...")
        mapping = map_words_to_lines(lines, engine_result.words)
        if self.config.alignment.boundary_refinement_enabled:
            refined_cues = refine_cue_boundaries(
                mapping.cues,
                engine_result.silence_intervals,
                engine_result.duration_seconds,
                self.config.alignment.boundary_search_radius,
                self.config.alignment.boundary_speech_padding,
                mapping.words_by_line,
                self.config.alignment.boundary_embedded_silence_minimum,
            )
            mapping = type(mapping)(
                cues=refined_cues,
                expected_words=mapping.expected_words,
                matched_words=mapping.matched_words,
                unmatched_expected=mapping.unmatched_expected,
                words_by_line=mapping.words_by_line,
            )
        report = analyze_quality(
            pair.name, lines, mapping, engine_result.duration_seconds,
            engine_result.leading_silence_seconds, self.config.quality,
        )
        write_report(report, self.config.report_dir)
        self.logger.info(
            "lesson=%s alignment quality=%s coverage=%.2f%% aligned_lines=%d/%d warnings=%s",
            pair.name, report.status, report.alignment_coverage * 100,
            report.successfully_aligned, report.total_script_lines,
            report.warnings + report.suspicious_lines,
        )
        if report.status == "FAIL":
            details = "; ".join(report.timing_issues + report.suspicious_lines) or "coverage below threshold"
            raise PermanentJobError(
                f"Alignment quality failed ({report.alignment_coverage:.1%} coverage): {details}",
                report_written=True,
            )
        self.print("Generating and validating Standard SRT...")
        write_srt(mapping.cues, pair.srt_path, engine_result.duration_seconds)
        if self.config.copy_audio_to_output:
            self.print("Copying original MP3 without modification...")
            _copy_audio_unchanged(pair.audio_path, pair.output_audio_path)
        return report


def _pair_from_row(row) -> LessonPair:
    return LessonPair(
        name=row["lesson_name"],
        audio_path=Path(row["audio_path"]),
        script_path=Path(row["script_path"]),
        srt_path=Path(row["srt_path"]),
        output_audio_path=Path(row["output_audio_path"]),
    )


def _validate_pair(pair: LessonPair) -> None:
    if not pair.audio_path.is_file():
        raise PermanentJobError(f"MP3 file not found: {pair.audio_path}")
    if not pair.script_path.is_file():
        raise PermanentJobError(f"TXT file not found: {pair.script_path}")
    if pair.audio_path.suffix.casefold() != ".mp3" or not pair.script_path.name.casefold().endswith(".en.txt"):
        raise PermanentJobError("Input pair must use .mp3 and .en.txt extensions")
    script_basename = pair.script_path.name[:-len(".en.txt")]
    if pair.audio_path.stem.casefold() != script_basename.casefold():
        raise PermanentJobError("MP3 basename must match the part before .en.txt")
    if pair.srt_path.stem.casefold() != pair.audio_path.stem.casefold():
        raise PermanentJobError("Output SRT basename must match the input MP3")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_audio_unchanged(source: Path, destination: Path) -> None:
    if source.resolve() == destination.resolve():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_hash = _sha256(source)
    if destination.exists():
        if destination.is_file() and _sha256(destination) == source_hash:
            return
        raise RuntimeError(f"Refusing to replace a different output MP3: {destination}")
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        shutil.copy2(source, temporary)
        if _sha256(temporary) != source_hash:
            raise RuntimeError("Copied MP3 checksum does not match the source")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
