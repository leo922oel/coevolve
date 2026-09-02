---
name: predict
description: Record a ten-second prediction about a just-finished session — how much time it saved and how confident you are the output is right — BEFORE the outcome is known. Use when the session-start nudge says predictions are pending, when the Stop hook asks for one, when the user says "log this session", "record my estimate", "預測", or right after finishing a substantial piece of work. This is what makes the later calibration honest, so prefer capturing a rough prediction now over a precise one later.
---

# Predict

A prediction made after you know how it turned out is not a prediction. This
skill exists to catch the estimate while the outcome is still open — that is the
entire value, and it is why the interaction is deliberately tiny.

## 1. Find what is waiting

Read `$COEVOLVE_HOME/predictions/pending.jsonl`. Each line names a transcript,
its date, its tool-call count, and the session's title hint. If it is empty,
say so and stop — do not go hunting for sessions to ask about.

## 2. Ask, briefly

Take the oldest pending entries, at most three in one sitting. For each, show
the hint and the size, then ask two questions with `AskUserQuestion`:

- **Time saved versus doing it the old way**: `<25%` / `25–50%` / `50–75%` / `>75%`
- **Confidence the output is actually correct**: high / medium / low

Buckets rather than numbers, on purpose. A range you can answer in two seconds
beats a percentage you would have to invent, and invented precision is what
makes a calibration loop worthless later.

If the user wants to skip one, skip it and move on. A skipped prediction is a
missing data point; a coerced one is a wrong data point.

## 3. Record and clear

Append one line per answer to `$COEVOLVE_HOME/predictions/recorded.jsonl`:

```json
{"transcript_id": "...", "date": "YYYY-MM-DD", "time_saved": "50-75", "confidence": "low", "note": ""}
```

Then remove those entries from `pending.jsonl`. If the user volunteered a note
about what was hard or surprising, keep it — one honest sentence here often
becomes a lesson or a pattern later.

## 4. Say the useful thing, if there is one

If the user's confidence pattern is visibly at odds with their own calibration
history — the playbook or `calibrate-log.md` may already record, say, systematic
under-confidence on delivered tooling — mention it in one line. Not to argue
them out of the answer they gave, but because the point of the loop is that the
next prediction is better than the last.

## Boundaries

- Writes only `predictions/*.jsonl`. Never touches episodes, lessons, or the playbook.
- Never fills in a prediction the user did not give. An invented estimate
  poisons calibration precisely where it is supposed to be most reliable.
