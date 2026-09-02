#!/usr/bin/env bash
# T-001: any caller can capture a one-line note into the inbox via capture.sh.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CAP="$HERE/../scripts/capture.sh"
fail() { echo "FAIL: $1"; exit 1; }

tmp="$(mktemp)"

# arg mode: multi-word note appended in "- [YYYY-MM-DD HH:MM] <note>" format
COEVOLVE_INBOX="$tmp" bash "$CAP" "multi word note" >/dev/null
line="$(tail -1 "$tmp")"
echo "$line" | grep -qE '^- \[[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}\] multi word note$' \
  || fail "arg mode bad format: >>$line<<"
[ "$(grep -c '^- ' "$tmp")" -eq 1 ] || fail "expected exactly 1 line after arg mode"

# stdin mode
echo "from stdin" | COEVOLVE_INBOX="$tmp" bash "$CAP" >/dev/null
tail -1 "$tmp" | grep -qE '^- \[[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}\] from stdin$' \
  || fail "stdin mode bad format: >>$(tail -1 "$tmp")<<"

# empty note rejected, nothing appended
before="$(grep -c '^- ' "$tmp")"
if COEVOLVE_INBOX="$tmp" bash "$CAP" "" </dev/null 2>/dev/null; then
  fail "empty note must exit non-zero"
fi
[ "$(grep -c '^- ' "$tmp")" -eq "$before" ] || fail "empty note must not append"

rm -f "$tmp"
echo PASS
