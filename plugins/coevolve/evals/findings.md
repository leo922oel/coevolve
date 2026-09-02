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

---

## F4 — this harness cannot measure triggering at all (eval defect, both iterations void)

Iteration 1 reported 2/9 skill invocations, iteration 2 reported 0/9. Both
numbers are artifacts and neither should be quoted.

The decisive evidence is the order of tool calls in the one run that did invoke
a skill. `enact-r1` called `Skill :: coevolve:enact` as its **sixth** tool call,
immediately after its fifth: `cd <repo>/plugins/coevolve/skills && ls -R && cat
enact/SKILL.md`. It did not trigger on the description. It found the skill on
disk and then called it by name.

Moving the workspace to /tmp for iteration 2 did not help. Every run still
located the plugin — agents search the filesystem for "coevolve" and find both
the repo and the installed cache. And because the plugin was uninstalled and
reinstalled between iterations, whether the skills were even present in each
subagent's available-skills list is not something this run can establish.

So what these eighteen runs measured is **behaviour given the skill's guidance**,
which is a real and useful question, and they answer it well. What they did not
measure, at all, is whether the guidance would ever be reached.

Measuring triggering needs an environment where the agent cannot read the
plugin's source and the prompt does not name it — a fresh sandbox per run, which
is exactly what `claude plugin eval` provides and this account cannot yet run.
Until then, triggering is untested, and any description tuning would be tuning
against a number that does not mean what it says.

## F5 — the F1 fix reached behaviour (confirmed)

Iteration 2's verify runs used the new signal without being told to.
`verify2-r1` read `blocked_by: both` and gave the two sides opposite advice —
the before window is closed and its backfill option expires within days, the
after window fills on its own — and traced the root cause to the lesson having
no `baseline:` field, which is precisely what the fix added.

`verify2-r2` went further than the rubric asked: an exact permutation test
showing that 2-versus-2 has a floor of p = 1/6 no matter which test is used, so
more statistics cannot help and only more data can; and it explicitly refused
the pseudo-replication that would treat 400 tool calls as independent samples
and produce p ≈ 1e-4. Neither is in the skill text. The skill asked for honest
refusal and left the reasoning to the model, which is the right division.

## F6 — triggering is fine; the harness was the problem (resolved)

Re-measured properly: `claude -p` in a fresh session with an empty working
directory, so the plugin cannot be found by exploration and the prompt does not
name it.

| case | skill fired | first tool call |
|---|---|---|
| export my cowork profile | `coevolve:profile` | Skill |
| a high-severity lesson is stuck | `coevolve:status` → `coevolve:enact` | Skill |
| did that rule actually help | `coevolve:verify` | Skill |
| why does this python raise IndexError | none | none |

Three of three positives fired as the **first** action, before any exploration
could have revealed the plugin, and the negative correctly did not. The enact
case chained status → enact, which is the right order: navigate, then act.

So the descriptions work. Both iterations' triggering numbers measured the
harness, not the product. `trigger_check.sh` fixes the method: it is the same
measurement, repeatable, and it runs today rather than waiting on the gated
`plugin eval`.

## F8 — the rubric was measuring itself (rewritten)

22 of 25 assertions passing 3/3 was a fact about the rubric. Three faults:

- Assertions nothing could fail were scored as if they discriminated. They are
  now marked `[floor]` and reported apart from the score.
- `verify-refuses-thin-evidence`'s answer is printed verbatim by the tool the
  run is expected to call, so the case cannot fail. Kept as a regression check,
  demoted from measurement, and replaced by `verify-questions-a-clean-result`.
- The two most valuable observed behaviours had no assertion at all: replaying
  the real incident through a proposed detector, and running a negative control
  on the de-identification gate.

The new verify case is the interesting one. Six sessions each side,
`derived.error_rate` 0.100 → 0.022, `compare` returns `measured / down`, and the
user asks for confirmation so they can put it in a monthly report. The after
window is a different project, a third the size, review work where there had
been integration. Nothing in the tooling can see that. A run either interrogates
its own clean result or it does not — and no amount of reading tool output
answers it.
