# Evals

How the coevolve skills are measured, and the rules a run has to follow to be
worth anything.

These skills are mostly judgement. There is no unit test for "did ENACT refuse
to invent a detector that could not fire" — so the eval suite is the test suite
for the half of this product that lives in prose.

## Layout

```
evals/
├── cases/<case-name>/
│   ├── prompt.md          what the user says, in their own words
│   └── fixture            the fixture name build.sh should construct
├── fixtures/
│   ├── build.sh           builds a synthetic $COEVOLVE_HOME per case
│   ├── make_transcript.py synthesises a transcript for one session
│   └── UNUSED             fixtures deliberately shipped without a case
├── rubric.md              the assertions each case is judged on
├── grade_deterministic.py everything scoreable without judgement
├── trigger_check.sh       does the skill fire when nobody names it
└── findings.md            what the runs actually found, and what changed
```

Every case names its fixture in a file rather than in someone's memory. A test
(`tests/test-evals-complete.sh`) enforces that each case has a prompt, names a
fixture `build.sh` can actually build, and has a matching `## Case:` section in
the rubric — because for a while seven of twelve cases had no assertions, and
nothing about the directory tree said so.

## A run

```
<workspace>/<case-name>/<arm>/run-N/
├── prompt.md          copied from the case
├── coevolve-home/     the fixture — the agent works in here
├── .baseline-home/    a pristine copy of the same fixture, taken before the run
└── outputs/answer.md  what the agent produced
```

`.baseline-home` is what makes the disk check possible: the grader diffs it
against `coevolve-home` and sees what the run actually changed, as opposed to
what it said it changed. The traps in these cases are all disk-level — quietly
editing the denylist so an export passes, marking a lesson verified on two
sessions, stamping `enacted:` for a hook nobody registered. An answer can claim
restraint it did not exercise; a diff cannot.

Three runs per case. One run tells you nothing about a stochastic system, and
the variance between runs has repeatedly been the finding — see the isolation
rule below for the sharpest example.

## Isolation — read this before running anything

**A run must not be able to reach the real `~/.claude/`.** This is not a
tidiness rule.

On 2026-09-02 an eval subject working inside a fixture directory ran the
shipped installer and registered a `UserPromptSubmit` hook in the operator's
real `~/.claude/settings.json`, pointing at a guard under `/tmp`. It was
removed three minutes later by the harness's own cleanup, so nothing broke —
but had the temp directory been reaped first, every prompt in every session on
that machine would have been blocked, because a missing hook script exits 2 and
exit 2 on `UserPromptSubmit` means *deny*.

Two of the three runs given that identical prompt refused to touch settings and
said so. One did it. That variance is exactly why the boundary cannot be a line
in a rubric:

- `rubric.md` asserts it (E8, `[floor]`) — that measures it, it does not prevent it.
- `templates/enforcement-install.sh` now refuses to guess: when `COEVOLVE_HOME`
  points anywhere other than `~/.claude/coevolve` and no `--settings` is given,
  it exits 2 and writes nothing. That closes the specific path.
- The harness should still relocate the config directory per run, so the next
  not-yet-imagined path is closed too.

Set both, per run:

```bash
export COEVOLVE_HOME="$run/coevolve-home"
export CLAUDE_CONFIG_DIR="$run/.claude"     # Claude Code's own switch: CLAUDE_CONFIG_DIR ?? ~/.claude
```

`CLAUDE_CONFIG_DIR` is what Claude Code itself uses to locate `settings.json`,
so setting it moves the whole config directory into the run — the installer
follows it without being told, and a run that reaches for "the user's settings"
finds its own. Keep the working directory inside the run directory. Keep the workspace **outside** the plugin tree: a run
that can walk up into the plugin source may read `SKILL.md` through the shell
instead of invoking the skill, which silently turns a triggering measurement
into something else.

## Grading

Two passes, and they are weighted differently.

**Deterministic** — `python3 grade_deterministic.py <workspace>`. Fingerprints
each run's own transcript with the plugin's own extractor (which skills fired,
tool count, tokens), diffs the fixture against its baseline, validates any
`profile.json` against the denylist, and reads every lesson's state off disk.
Writes `deterministic-grades.json`.

Using coevolve to measure coevolve is not just tidy — it means the triggering
check is the same measurement the product itself makes.

**Rubric** — `rubric.md`, judged on `outputs/answer.md` and cross-checked
against those grades. **Where the answer and the disk disagree, the disk wins.**

Assertions marked `[floor]` are safety properties that must always hold and are
reported separately. They are worth checking and worthless as measurement:
nothing ever comes close to violating them, so mixing them into a score inflates
it and hides where a skill is actually weak. E8 was a floor assertion right up
until the morning something violated it.

## Triggering

`bash trigger_check.sh [case ...]` answers a different question: does the skill
fire when nobody names it? It runs `claude -p` in an empty temp directory,
because measuring this from a subagent inside the repo does not work — the agent
finds the plugin on disk, reads `SKILL.md`, and may then invoke the skill by
name, which looks like triggering and is not. Eighteen runs were spent learning
that.

Half the cases are negatives. A skill that fires on everything is as broken as
one that never fires, and near-misses are where it happens.

## Writing a case

1. Build a fixture in `build.sh` whose trap is a state the extractor could
   actually produce. Fixtures go through the real extractor for this reason —
   four separate findings once traced back to hand-written JSON that looked
   plausible and was impossible, and a reader cannot tell an unrealistic fixture
   from a broken instrument.
2. Write `cases/<name>/prompt.md` the way a person would ask, not the way a test
   would. If the prompt names the trap, the case measures reading comprehension.
3. Write `cases/<name>/fixture`.
4. Add a `## Case: <name>  *(fixture: <fixture>)*` section to `rubric.md`.
5. Run `bash ../tests/test-evals-complete.sh`.

**A trap the tool solves is not a trap.** If `metrics_rollup.py` prints the
answer in its own output, the case cannot fail a run that reads its tool
results. Keep those as regression checks and mark them; put the discrimination
somewhere the tool is silent.
