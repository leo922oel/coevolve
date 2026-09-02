---
id: L-YYYY-MM-DD-short-slug
severity: high | medium | low
# logged    — known, nothing enforcing it yet
# enacted   — enforcement is LIVE (see `enacted:` below)
# verified  — the change was measured and it moved
# accepted  — looked, nothing can enforce this, the risk is carried knowingly.
#             Requires `review_on:`, an `observable_check:`, and the per-layer
#             reasoning below. Never use `enacted` for this:
#             it claims something fired when nothing did, and sends VERIFY
#             looking for a change that never happened.
# retired   — no longer live
state: logged
enforcement: none
logged: YYYY-MM-DD
# The day enforcement actually STARTED FIRING — not the day it was written.
# VERIFY splits its comparison here, so a date set early creates a window in
# which nothing was enforced and nothing downstream can tell. Let
# templates/enforcement-install.sh set it: it activates and stamps together.
enacted:
verified:
retired:
# accepted only: the date to look at this again. Acceptance is a decision to
# carry a risk, not a way to stop the alarm — without a date the nudge treats
# the lesson as unhandled.
review_on:
# accepted only: what would be looked at on the review date, where that evidence
# lives, and who looks. Without it the review has nothing to examine and comes
# out word-for-word identical to the last one — which is how a review date
# becomes theatre.
observable_check:
# The metric VERIFY will compare, named NOW — before the outcome is known.
# Choosing it afterwards is metric shopping, and it always finds a win.
metric:
metric_direction: down | up
# The before-window, snapshotted at enactment. This is not a convenience: the
# before side closes the moment the change ships, and the transcripts behind it
# expire in about a month. Without this the lesson becomes unverifiable and sits
# in `enacted` forever.
#   metrics_rollup.py baseline --metric <metric> --until <enacted date>
baseline:
evidence:
---

## What happened

One or two sentences, de-identified. What went wrong, not who.

## Why it happened

The mechanism. A lesson without a mechanism cannot be enforced, only remembered.

## How it gets enforced

`rule` (an always-loaded instruction), `hook` (a deterministic gate), or `skill`
(a workflow that makes the right thing the easy thing). Writing it in the
playbook is not enforcement — the playbook is read when consulted, and the
failures worth this file are the ones that happen when nobody is consulting.

When the answer is `none`, write down **why each of the three was rejected, and
on what premise**. A later review tests those premises; it cannot re-derive them.
One acceptance here was overturned three months on because its note said the
skill layer "would have to trigger on being tired, which is not observable" —
a premise a reviewer could see was wrong, since a skill triggers on the task and
reviewing is perfectly observable. Had the note only said "nothing fits", the
error would have survived every future review.

## History

- YYYY-MM-DD logged
