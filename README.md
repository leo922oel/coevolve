# coevolve

A closed feedback loop over your own use of Claude Code. It records how you
actually work with an AI assistant, distils that into a playbook you read and a
profile a platform can consume — and then **changes your harness so the lessons
stick**, and measures whether your behaviour actually changed.

## Why the last part matters

Most "AI productivity tracking" stops at writing things down. Writing things
down does not change behaviour.

The evidence that shaped this design came from an earlier version of the system
itself. A lesson about pasting credentials into a transcript was recorded on one
date. The same mistake happened again two weeks later. The note was accurate,
well-written, and completely absent from the moment it was needed.

So the loop has six stages, and the last two are the point:

```
 ①  SENSE      every substantial session is fingerprinted automatically,
               plus a ten-second prediction from you

 ②  CURATE     raw signal becomes episodes

 ③  CALIBRATE  your prediction meets the outcome; the gap is the lesson

 ④  DISTILL    episodes and fingerprints become four kinds of knowledge

 ⑤  ENACT      high-severity lessons become hooks, rules, or skills
               — not another bullet in a document

 ⑥  VERIFY     the fingerprint measures whether behaviour actually changed.
               If it did not, the lesson goes back to ⑤.
```

## What gets measured

A deterministic extractor reads session transcripts — no LLM, no self-report —
and emits counts only:

- tool histogram, and which **skills** were actually invoked by name
- which **subagent types** were dispatched, and how much work happened inside them
- **model mix** across the session
- tool error rate, and how often you **interrupted** the assistant
- how many real steering turns a session needed
- session span, token usage, permission mode

Two rules keep it safe and useful: it contains **counts and vocabulary names
only, never content**, and it is computed identically every time — otherwise
before/after comparison means nothing.

Transcripts are retained for roughly 30 days, so capture happens at session end.
Whatever is not fingerprinted while the transcript exists cannot be recovered.

## Install

```
/plugin marketplace add <this repo>
/plugin install coevolve
```

Then run `coevolve:setup`. It creates `~/.claude/coevolve/`, asks for the terms
that must never leave your machine, and offers to migrate an existing
dev-worklog installation.

Requires `python3`, `bash`, and `jq`. No Python packages, no Notion account, no
network calls.

## Skills

| Skill | Stage | What it does |
|---|---|---|
| `coevolve:setup` | — | one-time scaffold, denylist, migration |
| `coevolve:status` | — | read-only navigator; recommends exactly one next action, plus a report mode |
| `coevolve:predict` | ① | ten-second prediction before the outcome is known |
| `coevolve:curate` | ② | flags + fingerprints + predictions → episodes |
| `coevolve:calibrate` | ③ | prediction versus outcome; corrects the record |
| `coevolve:distill` | ④ | habits, patterns, lessons, profile → playbook diff |
| `coevolve:enact` | ⑤ | a lesson becomes a hook, a rule, or a skill |
| `coevolve:verify` | ⑥ | did the metric actually move |
| `coevolve:profile` | ④ | export the portable cowork profile |
| `dev-playbook` | — | loads your playbook when planning work |

## Engine and profile are separate

The repo is an engine. It ships skills, scripts, hooks, schemas, templates and
tests, and contains **no personal data** — there is a test that enforces this,
including against your own denylist.

Everything personal lives in `$COEVOLVE_HOME` (default `~/.claude/coevolve`):

```
config.md  denylist.txt  salt  vocabulary.md
metrics/    ① fingerprints, one record per session
episodes/   ② curated work episodes
lessons/    failure lessons, each with a state machine
patterns/   reusable moves, each with an evidence count
playbook.md ④ the distillate you read
profile.json ④ the distillate a platform consumes
```

This separation is what lets the same repo be published publicly and installed
inside a company. It is also why the previous design — where the playbook was a
skill file full of one person's real project names — could not be shared at all.

## Privacy

- **Local artifacts stay detailed.** Episodes and lessons never leave the
  machine, so they are written in full. Blurring them at capture would cost the
  detail distillation needs, to protect a file that never travels.
- **De-identification happens at the exits.** Any Notion export and the profile
  export pass a deterministic denylist gate; a single hit blocks that artifact
  and names the term.
- **The fingerprint carries no content.** Not prompts, not code, not paths, not
  branch names. Project grouping uses a salted hash, so "sessions on the same
  project" works without the project's name ever existing outside your machine.
- The denylist itself is never exported, committed, or printed into a transcript.

## The cowork profile

`profile.json` is a portable, schema-validated summary of how one person works
with AI: measured interaction characteristics, what they delegate versus keep,
reusable patterns, live failure modes with their enforcement state, boundaries,
and their calibration bias. Every claim carries its evidence count and
confidence; claims without support are omitted rather than softened, and a
profile built on too little data says `insufficient_data` instead of guessing.

Schema: [`plugins/coevolve/schemas/profile.schema.json`](plugins/coevolve/schemas/profile.schema.json).

## Working on it

```bash
bash plugins/coevolve/tests/run-all.sh
```

One gotcha when developing against a local marketplace: an installed plugin is a
**version-pinned cache copy**, so edits to the repo do not take effect until the
version changes. `claude plugin update` will report you are already on the latest
version. Either bump `version` in `plugin.json`, or uninstall and reinstall:

```bash
claude plugin marketplace update coevolve
claude plugin uninstall coevolve && claude plugin install coevolve@coevolve
```

Acceptance criteria for every component are in
[`docs/acceptance.md`](docs/acceptance.md), written before the implementation.

## License

MIT.
