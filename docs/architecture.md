# Architecture

## The problem this exists to solve

Most "AI productivity tracking" stops at writing things down. Writing things
down does not change behaviour. The evidence that motivated this rewrite came
from the system's own calibration log: a lesson about pasting credentials into
a transcript was recorded, and the same mistake happened again two weeks later.
A lesson that never reaches an enforcement layer is a diary entry.

So the loop has six stages, and the last two are the ones that matter most.

```
 ①  SENSE      hooks capture every substantial session:
               a deterministic fingerprint + a 10-second prediction from you

 ②  CURATE     raw signal becomes episodes — de-identified, structured

 ③  CALIBRATE  your prediction meets the outcome; the gap is the lesson

 ④  DISTILL    episodes + fingerprints become four kinds of knowledge

 ⑤  ENACT      high-severity lessons become rules, hooks, or skills
               ─ not another playbook bullet

 ⑥  VERIFY     the fingerprint from ① measures whether behaviour actually
               changed after ⑤. If it did not, the lesson goes back to ⑤.
```

⑥ feeding back into ⑤ is what makes this a loop rather than a pipeline.

## Engine vs. profile

The repo is an **engine**. It ships skills, scripts, hooks, schemas, seed
templates, and tests, and contains no personal data whatsoever.

Everything personal lives in **`$COEVOLVE_HOME`** (default `~/.claude/coevolve`),
outside the repo, never synced:

```
$COEVOLVE_HOME/
├── config.md              settings; the only file setup writes
├── denylist.txt           terms that must never leave this machine
├── inbox.md               raw flags awaiting curation
├── metrics/*.jsonl        ① deterministic fingerprints, one record per session
├── episodes/*.md          ② curated work episodes
├── lessons/*.md           failure lessons, each with a state machine
├── patterns/*.md          reusable success patterns, each with evidence count
├── playbook.md            ④ the human-readable distillate you actually read
└── profile.json           ④ the machine-readable distillate a platform consumes
```

The separation is load-bearing. It is what lets the same repo be published
publicly and installed inside a company, and it is why the previous version —
where the playbook was a skill file containing one person's real project names —
could not be distributed at all.

## Why four knowledge families instead of one table

The previous design put everything in one flat row type. But the four things
worth knowing have different shapes and different lifecycles:

| Family | Shape | Lifecycle | Produced by |
|---|---|---|---|
| **Interaction fingerprint** | time series, numeric | continuous, append-only | a script, deterministically |
| **Episodes** | discrete records | curated in batches | a person + Claude |
| **Failure lessons** | records with **state** | logged → enacted → verified | calibration + distillation |
| **Reusable patterns** | recipes with evidence counts | grow, get promoted, get retired | distillation |

Only the fingerprint can be measured. Only lessons need enforcement. Only
patterns need promotion. Forcing them into one schema is what made the old
system unable to do ⑤ or ⑥.

## Detail stays local; de-identification happens at the exits

The previous design de-identified at capture, because its store was a hosted
database — so every episode was abstracted the moment it was written, and the
detail that distillation needed later was destroyed on the way in.

Making the store local inverts that. Episodes and lessons are written in full,
because they never travel. The denylist gate moves to the boundary and guards
the two artifacts that actually leave: the exported profile, and the optional
hosted export. One gate, at the place where it matters, instead of a tax on
every write.

## What the fingerprint contains

Extracted from session transcripts with no LLM involvement, so it is objective,
reproducible, and cheap:

- tool histogram, and which **skills** were actually invoked by name
- which **subagent types** were dispatched, and how often
- **model mix** across the session — evidence for how delegation actually splits
- error rate (`is_error` on tool results) and user-interrupt count
- number of real steering turns from the human
- session span, token usage, permission mode

Two rules keep it safe and useful: it contains **counts and vocabulary names
only, never content**, and it is computed the same way every time so that
before/after comparison in ⑥ means something.

## Two exits from distillation

- **`playbook.md`** — for you. Read by the `dev-playbook` skill when planning work.
- **`profile.json`** — for a platform. A portable, schema-validated, fully
  de-identified summary of how one person works with AI, so an agent platform
  can personalise for them without re-deriving it. Every claim carries its
  evidence count and confidence; unsupported claims are omitted rather than
  softened.
