import tempfile
import unittest
from pathlib import Path

from me2listen_alignment.config import AppConfig
from me2listen_alignment.discovery import discover_pairs
from me2listen_alignment.jobs import JobStore


class JobsDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.config = AppConfig(
            input_dir=root / "input",
            output_dir=root / "output",
            state_db=root / "state/jobs.sqlite",
            report_dir=root / "state/reports",
            log_file=root / "logs/test.log",
        )
        self.config.input_dir.mkdir(parents=True)

    def tearDown(self):
        self.directory.cleanup()

    def test_discovers_missing_counterpart_as_failed_candidate(self):
        (self.config.input_dir / "one.mp3").write_bytes(b"audio")
        pairs = discover_pairs(self.config)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].script_path.name, "one.txt")

    def test_sqlite_state_resets_when_input_changes(self):
        audio = self.config.input_dir / "one.mp3"
        script = self.config.input_dir / "one.txt"
        audio.write_bytes(b"audio")
        script.write_text("Hello.\n", encoding="utf-8")
        pairs = discover_pairs(self.config)
        store = JobStore(self.config.state_db)
        try:
            store.sync(pairs)
            row = store.pending()[0]
            pairs[0].srt_path.parent.mkdir(parents=True)
            pairs[0].srt_path.write_text("done", encoding="utf-8")
            pairs[0].output_audio_path.write_bytes(b"audio")
            store.mark_completed(row["job_id"], "PASS", 1.0, 1.0)
            store.sync(pairs)
            self.assertEqual(store.pending(), [])
            script.write_text("Changed.\n", encoding="utf-8")
            store.sync(pairs)
            self.assertEqual(len(store.pending()), 1)
        finally:
            store.close()

    def test_multiple_pairs_per_subdirectory_and_mirrored_outputs(self):
        unit = self.config.input_dir / "course/unit-01"
        unit.mkdir(parents=True)
        for lesson in ("one", "two"):
            (unit / f"{lesson}.mp3").write_bytes(b"audio")
            (unit / f"{lesson}.txt").write_text("Hello.\n", encoding="utf-8")
        other = self.config.input_dir / "course/unit-02"
        other.mkdir(parents=True)
        (other / "one.mp3").write_bytes(b"audio")
        (other / "one.txt").write_text("Hello.\n", encoding="utf-8")

        pairs = discover_pairs(self.config)

        self.assertEqual([pair.name for pair in pairs], [
            "course/unit-01/one", "course/unit-01/two", "course/unit-02/one"
        ])
        self.assertEqual(
            pairs[1].srt_path,
            self.config.output_dir / "course/unit-01/two.srt",
        )
