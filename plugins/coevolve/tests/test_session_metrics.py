#!/usr/bin/env python3
"""Acceptance tests A1-A6 for scripts/session_metrics.py.

Stdlib only on purpose: this plugin must install and self-test on a machine
that has nothing but python3.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "session_metrics.py"

# Planted in the fixture's free text. If either of these ever appears in the
# output, the fingerprint is leaking content and A4 has failed.
SECRET = "SUPERSECRET_TOKEN_ABC123"
PRIVATE_PATH = "/home/someone/private-customer-repo"


def _asst(ts, blocks, model="claude-opus-4-8"):
    return {
        "type": "assistant",
        "timestamp": ts,
        "sessionId": "sess-1",
        "cwd": PRIVATE_PATH,
        "gitBranch": "feature/acme-migration",
        "message": {"model": model, "content": blocks,
                    "usage": {"input_tokens": 10, "output_tokens": 20,
                              "cache_read_input_tokens": 100,
                              "cache_creation_input_tokens": 5}},
    }


def _tool_use(name, **inp):
    return {"type": "tool_use", "name": name, "input": inp}


def build_fixture(path: Path) -> None:
    lines = [
        _asst("2026-08-13T03:00:00.000Z", [_tool_use("Bash", command=f"cat {PRIVATE_PATH}/x")]),
        {"type": "user", "timestamp": "2026-08-13T03:00:05.000Z",
         "message": {"content": [{"type": "tool_result", "is_error": False, "content": "ok"}]}},
        _asst("2026-08-13T03:01:00.000Z", [_tool_use("Bash", command="ls")]),
        {"type": "user", "timestamp": "2026-08-13T03:01:05.000Z",
         "message": {"content": [{"type": "tool_result", "is_error": True, "content": "boom"}]}},
        _asst("2026-08-13T03:02:00.000Z", [_tool_use("Edit", file_path="a.py")], model="claude-fable-5"),
        {"type": "user", "timestamp": "2026-08-13T03:02:05.000Z",
         "message": {"content": [{"type": "tool_result", "is_error": False, "content": "ok"}]}},
        _asst("2026-08-13T03:03:00.000Z", [_tool_use("Skill", skill="design-like-senior", args="x")]),
        _asst("2026-08-13T03:04:00.000Z", [_tool_use("Agent", subagent_type="Explore", prompt="go")]),
        # A real human steering turn, carrying a secret we must never echo back.
        {"type": "user", "timestamp": "2026-08-13T03:05:00.000Z",
         "message": {"content": [{"type": "text", "text": f"use {SECRET} to log in"}]}},
        # An interrupt.
        {"type": "user", "timestamp": "2026-08-14T03:06:00.000Z",
         "message": {"content": [{"type": "text", "text": "[Request interrupted by user]"}]}},
        {"type": "permission-mode", "timestamp": "2026-08-14T03:06:30.000Z", "permissionMode": "acceptEdits"},
        # Real transcripts also carry user content as a bare string, not an array.
        {"type": "user", "timestamp": "2026-08-14T03:06:40.000Z",
         "message": {"content": "<command-name>/clear</command-name>"}},
        # Last event two days after the first → span_days == 2.
        _asst("2026-08-15T03:07:00.000Z", [{"type": "text", "text": "done"}]),
    ]
    with path.open("w", encoding="utf-8") as fh:
        for obj in lines:
            fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
        fh.write("{not json at all\n")          # A3: one malformed line
        fh.write("\n")                            # blank lines are not errors


def run_script(*args):
    proc = subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True)
    return proc


class SessionMetricsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.fixture = Path(cls.tmp.name) / "transcript.jsonl"
        build_fixture(cls.fixture)
        cls.salt = Path(cls.tmp.name) / "salt"
        cls.salt.write_text("test-salt-value\n", encoding="utf-8")
        cls.proc = run_script(str(cls.fixture), "--salt-file", str(cls.salt))
        if cls.proc.returncode != 0:
            raise AssertionError(f"script failed: {cls.proc.stderr}")
        cls.out = json.loads(cls.proc.stdout)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    # ---- A1: the fingerprint contains what downstream stages need ----
    def test_a1_tool_histogram(self):
        self.assertEqual(self.out["tools"], {"Bash": 2, "Edit": 1, "Skill": 1, "Agent": 1})

    def test_a1_skills_by_name(self):
        self.assertEqual(self.out["skills"], {"design-like-senior": 1})

    def test_a1_subagents_by_type(self):
        self.assertEqual(self.out["subagents"], {"Explore": 1})

    def test_a1_model_mix(self):
        self.assertEqual(self.out["models"], {"claude-opus-4-8": 5, "claude-fable-5": 1})

    def test_a1_error_and_interrupt_counts(self):
        self.assertEqual(self.out["counts"]["tool_errors"], 1)
        self.assertEqual(self.out["counts"]["interrupts"], 1)

    def test_a1_real_user_turns_excludes_tool_results_and_interrupts(self):
        # Three tool_result lines and one interrupt line are not steering turns.
        self.assertEqual(self.out["counts"]["user_turns"], 1)

    def test_a1_tool_call_total(self):
        self.assertEqual(self.out["counts"]["tool_calls"], 5)

    def test_a1_tokens_accumulate(self):
        self.assertEqual(self.out["tokens"]["output"], 6 * 20)

    def test_a1_project_key_is_stable_hash(self):
        self.assertRegex(self.out["project_key"], r"^proj_[0-9a-f]{8}$")

    def test_a1_permission_modes_recorded(self):
        self.assertIn("acceptEdits", self.out["permission_modes"])

    def test_a1_derived_metrics_present(self):
        d = self.out["derived"]
        self.assertAlmostEqual(d["error_rate"], 1 / 5, places=6)
        self.assertIn("bash_share", d)
        self.assertIn("turns_per_100_tool_calls", d)

    # ---- A2: determinism ----
    def test_a2_deterministic(self):
        again = run_script(str(self.fixture), "--salt-file", str(self.salt))
        self.assertEqual(again.stdout, self.proc.stdout)

    def test_a2_salt_changes_project_key(self):
        other = Path(self.tmp.name) / "salt2"
        other.write_text("different-salt\n", encoding="utf-8")
        alt = json.loads(run_script(str(self.fixture), "--salt-file", str(other)).stdout)
        self.assertNotEqual(alt["project_key"], self.out["project_key"])

    # ---- A3: malformed input ----
    def test_a3_malformed_line_counted_not_fatal(self):
        self.assertEqual(self.proc.returncode, 0)
        self.assertEqual(self.out["counts"]["parse_errors"], 1)

    def test_a3_empty_file_is_valid_output(self):
        empty = Path(self.tmp.name) / "empty.jsonl"
        empty.write_text("", encoding="utf-8")
        proc = run_script(str(empty), "--salt-file", str(self.salt))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["counts"]["tool_calls"], 0)

    # ---- A4: never emits content. The whole point. ----
    def test_a4_no_secret_in_output(self):
        self.assertNotIn(SECRET, self.proc.stdout)

    def test_a4_no_paths_or_branch_in_output(self):
        self.assertNotIn(PRIVATE_PATH, self.proc.stdout)
        self.assertNotIn("acme", self.proc.stdout.lower())

    def test_a4_values_are_counts_not_strings(self):
        # Every value under the vocabulary maps must be an int.
        for key in ("tools", "skills", "subagents", "models"):
            for v in self.out[key].values():
                self.assertIsInstance(v, int, f"{key} holds a non-count value")

    # ---- A8: a stable per-transcript identity, so repeated captures dedup ----
    def test_a8_transcript_id_is_the_file_stem(self):
        self.assertEqual(self.out["transcript_id"], "transcript")

    def test_a8_transcript_id_carries_no_directory(self):
        self.assertNotIn("/", self.out["transcript_id"])

    # ---- A6: multi-day sessions ----
    def test_a6_span_days(self):
        self.assertEqual(self.out["span_days"], 2)
        self.assertEqual(self.out["started_at"], "2026-08-13T03:00:00.000Z")
        self.assertEqual(self.out["ended_at"], "2026-08-15T03:07:00.000Z")


class TranscriptKindTest(unittest.TestCase):
    """A7 — a subagent transcript is not a session.

    Roughly half the transcript files on a real machine are `agent-*.jsonl`
    sidechains carrying their parent's session id. Counting them as sessions
    halves the apparent steering-turn rate and double-counts projects, so the
    fingerprint has to say which kind of transcript it just read.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, name, records):
        path = self.dir / name
        with path.open("w", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r) + "\n")
        return path

    def test_a7_main_transcript_is_a_session(self):
        f = self.dir / "main.jsonl"
        build_fixture(f)
        out = json.loads(run_script(str(f)).stdout)
        self.assertEqual(out["transcript_kind"], "session")

    def test_a7_all_sidechain_transcript_is_a_subagent(self):
        rec = _asst("2026-08-13T03:00:00.000Z", [_tool_use("Read", file_path="a")])
        rec["isSidechain"] = True
        f = self._write("agent-abc.jsonl", [rec, rec])
        out = json.loads(run_script(str(f)).stdout)
        self.assertEqual(out["transcript_kind"], "subagent")
        # It still reports its parent session id, so a roll-up can attach it.
        self.assertEqual(out["session_id"], "sess-1")

    def test_a7_empty_transcript_is_not_guessed(self):
        f = self._write("empty.jsonl", [])
        out = json.loads(run_script(str(f)).stdout)
        self.assertEqual(out["transcript_kind"], "unknown")


class CorpusSmokeTest(unittest.TestCase):
    """A5 — only runs when COEVOLVE_CORPUS points at a directory of real transcripts."""

    def test_a5_corpus(self):
        corpus = os.environ.get("COEVOLVE_CORPUS")
        if not corpus:
            self.skipTest("set COEVOLVE_CORPUS to a transcript directory to run A5")
        files = sorted(Path(corpus).rglob("*.jsonl"))
        self.assertTrue(files, "no transcripts found")
        durations = []
        for f in files:
            t0 = time.time()
            proc = run_script(str(f))
            durations.append(time.time() - t0)
            self.assertEqual(proc.returncode, 0, f"crashed on {f.name}: {proc.stderr[:400]}")
            json.loads(proc.stdout)
        durations.sort()
        p95 = durations[int(len(durations) * 0.95) - 1]
        self.assertLess(p95, 2.0, f"p95 {p95:.2f}s over {len(files)} files")


if __name__ == "__main__":
    unittest.main(verbosity=2)
