#!/usr/bin/env bash
# F2: the repo is an engine and must contain no personal data.
#
# This is the test that lets the same repo be published publicly and installed
# inside a company. It runs against the caller's own denylist when one exists,
# so it catches the specific terms that matter on this machine — not just the
# generic shapes.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
fail() { echo "FAIL: $1"; exit 1; }
scan() { git -C "$REPO" ls-files 2>/dev/null | grep -v '^plugins/coevolve/tests/test-no-personal-data.sh$' || true; }

files="$(scan)"
if [ -z "$files" ]; then
  files="$(cd "$REPO" && find . -type f -not -path './.git/*' -not -path './.omc/*' \
           -not -name 'test-no-personal-data.sh' | sed 's|^\./||')"
fi

# ── absolute home paths: the most common way a personal path leaks in ──────────
hits="$(cd "$REPO" && grep -nE '/(home|Users)/[a-z0-9._-]+/' $files 2>/dev/null \
        | grep -v '\$HOME' | grep -vE '/(home|Users)/(<user>|USER|you|someone|example)' || true)"
[ -z "$hits" ] || fail "absolute home path in the repo:
$hits"
echo "PASS no absolute home paths"

# ── email addresses ───────────────────────────────────────────────────────────
hits="$(cd "$REPO" && grep -nE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' $files 2>/dev/null \
        | grep -vE 'example\.(com|org)|@[A-Za-z0-9.-]*schemastore|anthropic\.com|json-schema\.org' || true)"
[ -z "$hits" ] || fail "email address in the repo:
$hits"
echo "PASS no email addresses"

# ── the caller's own denylist, if they have one ───────────────────────────────
deny=""
for cand in "${COEVOLVE_HOME:-$HOME/.claude/coevolve}/denylist.txt" "$HOME/.claude/worklog/denylist.txt"; do
  [ -f "$cand" ] && { deny="$cand"; break; }
done
if [ -n "$deny" ]; then
  found=""
  while IFS= read -r term; do
    case "$term" in ''|\#*) continue ;; esac
    hit="$(cd "$REPO" && grep -rniF -- "$term" $files 2>/dev/null | head -3 || true)"
    [ -n "$hit" ] && found="${found}${term}: ${hit}
"
  done < "$deny"
  [ -z "$found" ] || fail "denylisted term(s) present in the repo:
$found"
  echo "PASS repo is clean against $deny"
else
  echo "SKIP no denylist found to check against" >&2
fi

# ── nothing writes outside the user's own home, except templates ──────────────
hits="$(cd "$REPO" && grep -rnE '>\s*"?\$HOME/\.claude/(?!coevolve)' plugins/coevolve/scripts plugins/coevolve/hooks 2>/dev/null -P || true)"
[ -z "$hits" ] || fail "a script writes outside \$COEVOLVE_HOME:
$hits"
echo "PASS all writes are confined to the coevolve home"
echo "PASS"
