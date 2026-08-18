from __future__ import annotations

import json
import os
from pathlib import Path

from ..alignment.mapper import MappingResult
from ..config import QualityConfig
from ..models import QualityReport, ScriptLine


def analyze_quality(
    lesson_name: str,
    lines: list[ScriptLine],
    mapping: MappingResult,
    duration: float,
    leading_silence: float,
    config: QualityConfig,
) -> QualityReport:
    timing_issues: list[str] = []
    suspicious: list[str] = []
    warnings: list[str] = []
    cue_by_index = {cue.index: cue for cue in mapping.cues}
    previous_end = -1.0
    for line in lines:
        cue = cue_by_index.get(line.index)
        if cue is None:
            timing_issues.append(f"line {line.index}: no aligned words")
            continue
        if cue.start < 0 or cue.start >= cue.end or cue.end > duration + 0.05:
            timing_issues.append(f"line {line.index}: impossible timing {cue.start:.3f}-{cue.end:.3f}")
        if cue.start < previous_end:
            timing_issues.append(f"line {line.index}: overlaps the previous cue")
        previous_end = max(previous_end, cue.end)
        line_coverage = cue.matched_words / cue.expected_words
        if line_coverage < config.suspicious_line_coverage:
            suspicious.append(f"line {line.index}: only {line_coverage:.1%} of words aligned")
        if cue.average_score is not None and cue.average_score < config.low_word_score:
            suspicious.append(f"line {line.index}: low average word score {cue.average_score:.3f}")
        if len(line.original) > config.long_line_characters or len(line.tokens) > config.long_line_words:
            warnings.append(f"line {line.index}: sentence exceeds recommended subtitle length")
    if not (config.leading_silence_minimum <= leading_silence <= config.leading_silence_maximum):
        warnings.append(
            f"leading silence is {leading_silence:.2f}s; recommended range is "
            f"{config.leading_silence_minimum:.2f}-{config.leading_silence_maximum:.2f}s"
        )
    coverage = mapping.coverage
    if timing_issues or len(mapping.cues) != len(lines) or coverage < config.warning_coverage:
        status = "FAIL"
    elif coverage < config.pass_coverage or suspicious or warnings:
        status = "WARNING"
    else:
        status = "PASS"
    return QualityReport(
        lesson_name=lesson_name,
        status=status,
        total_script_lines=len(lines),
        successfully_aligned=len(mapping.cues),
        expected_words=mapping.expected_words,
        aligned_words=mapping.matched_words,
        alignment_coverage=round(coverage, 6),
        timing_issues=timing_issues,
        suspicious_lines=suspicious,
        warnings=warnings,
        leading_silence_seconds=leading_silence,
        audio_duration_seconds=round(duration, 3),
    )


def write_report(report: QualityReport, report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    destination = report_dir / f"{report.lesson_name}.quality.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, destination)
    return destination
