#!/usr/bin/env python3
"""Turn one Claude Code session transcript into a deterministic fingerprint.

This is the measurement floor of the whole loop. Everything downstream — and
the VERIFY stage in particular, which has to answer "did my behaviour actually
change after I enacted that lesson" — is only as trustworthy as this script.
So it holds two lines absolutely:

  * **Counts and vocabulary only, never content.** Tool names, skill names,
    subagent types and model ids are drawn from a fixed vocabulary and are safe
    to keep. Prompts, file contents, paths, branch names and commands are not,
    and never enter the output. A fingerprint you would hesitate to hand to
    someone is a fingerprint you will stop collecting.
  * **Same input, same bytes out.** No clocks, no randomness, no set iteration
    order. Before/after comparison is meaningless if the measurement drifts.

Stdlib only, so it runs anywhere python3 does.

Usage:
    session_metrics.py TRANSCRIPT.jsonl [--salt-file PATH] [--label LABEL]
    session_metrics.py -   # read the transcript on stdin
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

SCHEMA = "coevolve/session-metrics/1"

# A user "turn" means the human steering the work. Transcripts also route
# command echoes, task notifications and system reminders through user lines;
# counting those would inflate the one number that tells you how much manual
# course-correction a session needed.
NON_TURN_PREFIXES = (
    "<command-name>", "<command-message>", "<local-command",
    "<task-notification>", "<system-reminder>", "<user-prompt-submit-hook>",
)
INTERRUPT_MARKER = "Request interrupted by user"


def _iter_records(handle):
    """Yield parsed records; count what will not parse instead of dying on it.

    Transcripts are appended to live and can be truncated mid-write, so a
    malformed tail is normal rather than exceptional.
    """
    errors = 0
    total = 0
    for line in handle:
        line = line.strip()
        if not line:
            continue
        total += 1
        try:
            obj = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            errors += 1
            continue
        if isinstance(obj, dict):
            yield obj
        else:
            errors += 1
    _iter_records.errors = errors  # type: ignore[attr-defined]
    _iter_records.total = total    # type: ignore[attr-defined]


def _content_blocks(message):
    """Normalise a message's content to a list of blocks.

    Content is sometimes a bare string and sometimes a list of typed blocks;
    treating the string case as a single text block keeps callers simple.
    """
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    return []


def _texts(blocks):
    return [b.get("text", "") for b in blocks if b.get("type") == "text"]


def _is_steering_turn(texts) -> bool:
    joined = "".join(texts).strip()
    if not joined:
        return False
    if INTERRUPT_MARKER in joined:
        return False
    return not joined.startswith(NON_TURN_PREFIXES)


def _project_key(cwd: str, salt: str) -> str:
    """Stable, non-identifying grouping key for a working directory.

    Sessions need to be groupable by project — "my error rate on project X
    halved" is a useful sentence — without the directory name, which routinely
    contains a customer or product name, ever leaving the machine.
    """
    if not cwd:
        return "proj_00000000"
    digest = hashlib.sha256((salt + "\x00" + cwd).encode("utf-8")).hexdigest()
    return "proj_" + digest[:8]


def _read_salt(salt_file: Path | None) -> str:
    if salt_file and salt_file.exists():
        return salt_file.read_text(encoding="utf-8").strip()
    # No salt configured: still deterministic, just not unlinkable. Setup
    # writes a real salt; this keeps the script usable standalone.
    return "coevolve-default-salt"


def analyse(handle, salt: str, label: str | None, transcript_id: str = "") -> dict:
    tools: Counter = Counter()
    skills: Counter = Counter()
    subagents: Counter = Counter()
    models: Counter = Counter()
    perm_modes: Counter = Counter()
    modes: Counter = Counter()

    tokens = Counter()
    tool_errors = 0
    tool_results = 0
    interrupts = 0
    user_turns = 0
    assistant_messages = 0
    sidechain_tool_calls = 0

    session_id = ""
    cwd = ""
    first_ts = ""
    last_ts = ""
    # A transcript whose every message is a sidechain is a subagent's, not a
    # session's. Deciding from content rather than filename keeps this true
    # even if the naming convention changes.
    message_records = 0
    sidechain_records = 0

    for rec in _iter_records(handle):
        rtype = rec.get("type")
        ts = rec.get("timestamp") or ""
        if ts:
            if not first_ts or ts < first_ts:
                first_ts = ts
            if ts > last_ts:
                last_ts = ts
        if not session_id:
            session_id = rec.get("sessionId") or rec.get("session_id") or ""
        if not cwd:
            cwd = rec.get("cwd") or ""

        if rtype == "permission-mode":
            mode = rec.get("permissionMode")
            if isinstance(mode, str):
                perm_modes[mode] += 1
            continue
        if rtype == "mode":
            mode = rec.get("mode")
            if isinstance(mode, str):
                modes[mode] += 1
            continue

        if rtype in ("assistant", "user"):
            message_records += 1
            if rec.get("isSidechain"):
                sidechain_records += 1

        if rtype == "assistant":
            assistant_messages += 1
            message = rec.get("message")
            if isinstance(message, dict):
                model = message.get("model")
                if isinstance(model, str):
                    models[model] += 1
                usage = message.get("usage")
                if isinstance(usage, dict):
                    tokens["input"] += int(usage.get("input_tokens") or 0)
                    tokens["output"] += int(usage.get("output_tokens") or 0)
                    tokens["cache_read"] += int(usage.get("cache_read_input_tokens") or 0)
                    tokens["cache_creation"] += int(usage.get("cache_creation_input_tokens") or 0)
            for block in _content_blocks(rec.get("message")):
                if block.get("type") != "tool_use":
                    continue
                name = block.get("name")
                if not isinstance(name, str):
                    continue
                tools[name] += 1
                if rec.get("isSidechain"):
                    sidechain_tool_calls += 1
                inp = block.get("input")
                if not isinstance(inp, dict):
                    continue
                # Only two fields are read out of tool inputs, and both are
                # vocabulary rather than content: which skill, which agent.
                if name == "Skill":
                    skill = inp.get("skill")
                    if isinstance(skill, str):
                        skills[skill] += 1
                elif name == "Agent":
                    sub = inp.get("subagent_type")
                    skills_free = sub if isinstance(sub, str) else "unspecified"
                    subagents[skills_free] += 1
            continue

        if rtype == "user":
            blocks = _content_blocks(rec.get("message"))
            for block in blocks:
                if block.get("type") == "tool_result":
                    tool_results += 1
                    if block.get("is_error"):
                        tool_errors += 1
            texts = _texts(blocks)
            if any(INTERRUPT_MARKER in t for t in texts):
                interrupts += 1
            elif not rec.get("isMeta") and not rec.get("isSidechain") and _is_steering_turn(texts):
                user_turns += 1

    parse_errors = getattr(_iter_records, "errors", 0)
    total_lines = getattr(_iter_records, "total", 0)
    tool_calls = sum(tools.values())

    if message_records == 0:
        transcript_kind = "unknown"
    elif sidechain_records == message_records:
        transcript_kind = "subagent"
    else:
        transcript_kind = "session"

    span_days = 0
    if first_ts and last_ts:
        span_days = _day_span(first_ts, last_ts)

    derived = {
        "error_rate": round(tool_errors / tool_calls, 6) if tool_calls else 0.0,
        "interrupt_rate": round(interrupts / tool_calls, 6) if tool_calls else 0.0,
        "bash_share": round(tools.get("Bash", 0) / tool_calls, 6) if tool_calls else 0.0,
        "turns_per_100_tool_calls": round(user_turns * 100 / tool_calls, 6) if tool_calls else 0.0,
        "skill_calls": sum(skills.values()),
        "subagent_calls": sum(subagents.values()),
        "delegated_tool_call_share": (
            round(sidechain_tool_calls / tool_calls, 6) if tool_calls else 0.0
        ),
    }

    return {
        "schema": SCHEMA,
        "session_id": session_id,
        # File stem only: it is a uuid or an agent id, never a directory —
        # directories carry project and customer names. Repeated Stop events
        # on one transcript dedup on this.
        "transcript_id": transcript_id,
        "transcript_kind": transcript_kind,
        "project_key": _project_key(cwd, salt),
        "label": label,
        "started_at": first_ts,
        "ended_at": last_ts,
        "span_days": span_days,
        "counts": {
            "lines": total_lines,
            "parse_errors": parse_errors,
            "tool_calls": tool_calls,
            "tool_results": tool_results,
            "tool_errors": tool_errors,
            "interrupts": interrupts,
            "user_turns": user_turns,
            "assistant_messages": assistant_messages,
        },
        "tools": _sorted(tools),
        "skills": _sorted(skills),
        "subagents": _sorted(subagents),
        "models": _sorted(models),
        "permission_modes": sorted(perm_modes),
        "modes": sorted(modes),
        "tokens": {k: tokens[k] for k in ("input", "output", "cache_read", "cache_creation")},
        "derived": derived,
    }


def _day_span(first_ts: str, last_ts: str) -> int:
    """Whole days between two ISO timestamps, without importing a date parser.

    Transcripts are resumable, so a "session" can stretch across days; knowing
    that stops the curation stage from treating one file as one work episode.
    """
    try:
        from datetime import datetime

        def parse(value: str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))

        return max(0, (parse(last_ts) - parse(first_ts)).days)
    except Exception:
        return 0


def _sorted(counter: Counter) -> dict:
    # Sort by count then name so the output is byte-stable across runs.
    return {k: v for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("transcript", help="path to a session .jsonl, or - for stdin")
    parser.add_argument("--salt-file", type=Path,
                        default=_default_salt_file(),
                        help="file holding the project-key salt (default: $COEVOLVE_HOME/salt)")
    parser.add_argument("--label", default=None,
                        help="optional caller-supplied label; the caller owns its safety")
    args = parser.parse_args(argv)

    salt = _read_salt(args.salt_file)
    if args.transcript == "-":
        result = analyse(sys.stdin, salt, args.label, "")
    else:
        path = Path(args.transcript)
        if not path.exists():
            print(f"session_metrics: no such transcript: {path}", file=sys.stderr)
            return 2
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            result = analyse(fh, salt, args.label, path.stem)

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2, sort_keys=False)
    sys.stdout.write("\n")
    return 0


def _default_salt_file() -> Path:
    home = os.environ.get("COEVOLVE_HOME") or os.path.expanduser("~/.claude/coevolve")
    return Path(home) / "salt"


if __name__ == "__main__":
    raise SystemExit(main())
