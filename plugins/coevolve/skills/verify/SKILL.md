---
name: verify
description: Measure whether an enacted lesson actually changed your behaviour, by comparing the metric named at enactment time across sessions before and after. Use when the session-start nudge reports enacted-but-unverified lessons, when the user asks "did that actually help", "is it working", "驗效", "did my error rate drop", or a few weeks after any enact. Refuses to declare a verdict on thin evidence — an unverified lesson is safer than one retired on noise.
---

# Verify

The stage that makes this a loop rather than a pipeline. Without it, "enacted"
just means "I felt like I fixed it".

## 1. Take the enacted, unverified lessons

Read `$COEVOLVE_HOME/lessons/*.md` for `state: enacted`. Each carries the metric
and direction chosen *before* the outcome was known, plus the `enacted:` date
that splits the windows.

If a lesson has `enforcement: none`, there is nothing to measure — check whether
it recurred, and say so qualitatively rather than forcing a number onto it.

## 2. Compare the two windows

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/metrics_rollup.py" compare \
  --metric derived.interrupt_rate --split 2026-08-20 --min-n 5
```

If the lesson carries a `baseline:` snapshot, write it to a file and pass
`--baseline-file`. A snapshot taken at enactment beats one re-derived now:
transcripts expire, so re-deriving quietly measures whatever survived.

Use the metric written in the lesson. Do not substitute a different one because
it looks better — that is the whole reason it was chosen in advance.

The tool reports both windows side by side, and returns
`verdict: insufficient evidence` when either side is thinner than `--min-n`. Do
not talk past that. A lesson retired on two sessions of noise is worse than one
left open, because the real problem is now marked solved.

**When it refuses, read `blocked_by` before saying anything — the two cases call
for opposite advice:**

- `after_window` — the change is too recent. This resolves by itself; say roughly
  how many more sessions are needed and move on.
- `before_window` — the comparison is **stuck, not pending**. Every session
  earlier than the split has already happened, so waiting will never help, and
  the transcripts that could still widen it are expiring. Telling the user to
  check back later here is actively wrong: it converts a fixable problem into a
  lesson that sits in `enacted` forever. Say plainly that the only route is to
  run `backfill_metrics.py` now, or to accept a qualitative check — and that the
  window on the first option is closing.

## 3. Read the result like an adult

- **Moved in the intended direction, both windows adequate** → the enforcement is
  working. Set `state: verified`, record the before/after numbers, and say which
  metric moved by how much.
- **Flat** → the enforcement did not reach the behaviour. Send it back to
  `coevolve:enact` with what you learned: usually the layer was wrong (a rule
  where a hook was needed), or it fires in the wrong moment.
- **Moved the wrong way** → look for the cost. Enforcement has side effects: a
  blocking hook can push work into paths the fingerprint does not see. Say so
  rather than quietly reverting.
- **Insufficient evidence** → say exactly how many sessions are on each side and
  roughly when there will be enough. Leave the state as `enacted`.

Before concluding, ask one question of the data: **could something else explain
this?** A month with different work in it moves every metric. Where a
confounder is plausible, name it and lower the confidence rather than claiming a
clean result — a verification stage that always confirms is just a slower way of
guessing.

## 4. Record

Update the lesson's frontmatter (`state`, `verified:`) and append the numbers to
its History. That record is what makes the claim auditable later — a report that
says "interrupt rate fell from 0.31 to 0.12 across 14 and 11 sessions" survives
scrutiny in a way that "we fixed it" does not.

## 5. Retire when it is genuinely over

A verified lesson whose enforcement has been quiet for months can move to
`retired`, with the enforcement left in place. Retiring the lesson is not
removing the guard.

## Boundaries

- Reads metrics and lessons; writes only lesson state and history.
- Never invents a comparison metric, never widens a window to reach
  significance, and never states a direction the tool declined to state.
