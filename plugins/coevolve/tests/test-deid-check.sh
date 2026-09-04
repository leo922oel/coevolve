#!/usr/bin/env bash
# T-004: text containing denylist terms is blocked with terms named; clean text passes.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEID="$HERE/../scripts/deid-check.sh"
fail() { echo "FAIL: $1"; exit 1; }

deny="$(mktemp)"
cat > "$deny" <<'EOF'
# test-owned denylist (comment line must not match anything)
AcmeCorp
orders-etl

secret-repo/internal
EOF
sum_before="$(md5sum "$deny")"

# hit, exact case → exit 1, term named on stdout
if out="$(printf 'refactored AcmeCorp pipeline tests' | COEVOLVE_DENYLIST="$deny" bash "$DEID")"; then
  fail "exact-case hit must exit non-zero"
fi
echo "$out" | grep -q 'AcmeCorp' || fail "hit term not named: >>$out<<"

# hit, different case → still blocked (case-insensitive), term named
if out="$(printf 'touched ACMECORP again' | COEVOLVE_DENYLIST="$deny" bash "$DEID")"; then
  fail "case-variant hit must exit non-zero"
fi
echo "$out" | grep -qi 'acmecorp' || fail "case-variant hit not named: >>$out<<"

# multiple hits across multi-line stdin → each term listed on its own line
if out="$(printf 'line one mentions orders-etl\nline two mentions secret-repo/internal\n' \
    | COEVOLVE_DENYLIST="$deny" bash "$DEID")"; then
  fail "multi-hit input must exit non-zero"
fi
echo "$out" | grep -q '^orders-etl$' || fail "orders-etl not listed: >>$out<<"
echo "$out" | grep -q '^secret-repo/internal$' || fail "secret-repo/internal not listed: >>$out<<"

# clean text → exit 0, no output (blank/comment lines in denylist must not cause hits)
out="$(printf 'a clean multi-line note\nabout some ETL refactor\n' | COEVOLVE_DENYLIST="$deny" bash "$DEID")" \
  || fail "clean text must exit 0"
[ -z "$out" ] || fail "clean text must produce no output: >>$out<<"

# read-only: denylist unmodified after runs
echo "$sum_before" | md5sum -c --quiet || fail "denylist was modified"

# ── negative control: a denylist whose last line has no trailing newline ──────
# `while read` returns false on the final line when the file does not end in a
# newline, so the last term was silently never checked. A hand-edited denylist
# is exactly how a file ends up like that, and the term most recently added —
# the one someone cared enough to add today — is the one that gets dropped.
# The python gate (validate_profile.py) reads the same file with .splitlines()
# and caught it, so the two gates disagreed on the same input.
nonl="$(mktemp)"
printf 'AcmeCorp\nlast-term-no-newline' > "$nonl"   # deliberately no trailing \n
if out="$(printf 'we shipped last-term-no-newline today' | COEVOLVE_DENYLIST="$nonl" bash "$DEID")"; then
  fail "final denylist term without a trailing newline must still block (got exit 0)"
fi
echo "$out" | grep -q '^last-term-no-newline$' || fail "final term not named: >>$out<<"
# and the earlier terms in the same file must keep working
if out="$(printf 'about AcmeCorp' | COEVOLVE_DENYLIST="$nonl" bash "$DEID")"; then
  fail "earlier term in a no-trailing-newline denylist must still block"
fi
rm -f "$nonl"

# T-005: missing denylist → fail-open (exit 0, clean stdout) with a loud stderr warning
missing="$(mktemp -u)"
out="$(printf 'any text at all' | COEVOLVE_DENYLIST="$missing" bash "$DEID" 2>/tmp/deid-stderr.$$)" \
  || fail "missing denylist must fail open (exit 0)"
[ -z "$out" ] || fail "missing denylist must keep stdout clean: >>$out<<"
grep -qi 'denylist' /tmp/deid-stderr.$$ || fail "missing denylist must warn on stderr: >>$(cat /tmp/deid-stderr.$$)<<"
rm -f /tmp/deid-stderr.$$

rm -f "$deny"
echo PASS
