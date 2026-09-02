#!/usr/bin/env python3
"""Acceptance tests for scripts/metrics_rollup.py — session roll-up (A7 follow-on)
and the before/after comparison that VERIFY depends on (D1-D3)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "metrics_rollup.py"


def fingerprint(session_id, transcript_id, kind, started, *, tool_calls=10,
                errors=0, interrupts=0, turns=3, project="proj_aaaaaaaa"):
    return {
        "schema": "coevolve/session-metrics/1",
        "session_id": session_id,
        "transcript_id": transcript_id,
        "transcript_kind": kind,
        "project_key": project,
        "started_at": started + "T09:00:00.000Z",
        "ended_at": started + "T10:00:00.000Z",
        "span_days": 0,
        "counts": {"lines": 100, "parse_errors": 0, "tool_calls": tool_calls,
                   "tool_results": tool_calls, "tool_errors": errors,
                   "interrupts": interrupts, "user_turns": turns,
                   "assistant_messages": tool_calls},
        "tools": {"Bash": tool_calls}, "skills": {}, "subagents": {},
        "models": {"claude-opus-5": tool_calls},
        "permission_modes": [], "modes": [],
        "tokens": {"input": 1, "output": 2, "cache_read": 3, "cache_creation": 4},
        "derived": {"error_rate": round(errors / tool_calls, 6) if tool_calls else 0.0,
                    "interrupt_rate": 0.0, "bash_share": 1.0,
                    "turns_per_100_tool_calls": 0.0, "skill_calls": 0,
                    "subagent_calls": 0, "delegated_tool_call_share": 0.0},
    }


def run(*args, store=None):
    cmd = [sys.executable, str(SCRIPT), *args]
    if store:
        cmd += ["--store", str(store)]
    return subprocess.run(cmd, capture_output=True, text=True)


class RollupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Path(self.tmp.name)
        self.write([
            fingerprint("s1", "t1", "session", "2026-08-01", tool_calls=20, turns=5),
            fingerprint("s1", "agent-a", "subagent", "2026-08-01", tool_calls=30, turns=0),
            fingerprint("s2", "t2", "session", "2026-08-02", tool_calls=10, turns=2),
        ])

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, records, name="2026-08.jsonl"):
        with (self.store / name).open("a", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r) + "\n")

    def sessions(self):
        proc = run("sessions", store=self.store)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]

    def test_subagent_work_rolls_into_its_parent_session(self):
        rows = {r["session_id"]: r for r in self.sessions()}
        self.assertEqual(rows["s1"]["tool_calls"], 50)
        self.assertEqual(rows["s1"]["own_tool_calls"], 20)
        self.assertEqual(rows["s1"]["delegated_tool_calls"], 30)

    def test_one_row_per_session_not_per_transcript(self):
        self.assertEqual(len(self.sessions()), 2)

    def test_repeated_capture_of_same_transcript_does_not_double_count(self):
        # A long session fires Stop many times; the store accumulates duplicates.
        self.write([fingerprint("s2", "t2", "session", "2026-08-02", tool_calls=40, turns=9)])
        rows = {r["session_id"]: r for r in self.sessions()}
        self.assertEqual(rows["s2"]["tool_calls"], 40, "latest record per transcript must win")
        self.assertEqual(rows["s2"]["user_turns"], 9)

    def test_orphan_subagent_still_reported(self):
        # A subagent whose parent transcript was never captured must not vanish.
        self.write([fingerprint("s9", "agent-z", "subagent", "2026-08-03", tool_calls=7)])
        rows = {r["session_id"]: r for r in self.sessions()}
        self.assertIn("s9", rows)
        self.assertEqual(rows["s9"]["delegated_tool_calls"], 7)


class CompareTest(unittest.TestCase):
    """D1-D3: did behaviour change after a lesson was enacted?"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def seed(self, before_n, after_n, before_err, after_err):
        recs = []
        for i in range(before_n):
            recs.append(fingerprint(f"b{i}", f"tb{i}", "session", "2026-08-0%d" % (i % 9 + 1),
                                    tool_calls=100, errors=before_err))
        for i in range(after_n):
            recs.append(fingerprint(f"a{i}", f"ta{i}", "session", "2026-08-2%d" % (i % 9),
                                    tool_calls=100, errors=after_err))
        with (self.store / "2026-08.jsonl").open("w", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r) + "\n")

    def compare(self, **kw):
        args = ["compare", "--metric", kw.get("metric", "derived.error_rate"),
                "--split", kw.get("split", "2026-08-15")]
        if "min_n" in kw:
            args += ["--min-n", str(kw["min_n"])]
        proc = run(*args, store=self.store)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_d1_reports_both_windows_side_by_side(self):
        self.seed(6, 6, before_err=10, after_err=2)
        out = self.compare()
        self.assertEqual(out["before"]["n"], 6)
        self.assertEqual(out["after"]["n"], 6)
        self.assertAlmostEqual(out["before"]["mean"], 0.1, places=6)
        self.assertAlmostEqual(out["after"]["mean"], 0.02, places=6)
        self.assertEqual(out["direction"], "down")

    def test_d2_refuses_a_verdict_on_thin_evidence(self):
        self.seed(2, 2, before_err=10, after_err=2)
        out = self.compare(min_n=5)
        self.assertEqual(out["verdict"], "insufficient evidence")
        self.assertNotIn("direction", out)

    def test_d2_thin_evidence_still_reports_the_numbers(self):
        self.seed(2, 2, before_err=10, after_err=2)
        out = self.compare(min_n=5)
        self.assertEqual(out["before"]["n"], 2)
        self.assertEqual(out["after"]["n"], 2)

    def test_d4_a_thin_after_window_is_reported_as_still_filling(self):
        self.seed(6, 2, before_err=10, after_err=2)
        out = self.compare(min_n=5)
        self.assertEqual(out["blocked_by"], "after_window")
        self.assertIn("more sessions", out["note"])

    def test_d4_a_thin_before_window_is_reported_as_closed_not_pending(self):
        """The before side cannot grow: every session earlier than the split has
        already happened. Telling the user to wait would strand the lesson."""
        self.seed(2, 6, before_err=10, after_err=2)
        out = self.compare(min_n=5)
        self.assertEqual(out["blocked_by"], "before_window")
        self.assertIn("backfill", out["note"].lower())
        self.assertNotIn("more sessions", out["note"])

    def test_d4_both_windows_thin_names_both(self):
        self.seed(2, 2, before_err=10, after_err=2)
        self.assertEqual(self.compare(min_n=5)["blocked_by"], "both")

    def test_d5_a_stored_baseline_is_used_instead_of_the_store(self):
        # Only after-side sessions survive; the baseline was captured at enactment.
        self.seed(0, 6, before_err=0, after_err=2)
        baseline = Path(self.tmp.name) / "baseline.json"
        baseline.write_text(json.dumps(
            {"n": 12, "mean": 0.1, "median": 0.1, "p90": 0.12, "min": 0.08, "max": 0.14,
             "captured": "2026-08-20", "metric": "derived.error_rate"}), encoding="utf-8")
        proc = run("compare", "--metric", "derived.error_rate", "--split", "2026-08-15",
                   "--min-n", "5", "--baseline-file", str(baseline), store=self.store)
        out = json.loads(proc.stdout)
        self.assertEqual(out["verdict"], "measured")
        self.assertEqual(out["direction"], "down")
        self.assertEqual(out["baseline_source"], "snapshot")
        self.assertEqual(out["before"]["n"], 12)

    def test_d5_a_stored_baseline_must_still_be_thick_enough(self):
        self.seed(0, 6, before_err=0, after_err=2)
        baseline = Path(self.tmp.name) / "thin.json"
        baseline.write_text(json.dumps({"n": 2, "mean": 0.1}), encoding="utf-8")
        out = json.loads(run("compare", "--metric", "derived.error_rate", "--split",
                             "2026-08-15", "--min-n", "5", "--baseline-file", str(baseline),
                             store=self.store).stdout)
        self.assertEqual(out["verdict"], "insufficient evidence")
        self.assertEqual(out["blocked_by"], "before_window")

    def test_d5_a_baseline_for_a_different_metric_is_refused(self):
        """Comparing today's error rate against a snapshot of something else is
        worse than having no baseline, because it looks like a result."""
        self.seed(0, 6, before_err=0, after_err=2)
        baseline = Path(self.tmp.name) / "wrong.json"
        baseline.write_text(json.dumps(
            {"n": 12, "mean": 0.1, "metric": "derived.interrupt_rate"}), encoding="utf-8")
        proc = run("compare", "--metric", "derived.error_rate", "--split", "2026-08-15",
                   "--baseline-file", str(baseline), store=self.store)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("interrupt_rate", proc.stderr)

    def test_d6_a_verdict_is_possible_with_no_before_sessions_left(self):
        self.seed(0, 8, before_err=0, after_err=1)
        baseline = Path(self.tmp.name) / "b.json"
        baseline.write_text(json.dumps({"n": 20, "mean": 0.09}), encoding="utf-8")
        out = json.loads(run("compare", "--metric", "derived.error_rate", "--split",
                             "2026-08-15", "--min-n", "5", "--baseline-file", str(baseline),
                             store=self.store).stdout)
        self.assertEqual(out["verdict"], "measured")

    def test_d7_identical_sessions_are_not_independent_observations(self):
        """A count is not independence. Six sessions with the same value are one
        observation wearing six hats, and --min-n cannot tell the difference."""
        self.seed(6, 6, before_err=10, after_err=2)   # generator makes each side uniform
        out = self.compare(min_n=5)
        self.assertEqual(out["before"]["distinct_values"], 1)
        self.assertEqual(out["after"]["distinct_values"], 1)
        self.assertTrue(out["degenerate_spread"])
        self.assertIn("identical", out["caveat"].lower())

    def test_d7_real_spread_is_not_flagged(self):
        recs = []
        for i in range(6):
            recs.append(fingerprint(f"b{i}", f"tb{i}", "session", "2026-08-0%d" % (i + 1),
                                    tool_calls=100, errors=8 + i))
        for i in range(6):
            recs.append(fingerprint(f"a{i}", f"ta{i}", "session", "2026-08-2%d" % i,
                                    tool_calls=100, errors=1 + i % 3))
        with (self.store / "2026-08.jsonl").open("w", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r) + "\n")
        out = self.compare(min_n=5)
        self.assertGreater(out["before"]["distinct_values"], 1)
        self.assertFalse(out["degenerate_spread"])
        self.assertNotIn("caveat", out)

    def test_d3_metric_is_echoed_so_the_choice_is_auditable(self):
        self.seed(6, 6, before_err=10, after_err=10)
        out = self.compare()
        self.assertEqual(out["metric"], "derived.error_rate")
        self.assertEqual(out["split"], "2026-08-15")
        self.assertEqual(out["direction"], "flat")

    def test_unknown_metric_path_is_an_error_not_a_silent_zero(self):
        self.seed(6, 6, 10, 2)
        proc = run("compare", "--metric", "derived.nope", "--split", "2026-08-15",
                   store=self.store)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("nope", proc.stderr)


class BaselineCaptureTest(unittest.TestCase):
    """C5 — enactment has to be able to take the snapshot in one command, or it
    will not happen, and the snapshot is the whole fix."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Path(self.tmp.name)
        recs = [fingerprint(f"s{i}", f"t{i}", "session", f"2026-08-{i+1:02d}",
                            tool_calls=100, errors=10) for i in range(8)]
        recs += [fingerprint(f"a{i}", f"ta{i}", "session", f"2026-08-2{i}",
                             tool_calls=100, errors=1) for i in range(3)]
        with (self.store / "2026-08.jsonl").open("w", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r) + "\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_baseline_emits_a_snapshot_for_one_metric_before_a_date(self):
        out = json.loads(run("baseline", "--metric", "derived.error_rate",
                             "--until", "2026-08-20", store=self.store).stdout)
        self.assertEqual(out["metric"], "derived.error_rate")
        self.assertEqual(out["n"], 8)
        self.assertAlmostEqual(out["mean"], 0.1, places=6)
        self.assertEqual(out["captured_until"], "2026-08-20")
        self.assertIn("captured", out)

    def test_the_snapshot_feeds_straight_back_into_compare(self):
        snap = Path(self.tmp.name) / "b.json"
        snap.write_text(run("baseline", "--metric", "derived.error_rate",
                            "--until", "2026-08-20", store=self.store).stdout, encoding="utf-8")
        out = json.loads(run("compare", "--metric", "derived.error_rate",
                             "--split", "2026-08-20", "--min-n", "3",
                             "--baseline-file", str(snap), store=self.store).stdout)
        self.assertEqual(out["verdict"], "measured")
        self.assertEqual(out["direction"], "down")

    def test_a_thin_baseline_says_so_at_capture_time(self):
        out = json.loads(run("baseline", "--metric", "derived.error_rate",
                             "--until", "2026-08-02", store=self.store).stdout)
        self.assertEqual(out["n"], 1)
        self.assertTrue(out["too_thin"],
                        "enactment must learn now that this metric can never be verified")


class WindowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Path(self.tmp.name)
        recs = [fingerprint(f"s{i}", f"t{i}", "session", f"2026-08-0{i+1}",
                            tool_calls=10 * (i + 1)) for i in range(5)]
        with (self.store / "2026-08.jsonl").open("w", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r) + "\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_window_filters_by_date(self):
        proc = run("window", "--since", "2026-08-03", store=self.store)
        out = json.loads(proc.stdout)
        self.assertEqual(out["sessions"], 3)

    def test_window_reports_median_and_p90_not_just_mean(self):
        out = json.loads(run("window", store=self.store).stdout)
        self.assertEqual(out["tool_calls"]["median"], 30)
        self.assertIn("p90", out["tool_calls"])

    def test_window_separates_aggregate_ratios_from_per_session_means(self):
        """A per-session mean and a pooled ratio are different numbers, and the
        pooled one is what a report quotes. Reporting only the mean understates
        delegation badly, because most sessions are small and delegate nothing."""
        store = self.store
        # one big delegating session, four small ones that delegate nothing
        recs = [fingerprint("big", "tb", "session", "2026-08-10", tool_calls=100),
                fingerprint("big", "ab", "subagent", "2026-08-10", tool_calls=300)]
        recs += [fingerprint(f"s{i}", f"t{i}", "session", "2026-08-11", tool_calls=5)
                 for i in range(4)]
        with (store / "2026-09.jsonl").open("w", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r) + "\n")
        out = json.loads(run("window", "--since", "2026-08-10", store=store).stdout)
        self.assertAlmostEqual(out["totals"]["delegated_share"], 300 / 420, places=4)
        self.assertLess(out["delegated_share"]["mean"], 0.2,
                        "the per-session mean should still be reported, and still be low")

    def test_window_counts_sessions_that_actually_did_something(self):
        with (self.store / "2026-09.jsonl").open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(fingerprint("idle", "ti", "session", "2026-08-09",
                                            tool_calls=0, turns=0)) + "\n")
        out = json.loads(run("window", store=self.store).stdout)
        self.assertEqual(out["sessions"], 6)
        self.assertEqual(out["sessions_with_work"], 5,
                         "a session with no tool calls should not dilute the averages")

    def test_empty_window_is_valid_output(self):
        out = json.loads(run("window", "--since", "2027-01-01", store=self.store).stdout)
        self.assertEqual(out["sessions"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
