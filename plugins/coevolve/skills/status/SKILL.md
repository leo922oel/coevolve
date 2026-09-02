---
name: status
description: Read-only status and navigator for the coevolve loop — reports how much is uncurated, which predictions are pending, which lessons are stuck unenforced, when you last calibrated / distilled / verified, and recommends exactly ONE next action. Also has a report mode that assembles an evidence-backed write-up of how you use AI (what for, what suits it, measured effect, techniques, boundaries) for a manager, a team, or a talk. Use whenever the user asks "where am I with the worklog / coevolve", "what should I run next", "how much have I got queued", "am I behind on any of this", or wants to turn accumulated sessions into a report or share-out. Never writes anything.
---

# Status

Read-only, always. State is derived from the artifacts on disk, never from a
status file — a status file is one more thing that can be wrong.

## 1. Derive the state

Read `$COEVOLVE_HOME/config.md`, then:

| What | Where it comes from |
|---|---|
| stuck lessons | `lessons/*.md` with `severity: high` and `state: logged` |
| unverified lessons | `lessons/*.md` with `state: enacted` |
| pending predictions | line count in `predictions/pending.jsonl` |
| pending curation | `^- ` lines in `inbox.md`; age from the **oldest** entry's date |
| last curated | newest filename in `inbox-archive/` — each run archives as `<date>.md` |
| last calibrated | newest date in `calibrate-log.md` |
| last distilled | `updated:` in `playbook.md` frontmatter |
| measured activity | `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/metrics_rollup.py" window --since <date>` |

Deriving "last curated" from the archive rather than from episode dates matters:
back-filled episodes carry old task dates and would report curation as overdue
forever.

## 2. Report: a short table, then one recommendation

Recommend exactly one thing, in this order of precedence:

1. **A high-severity lesson still sitting in `logged`** past `enact_due_days` →
   `coevolve:enact`. This outranks everything, including collecting more
   material. The failure this system exists to fix was a lesson that got
   written down, filed, and repeated two weeks later — capturing more while a
   known high-severity lesson goes unenforced is motion, not progress.
2. Pending predictions → `coevolve:predict`. Ten seconds, and they decay:
   a prediction reconstructed a week later is a memory, not a prediction.
3. Enacted-but-unverified lessons past a couple of weeks → `coevolve:verify`.
4. Inbox at or over `inbox_nudge_count`, or older than `weekly_due_days` →
   `coevolve:curate`.
5. Calibration older than `calibrate_due_days` → `coevolve:calibrate`.
6. Distillation older than `monthly_due_days` **and** roughly ten new episodes →
   `coevolve:distill`.
7. Otherwise: nothing is due. Say so in one line and stop.

Resist listing everything that is slightly overdue. A navigator that returns
seven tasks is a to-do list, and to-do lists get ignored.

## Report mode

When the user wants a write-up — for a manager, a team, a talk — assemble it
from evidence and be explicit about the strength of each part:

- **What the AI gets used for, and with what** — group episodes by task type and
  tool combination. Cross-check against the measured `skills` and `subagents`
  histograms from `metrics_rollup window`; where the story and the measurement
  disagree, the measurement wins and the disagreement is itself worth reporting.
- **What it suits** — rank task types by recorded fit.
- **Measured effect** — this is where most reports quietly cheat. Separate three
  tiers and never merge them: (a) **deterministic metrics** from the fingerprint
  — session sizes, delegation share, error and interrupt rates, before/after
  comparisons from verified lessons; (b) **calibrated self-estimates** — episodes
  whose prediction was checked against the outcome; (c) **uncalibrated
  self-estimates** — label these as self-assessed and never quote them as
  measurement. Report ranges, not single numbers. If there is nothing in (a) or
  (b), say so plainly rather than dressing up (c).
- **Techniques that work** — from `patterns/`, each with its evidence count.
- **Boundaries** — from `lessons/` and the playbook's "when not to reach for the
  AI", plus the configured-but-unused finding: compare installed skills and MCP
  servers against the measured invocation histogram. Configuration is not usage,
  and the gap is usually large and always interesting.

Flag any section standing on thin evidence so it gets more capture before the
report goes anywhere.

## Boundaries

- Never writes a file — not even a cache. The artifacts are the truth.
- Never creates episodes, edits the playbook, or changes a lesson's state.
