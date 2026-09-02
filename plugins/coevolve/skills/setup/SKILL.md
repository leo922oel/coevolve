---
name: setup
description: One-time setup for the coevolve loop — creates the local data home (~/.claude/coevolve), the de-identification denylist, the fingerprint salt, and your starting playbook, and offers to migrate an existing dev-worklog installation. Use this whenever the user says they want to start tracking how they work with AI, mentions setting up or installing coevolve, asks "where do my episodes/lessons/metrics live", hits a skill in this plugin that reports no config, or wants to reconfigure cadence, the prediction prompt, or Notion export. Run it before any other coevolve skill — every one of them reads the config this writes.
---

# Setup

Everything this creates is yours and stays on this machine. The plugin is an
engine; your data never enters it. That separation is why the same repo can be
published publicly and installed inside a company.

## 1. Look before you write

- `cat "${COEVOLVE_HOME:-$HOME/.claude/coevolve}/config.md"` — already set up?
- `ls ~/.claude/worklog/` — an earlier dev-worklog install worth migrating?
- `/plugin` — confirm the coevolve plugin is enabled, so its two hooks are live.

## 2. Show the plan, then scaffold

Run the scaffold in dry-run first and show the user exactly what will appear:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/scaffold.sh" --dry-run
```

It is additive and idempotent — it never overwrites a file that already exists,
because the denylist and the playbook's human zone are expensive to recreate.
On approval, run it without `--dry-run`.

## 3. Fill in the denylist — the one step worth slowing down for

The denylist is the deterministic backstop under every export. Ask for the terms
that must never leave the machine: employer and product names, customer names,
internal hostnames and repo paths, project code names. Write them into
`$COEVOLVE_HOME/denylist.txt`, one per line.

Two things to say out loud: matching is case-insensitive substring, so short
terms are broad; and the denylist file itself is never exported, committed, or
pasted into a conversation, because it is a list of exactly the things being
protected.

## 4. Settle the cadence and the prediction moment

Walk the config, one question at a time. Most defaults are fine; the one that
genuinely changes the experience is `prediction_prompt`:

- `next-session` (default) — the next session start asks about the previous one.
  Never interrupts.
- `stop` — asks the moment a substantial session ends, while the work is still
  in your head. Best recall, costs one interruption per substantial session.
- `off` — predictions become optional.

Explain why predictions exist at all: recording what you *expected* before the
outcome is known is the only thing that makes calibration non-circular. Estimating
at curation time is hindsight wearing a prediction's clothes, and it quietly
destroys the value of the whole calibration stage.

## 5. Optional: migrate an existing worklog

If `~/.claude/worklog/` exists, offer migration. It copies rather than moves, is
dry-run by default, and leaves the old tree untouched until the user says
otherwise:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/migrate_worklog.py" --dry-run
```

The calibration history is the single most valuable thing in an old install —
it takes months of cycles to accumulate and cannot be reconstructed. Confirm it
survived before suggesting the old tree be removed.

## 6. Verify, do not assume

Prove the loop is live rather than declaring it:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/hooks/due-check.sh"        # should print nothing yet
bash "${CLAUDE_PLUGIN_ROOT}/tests/run-all.sh"          # should be all green
```

Then say plainly what happens next: the next substantial session gets
fingerprinted automatically, and after a week or two there is enough to curate.

## Boundaries

- Writes only inside `$COEVOLVE_HOME`. Never edits the plugin, other skills, or
  the user's settings without asking.
- Never invents denylist terms. An unasked-for guess about someone's employer is
  both wrong and unsettling.
