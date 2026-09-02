---
name: distill
description: Turn accumulated episodes, fingerprints, and calibration history into the four things worth keeping — habits, reusable patterns, failure lessons, and your measured interaction profile — and propose a diff to your personal playbook. Use monthly, when the session-start nudge says distillation is due, or when the user says "distill", "蒸餾", "what patterns am I repeating", "update my playbook", "what have I learned lately". Proposes; never writes the playbook silently.
---

# Distill

Episodes are raw material. This turns them into the four families, each of which
lives differently:

| Family | Where it goes | What makes it real |
|---|---|---|
| habits & tool combinations | playbook sections | repetition across episodes |
| reusable patterns | `patterns/*.md` | a trigger you can recognise in the moment |
| failure lessons | `lessons/*.md` | a mechanism, and a way to enforce it |
| interaction profile | measured, not written | the fingerprint |

## 1. Read all four inputs

```bash
HOME_DIR="${COEVOLVE_HOME:-$HOME/.claude/coevolve}"
ls "$HOME_DIR/episodes"/*.md
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/metrics_rollup.py" window --since <last distill date>
cat "$HOME_DIR/calibrate-log.md"
ls "$HOME_DIR/lessons"/*.md "$HOME_DIR/patterns"/*.md 2>/dev/null
```

Start from the measurement, not the story. The fingerprint will contradict the
narrative sometimes — a skill everyone "always uses" that shows up twice, a
session size remembered as moderate that measures in the hundreds. Where they
disagree, the measurement wins, and the disagreement is itself a finding worth
writing down.

## 2. Let the sample size set the standard

**Ten or more new episodes** — look for repetition: tool combinations recurring
three or more times within a task type, repeated effective moves, repeated
limits hit, fit trends by task type.

**Fewer than ten** — still distill, but qualitatively, and label every entry
`small sample (n=X), low confidence`. Never skip the cycle silently; a quarter
of quiet months is how a playbook goes stale without anyone noticing.

## 3. Check whether your own fields still discriminate

Before reading anything into a controlled field, count its distribution. When
one value takes more than about 85% of recent episodes, that field has stopped
carrying information — it is measuring your optimism, not the work. Say so, and
either retire it to a coarse screen or split it into something that can actually
come out differently.

This is worth doing every cycle. A saturated field is invisible from the inside:
every episode looks well-rated, and the average keeps looking good, right up
until someone asks what it is evidence of. Where a self-rated field has
saturated, lean on the calibrated fields and the fingerprint instead — those
cannot flatter you, because you do not write them.

## 4. Promote and retire, deliberately

- A move seen once is a **candidate pattern**; seen three times it becomes
  `active`. Every pattern needs a *trigger* — a pattern you cannot recognise in
  the moment is a nice story, not a reusable move.
- A limitation hit repeatedly becomes a **lesson**. Give it a mechanism and an
  enforcement route; if it is high severity, hand it straight to `coevolve:enact`
  rather than filing it in the playbook and hoping.
- **Retire what the data no longer supports.** A playbook that only grows stops
  being read. When a tool has gone unused for a whole cycle, decide out loud
  whether the work changed or the advice was wrong, and either make the rule
  conditional or cut it.

## 5. Propose a diff — and leave the human zone alone

Show a diff against the current `playbook.md` and let the user approve or edit.
Default to proposing; never write silently.

**Never touch the human zone**: the core principle line, the ground rules, the
delegation split, and the keeping-your-own-edge section are hand-authored. They
are the part that should change slowly and deliberately, and they are not
derivable from usage data. Distillation edits only the data-derived sections:
opening moves, tool combinations, how work gets broken down, when not to reach
for the AI, red flags, and the changelog.

## 6. Write

Apply the approved changes to `playbook.md`, set frontmatter `updated:` to
today, and append a one-line changelog entry saying what evidence drove it and
how strong that evidence was.

## Boundaries

- Writes `playbook.md`, `patterns/`, and `lessons/`. Never episodes, never
  metrics.
- Never edits the human zone.
- Never states a frequency it did not count, or a trend from a single episode
  without labelling it as such.
