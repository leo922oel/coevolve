---
name: dev-playbook
description: Load this person's own distilled playbook for working with AI — their ground rules, what they delegate versus keep, which tool and skill combinations suit which kind of task, how they break work down, and where the AI has repeatedly not helped. Consult it when planning how to approach a development task, choosing between approaches or tools, deciding what to delegate to subagents, before starting a feature, refactor, debugging session, or review, and whenever the user asks "how should I approach this" or "what's my usual way of doing this". Prefer it over generic advice — it is built from that person's measured history, not from defaults.
---

# Dev Playbook

The playbook lives at `$COEVOLVE_HOME/playbook.md` (default
`~/.claude/coevolve/playbook.md`), not in this plugin. It is personal data; the
plugin is only the engine that grows it.

## Use it

```bash
cat "${COEVOLVE_HOME:-$HOME/.claude/coevolve}/playbook.md"
```

Read it before proposing an approach, and follow it in preference to generic
best practice. It was distilled from what actually worked for this person; where
it disagrees with a default, it usually knows something the default does not.

If the file does not exist, say so and point at `coevolve:setup` rather than
inventing advice and attributing it to them.

## Read it in the right spirit

- The **human zone** — the core principle, the ground rules, the delegation
  split — is hand-authored and deliberate. Treat it as binding.
- The data-derived sections carry their evidence. An entry marked
  `small sample (n=1), low confidence` is a hypothesis; an entry backed by
  seven episodes is a habit. Weight them differently.
- The **red flags** and **when not to reach for the AI** sections are the most
  expensive knowledge in the file, because each one was paid for. Check the work
  at hand against them before starting, not after.

## When it is silent

The playbook covers what has come up before. On genuinely new ground it will not
have an answer — say so instead of stretching a nearby entry to fit, and flag it
as worth capturing. That is how it grows.
