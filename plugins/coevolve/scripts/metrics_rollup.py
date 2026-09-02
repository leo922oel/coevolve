#!/usr/bin/env python3
"""Roll per-transcript fingerprints up into sessions, and compare windows of them.

`session_metrics.py` looks at one transcript file. That is the wrong unit for
almost every question worth asking, for two reasons:

  * About half the transcript files on a real machine are subagent sidechains
    carrying their parent's session id. A session's true cost includes what its
    subagents did, so those have to be folded back in.
  * A long session fires Stop repeatedly, so the store accumulates several
    fingerprints of the same transcript at different points in its life. Only
    the last one is true.

The `compare` subcommand is the VERIFY stage's engine: given a metric chosen
*before* the outcome was known and the date a lesson was enacted, it puts the
two windows next to each other. It refuses to name a direction when either
window is too thin — a lesson "verified" off two sessions is worse than an
unverified one, because it retires a real problem on noise.

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path


def default_store() -> Path:
    import os
    home = os.environ.get("COEVOLVE_HOME") or os.path.expanduser("~/.claude/coevolve")
    return Path(home) / "metrics"


def load_fingerprints(store: Path) -> list[dict]:
    """Latest record wins per transcript; malformed lines are skipped, not fatal."""
    latest: dict[str, dict] = {}
    order: list[str] = []
    if not store.exists():
        return []
    for path in sorted(store.glob("*.jsonl")):
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(rec, dict):
                    continue
                key = rec.get("transcript_id") or f"{rec.get('session_id','')}::{rec.get('transcript_kind','')}"
                if key not in latest:
                    order.append(key)
                latest[key] = rec
    return [latest[k] for k in order]


def _merge(target: Counter, source) -> None:
    if isinstance(source, dict):
        for k, v in source.items():
            if isinstance(v, int):
                target[k] += v


def roll_up(fingerprints: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for fp in fingerprints:
        sid = fp.get("session_id") or fp.get("transcript_id") or "unknown"
        row = grouped.get(sid)
        if row is None:
            row = grouped[sid] = {
                "session_id": sid,
                "project_key": fp.get("project_key", ""),
                "started_at": fp.get("started_at", ""),
                "ended_at": fp.get("ended_at", ""),
                "own_tool_calls": 0, "delegated_tool_calls": 0,
                "user_turns": 0, "tool_errors": 0, "interrupts": 0,
                "tool_results": 0, "assistant_messages": 0,
                "transcripts": {"session": 0, "subagent": 0, "unknown": 0},
                "_tools": Counter(), "_skills": Counter(),
                "_subagents": Counter(), "_models": Counter(), "_tokens": Counter(),
            }
        kind = fp.get("transcript_kind", "unknown")
        row["transcripts"][kind] = row["transcripts"].get(kind, 0) + 1
        counts = fp.get("counts", {}) or {}
        calls = int(counts.get("tool_calls") or 0)
        if kind == "subagent":
            row["delegated_tool_calls"] += calls
        else:
            # A main transcript can carry sidechain calls of its own. Reading
            # only separate subagent rows discarded the fingerprint's own
            # measurement, so two fields that should agree could disagree with
            # nothing to notice. Zero on every real transcript today, because
            # subagent work goes to its own file — which is exactly the sort of
            # assumption that changes without announcement.
            inner = int(round(float((fp.get("derived") or {})
                                    .get("delegated_tool_call_share") or 0.0) * calls))
            inner = max(0, min(inner, calls))
            row["delegated_tool_calls"] += inner
            row["own_tool_calls"] += calls - inner
        row["user_turns"] += int(counts.get("user_turns") or 0)
        row["tool_errors"] += int(counts.get("tool_errors") or 0)
        row["interrupts"] += int(counts.get("interrupts") or 0)
        row["tool_results"] += int(counts.get("tool_results") or 0)
        row["assistant_messages"] += int(counts.get("assistant_messages") or 0)
        _merge(row["_tools"], fp.get("tools"))
        _merge(row["_skills"], fp.get("skills"))
        _merge(row["_subagents"], fp.get("subagents"))
        _merge(row["_models"], fp.get("models"))
        _merge(row["_tokens"], fp.get("tokens"))
        started, ended = fp.get("started_at", ""), fp.get("ended_at", "")
        if started and (not row["started_at"] or started < row["started_at"]):
            row["started_at"] = started
        if ended and ended > row["ended_at"]:
            row["ended_at"] = ended
        if not row["project_key"]:
            row["project_key"] = fp.get("project_key", "")

    rows = []
    for row in grouped.values():
        total = row["own_tool_calls"] + row["delegated_tool_calls"]
        tools = _stable(row.pop("_tools"))
        skills = _stable(row.pop("_skills"))
        subagents = _stable(row.pop("_subagents"))
        models = _stable(row.pop("_models"))
        tokens = dict(row.pop("_tokens"))
        row["tool_calls"] = total
        row["tools"], row["skills"] = tools, skills
        row["subagents"], row["models"] = subagents, models
        row["tokens"] = tokens
        row["counts"] = {
            "tool_calls": total,
            "own_tool_calls": row["own_tool_calls"],
            "delegated_tool_calls": row["delegated_tool_calls"],
            "tool_results": row["tool_results"],
            "tool_errors": row["tool_errors"],
            "interrupts": row["interrupts"],
            "user_turns": row["user_turns"],
            "assistant_messages": row["assistant_messages"],
        }
        row["derived"] = {
            "error_rate": _ratio(row["tool_errors"], total),
            "interrupt_rate": _ratio(row["interrupts"], total),
            "bash_share": _ratio(tools.get("Bash", 0), total),
            "turns_per_100_tool_calls": _ratio(row["user_turns"] * 100, total),
            "delegated_share": _ratio(row["delegated_tool_calls"], total),
            "skill_calls": sum(skills.values()),
            "subagent_calls": sum(subagents.values()),
        }
        rows.append(row)
    rows.sort(key=lambda r: (r["started_at"], r["session_id"]))
    return rows


def _stable(counter: Counter) -> dict:
    return {k: v for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))}


def _ratio(num, den) -> float:
    return round(num / den, 6) if den else 0.0


def _dig(row: dict, path: str):
    node = row
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, (int, float)) else None


def _session_signature(row: dict) -> tuple:
    """What makes two sessions the same observation wearing two hats.

    Shape, not content: how much work, how much steering, on which project. Two
    runs agreeing on all three are one observation however much the compared
    metric differs between them.

    The date is deliberately excluded. Different days is weak evidence of
    independence — a scripted daily run has different dates and an identical
    shape — and including it makes the check fire on almost nothing.
    """
    return (row.get("tool_calls", 0),
            row.get("user_turns", 0),
            row.get("project_key", ""))


def _stats(values: list[float], rows: list[dict] | None = None) -> dict:
    if not values:
        return {"n": 0, "distinct_values": 0, "distinct_sessions": 0,
                "mean": 0.0, "median": 0.0, "p90": 0.0, "min": 0.0, "max": 0.0}
    ordered = sorted(values)
    idx = max(0, int(len(ordered) * 0.9) - 1)
    return {
        "n": len(ordered),
        # A count is not independence. Six sessions carrying the same value are
        # one observation wearing six hats, and a minimum-n threshold cannot see
        # the difference — so the spread is reported alongside the count.
        "distinct_values": len(set(ordered)),
        # And the metric is only one column. Rows identical in shape are not
        # independent either, however much the compared column moves.
        "distinct_sessions": len({_session_signature(r) for r in rows}) if rows else len(set(ordered)),
        "mean": round(statistics.mean(ordered), 6),
        "median": round(statistics.median(ordered), 6),
        "p90": round(ordered[idx], 6),
        "min": round(ordered[0], 6),
        "max": round(ordered[-1], 6),
    }


def apply_filters(rows, wheres):
    """Restrict to a subpopulation before comparing.

    Every eval run that met a confounded result reached the same conclusion —
    compare like with like, inside one project — and none of them could express
    it, because this did not exist. A tool that can diagnose a confound and not
    control for it leaves the correct next step unreachable.

    An unknown field is an error rather than an empty result: silently comparing
    nothing looks identical to comparing something and finding no sessions.
    """
    if not wheres:
        return rows, None
    parsed = []
    for clause in wheres:
        if "=" not in clause:
            raise ValueError(f"--where needs field=value, got {clause!r}")
        field, value = clause.split("=", 1)
        parsed.append((field.strip(), value.strip()))
    known = set()
    for row in rows:
        known.update(k for k, v in row.items() if isinstance(v, (str, int, float)))
    for field, _ in parsed:
        if rows and field not in known:
            raise ValueError(f"unknown field {field!r}; try one of: "
                             + ", ".join(sorted(known)[:12]))
    kept = [r for r in rows if all(str(r.get(f, "")) == v for f, v in parsed)]
    return kept, list(wheres)


def _in_window(row, since, until) -> bool:
    day = (row.get("started_at") or "")[:10]
    if since and day < since:
        return False
    if until and day > until:
        return False
    return True


def cmd_sessions(rows, _args) -> int:
    for row in rows:
        json.dump(row, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
    return 0


def cmd_window(rows, args) -> int:
    try:
        rows, applied = apply_filters(rows, args.where)
    except ValueError as exc:
        print(f"metrics_rollup: {exc}", file=sys.stderr)
        return 2
    rows = [r for r in rows if _in_window(r, args.since, args.until)]
    worked = [r for r in rows if r["tool_calls"] > 0]
    out = {
        "since": args.since or "", "until": args.until or "",
        **({"where": applied} if applied else {}),
        "sessions": len(rows),
        "sessions_with_work": len(worked),
        # Pooled ratios, not averages of ratios. These are different numbers and
        # the pooled one is what a report should quote: most sessions are small,
        # so a mean of per-session shares is dominated by sessions where almost
        # nothing happened. Both are reported so neither can be mistaken for the
        # other.
        "totals": _totals(rows),
        "tool_calls": _stats([r["tool_calls"] for r in rows]),
        "user_turns": _stats([r["user_turns"] for r in rows]),
        "error_rate": _stats([r["derived"]["error_rate"] for r in rows]),
        "interrupts": _stats([r["interrupts"] for r in rows]),
        "delegated_share": _stats([r["derived"]["delegated_share"] for r in rows]),
        "tools": _stable(_sum_maps(rows, "tools")),
        "skills": _stable(_sum_maps(rows, "skills")),
        "subagents": _stable(_sum_maps(rows, "subagents")),
        "models": _stable(_sum_maps(rows, "models")),
        "sessions_using_a_skill": sum(1 for r in rows if r["skills"]),
    }
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def _totals(rows) -> dict:
    tool_calls = sum(r["tool_calls"] for r in rows)
    delegated = sum(r["delegated_tool_calls"] for r in rows)
    errors = sum(r["tool_errors"] for r in rows)
    return {
        "tool_calls": tool_calls,
        "own_tool_calls": sum(r["own_tool_calls"] for r in rows),
        "delegated_tool_calls": delegated,
        "delegated_share": _ratio(delegated, tool_calls),
        "tool_errors": errors,
        "error_rate": _ratio(errors, tool_calls),
        "interrupts": sum(r["interrupts"] for r in rows),
        "user_turns": sum(r["user_turns"] for r in rows),
        "sessions_interrupted": sum(1 for r in rows if r["interrupts"] > 0),
    }


def _sum_maps(rows, key) -> Counter:
    total: Counter = Counter()
    for row in rows:
        _merge(total, row.get(key))
    return total


def _load_baseline(path: Path, metric: str):
    """A before-window snapshot taken at enactment time.

    The before side of a comparison is closed the moment a change ships: every
    session earlier than the split has already happened. Recomputing it later
    therefore depends entirely on transcripts that expire, which is how a lesson
    ends up permanently unverifiable. Capturing the baseline while the data
    exists is the only thing that survives that.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("baseline"), dict):
        data = data["baseline"]          # tolerate a whole lesson record
    if not isinstance(data, dict) or "n" not in data or "mean" not in data:
        raise ValueError("a baseline snapshot needs at least 'n' and 'mean'")
    stored_metric = data.get("metric")
    if stored_metric and stored_metric != metric:
        # Comparing today's metric against yesterday's snapshot of a different
        # one is worse than having no baseline, because it looks like a result.
        raise ValueError(f"baseline is for {stored_metric!r}, not {metric!r}")
    mean = float(data["mean"])
    n = int(data["n"])
    return {
        "n": n,
        "distinct_values": data.get(
            "distinct_values",
            1 if n > 1 and data.get("min", mean) == data.get("max", mean) else None),
        "mean": mean,
        "median": float(data.get("median", mean)),
        "p90": float(data.get("p90", mean)),
        "min": float(data.get("min", mean)),
        "max": float(data.get("max", mean)),
        "captured": data.get("captured", ""),
    }


def cmd_baseline(rows, args) -> int:
    """Snapshot one metric's before-window, for a lesson to carry.

    Run at enactment time, while the sessions that will become "before" are
    still in the store. After that the window is closed and the transcripts
    behind it start expiring, so this is the last moment the number exists.
    """
    from datetime import date

    subset = [r for r in rows if (r.get("started_at") or "")[:10] < args.until]
    values = []
    for row in subset:
        val = _dig(row, args.metric)
        if val is None:
            print(f"metrics_rollup: unknown metric path: {args.metric}", file=sys.stderr)
            return 2
        values.append(val)
    stats = _stats(values, subset)
    thin = stats["n"] < args.min_n
    degenerate = stats["n"] > 1 and (stats["distinct_values"] == 1
                                     or stats["distinct_sessions"] == 1)
    stats.update({
        "metric": args.metric,
        "captured_until": args.until,
        "captured": date.today().isoformat(),
        # Said plainly at capture time, because enactment is the only moment
        # anything can still be done about it. Two ways to be useless and they
        # are not the same: too few sessions, or enough sessions that are all
        # the same observation. `usable` is the one ENACT should read — reading
        # `too_thin` alone reports twenty-four identical sessions as fine.
        "too_thin": thin,
        "degenerate": degenerate,
        "usable": not thin and not degenerate,
        "min_n": args.min_n,
    })
    json.dump(stats, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def _composition(before_rows, after_rows) -> tuple[dict, str | None]:
    """Describe what each window was made of, not just how much of it there was.

    `blocked_by` guards the count. Nothing guarded the contents, so a comparison
    across two windows holding entirely different work returned a clean verdict —
    true about the numbers, misleading about the change. Seven eval runs found
    this by hand, every time from fields already sitting in the row.

    The verdict is not blocked. The numbers are real, and sometimes a shift in
    what you worked on is exactly what you meant to measure. But a `measured`
    that arrives with "these windows share no project and the tool mix halved"
    is a different sentence from one that does not.
    """
    def projects(rows):
        return {r.get("project_key") for r in rows if r.get("project_key")}

    def median_calls(rows):
        vals = sorted(r.get("tool_calls", 0) for r in rows)
        return statistics.median(vals) if vals else 0.0

    def bash_share(rows):
        total = sum(r.get("tool_calls", 0) for r in rows)
        bash = sum((r.get("tools") or {}).get("Bash", 0) for r in rows)
        return round(bash / total, 6) if total else 0.0

    pb, pa = projects(before_rows), projects(after_rows)
    mb, ma = median_calls(before_rows), median_calls(after_rows)
    bb, ba = bash_share(before_rows), bash_share(after_rows)
    comp = {
        "projects_before": sorted(pb),
        "projects_after": sorted(pa),
        "shared_projects": len(pb & pa),
        "median_tool_calls_before": mb,
        "median_tool_calls_after": ma,
        "size_ratio": round(ma / mb, 6) if mb else 0.0,
        "bash_share_before": bb,
        "bash_share_after": ba,
    }
    reasons = []
    if not before_rows or not after_rows:
        # An empty window is a count problem, and `blocked_by` already says so.
        # Reporting drift as well would double-report it, and "the Bash share
        # moved from 0.70 to 0.00" describes nothing.
        return comp, None
    if pb and pa and not (pb & pa):
        reasons.append("the two windows share no project")
    if mb and (comp["size_ratio"] < 0.5 or comp["size_ratio"] > 2.0):
        reasons.append(f"median session size moved by {comp['size_ratio']:.2f}x")
    if abs(bb - ba) > 0.2:
        reasons.append(f"the Bash share moved from {bb:.2f} to {ba:.2f}")
    caveat = None
    if reasons:
        caveat = ("; ".join(reasons) + ". The work changed across the split, so a "
                  "metric that moved with it cannot be read as an effect of the "
                  "change alone. Re-run with --where to compare inside one "
                  "population before drawing a conclusion.")
    return comp, caveat


def cmd_compare(rows, args) -> int:
    try:
        rows, applied = apply_filters(rows, args.where)
    except ValueError as exc:
        print(f"metrics_rollup: {exc}", file=sys.stderr)
        return 2
    before_rows = [r for r in rows if (r.get("started_at") or "")[:10] < args.split]
    after_rows = [r for r in rows if (r.get("started_at") or "")[:10] >= args.split]

    def values(subset):
        out = []
        for row in subset:
            val = _dig(row, args.metric)
            if val is None:
                raise KeyError(args.metric)
            out.append(val)
        return out

    try:
        before, after = values(before_rows), values(after_rows)
    except KeyError as exc:
        print(f"metrics_rollup: unknown metric path: {exc.args[0]}", file=sys.stderr)
        return 2

    before_stats = _stats(before, before_rows)
    baseline_source = "store"
    if args.baseline_file:
        try:
            before_stats = _load_baseline(args.baseline_file, args.metric)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"metrics_rollup: {exc}", file=sys.stderr)
            return 2
        baseline_source = "snapshot"

    result = {
        "metric": args.metric,
        "split": args.split,
        "min_n": args.min_n,
        "baseline_source": baseline_source,
        "before": before_stats,
        "after": _stats(after, after_rows),
    }
    if applied:
        result["where"] = applied
    comp, comp_caveat = _composition(before_rows, after_rows)
    result["composition"] = comp
    result["composition_drift"] = comp_caveat is not None
    if comp_caveat:
        result["composition_caveat"] = comp_caveat
    before_thin = before_stats["n"] < args.min_n
    after_thin = len(after) < args.min_n
    if before_thin or after_thin:
        # Naming a direction here would let the loop retire a real lesson on
        # noise, which is worse than leaving it open. But *which* side is thin
        # decides what the user should do, and the two are nothing alike.
        result["verdict"] = "insufficient evidence"
        result["blocked_by"] = ("both" if before_thin and after_thin
                                else "before_window" if before_thin else "after_window")
        notes = []
        if before_thin and baseline_source == "snapshot":
            notes.append(
                f"the stored baseline holds only {before_stats['n']} sessions, below the "
                f"floor of {args.min_n}; it was captured too late to support a verdict")
        elif before_thin:
            notes.append(
                f"the before window is closed - every session earlier than {args.split} has "
                f"already happened, so waiting changes nothing. Only a backfill of transcripts "
                f"still on disk can widen it, and transcripts age out after about 30 days, so "
                f"that option is expiring. In future, capture a baseline at enactment time")
        if after_thin:
            notes.append(
                f"the after window is still filling: {len(after)} of {args.min_n} sessions "
                f"since {args.split}. This one resolves on its own as more sessions accumulate")
        result["note"] = "; ".join(notes)
    else:
        b, a = before_stats["mean"], result["after"]["mean"]
        scale = max(abs(b), 1e-9)
        change = (a - b) / scale
        result["verdict"] = "measured"
        result["relative_change"] = round(change, 6)
        degenerate = [
            side for side, st in (("before", before_stats), ("after", result["after"]))
            if st["n"] > 1 and (st.get("distinct_values") == 1
                                or st.get("distinct_sessions") == 1)
        ]
        result["degenerate_spread"] = bool(degenerate)
        if degenerate:
            result["caveat"] = (
                f"the {' and '.join(degenerate)} window collapses to one observation — "
                f"either every session carries the same value, or the sessions are "
                f"identical in shape — so its effective sample is 1 regardless of n. "
                f"The min-n threshold cannot detect this. Treat the direction as "
                f"unconfirmed until the sessions actually differ from each other.")
        result["direction"] = "flat" if abs(change) < 0.05 else ("down" if change < 0 else "up")
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    # --store belongs to every subcommand rather than the top level, so it can
    # be written after the verb the way people actually type it.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--store", type=Path, default=None,
                        help="directory of fingerprint .jsonl files (default: $COEVOLVE_HOME/metrics)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sessions", parents=[common],
                   help="emit one rolled-up record per session, as JSONL")

    win = sub.add_parser("window", parents=[common],
                         help="aggregate statistics over a date window")
    win.add_argument("--since"), win.add_argument("--until")
    win.add_argument("--where", action="append", metavar="FIELD=VALUE",
                     help="restrict to a subpopulation, e.g. project_key=proj_x (repeatable)")

    base = sub.add_parser("baseline", parents=[common],
                          help="snapshot one metric's before-window, to store in a lesson")
    base.add_argument("--metric", required=True)
    base.add_argument("--until", required=True,
                      help="YYYY-MM-DD the change takes effect; sessions before this are the baseline")
    base.add_argument("--min-n", type=int, default=5)

    cmp_ = sub.add_parser("compare", parents=[common],
                          help="before/after comparison around a split date")
    cmp_.add_argument("--metric", required=True,
                      help="dotted path into a session row, e.g. derived.error_rate")
    cmp_.add_argument("--split", required=True, help="YYYY-MM-DD the change took effect")
    cmp_.add_argument("--min-n", type=int, default=5,
                      help="minimum sessions per side before a direction is named")
    cmp_.add_argument("--where", action="append", metavar="FIELD=VALUE",
                      help="compare like with like — e.g. project_key=proj_x, so a change "
                           "in what you worked on cannot be read as a change in how it went "
                           "(repeatable)")
    cmp_.add_argument("--baseline-file", type=Path, default=None,
                      help="a before-window snapshot captured at enactment time; used "
                           "instead of re-deriving the before window from the store")

    args = parser.parse_args(argv)
    store = args.store or default_store()
    rows = roll_up(load_fingerprints(store))

    if args.command == "sessions":
        return cmd_sessions(rows, args)
    if args.command == "window":
        return cmd_window(rows, args)
    if args.command == "baseline":
        return cmd_baseline(rows, args)
    return cmd_compare(rows, args)


if __name__ == "__main__":
    raise SystemExit(main())
