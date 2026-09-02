# Acceptance Criteria

The gate every component must pass before it counts as done. Written before
implementation on purpose: if a criterion here cannot be checked by running
something, it is not a criterion — rewrite it until it is.

Each ID maps to a test in `plugins/coevolve/tests/`. `[manual]` marks the few
that need a human to look at output; everything else is scripted.

---

## A. `session-metrics` — deterministic interaction fingerprint

The one component that turns "how I work with AI" from self-report into
measurement. Everything downstream (VERIFY especially) depends on it being
objective, so its bar is the highest.

| ID | Criterion |
|----|-----------|
| A1 | Given a transcript JSONL, emits JSON containing: tool histogram, skill invocations by name, subagent types, model mix, `is_error` count, user-interrupt count, real user turn count, first/last timestamp, token usage, and a redacted project key. |
| A2 | Deterministic: same input twice → byte-identical output. |
| A3 | Malformed / truncated JSONL never crashes; unparseable lines are counted and reported in `parse_errors`. |
| A4 | **Never emits content.** Output contains no prompt text, file contents, code, paths, or command strings — only counts and names drawn from a fixed vocabulary. Enforced by a test that greps the output for known-secret sentinel strings planted in the fixture. |
| A5 | Runs over the full local transcript corpus without crashing; p95 per-file wall time < 2s. |
| A6 | Works on a transcript spanning multiple days / resumes (sessions are not clean episodes) and reports `span_days`. |
| A7 | Reports `transcript_kind`: a file whose every message is a sidechain is a **subagent** transcript, not a session, and still carries its parent `session_id` so a roll-up can attach it. Decided from content, not filename. |

> **Why A7 exists**: on a real machine roughly half the transcript files are
> `agent-*.jsonl` sidechains sharing their parent's session id. Counting them as
> sessions halves the apparent steering-turn rate and inflates the session count.
>
> **Why ① SENSE must run at Stop time**: transcripts are retained for about 30
> days. Fingerprint history cannot be backfilled beyond that window — it is
> gone. Capture is not an optimisation here, it is the only chance.

## B. De-identification gate

Inherited from the existing worklog suite; it must not regress, and it now
guards one more exit (the exported profile).

| ID | Criterion |
|----|-----------|
| B1 | Existing `deid-check` tests still pass unchanged. |
| B2 | Missing denylist fails **open** with a loud stderr warning (a broken guard must not paralyse capture). |
| B3 | Every outbound artifact — Notion export, `profile.json`, playbook diff — passes the gate before it is written. A single hit blocks that artifact, not the whole run. |
| B4 | The denylist itself is never written to the repo, never exported, never printed into a transcript. |

## C. Lesson state machine — the piece that closes the loop

The existing system logs lessons and stops. Recorded failure: a credential
leak was logged 2026-07-06 and repeated 2026-07-21. A lesson that never
reaches an enforcement layer does not change behaviour, so state is tracked.

| ID | Criterion |
|----|-----------|
| C1 | Every lesson carries `id`, `severity` (high/medium/low), `state` (logged → enacted → verified → retired), and `enforcement` (rule / hook / skill / none). |
| C2 | A `severity: high` lesson sitting in `state: logged` past `enact_due_days` is surfaced by `status` as the single top recommendation, ahead of curation and distillation. |
| C3 | **Regression test against real history**: fed the 2026-07-06 credential lesson, the system escalates it and proposes a concrete enforcement artifact rather than another playbook bullet. |
| C4 | State transitions are append-only and dated; a lesson's history is reconstructable. |
| C5 | On enactment, a lesson records a **baseline snapshot** of its registered metric, taken while the data still exists — and enactment warns when that baseline is already too thin to ever support a verdict. |
| C6 | A lesson's `enacted:` date is the day enforcement actually became **live**. Where activation needs a user action, the lesson stays `logged` and the stamp is performed by the installer that does the activation, so the two cannot diverge. |
| C7 | ENACT writes only under `lessons/` and `enforcement/`. The playbook belongs to DISTILL and the calibration log to CALIBRATE; a stage that edits its neighbours' artifacts makes every later diff ambiguous. |

> **Why C6 exists** — found by the grader, not by design. Two of three enact
> runs stamped `state: enacted` with today's date for a hook that was not
> registered and could not fire until the user edited settings. The skill's own
> text says that date is the split VERIFY will use and must be the day the
> change took effect; stamping early silently poisons every later comparison
> with a window in which nothing was actually enforced. The run that refused to
> stamp scored lowest, because the rubric rewarded the stamp — so the criterion
> is recorded here, where it cannot be graded away.

## D. `verify` — did the change actually change behaviour

| ID | Criterion |
|----|-----------|
| D1 | Given an enacted lesson and its enactment date, pulls the relevant metric from sessions before and after, and reports both windows side by side. |
| D2 | With too few sessions on either side, reports `insufficient evidence` and refuses to state a verdict. Never manufactures a trend from n=1. |
| D3 | The metric being compared is named in the lesson's enactment record, chosen *before* the outcome is known — no post-hoc metric shopping. |
| D4 | Distinguishes a thin **after** window from a thin **before** window, and says which is blocking. They are not the same problem: the after side fills as you work, the before side is closed forever. |
| D5 | Accepts a **baseline snapshot stored at enactment time** and compares against it instead of re-deriving the before window, so a lesson stays verifiable after its transcripts age out. |
| D6 | With an adequate stored baseline, produces a verdict even when the store holds no before-side sessions at all. |

> **Why D4-D6 exist** — found by the first eval run, not by design. VERIFY
> correctly refused a verdict on two sessions per side, then pointed out that the
> before side can never grow: sessions earlier than the enactment date are
> already all the sessions there will ever be. Transcripts age out in about 30
> days, so the one recovery route expires too. A correct refusal had turned into
> a permanent stall, and every lesson enacted early in a store's life was
> unverifiable forever. D2 was right and incomplete: refusing thin evidence only
> helps if the evidence can still arrive.

## E. `profile` — the portable cowork profile

| ID | Criterion |
|----|-----------|
| E1 | Output validates against `schemas/profile.schema.json`. |
| E2 | Zero identifying information: passes the deid gate and contains only whitelisted fields. |
| E3 | A brand-new user with no data produces a **valid** profile marked `insufficient_data`, not an error and not a fabricated one. |
| E4 | Every claim in the profile carries its evidence count and confidence, so a consumer can weight it. Unsupported claims are omitted, not softened. |

## F. Distribution

| ID | Criterion |
|----|-----------|
| F1 | `/plugin marketplace add <repo>` then `/plugin install coevolve` works on a clean machine. |
| F2 | The repo contains **zero personal data**. All user data lives under `$COEVOLVE_HOME` (default `~/.claude/coevolve`). Checked by a test that greps the repo for the denylist and for `~/.claude/coevolve` writes outside the templates. |
| F3 | The full six-stage loop runs with **no Notion MCP present**. Notion is an optional export target, never a dependency. |
| F4 | Every script honours `$COEVOLVE_HOME`, so tests run against a temp dir and never touch the user's real data. |

## G. Migration from the existing worklog suite

| ID | Criterion |
|----|-----------|
| G1 | Migration is idempotent: running it twice produces the same result and never duplicates an episode. |
| G2 | The four calibration cycles' findings survive migration intact — they are the most valuable accumulated asset. |
| G3 | Migration is dry-run by default and prints what it would write before writing anything. |
| G4 | The existing `~/.claude/worklog` tree is left untouched (copy, never move) until the user confirms. |
