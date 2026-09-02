---
name: curate
description: Turn raw session flags, fingerprints, and predictions into structured episodes in the local store. Use when the session-start nudge says entries are waiting, when the user says "curate", "策展", "process my worklog", "write up last week's sessions", or when enough substantial sessions have piled up to be worth reviewing together. Runs weekly-ish; produces local Markdown episodes and, only if configured, exports to Notion.
---

# Curate

Raw signal becomes episodes here. Three streams merge: the inbox flags (what
happened), the fingerprints (how it actually went), and the predictions (what
you expected at the time).

**Episodes stay on this machine, so write them in full.** Do not abstract names
or paths out of a local episode — de-identification belongs at the exits
(`coevolve:profile`, Notion export), not at capture. Blurring an episode as you
write it costs you the detail that distillation needs later, in exchange for
protecting a file that never leaves.

## 1. Gather the three streams

```bash
HOME_DIR="${COEVOLVE_HOME:-$HOME/.claude/coevolve}"
cat "$HOME_DIR/inbox.md"
cat "$HOME_DIR/predictions/recorded.jsonl" 2>/dev/null
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/metrics_rollup.py" sessions | tail -40
```

Each inbox line points at a transcript. Read the ones you need — a title and a
tool count do not tell you what the work was — but let the fingerprint carry the
numbers. Counting tool calls by hand is exactly the kind of thing that comes out
wrong.

## 2. Cluster into episodes, not sessions

A session is a file; an episode is a piece of work. They are not the same, and
the fingerprint says so: some sessions span days (`span_days > 0`), and one
piece of work often runs across several sessions. Cluster on the work.

## 3. Draft each episode

Write `$COEVOLVE_HOME/episodes/E-<date>-<slug>.md`, using `vocabulary.md` for
every controlled field:

```markdown
---
id: E-2026-08-17-sso-integration
date: 2026-08-17
task_type: integration
sessions: [<session ids>]
tools: [<what was actually used>]
fit: good
time_saved: 50-75
confidence: low
prediction_source: recorded        # or curation-time — see below
value: [sped up work I already do]
calibrated: false
metrics:
  tool_calls: 323
  delegated_share: 0.25
  interrupts: 1
  error_rate: 0.02
---

## What happened
## What worked
## What got in the way
```

`prediction_source` is load-bearing. When a recorded prediction exists, copy it
verbatim and mark `recorded`. When there is none, you may estimate — but mark it
`curation-time`, because that estimate was made knowing the outcome and
calibration must later treat it as much weaker evidence. Silently mixing the two
is how a calibration loop starts confirming itself.

Fill `metrics` from the roll-up, never by hand.

## 4. Confirm, then write

Show the drafts as a table. Let the user edit or drop before anything is
written. Then:

- Skip any episode whose date and slug already exist — curation is re-runnable.
- Append the curated inbox lines to `inbox-archive/<today>.md`, then truncate
  the inbox. Archive before truncating, always; the archive is also how `status`
  knows when curation last ran.

## 5. Optional Notion export

Only if `notion_db_id` is set. Notion is a view, not the store. Before writing
anything to it, pipe every field through the gate:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/deid-check.sh" < text
```

Exit 1 blocks that row: show the matched terms and re-abstract for the export
only — the local episode keeps its full detail. A missing denylist fails open
with a warning; relay the warning rather than swallowing it.

## Boundaries

- Writes episodes, the inbox archive, and (if configured) Notion. Nothing else.
- Does not distill patterns, edit the playbook, or change lesson state.
- Never invents a prediction, a metric, or a fit rating that the evidence and
  the user did not supply.
