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

Fixed after iteration 3 (deferred so all three runs saw the same fixture). Each
group now holds six distinct values with the ranges overlapping at the edges —
before 0.054-0.138, after 0.021-0.059 — so `degenerate_spread` is false and the
verdict is still a clean `measured / down / -62.4%`. The confound can only be
found where it actually lives: the project key, the session size, and the tool
mix.

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


## F14 — the same filter, reintroduced in the commit that removed it

F12 was the enact nudge filtering on `severity: high`, so medium lessons never
surfaced. The fix removed that filter from the `logged` branch — and the same
edit wrote `[[ "$sev" == high ]] || continue` into the `accepted` branch that it
was adding. An accepted medium lesson's review date would therefore never come
back, which is F12 again, one branch over.

The commit message for that change reads, in full: *"fixing one instance of a
pattern is not fixing the pattern"*. It was written while committing the second
instance.

Found by a run that was not looking for it — `unenf-r3` noticed the gap while
explaining why its own medium lesson's review would be nobody's job.

This is the system's own thesis demonstrated on the system: **a rule that lives
only in prose does not change behaviour, and a commit message is weaker prose
than a playbook.** What would have caught it is what caught it in the end — a
test. The regression test now covers both severities in the accepted branch,
because one branch having a test was demonstrably not enough.

Two smaller process notes from the same fix, both worth keeping:

- Two of the three edits attempted here **failed silently**: `str.replace` with
  a drifted anchor is a no-op, and the script reported success. The third
  attempt asserted on the result and caught it immediately. Any edit script that
  cannot fail is an edit script that will eventually lie.
- The bug was invisible in review and obvious in one command. Running the hook
  against a two-lesson fixture took seconds; re-reading the diff had already
  missed it twice.


## F15 — the tool could diagnose a confound but not control for it

Six runs across two iterations, on two different versions of the fixture, all
reached the same recommendation: compare like with like, inside one project.
None of them could do it. `compare` had no way to restrict to a subpopulation,
although `project_key` sits in every session record.

Six independent runs converging on the same missing capability is a stronger
signal than any single failure. It is also a shape worth recognising: the
diagnosis was right, the tool made the correct next step unreachable, and every
run therefore ended with advice instead of an answer.

`--where field=value` now exists on `compare` and `window`, and is echoed in the
result so a filtered comparison cannot be mistaken for an unfiltered one. On the
confound fixture the two commands give opposite readings of the same data —
`measured / down / -62.4%` unfiltered, and `insufficient evidence (after_window,
0 of 5)` once restricted to the population the rule targets. The second is the
truth, and it was one flag away the whole time.

An unknown field errors rather than returning an empty window: comparing nothing
and comparing something that yielded nothing look identical in the output.

## F16 *(fixed)* — compare blocks on count, never on composition

`blocked_by` has three values and all three are about how many sessions a window
holds. The confound case has six on each side, clears `min-n`, returns
`verdict: measured` — and is still unverifiable, because the two windows contain
different work. One run put the distinction exactly: *"卡點不是樣本數不足，是
組成錯了"*, and that changes the advice completely. A thin window resolves by
waiting. A mismatched one never does.

All six runs across iterations 3 and 4 did the same manual analysis to find it:
split by `project_key` and look for overlap, compare `bash_share`, compare
median session size, compare which skills appear. Every one of those fields is
already in the rolled-up row. Six runs independently writing the same analysis
is the signal that it belongs in the tool — the same reasoning that produced
`--where` from the same six runs, one step further.

Proposed: a `composition` block on `compare`, reporting project overlap between
the windows, tool-mix shift, and the session-size ratio, plus a
`composition_drift` flag alongside `degenerate_spread`. The verdict need not be
blocked — the numbers are real — but a `measured / down` that comes with
"these two windows share no project and the tool mix moved by half" is a
different sentence from one that does not.

**Deferred until iteration 5 finishes.** Its `verify-uses-subpopulation` case is
running now and asks whether a run discovers `--where` on its own. Adding
automatic drift detection mid-flight would answer that question for it and make
the three runs incomparable — the same discipline that deferred the F9 fixture
fix.

## F17 *(fixed)* — the recovery path exists and nothing tells the skill to use it

Raised by a run noticing that the fixture's inbox pointed at transcripts which
were not there. That part was a fixture artifact, but checking the real store
turned up something worth fixing.

Of 174 transcript pointers in the archived inbox flags, 97 point at files that
no longer exist. All 97 predate coevolve — they are worklog-era flags from a
time when no fingerprint was taken, so the evidence really is gone, and that is
just history.

What matters is the structural property, and it holds: a flag written now has a
fingerprint stored under the same `transcript_id`, because the Stop hook takes
both in the same moment. Verified directly rather than inferred from the absence
of dead pointers in recent archives — those transcripts simply have not expired
yet, which proves nothing.

So evidence survives transcript expiry. **But `curate` has no idea.** It contains
no mention of a transcript possibly being gone, and no instruction to fall back
to the fingerprint keyed by the path's stem. A run curating a five-week-old flag
hits a missing file with nothing to fall back on, and will most likely drop the
episode or guess at it — losing an episode whose measurements were sitting right
there.

Fix: say so in `curate`, and have it join on `transcript_id` when the file is
gone. Deferred until iteration 5 finishes, for the same reason as F16.

## F18 *(fixed)* — acceptance comes back with nothing to look at

`accepted` requires a reason and a `review_on:` date. It does not require an
observable check, and without one the review has nothing to examine. As the run
that found it put it: the next review would be word-for-word identical to this
one — same three layers re-tested, same conclusion, same date pushed out.

`review_on` makes acceptance return. Something to look at is what makes the
return worth anything. Otherwise the date is theatre and `accepted` becomes the
graveyard the date was added to prevent.

The same run made the sharper version of the point, about the fixture's own
state: no new incident had been recorded since acceptance, but nothing was
recording either — `episodes/` and the inbox were both empty. Silence from a
system that is not watching looks exactly like silence from a system that is
safe, and reading the first as the second is precisely how a carried risk
quietly stops being carried.

Fix: `accepted` must also name what would be observed, where that evidence
lives, and who looks — the same discipline `enact` already applies to a metric,
applied to the case where no metric exists. C8 needs amending and the lesson
template needs the field.

Worth noting separately: this run used `distinct_values` — added hours earlier
to flag degenerate comparison windows — for something else entirely, to
demonstrate that *no* metric could carry the lesson, since 24 sessions came back
with one distinct value on every field. A store with no variance cannot separate
a careful review from a quick one. That the field was useful for a purpose it
was not designed for is a good sign about the field.


---

## Iteration 5 outcome

All three cases targeted surfaces added during this session, so this round asked
whether the fixes introduced new problems. They did not, and two of them were
used in ways nobody instructed.

`status-picks-one` — 3/3 recommended exactly one action, the same one, on the
same reasoning: the credential lesson is the only one whose text layer has
already been tried and failed, and the only one that is irreversible. One run
also ran verify on a second lesson and identified in two minutes that it can
never be verified — no baseline was taken at enactment and its transcripts have
expired. That is the F1 scenario recognised in the wild.

`verify-uses-subpopulation` — 3/3 **executed** `--where`, four to five times
each, across two or three populations. Confirmed from the transcripts, not from
the answers. Two of them ran it in both directions and got opposite verdicts
from the same data: `proj_integration` blocked on `after_window`, which fills by
itself, and `proj_review_other` blocked on `before_window`, which never will.
`blocked_by` came from F1 and `--where` from F15, added hours apart; no prompt
mentioned either, and the runs composed them into a distinction neither makes
alone.

`enact-reviews-an-acceptance` — the case discriminated, and in the most useful
direction. Two runs re-accepted with an observable check added. One **overturned
the acceptance**, catching that the original note had rejected the skill layer on
a false premise: a skill triggers on the task, and reviewing is observable, so
"would have to trigger on being tired" was never the right test. That overturn
was only possible because the June note recorded its reasoning per layer, which
is what sharpened F18 from "name a check" into "record the premise".

Three runs, three outcomes, none of them wrong. On disk all three left the state
alone and asked first, which is the behaviour the case was checking.

## F19 — `baseline` says "not too thin" to a sample that cannot discriminate (deferred)

`compare` learned to report `distinct_values` and flag `degenerate_spread`
(D7). `baseline`, which computes the same statistics, still decides `too_thin`
from `n` alone. Twenty-four identical sessions come back `n: 24,
distinct_values: 1, too_thin: false` — an explicit reassurance given to a sample
whose effective size is one.

That is worse than the `compare` case it mirrors. `compare` at least reports the
degeneracy alongside its verdict. `baseline` is read by ENACT at the exact
moment a metric is registered, and C5 exists to warn precisely then. So the one
check placed at the one moment something can still be done says "fine" when it
should not.

Found by a run that ran `baseline` while explaining why no metric could carry
its lesson, and noticed the flag disagreed with the numbers beside it.

### The third time, which is the more useful finding

This is the same shape as F14: a guard added to one code path and not to its
sibling.

- F12 removed a `severity: high` filter from the `logged` branch; the same edit
  wrote that filter into the `accepted` branch it was adding. (F14)
- D7 added degeneracy detection to `compare`; `baseline` computes the same
  statistics from the same helper and did not get it. (F19)

Twice is coincidence, three times is a habit, and the habit has a name: the fix
is applied where the bug was reported rather than where the bug lives. Both
times the sibling was in the same file, both times a two-line test would have
caught it, and both times review did not.

Deferred until iteration 6 finishes — `enact-accepts-with-a-check` is running
now and calls `baseline`.

## F20 — the degeneracy check looks at one column; independence is a property of the row (deferred)

`degenerate_spread` compares `distinct_values` of the metric under test. Six
sessions with identical `tool_calls`, `user_turns` and duration, differing only
in error count, pass it cleanly — and are obviously not six independent
observations. Verified directly: `degenerate_spread: false`, `distinct_values:
6` and `3`, while every other field on every row is the same.

Found by a run that had already accepted the verdict and was listing what it
would still discount, which is the more valuable kind of finding: it did not
change the conclusion, it changed how much the conclusion is worth.

Adjacent to F19 rather than identical. F19 was a guard that did not reach its
sibling function. This is a guard that examines one column when the property it
exists to test — are these observations independent — is about the whole row.
The common half is that the fix addressed the instance that was reported rather
than the property that was broken.

Proposed: derive degeneracy from the row, not the metric. Sessions identical
across `tool_calls`, `user_turns` and duration should count once regardless of
how the compared metric varies, and `compare` should report the effective count
next to the nominal one.

Deferred until iteration 6 finishes.

### Provisional: no state for "verified, but provisionally"

One run marked a lesson `verified` while stating medium confidence, four
explicit discounts, and a recommendation to re-check in one to two weeks. The
analysis was careful and the state machine gave it nothing better: `enacted`
understates a real, bounded result, `verified` overstates it. Same shape as F10,
where the missing state was `accepted`.

Held as provisional until the other two runs of this case land — if they diverge
on the state, it is a judgement call rather than a gap.
