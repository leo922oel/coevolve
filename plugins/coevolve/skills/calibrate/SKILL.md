---
name: calibrate
description: Close the prediction loop — find episodes whose predicted time-saving and confidence were never checked against what actually happened, reconstruct the real outcome, and correct the record. Use when the session-start nudge says calibration is due, when the user asks "was I right", "did that estimate hold up", "校準", "check my confidence", or before producing any report that quotes a time-saving number. This is the only thing that keeps self-assessment honest; without it the numbers drift and no report built on them is worth quoting.
---

# Calibrate

Compare what each episode PREDICTED against what actually happened, write down
the lesson, and mark it calibrated. The payoff is not the corrected row — it is
the cross-episode pattern, because that is what improves the next prediction.

## 1. Find genuine candidates

Read config for `calibrate_min_age_days` (default 5). Take episodes where
`calibrated: false` and `date <= today - min_age_days`.

Two exclusions matter more than they look:

- **An episode with `prediction_source: curation-time` is weak evidence.** Its
  estimate was made knowing the outcome. Calibrate it if you like, but never let
  it drive a cross-episode conclusion, and say so when reporting.
- **Do not calibrate what was written up today.** Same-day estimates carry
  hindsight; checking them against hindsight is circular. Defer them to the next
  cycle and say which ones you deferred and why.

## 2. Reconstruct the outcome from evidence, before asking

For each candidate, look for objective signal first:

- Does the thing exist and is it in use — file present, hook firing, change
  merged, tests green?
- Did later sessions show rework, reversal, or abandonment? The fingerprint
  helps here: a follow-up session on the same `project_key` with a high
  interrupt or error rate is a rework signal.
- Anything that plainly contradicts the recorded fit or time-saving.

Tag each as: evidence supports the prediction / contradicts it / no objective
signal. Only the third kind needs the user.

## 3. Ask about the rest, and let them be right

Show a table: episode | predicted confidence and time-saving | what is
observable | your reading. For rows with no objective signal, offer verdicts to
choose from: accurate / under-confident / over-confident / time-saving
overestimated / time-saving underestimated.

The user's recollection is the ground truth; your reconstruction only frames the
question. Where an episode has no citable outcome and the user does not recall,
leave it uncalibrated and say so. Rubber-stamping "accurate" to clear the queue
is how a calibration log becomes decoration.

## 4. Write back, narrowly

On each confirmed episode, update only: `calibrated: true`, a one-line
`calibration_note` (what actually happened versus what was predicted, and the
lesson), and `confidence` / `time_saved` **only where calibration says they were
wrong**. Never touch the description, task type, tools, or metrics.

## 5. Escalate a repeat immediately — do not wait for distillation

If calibration surfaces a failure that has happened before, and it is the kind
that costs real damage — leaked credentials, destroyed state, a wrong external
operation — create or escalate a lesson in `$COEVOLVE_HOME/lessons/` right now
with `severity: high` and `state: logged`, using `templates/lesson.md`. Name the
metric that would show whether it stops.

High-severity lessons are exactly the ones that must not wait a month for the
monthly pass. The system's own history says so: a credential leak was recorded,
filed for later, and repeated a fortnight afterwards.

## 6. Log the run and say the cross-episode thing

Append a dated block to `calibrate-log.md`: date, episodes touched, verdicts,
and the aggregate lesson. `status` and the session-start hook read the newest
date here.

Then tell the user the pattern across episodes — "under-confident on delivered
tooling, honest on unstabilised work" is worth far more than a list of corrected
rows, because it is the thing that changes the next prediction.

## Boundaries

- Updates only calibration fields on existing episodes. Never creates episodes
  (`curate`) or edits the playbook (`distill`).
- May create or escalate a high-severity lesson, and nothing else in `lessons/`.
- Never fabricates an outcome. No signal and no recollection means the episode
  stays uncalibrated, and the report says which ones and why.
