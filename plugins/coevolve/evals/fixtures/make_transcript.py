#!/usr/bin/env python3
"""Synthesise a session transcript, so fixtures come from the real extractor.

Fixtures used to be hand-written fingerprint JSON. Four separate eval findings
traced back to that one choice: identical values within a window, byte-identical
token fields, and a main transcript claiming a delegated share that Claude Code
cannot produce. A reader cannot tell an unrealistic fixture from a broken
extractor, so impossible data costs real analysis time — one run refused to
quote its own result until the extractor had been checked.

Writing a transcript and running `session_metrics.py` over it removes the whole
class: every field is computed the way it is computed in production, so a
fixture can only ever hold a state the extractor can emit.

Usage:
  make_transcript.py --out T.jsonl --date 2026-08-03 --project acme
                     --bash 210 --read 85 --edit 0 --errors 27 --turns 38
                     [--interrupts 2] [--hours 8] [--skill diagnose]
                     [--subagent Explore] [--sidechain 0]
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--project", default="proj")
    ap.add_argument("--bash", type=int, default=0)
    ap.add_argument("--read", type=int, default=0)
    ap.add_argument("--edit", type=int, default=0)
    ap.add_argument("--errors", type=int, default=0)
    ap.add_argument("--turns", type=int, default=1)
    ap.add_argument("--interrupts", type=int, default=0)
    ap.add_argument("--hours", type=int, default=1)
    ap.add_argument("--skill", action="append", default=[])
    ap.add_argument("--subagent", action="append", default=[])
    ap.add_argument("--sidechain", type=int, default=0,
                    help="tool calls marked isSidechain, inside this transcript")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    rng = random.Random(args.seed if args.seed is not None else hash(args.out.name) & 0xFFFF)
    sid = f"{args.project}-{args.date}"
    cwd = f"/work/{args.project}"
    lines: list[dict] = []
    clock = [0]

    def ts() -> str:
        m = clock[0]
        clock[0] += max(1, (args.hours * 60) // max(1, args.bash + args.read + args.edit + 1))
        return f"{args.date}T{9 + m // 60:02d}:{m % 60:02d}:00.000Z"

    def assistant(blocks, sidechain=False):
        rec = {"type": "assistant", "timestamp": ts(), "sessionId": sid, "cwd": cwd,
               "message": {"model": "claude-opus-5", "content": blocks,
                           # Real usage varies per turn; a constant here is what
                           # made three runs suspect the extractor.
                           "usage": {"input_tokens": rng.randint(2, 900),
                                     "output_tokens": rng.randint(40, 1200),
                                     "cache_read_input_tokens": rng.randint(1000, 90000),
                                     "cache_creation_input_tokens": rng.randint(0, 4000)}}}
        if sidechain:
            rec["isSidechain"] = True
        lines.append(rec)

    def result(is_error=False):
        lines.append({"type": "user", "timestamp": ts(),
                      "message": {"content": [{"type": "tool_result",
                                               "is_error": is_error, "content": "…"}]}})

    lines.append({"type": "ai-title", "aiTitle": f"{args.project} work {args.date}"})
    for _ in range(args.turns):
        lines.append({"type": "user", "timestamp": ts(),
                      "message": {"content": [{"type": "text", "text": "next step please"}]}})
    for s in args.skill:
        assistant([{"type": "tool_use", "name": "Skill", "input": {"skill": s}}])
        result()
    for a in args.subagent:
        assistant([{"type": "tool_use", "name": "Agent", "input": {"subagent_type": a}}])
        result()

    calls = ([("Bash", True)] * args.bash + [("Read", False)] * args.read
             + [("Edit", False)] * args.edit)
    rng.shuffle(calls)
    errors_left = args.errors
    for i, (name, can_fail) in enumerate(calls):
        assistant([{"type": "tool_use", "name": name, "input": {}}],
                  sidechain=i < args.sidechain)
        fail = can_fail and errors_left > 0 and rng.random() < 0.6
        if fail:
            errors_left -= 1
        result(is_error=fail)
    # Any error budget the shuffle did not spend still has to land.
    for _ in range(errors_left):
        assistant([{"type": "tool_use", "name": "Bash", "input": {}}])
        result(is_error=True)
    for _ in range(args.interrupts):
        lines.append({"type": "user", "timestamp": ts(),
                      "message": {"content": [{"type": "text",
                                               "text": "[Request interrupted by user]"}]}})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for rec in lines:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
