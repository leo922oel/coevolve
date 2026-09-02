#!/usr/bin/env python3
"""Fingerprint the transcripts that already exist, before they age out.

Transcripts are kept for roughly a month. Everything older than that is gone,
so a fresh install starts with an empty history unless it sweeps up what is
still on disk — which is usually a few hundred sessions and the only chance to
have any history at all on day one.

Idempotent: a transcript already in the store is skipped, so this can be run
again as new files appear. Dry-run unless told otherwise.

Usage:
    backfill_metrics.py [--transcripts DIR] [--store DIR] [--apply]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session_metrics import analyse, _read_salt  # noqa: E402


def existing_ids(store: Path) -> set[str]:
    seen: set[str] = set()
    if not store.exists():
        return seen
    for path in store.glob("*.jsonl"):
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                tid = rec.get("transcript_id")
                if tid:
                    seen.add(tid)
    return seen


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--transcripts", type=Path,
                        default=Path(os.path.expanduser("~/.claude/projects")))
    parser.add_argument("--store", type=Path, default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    home = Path(os.environ.get("COEVOLVE_HOME") or os.path.expanduser("~/.claude/coevolve"))
    store = args.store or home / "metrics"
    if not args.transcripts.exists():
        print(f"backfill: no transcripts at {args.transcripts}", file=sys.stderr)
        return 1

    salt = _read_salt(home / "salt")
    known = existing_ids(store)
    files = sorted(args.transcripts.rglob("*.jsonl"))

    # Partition by the SESSION's month, not today's, so date-window queries line
    # up with when the work actually happened.
    buckets: dict[str, list[str]] = {}
    kinds: Counter = Counter()
    skipped = 0
    failed = 0
    for path in files:
        if path.stem in known:
            skipped += 1
            continue
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                fp = analyse(fh, salt, None, path.stem)
        except Exception:
            failed += 1
            continue
        # A transcript that yielded no messages carries no information, and
        # filing it under an "unknown" month would leave a bucket of zeroes that
        # every later average has to be defended against.
        month = (fp.get("started_at") or "")[:7]
        if fp.get("transcript_kind") == "unknown" or not month:
            failed += 1
            continue
        buckets.setdefault(month, []).append(json.dumps(fp, ensure_ascii=False))
        kinds[fp.get("transcript_kind", "unknown")] += 1

    total = sum(len(v) for v in buckets.values())
    print(f"transcripts found : {len(files)}")
    print(f"already captured  : {skipped}")
    print(f"empty/unreadable  : {failed}")
    print(f"to write          : {total}  "
          f"({kinds.get('session', 0)} sessions, {kinds.get('subagent', 0)} subagent)")
    for month in sorted(buckets):
        print(f"  {month}.jsonl  +{len(buckets[month])}")

    if not args.apply:
        print("\ndry run — nothing was written. Re-run with --apply.")
        return 0

    store.mkdir(parents=True, exist_ok=True)
    for month, lines in buckets.items():
        with (store / f"{month}.jsonl").open("a", encoding="utf-8") as fh:
            for line in lines:
                fh.write(line + "\n")
    print(f"\nwrote {total} fingerprints to {store}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
