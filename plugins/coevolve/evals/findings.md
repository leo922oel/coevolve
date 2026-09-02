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

## F9 — the confound fixture leaks its own answer through zero variance

Found by the first run of the case it was built for.

`confounded-improvement` generates six identical before-sessions and six
identical after-sessions, so `derived.error_rate` is a perfect constant within
each group. A run can therefore prove the entire effect is between-group without
ever reasoning about project keys or task shapes — the variance structure hands
it over. Real data never looks like that.

This is the same fault the rubric rewrite was meant to remove, one level down:
the case is supposed to require noticing that the *work* changed, and instead it
can be solved by noticing that a number is impossibly stable. The confound
should have to be found in `project_key`, session size and tool mix, which is
where it would actually live.

Fix: give each group realistic within-group spread, with the distributions
overlapping enough that a constant cannot be the tell. Deferred until after
iteration 3 finishes so all three runs of the case see the same fixture — a
fixture changed mid-iteration makes the three runs incomparable, which would
cost more than the finding is worth.

Also observed by the same run, and worth keeping deliberately: no session falls
between 08-07 and 08-20, so nothing straddles the enactment date. That was
accidental, and it is a good second tell — real stores do have gaps, and a gap
around the split is genuinely suspicious.


## F10 — the state machine had nowhere to put a lesson nothing can enforce

Found by `enact-declines-unenforceable`, run 1 of 3 — the first genuine failure
in the eval programme, and the case existed precisely because the old rubric's
E2 could not fail.

Asked to handle a lesson with no detectable signal, the run wrote
`state: enacted`, `enforcement: none`, `enacted: <today>`, and no metric. That
lesson now looks handled, cannot fire, has nothing to verify, and the nudge has
gone quiet on it. Runs 2 and 3 left it `logged`.

The skill was the cause. It said to record `enforcement: none` and say why, and
said nothing about state — so the run had to guess, and one guess in three was
the damaging one. Both available answers were wrong anyway: `logged` keeps a
high-severity alarm firing forever for something nobody can act on, and an alarm
that cries wolf is exactly how a person learns to ignore the only enforcement
mechanism this system has.

Fixed by adding **`accepted`**: looked, nothing fits, the risk is carried
knowingly. It requires a reason and a `review_on:` date and comes back then, so
it cannot become where lessons go to be forgotten — and acceptance *without* a
date is treated as unhandled, so it cannot be used to silence anything.
Acceptance criterion C8; three hook tests cover it.

**The three runs disagreed three ways, which is the finding.** run-1 wrote
`enacted`, run-2 left it `logged`, and run-3 invented `state: accepted` —
together with a `review_on:` field and the rationale "nothing fits, risk carried
knowingly ... the review date is when it gets looked at again". None of that
existed anywhere: not in the skill, not in the template, not in the vocabulary.

A three-way split on the same question is what an under-specified instruction
looks like from the outside. One run reaching for a state that does not exist,
and independently choosing the same name and the same review-date mechanism that
the fix later used, is about as clear as this kind of evidence gets. The design
was not invented to patch a failure; it was the answer the material already
implied, and the eval surfaced it by making three attempts visible side by
side.


## F11-F13 — three independent runs each found a different hole in the nudge

None was looking for it. All three are the same disease: the session-start nudge
is the only enforcement layer in this design, so anything that makes it noisy or
silent removes the system's reason to exist.

**F11 — a count is not independence.** `--min-n` guards against thin evidence by
counting sessions. The confound fixture's six sessions per side carry identical
values, so the effective sample is one per side while the threshold passes
cleanly. One run put it exactly: "n=6 是假的 6，實際上只有兩個獨立觀測值".
`compare` now reports `distinct_values` per window and flags
`degenerate_spread`. This began as a fixture defect (F9) and turned out to be a
product one — the fixture was extreme, but real stores hold near-duplicate
sessions all the time.

**F12 — the enact nudge filtered on `severity: high`.** A medium lesson with
three occurrences that cost two days sat invisible for 21 days. Lower severity
now gets a longer fuse and a quieter line, not silence.

**F13 — the verify nudge had no date gate.** Any `enacted` lesson nagged every
session from the day it landed, and verification legitimately takes weeks. This
is the same failure just fixed for `accepted`, sitting in the adjacent branch —
which is worth noticing: fixing one instance of a pattern is not fixing the
pattern.

A fourth, found while fixing the third: an `enacted` lesson with no `enacted:`
date was skipped silently. It is now counted as due, because a malformed state
is exactly what this stage exists to surface.
