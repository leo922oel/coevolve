#!/usr/bin/env python3
"""Migrate an existing dev-worklog installation into a coevolve home.

Copies, never moves, and is dry-run unless told otherwise. The old tree stays
exactly where it is until its owner decides to remove it — a migration that
destroys the source is a migration you can only run once, correctly.

The important piece is the playbook. In the old design it lived inside a skill
file, which is why that setup could never be shared: the "code" and one person's
real project names were the same artifact. Here it becomes ordinary personal
data outside the plugin.

Notion rows are not handled here — that needs the Notion MCP, so the `setup`
skill does it interactively.

Usage:
    migrate_worklog.py [--from DIR] [--to DIR] [--playbook PATH] --apply
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

# old name -> new name. Renames are deliberate: the config grew new keys and a
# couple of old ones now mean something more specific.
CONFIG_MAP = {
    "weekly_due_days": "weekly_due_days",
    "monthly_due_days": "monthly_due_days",
    "inbox_nudge_count": "inbox_nudge_count",
    "calibrate_due_days": "calibrate_due_days",
    "calibrate_min_age_days": "calibrate_min_age_days",
    "distill_lookback_weeks": "distill_lookback_weeks",
    "deidentify": "deidentify",
    "notion_db_id": "notion_db_id",
    "notion_db_url": "notion_db_url",
}

FILES = [
    ("inbox.md", "inbox.md"),
    ("calibrate-log.md", "calibrate-log.md"),
]


def _is_placeholder(path: Path) -> bool:
    """An empty file created by scaffold is a placeholder, not your content.

    Scaffold touches inbox.md and calibrate-log.md so the loop has somewhere to
    write from the first run. Treating those as existing content would silently
    drop the migrated history into a file nobody reads.
    """
    try:
        return path.is_file() and path.stat().st_size == 0
    except OSError:
        return False


class Plan:
    def __init__(self, apply: bool):
        self.apply = apply
        self.actions: list[str] = []

    def copy(self, src: Path, dst: Path, why: str = "") -> None:
        if not src.exists():
            return
        if dst.exists() and not _is_placeholder(dst):
            self.actions.append(f"kept existing   {dst}  (source left untouched)")
            return
        if dst.exists():
            self.actions.append(f"{'replace' if self.apply else 'would replace'}  {dst}  # empty placeholder")
            if self.apply:
                dst.unlink()
        self.actions.append(f"{'copy' if self.apply else 'would copy'}   {src} -> {dst}{'  # ' + why if why else ''}")
        if self.apply:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

    def write(self, dst: Path, text: str, why: str = "", force: bool = False) -> None:
        if dst.exists() and not force:
            self.actions.append(f"kept existing   {dst}")
            return
        if not force:
            self.actions.append(f"{'write' if self.apply else 'would write'}  {dst}{'  # ' + why if why else ''}")
        if self.apply:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(text, encoding="utf-8")


def merge_config(old_cfg: Path, new_cfg: Path, plan: Plan) -> None:
    """Carry forward the settings the user actually chose, leave new keys at their defaults."""
    if not old_cfg.exists() or not new_cfg.exists():
        return
    old_values = {}
    for line in old_cfg.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^[ \t]*([a-z_]+):[ \t]*(.*)$", line)
        if m and m.group(1) in CONFIG_MAP and m.group(2).strip():
            old_values[CONFIG_MAP[m.group(1)]] = m.group(2).strip()
    if not old_values:
        return
    text = new_cfg.read_text(encoding="utf-8")
    changed = []
    for key, value in old_values.items():
        pattern = re.compile(rf"^([ \t]*{re.escape(key)}:)[ \t]*.*$", re.MULTILINE)
        if pattern.search(text):
            text = pattern.sub(rf"\1 {value}", text)
            changed.append(f"{key}={value}")
    if changed:
        plan.actions.append(
            f"{'merge' if plan.apply else 'would merge'}  config: {', '.join(changed)}")
        if plan.apply:
            new_cfg.write_text(text, encoding="utf-8")


def convert_playbook(src: Path, dst: Path, plan: Plan) -> None:
    """A skill file becomes plain personal data.

    The old frontmatter described a skill; only `updated:` still means anything
    here, and it must survive because `status` uses it to decide when the next
    distillation is due.
    """
    replacing_seed = False
    if not src.exists():
        return
    # An untouched seed is not user data. Scaffold writes one so a fresh install
    # has something to read; refusing to replace it would silently drop the real
    # playbook, which is the single thing this migration exists to move.
    if dst.exists():
        existing = dst.read_text(encoding="utf-8")
        if re.search(r"^updated:[ \t]*SEED[ \t]*$", existing, re.MULTILINE):
            plan.actions.append(
                f"{'replace' if plan.apply else 'would replace'}  {dst}  # still the untouched seed")
            if plan.apply:
                dst.unlink()
            replacing_seed = True
        else:
            plan.actions.append(f"kept existing   {dst}  (already has your own content)")
            return
    raw = src.read_text(encoding="utf-8")
    updated = ""
    body = raw
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.DOTALL)
    if m:
        front, body = m.group(1), m.group(2)
        um = re.search(r"^updated:\s*(\S+)", front, re.MULTILINE)
        if um:
            updated = um.group(1)
    new = f"---\nname: playbook\nupdated: {updated or 'unknown'}\n---\n{body.lstrip(chr(10))}"
    plan.write(dst, new, why="playbook moves out of the plugin; it is your data, not code",
               force=replacing_seed)


def merge_denylist(old: Path, new: Path, plan: Plan) -> None:
    """Union, never replace.

    Scaffold ships a denylist of comments only, so a plain copy would be skipped
    and every term the user had accumulated would quietly stop being enforced —
    a privacy regression that nothing downstream would notice.
    """
    if not old.exists() or not new.exists():
        return
    def terms(text):
        return [l.strip() for l in text.splitlines()
                if l.strip() and not l.strip().startswith("#")]
    current = new.read_text(encoding="utf-8")
    have = {t.lower() for t in terms(current)}
    missing = [t for t in terms(old.read_text(encoding="utf-8")) if t.lower() not in have]
    if not missing:
        return
    plan.actions.append(
        f"{'merge' if plan.apply else 'would merge'}  denylist: +{len(missing)} term(s) carried over")
    if plan.apply:
        suffix = "" if current.endswith("\n") else "\n"
        new.write_text(current + suffix + "\n".join(missing) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--from", dest="src", type=Path,
                        default=Path(os.path.expanduser("~/.claude/worklog")))
    parser.add_argument("--to", dest="dst", type=Path, default=None)
    parser.add_argument("--playbook", type=Path,
                        default=Path(os.path.expanduser("~/.claude/skills/dev-playbook/SKILL.md")))
    parser.add_argument("--apply", action="store_true",
                        help="actually write; without it nothing is touched")
    args = parser.parse_args(argv)

    dst = args.dst or Path(os.environ.get("COEVOLVE_HOME")
                           or os.path.expanduser("~/.claude/coevolve"))
    if not args.src.exists() and not args.playbook.exists():
        print(f"migrate_worklog: nothing to migrate from {args.src}", file=sys.stderr)
        return 1
    if not dst.exists():
        print(f"migrate_worklog: {dst} does not exist — run scaffold.sh first", file=sys.stderr)
        return 2

    plan = Plan(args.apply)
    for old, new in FILES:
        plan.copy(args.src / old, dst / new)
    merge_denylist(args.src / "denylist.txt", dst / "denylist.txt", plan)
    if (args.src / "inbox-archive").exists():
        target = dst / "inbox-archive"
        for f in sorted((args.src / "inbox-archive").glob("*.md")):
            plan.copy(f, target / f.name)
    merge_config(args.src / "config.md", dst / "config.md", plan)
    convert_playbook(args.playbook, dst / "playbook.md", plan)

    for action in plan.actions:
        print(action)
    if not plan.actions:
        print("nothing to do — everything already migrated")
    if not args.apply:
        print("\ndry run — nothing was written. Re-run with --apply.")
    else:
        print(f"\nDone. The old tree at {args.src} was NOT modified; remove it yourself "
              f"once you have confirmed the calibration history came across intact.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
