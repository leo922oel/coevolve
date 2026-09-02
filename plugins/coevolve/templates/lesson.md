---
id: L-YYYY-MM-DD-short-slug
severity: high | medium | low
# logged    — known, nothing enforcing it yet
# enacted   — enforcement is LIVE (see `enacted:` below)
# verified  — the change was measured and it moved
# accepted  — looked, nothing can enforce this, the risk is carried knowingly.
#             Requires a reason and `review_on:`. Never use `enacted` for this:
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

## History

- YYYY-MM-DD logged
