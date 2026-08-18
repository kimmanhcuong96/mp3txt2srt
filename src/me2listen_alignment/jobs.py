from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from .models import LessonPair, utc_now


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    audio_path TEXT NOT NULL,
    script_path TEXT NOT NULL,
    srt_path TEXT NOT NULL,
    output_audio_path TEXT NOT NULL,
    input_signature TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL CHECK(status IN ('queued', 'processing', 'completed', 'failed')),
    quality_status TEXT,
    alignment_coverage REAL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    processing_seconds REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
"""

PIPELINE_REVISION = "embedded-speech-boundary-v3"


class JobStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def sync(self, pairs: Iterable[LessonPair], require_output_audio: bool = True) -> None:
        now = utc_now()
        with self.connection:
            self.connection.execute("UPDATE jobs SET active=0")
            for pair in pairs:
                signature = _input_signature(pair)
                self.connection.execute(
                    """
                    INSERT INTO jobs (
                        lesson_name, audio_path, script_path, srt_path, output_audio_path,
                        input_signature, active, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, 'queued', ?, ?)
                    ON CONFLICT(lesson_name) DO UPDATE SET
                        audio_path=excluded.audio_path,
                        script_path=excluded.script_path,
                        srt_path=excluded.srt_path,
                        output_audio_path=excluded.output_audio_path,
                        active=1,
                        status=CASE
                            WHEN jobs.input_signature <> excluded.input_signature THEN 'queued'
                            ELSE jobs.status
                        END,
                        quality_status=CASE WHEN jobs.input_signature <> excluded.input_signature THEN NULL ELSE jobs.quality_status END,
                        alignment_coverage=CASE WHEN jobs.input_signature <> excluded.input_signature THEN NULL ELSE jobs.alignment_coverage END,
                        error_message=CASE WHEN jobs.input_signature <> excluded.input_signature THEN NULL ELSE jobs.error_message END,
                        input_signature=excluded.input_signature,
                        updated_at=excluded.updated_at
                    """,
                    (
                        pair.name, str(pair.audio_path), str(pair.script_path), str(pair.srt_path),
                        str(pair.output_audio_path), signature, now, now,
                    ),
                )
                if not pair.srt_path.is_file():
                    self.connection.execute(
                        "UPDATE jobs SET status='queued', quality_status=NULL WHERE lesson_name=? AND status='completed'",
                        (pair.name,),
                    )
                if require_output_audio and not pair.output_audio_path.is_file():
                    self.connection.execute(
                        "UPDATE jobs SET status='queued', quality_status=NULL WHERE lesson_name=? AND status='completed'",
                        (pair.name,),
                    )

    def pending(self, selected: set[str] | None = None) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            "SELECT * FROM jobs WHERE active=1 AND status <> 'completed' ORDER BY lesson_name COLLATE NOCASE"
        ).fetchall()
        if selected is None:
            return rows
        wanted = {name.casefold() for name in selected}
        return [row for row in rows if row["lesson_name"].casefold() in wanted]

    def mark_processing(self, job_id: int) -> None:
        with self.connection:
            self.connection.execute(
                """UPDATE jobs SET status='processing', attempt_count=attempt_count+1,
                   error_message=NULL, updated_at=? WHERE job_id=?""",
                (utc_now(), job_id),
            )

    def mark_completed(self, job_id: int, quality_status: str, coverage: float, elapsed: float) -> None:
        with self.connection:
            self.connection.execute(
                """UPDATE jobs SET status='completed', quality_status=?, alignment_coverage=?,
                   processing_seconds=?, error_message=NULL, updated_at=? WHERE job_id=?""",
                (quality_status, coverage, elapsed, utc_now(), job_id),
            )

    def mark_failed(self, job_id: int, error: str, elapsed: float) -> None:
        with self.connection:
            self.connection.execute(
                """UPDATE jobs SET status='failed', quality_status='FAIL', error_message=?,
                   processing_seconds=?, updated_at=? WHERE job_id=?""",
                (error, elapsed, utc_now(), job_id),
            )

    def counts(self) -> dict[str, int]:
        result = {status: 0 for status in ("queued", "processing", "completed", "failed")}
        for row in self.connection.execute("SELECT status, COUNT(*) AS count FROM jobs WHERE active=1 GROUP BY status"):
            result[row["status"]] = row["count"]
        return result

    def completed(self) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM jobs WHERE active=1 AND status='completed' ORDER BY lesson_name COLLATE NOCASE"
        ).fetchall()


def _input_signature(pair: LessonPair) -> str:
    values: list[str] = []
    for path in (pair.audio_path, pair.script_path):
        try:
            stat = path.stat()
            values.append(f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}")
        except OSError:
            values.append(f"{path.absolute()}:missing")
    return PIPELINE_REVISION + "|" + "|".join(values)
