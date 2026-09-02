---
name: enact
description: Turn a recorded lesson into something that actually enforces itself — a hook, an always-loaded rule, or a skill — instead of another bullet in a document. Use when the session-start nudge reports a high-severity lesson stuck in `logged`, when the user says "enact", "make this stick", "how do I stop doing this again", "落實", "this keeps happening", or right after calibration surfaces a repeat failure. Proposes a concrete artifact and names the metric that will later show whether it worked; never applies anything without approval.
---

# Enact

This is the stage the loop was rebuilt around.

Writing a lesson down does not change behaviour. The evidence is in this
system's own history: a lesson about pasting credentials into a transcript was
recorded, filed, and the same mistake happened again a fortnight later. The
document was fine. The document was just never in the room when it mattered.

So the question here is never "how do I phrase this better" but **"what will be
present at the moment this goes wrong"**.

## 1. Take the most expensive lesson first

Read `$COEVOLVE_HOME/lessons/*.md` for `state: logged`, high severity first,
oldest first. Handle one properly rather than four superficially — a
half-enacted lesson is indistinguishable from an unenacted one.

Show the user which lesson you are on and what it cost, in one or two lines.

## 2. Choose the enforcement layer honestly

| Layer | Fires when | Right for | Costs |
|---|---|---|---|
| **hook** | deterministically, every time, whether or not anyone is thinking about it | anything detectable in a tool call, a file, or a message — secret-shaped strings, dangerous commands, a missing pre-step | needs a reliable signal; false positives train people to ignore it |
| **rule** | whenever the model reads its instructions | judgment calls that must be weighed every time — "confirm before external state changes" | competes with everything else always loaded; weak against habit |
| **skill** | when the task is recognised | multi-step procedures whose failure mode is "I skipped the procedure" | only fires if the description triggers |

Two honest tests before you pick:

- **Would this have fired for the actual incident?** Walk the real episode
  through the proposed enforcement. If it would not have caught it, the layer is
  wrong, however sensible it reads.
- **What does it cost when it is wrong?** A hook that blocks legitimate work
  gets disabled within a week, and then you have neither the hook nor the
  lesson. Prefer warn-and-continue over block unless the damage is
  irreversible — leaked credentials, destroyed data, an external side effect.

If nothing can enforce it — the signal genuinely is not detectable and the
judgment genuinely cannot be pre-stated — say so plainly, set
`enforcement: none`, and record why. An honest "this one has to stay a habit" is
worth more than a hook that does not fire.

## 3. Name the metric NOW, before anything is applied

Write into the lesson's frontmatter the metric `coevolve:verify` will compare
later, and the direction that counts as success:

```yaml
metric: derived.interrupt_rate
metric_direction: down
```

Any dotted path into a rolled-up session record works — `derived.error_rate`,
`counts.interrupts`, `derived.delegated_share`, `counts.tool_calls`. Verify with:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/metrics_rollup.py" sessions | head -1
```

Choosing the metric afterwards is metric shopping, and metric shopping always
finds a win. If no fingerprint metric can show this — many lessons are like that
— name the observable check instead ("no secret-shaped string appears in a
transcript for 30 days") and say who checks it.

## 4. Propose the artifact in full

Show the actual content, not a description of it:

- **hook** → the script plus the exact `hooks.json` or `settings.json` entry.
  Put the script in `$COEVOLVE_HOME/enforcement/` so it survives plugin updates
  and stays yours. Registering a hook edits the user's settings — always ask
  first, and use the `update-config` skill if it is available.
- **rule** → the exact lines, and which always-loaded file they go in. Keep it to
  a couple of sentences; a rule nobody finishes reading is not loaded.
- **skill** → the skill, with a description written so it actually triggers on
  the situation that goes wrong.

Then say what it does **not** cover. Every enforcement has a gap, and an unstated
gap gets mistaken for coverage.

## 5. Apply on approval, and record the transition

After the user approves and the artifact is in place, update the lesson:

```yaml
state: enacted
enforcement: hook          # or rule / skill / none
enacted: YYYY-MM-DD
metric: derived.interrupt_rate
metric_direction: down
```

Append to its History section. `enacted` is the split date `verify` will use, so
it must be the day the change actually took effect, not the day you wrote it up.

## 6. Say the quiet part

Tell the user the lesson is **not** verified yet — it is enacted. Nothing has
been measured. Come back in a few weeks with `coevolve:verify`, or the loop has
just produced a more elaborate way of writing things down.

## Boundaries

- Never applies an enforcement artifact without explicit approval, and never
  edits settings, hooks, or always-loaded rules silently.
- Never marks a lesson `verified` — that is `coevolve:verify`, and only with data.
- Never proposes an enforcement whose only mechanism is "remember to".
