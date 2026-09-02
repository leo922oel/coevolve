#!/usr/bin/env python3
"""E1-E4: the exported cowork profile is schema-valid, de-identified, and honest
about thin evidence."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "validate_profile.py"

MINIMAL = {
    "schema": "coevolve/cowork-profile/1",
    "generated": "2026-09-02",
    "status": "insufficient_data",
    "window": {"since": "2026-08-01", "until": "2026-09-02", "sessions": 3,
               "note": "fewer than 20 sessions; treat every claim as provisional"},
}

FULL = {
    **MINIMAL,
    "status": "ok",
    "interaction": {
        "session_size": {"n": 113, "median_tool_calls": 65, "p90": 330},
        "delegation": {"n": 113, "delegated_tool_call_share": 0.246},
        "tool_mix": {"Bash": 9882, "Read": 1148},
        "skill_use": {"code-review": 9},
        "model_mix": {"claude-opus-5": 13024},
    },
    "delegation_policy": {
        "trusted_to_ai": [{"claim": "boilerplate and format conversion",
                           "evidence": 12, "confidence": "high"}],
        "reserved_for_human": [{"claim": "defining acceptance criteria",
                                "evidence": 9, "confidence": "high"}],
    },
    "habits": [{"claim": "asks for the crux before asking for a change",
                "evidence": 7, "confidence": "high"}],
    "reusable_patterns": [{"id": "P-second-pass-review", "when": "after a plan is drafted",
                           "move": "dispatch an independent reviewer subagent",
                           "evidence": 7, "confidence": "high"}],
    "failure_modes": [{"id": "L-credentials", "summary": "secrets pasted into a transcript",
                       "severity": "high", "state": "enacted", "enforcement": "hook",
                       "evidence": 2}],
    "boundaries": [{"claim": "anything needing a real machine to confirm",
                    "evidence": 6, "confidence": "high"}],
    "calibration": {"bias": "under-confident on delivered tooling",
                    "evidence": 18, "cycles": 4, "confidence": "high"},
}


def check(profile, denylist=None):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "profile.json"
        path.write_text(json.dumps(profile), encoding="utf-8")
        cmd = [sys.executable, str(SCRIPT), str(path)]
        if denylist is not None:
            deny = Path(tmp) / "denylist.txt"
            deny.write_text("\n".join(denylist) + "\n", encoding="utf-8")
            cmd += ["--denylist", str(deny)]
        return subprocess.run(cmd, capture_output=True, text=True)


class ValidateProfileTest(unittest.TestCase):
    # ---- E3: a brand-new user is a valid case, not an error ----
    def test_e3_empty_profile_is_valid_and_marked(self):
        proc = check(MINIMAL)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_e1_full_profile_validates(self):
        proc = check(FULL)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    # ---- E1: the schema is actually enforced ----
    def test_e1_missing_required_field_is_rejected(self):
        bad = {k: v for k, v in MINIMAL.items() if k != "window"}
        proc = check(bad)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("window", proc.stderr)

    def test_e1_unknown_top_level_field_is_rejected(self):
        proc = check({**MINIMAL, "employer": "Acme"})
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("employer", proc.stderr)

    def test_e1_wrong_schema_id_is_rejected(self):
        proc = check({**MINIMAL, "schema": "something/else"})
        self.assertNotEqual(proc.returncode, 0)

    def test_e1_bad_enum_is_rejected(self):
        proc = check({**MINIMAL, "status": "great"})
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("status", proc.stderr)

    # ---- E4: no claim without its evidence ----
    def test_e4_claim_without_evidence_is_rejected(self):
        bad = json.loads(json.dumps(FULL))
        del bad["habits"][0]["evidence"]
        proc = check(bad)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("evidence", proc.stderr)

    def test_e4_zero_evidence_is_rejected(self):
        bad = json.loads(json.dumps(FULL))
        bad["habits"][0]["evidence"] = 0
        proc = check(bad)
        self.assertNotEqual(proc.returncode, 0)

    def test_histogram_values_must_be_counts(self):
        bad = json.loads(json.dumps(FULL))
        bad["interaction"]["tool_mix"]["Bash"] = "lots"
        proc = check(bad)
        self.assertNotEqual(proc.returncode, 0)

    def test_error_message_names_the_path(self):
        bad = json.loads(json.dumps(FULL))
        bad["reusable_patterns"][0]["confidence"] = "certain"
        proc = check(bad)
        self.assertIn("reusable_patterns[0].confidence", proc.stderr)

    # ---- E2: de-identification is part of the same gate ----
    def test_e2_denylist_term_blocks_export(self):
        leaky = json.loads(json.dumps(FULL))
        leaky["habits"][0]["claim"] = "ships the AcmeCorp pipeline every friday"
        proc = check(leaky, denylist=["AcmeCorp", "orders-etl"])
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("AcmeCorp", proc.stderr)

    def test_e2_denylist_match_is_case_insensitive(self):
        leaky = json.loads(json.dumps(FULL))
        leaky["boundaries"][0]["claim"] = "anything touching ACMECORP staging"
        proc = check(leaky, denylist=["AcmeCorp"])
        self.assertNotEqual(proc.returncode, 0)

    def test_e2_clean_profile_passes_the_denylist(self):
        proc = check(FULL, denylist=["AcmeCorp"])
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_e2_missing_denylist_fails_open_but_loudly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.json"
            path.write_text(json.dumps(FULL), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(path), "--denylist", str(Path(tmp) / "nope.txt")],
                capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("denylist", proc.stderr.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
