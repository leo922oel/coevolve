#!/usr/bin/env bash
# Everything the plugin needs at runtime must actually be in the repo.
#
# The failure this guards against is quiet and total: a .gitignore rule meant to
# keep personal data out also matched the shipped templates, so the repo tested
# green locally and could not scaffold on a fresh clone.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
fail() { echo "FAIL: $1"; exit 1; }

# every templates/<file> the scaffold copies must exist AND be tracked
refs="$(grep -oE '\$\{ROOT\}/templates/[A-Za-z0-9._-]+' "$ROOT/scripts/scaffold.sh" \
        | sed 's|.*/templates/||' | sort -u)"
[ -n "$refs" ] || fail "found no template references in scaffold.sh — did it move?"
for f in $refs; do
  [ -f "$ROOT/templates/$f" ] || fail "scaffold references templates/$f but it does not exist"
  if git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1; then
    git -C "$REPO" ls-files --error-unmatch "plugins/coevolve/templates/$f" >/dev/null 2>&1 \
      || fail "templates/$f exists but is NOT tracked by git — a fresh clone cannot scaffold"
    git -C "$REPO" check-ignore -q "plugins/coevolve/templates/$f" \
      && fail "templates/$f is matched by .gitignore"
  fi
done
echo "PASS all $(echo "$refs" | wc -w) scaffold templates exist and ship"

# scripts referenced by hooks and skills must exist
for s in session_metrics.py metrics_rollup.py validate_profile.py scaffold.sh \
         deid-check.sh capture.sh migrate_worklog.py backfill_metrics.py; do
  [ -f "$ROOT/scripts/$s" ] || fail "missing scripts/$s"
done
echo "PASS all referenced scripts present"

# every skill directory holds a SKILL.md with a name and a description
for d in "$ROOT"/skills/*/; do
  f="$d/SKILL.md"
  [ -f "$f" ] || fail "no SKILL.md in $d"
  grep -qE '^name: ' "$f" || fail "$f has no name"
  grep -qE '^description: ' "$f" || fail "$f has no description"
done
echo "PASS all $(ls -d "$ROOT"/skills/*/ | wc -l) skills have valid frontmatter"

# hooks/hooks.json is discovered automatically. Naming it in the manifest as
# well makes the loader see the same file twice and fail the WHOLE plugin —
# skills included — with an error that `claude plugin validate` does not catch.
if grep -qE '"hooks"[[:space:]]*:' "$ROOT/.claude-plugin/plugin.json"; then
  decl="$(grep -oE '"hooks"[[:space:]]*:[^,}]*' "$ROOT/.claude-plugin/plugin.json")"
  case "$decl" in
    *hooks/hooks.json*) fail "plugin.json declares the auto-loaded hooks/hooks.json ($decl) — the plugin will fail to load" ;;
  esac
fi
echo "PASS the manifest does not re-declare auto-loaded files"
echo "PASS"
