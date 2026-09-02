# Iteration 1 findings

Recorded as they arrive, before the whole set is in — so the analysis is not
written backwards from a conclusion.

## F1 — VERIFY can deadlock on a permanently thin before-window (product defect)  *(fixed)*

Found by: verify-refuses-thin-evidence, run 1.

The before-window of a comparison is **frozen**. Sessions before the enactment
date cannot increase, so a lesson enacted while the store was young can never
reach the minimum sample on that side. It stays `enacted` forever, and because
transcripts age out after about 30 days, the one recovery route — backfill —
expires too.

Acceptance criterion D2 says verify must refuse a verdict on thin evidence. It
is silent on evidence that will never arrive, which turns a correct refusal into
a permanent stall.

Candidate fixes:
- ENACT records the before-window statistics into the lesson at enactment time,
  when the data still exists. The baseline then survives transcript expiry, and
  VERIFY compares against a stored baseline rather than a re-derived one.
- VERIFY detects a frozen thin before-window and says so distinctly: this is not
  "not yet", it is "not with this metric unless you backfill now".
- ENACT warns at enactment time when the before-window is already too thin to
  ever support the metric it is about to register.

The first is the real fix; the second is what makes the existing lessons
recoverable. Both are cheap.

## F2 — fixture defect  *(fixed)*: stored `derived` block contradicts `counts`

The fixture builder hard-codes `"error_rate":0` while writing non-zero
`counts.tool_errors`. The roll-up recomputes derived values from counts, so
results were correct, but anyone reading the fixture directly sees four
error-free sessions. An internally inconsistent fixture can mask a real bug, so
it has to go.

## F3 — fixture defect, kept on purpose: lesson id disagrees with its registered metric

`L-2026-08-20-interrupt-rate` registers `metric: derived.error_rate`. The run
correctly followed the frontmatter and flagged the discrepancy. Unintentional,
but it is a genuinely good trap — a filename is exactly the kind of thing that
would tempt a later reader into swapping the metric, which is post-hoc metric
shopping wearing a tidy-up's clothes. Keep it, and document it as deliberate.

---

## F1 fix, as shipped

- `metrics_rollup.py baseline --metric M --until D` snapshots the before-window
  and flags `too_thin` at capture time, while something can still be done.
- `compare --baseline-file` compares against that snapshot instead of
  re-deriving, so a lesson survives transcript expiry.
- `compare` now reports `blocked_by`: `after_window` (resolves by itself),
  `before_window` (stuck — backfill now or never), or `both`.
- ENACT captures the baseline in the same step that registers the metric, and
  raises a thin baseline *before* applying anything, while the user still has a
  choice. VERIFY reads `blocked_by` and gives opposite advice for the two cases.
- Acceptance criteria D4-D6 and C5 added; 24 tests now cover this area.

The eval paid for itself here: the criteria said "refuse a verdict on thin
evidence", which was right, and missed that refusing forever is its own failure.
