---
name: profile
description: Export a portable, de-identified cowork profile (profile.json) describing how this person works with AI — measured interaction characteristics, what they delegate versus keep, reusable patterns, failure modes, boundaries, and their calibration bias — for an agent platform to personalise against. Use when the user says "export my profile", "cowork profile", "產出使用者輪廓", "give the platform my working style", when onboarding a personalised agent, or when another system needs a machine-readable summary of how someone collaborates with AI. Refuses to export anything that fails the de-identification gate.
---

# Profile

The playbook is for you to read. This is the same knowledge in a form another
system can consume — so a platform can personalise for someone without spending
months re-deriving how they work.

It leaves the machine, so two rules are absolute: **every claim carries its
evidence**, and **nothing identifying goes in**.

## 1. Assemble from the four families

```bash
HOME_DIR="${COEVOLVE_HOME:-$HOME/.claude/coevolve}"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/metrics_rollup.py" window --since <90 days ago>
ls "$HOME_DIR/patterns"/*.md "$HOME_DIR/lessons"/*.md
sed -n '1,80p' "$HOME_DIR/playbook.md"
tail -40 "$HOME_DIR/calibrate-log.md"
```

Map them onto the schema at `${CLAUDE_PLUGIN_ROOT}/schemas/profile.schema.json`:

| Section | Source | Note |
|---|---|---|
| `interaction` | roll-up window | measured, never self-reported |
| `delegation_policy` | playbook human zone + episode evidence | the single most useful field for a consumer |
| `habits` | distilled playbook sections | one claim each, with counts |
| `reusable_patterns` | `patterns/` with `state: active` | must carry a recognisable trigger |
| `failure_modes` | `lessons/`, any state | include `state` — a `logged` lesson is a live risk, and saying so is the honest thing |
| `boundaries` | playbook "when not to reach for the AI" | where the AI does not help is as actionable as where it does |
| `calibration` | `calibrate-log.md` | e.g. "under-confident on delivered tooling" lets a consumer correct for a known bias instead of inheriting it |

## 2. Count the evidence; drop what you cannot support

Every claim needs `evidence` (how many independent episodes back it) and
`confidence`. Where support is thin, **omit the claim** rather than softening the
wording. A profile of twelve well-supported statements is more useful than forty
hedged ones, because a consumer weighting them cannot tell hedging from
uncertainty.

If there are fewer than about twenty sessions, set `status: insufficient_data`
and put the reason in `window.note`. That is a valid profile and consumers are
expected to degrade gracefully — a thin profile honestly labelled beats a
confident one built on three sessions.

## 3. Gate it before it leaves

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_profile.py" \
  "$HOME_DIR/profile.json" --denylist "$HOME_DIR/denylist.txt"
```

One command, two gates: schema shape and de-identification. Exit non-zero means
do not export — the error names the field path or the matched term. Re-abstract
and run it again.

Watch skill names in particular: a privately named skill can carry a customer or
product name straight into `interaction.skill_use`. The denylist catches the
terms it knows; you are responsible for the ones it does not, so read the
histograms before shipping.

A missing denylist fails open with a warning. Relay it — an unscreened export is
not the same as a clean one.

## 4. Hand it over with its limits attached

Say the window it covers, the session count, and which sections are thin. A
consumer that knows a claim rests on two episodes can weight it; one that does
not will treat it as fact.

## Boundaries

- Writes only `profile.json`. Never modifies episodes, lessons, patterns, or the playbook.
- Never exports a profile that failed the gate, and never edits the denylist to
  make one pass.
- Never includes raw prompts, file paths, repository names, branch names, or
  anything else that is content rather than a count or a controlled name.
