#!/usr/bin/env python3
"""Backfill sweeps up existing transcripts exactly once, filed under the month
the work happened."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "backfill_metrics.py"


def transcript(path: Path, ts: str, sidechain=False):
    rec = {"type": "assistant", "timestamp": ts, "sessionId": "S", "cwd": "/p",
           "message": {"model": "m", "content": [{"type": "tool_use", "name": "Bash", "input": {}}]}}
    if sidechain:
        rec["isSidechain"] = True
    path.write_text(json.dumps(rec) + "\n", encoding="utf-8")


class BackfillTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.tr = base / "projects" / "proj"
        self.tr.mkdir(parents=True)
        transcript(self.tr / "june.jsonl", "2026-06-15T10:00:00.000Z")
        transcript(self.tr / "aug.jsonl", "2026-08-15T10:00:00.000Z")
        transcript(self.tr / "agent-x.jsonl", "2026-08-16T10:00:00.000Z", sidechain=True)
        (self.tr / "broken.jsonl").write_text("{oops\n", encoding="utf-8")
        self.store = base / "metrics"

    def tearDown(self):
        self.tmp.cleanup()

    def run_it(self, *extra):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--transcripts", str(self.tr.parent),
             "--store", str(self.store), *extra], capture_output=True, text=True)

    def test_dry_run_writes_nothing(self):
        proc = self.run_it()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("dry run", proc.stdout)
        self.assertFalse(self.store.exists())

    def test_files_are_partitioned_by_the_month_the_work_happened(self):
        self.run_it("--apply")
        self.assertTrue((self.store / "2026-06.jsonl").exists())
        self.assertTrue((self.store / "2026-08.jsonl").exists())
        self.assertEqual(len((self.store / "2026-06.jsonl").read_text().strip().splitlines()), 1)

    def test_subagent_transcripts_are_captured_too(self):
        self.run_it("--apply")
        text = (self.store / "2026-08.jsonl").read_text()
        self.assertIn('"transcript_kind": "subagent"', text)

    def test_running_twice_adds_nothing(self):
        self.run_it("--apply")
        before = sorted((p.name, p.read_text()) for p in self.store.glob("*.jsonl"))
        proc = self.run_it("--apply")
        after = sorted((p.name, p.read_text()) for p in self.store.glob("*.jsonl"))
        self.assertEqual(before, after)
        self.assertIn("already captured  : 3", proc.stdout)

    def test_a_malformed_transcript_does_not_stop_the_sweep(self):
        proc = self.run_it("--apply")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("to write          : 3", proc.stdout)
        self.assertIn("empty/unreadable  : 1", proc.stdout)
        self.assertFalse((self.store / "unknown.jsonl").exists(),
                         "an empty transcript must not create a bucket of zeroes")


if __name__ == "__main__":
    unittest.main(verbosity=2)
