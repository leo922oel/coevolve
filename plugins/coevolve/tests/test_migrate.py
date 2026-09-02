#!/usr/bin/env python3
"""G1-G4: migration is idempotent, dry-run by default, preserves the calibration
history, and never touches the source tree."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
MIGRATE = HERE.parent / "scripts" / "migrate_worklog.py"
SCAFFOLD = HERE.parent / "scripts" / "scaffold.sh"

CALIBRATION = "## 2026-06-08\n- Aggregate lesson: systematic under-confidence on shipped tooling.\n"
PLAYBOOK = """---
name: dev-playbook
description: a skill description that should not survive
updated: 2026-08-06
---

# Dev Playbook

## Ground rules
1. Verification before generation.
"""


class MigrateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.old = base / "worklog"
        (self.old / "inbox-archive").mkdir(parents=True)
        (self.old / "config.md").write_text(
            "notion_db_id: abc-123\nnotion_db_url: https://example.com/x\n"
            "weekly_due_days: 5\ninbox_nudge_count: 12\n", encoding="utf-8")
        (self.old / "denylist.txt").write_text("acme-corp\n", encoding="utf-8")
        (self.old / "inbox.md").write_text("- [2026-08-01 10:00] a flag\n", encoding="utf-8")
        (self.old / "calibrate-log.md").write_text(CALIBRATION, encoding="utf-8")
        (self.old / "inbox-archive" / "2026-08-04.md").write_text("archived\n", encoding="utf-8")
        self.pb = base / "SKILL.md"
        self.pb.write_text(PLAYBOOK, encoding="utf-8")
        self.new = base / "coevolve"
        subprocess.run(["bash", str(SCAFFOLD), "--home", str(self.new)],
                       capture_output=True, check=True,
                       env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(HERE.parent)})

    def tearDown(self):
        self.tmp.cleanup()

    def run_migrate(self, *extra):
        return subprocess.run(
            [sys.executable, str(MIGRATE), "--from", str(self.old), "--to", str(self.new),
             "--playbook", str(self.pb), *extra], capture_output=True, text=True)

    def test_g3_dry_run_is_the_default(self):
        proc = self.run_migrate()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("would copy", proc.stdout)
        self.assertIn("dry run", proc.stdout)
        self.assertFalse((self.new / "denylist.txt").read_text().strip().endswith("acme-corp"))

    def test_g2_calibration_history_survives(self):
        self.run_migrate("--apply")
        self.assertIn("under-confidence", (self.new / "calibrate-log.md").read_text())
        self.assertTrue((self.new / "inbox-archive" / "2026-08-04.md").exists())

    def test_playbook_becomes_data_not_a_skill(self):
        self.run_migrate("--apply")
        text = (self.new / "playbook.md").read_text()
        self.assertIn("Verification before generation", text)
        self.assertIn("updated: 2026-08-06", text, "distillation cadence depends on this date")
        self.assertNotIn("a skill description that should not survive", text)

    def test_chosen_settings_carry_forward(self):
        self.run_migrate("--apply")
        cfg = (self.new / "config.md").read_text()
        self.assertIn("notion_db_id: abc-123", cfg)
        self.assertIn("weekly_due_days: 5", cfg)
        self.assertIn("inbox_nudge_count: 12", cfg)
        self.assertIn("enact_due_days: 3", cfg, "new keys must keep their defaults")

    def test_denylist_terms_are_carried_over_not_dropped(self):
        self.run_migrate("--apply")
        deny = (self.new / "denylist.txt").read_text()
        self.assertIn("acme-corp", deny, "losing denylist terms silently weakens every export gate")
        self.assertIn("#", deny, "the seeded guidance comments should survive too")

    def test_an_edited_playbook_at_the_destination_is_never_clobbered(self):
        (self.new / "playbook.md").write_text(
            "---\nname: playbook\nupdated: 2026-09-01\n---\nMY OWN WORK\n", encoding="utf-8")
        self.run_migrate("--apply")
        self.assertIn("MY OWN WORK", (self.new / "playbook.md").read_text())

    def test_a_blank_setting_does_not_swallow_the_line_below_it(self):
        """Regression: `key:\\s*.*$` matches across newlines, so substituting a
        key whose template value is blank used to delete the next setting."""
        self.run_migrate("--apply")
        cfg = (self.new / "config.md").read_text()
        self.assertIn("notion_db_url:", cfg, "the following setting was deleted by the merge")

    def test_dry_run_does_not_report_contradictory_actions(self):
        proc = self.run_migrate()
        playbook_lines = [l for l in proc.stdout.splitlines() if "playbook.md" in l]
        self.assertEqual(len(playbook_lines), 1,
                         f"one file, one action; got: {playbook_lines}")

    def test_g1_running_twice_changes_nothing(self):
        self.run_migrate("--apply")
        before = {p.name: p.read_text() for p in self.new.rglob("*") if p.is_file()}
        proc = self.run_migrate("--apply")
        after = {p.name: p.read_text() for p in self.new.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertIn("kept existing", proc.stdout)

    def test_g4_source_tree_is_never_touched(self):
        before = {p.name: p.read_text() for p in self.old.rglob("*") if p.is_file()}
        self.run_migrate("--apply")
        after = {p.name: p.read_text() for p in self.old.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertTrue(self.pb.exists(), "the original playbook skill must survive")

    def test_missing_destination_is_an_error_not_a_surprise_mkdir(self):
        proc = subprocess.run(
            [sys.executable, str(MIGRATE), "--from", str(self.old),
             "--to", str(self.new.parent / "nope"), "--apply"],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("scaffold", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
