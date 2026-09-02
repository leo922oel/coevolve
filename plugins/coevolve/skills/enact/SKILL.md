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
oldest first — and for `state: accepted` whose `review_on:` has passed.

**A review is not a date change.** Re-run step 2 against today's facts: the
store has data it did not have then, and the premise behind each rejection may
no longer hold. Re-accepting is a fine outcome; arriving at it without testing
the premises is not. Handle one properly rather than four superficially — a
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
judgment genuinely cannot be pre-stated — say so plainly. An honest "this one
has to stay a habit" is worth more than a hook that does not fire.

Then put it in **`state: accepted`**, with `enforcement: none`, a recorded
reason, and a `review_on:` date. Not `enacted`: that claims something fires when
nothing does, stops the nudge, and sends VERIFY looking for a change that never
happened. Not `logged` either — leaving it there makes the alarm repeat forever
for something nobody can act on, and an alarm that cries wolf is how people
learn to ignore the one mechanism this system has.

`accepted` says what actually happened: you looked, nothing fits, and you are
carrying the risk on purpose. The review date is what stops it becoming the
place lessons go to be forgotten — the nudge comes back then.

Two things have to go in the file for that return to be worth anything:

- **`observable_check:`** — what would be looked at, where that evidence lives,
  and who looks. Without it the review has nothing to examine and comes out
  identical to the last one, and the date is theatre. Note that silence from a
  system nobody is watching looks exactly like safety; say which it is.
- **the premise behind each rejection** — not "nothing fits", but why a hook,
  a rule and a skill each fail, specifically. A later review tests those
  premises. One acceptance was overturned three months on because its note said
  a skill "would have to trigger on being tired, which is not observable" —
  visibly wrong, since a skill triggers on the task and reviewing is observable.
  Had it only recorded the conclusion, the mistake would have outlived every
  review of it.

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

**Then snapshot the baseline, in the same breath.** This is the step that is
easy to skip and impossible to redo:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/metrics_rollup.py" baseline \
  --metric derived.interrupt_rate --until <today>
```

Paste the result into the lesson's `baseline:` field. The before-window closes
the instant the change ships — every session earlier than today has already
happened — and the transcripts behind it age out in about a month. Capture it
now and the comparison stays possible forever; skip it and the lesson can become
permanently unverifiable, which is exactly how a loop quietly turns back into a
diary.

If the snapshot comes back `"too_thin": true`, say so **before** applying
anything. The user then has a real choice while it is still available: run
`backfill_metrics.py` to sweep up transcripts still on disk, pick a metric with
more history behind it, or accept a qualitative check instead. After enactment
that choice is gone.

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

## 5. Apply on approval — and never stamp ahead of reality

`enacted:` is the split date VERIFY compares across. It has to be the day the
enforcement actually started firing. Stamping it when the artifact was *written*
puts a window on one side of every future comparison in which nothing was being
enforced, and nothing downstream can detect that.

So do not write the stamp by hand. Use the shipped installer, which does the
activation and the stamp as one operation:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/templates/enforcement-install.sh" \
  --lesson  "$HOME_DIR/lessons/L-....md" \
  --guard   "$HOME_DIR/enforcement/<guard>" \
  --event   UserPromptSubmit --matcher Bash \
  --test    "python3 $HOME_DIR/enforcement/<guard> selftest" \
  --dry-run
```

It refuses to install a guard that fails its own tests, backs up settings,
preserves existing hooks, registers, and only then stamps — so a failed
registration leaves the lesson unstamped rather than silently lying.

**When activation needs the user (registering a hook edits their settings), the
lesson stays `logged` and you hand them the installer command.** A lesson marked
`enacted` for a hook nobody has registered looks handled and is not — and the
session-start nudge, which is the thing that would otherwise keep reminding
them, goes quiet. Leaving it noisy until it is genuinely live is the point.

For a `rule` or a `skill`, activation is the edit itself, so stamp when the edit
lands. Fill `metric`, `metric_direction` and `baseline` at proposal time either
way: those are decisions, not activations.

## 6. Say the quiet part

Tell the user the lesson is **not** verified yet — it is enacted. Nothing has
been measured. Come back in a few weeks with `coevolve:verify`, or the loop has
just produced a more elaborate way of writing things down.

## Boundaries

- Writes only under `lessons/` and `enforcement/`. The playbook belongs to
  `coevolve:distill` and the calibration log to `coevolve:calibrate` — a stage
  that edits its neighbours' artifacts makes every later diff ambiguous about
  which stage claimed what.
- Never applies an enforcement artifact without explicit approval, and never
  edits settings, hooks, or always-loaded rules silently.
- Never stamps `enacted:` for enforcement that is not yet live.
- Never marks a lesson `verified` — that is `coevolve:verify`, and only with data.
- Never proposes an enforcement whose only mechanism is "remember to".
