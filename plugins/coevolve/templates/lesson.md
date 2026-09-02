---
id: L-YYYY-MM-DD-short-slug
severity: high | medium | low
state: logged
enforcement: none
logged: YYYY-MM-DD
enacted:
verified:
retired:
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
