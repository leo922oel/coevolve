#!/usr/bin/env bash
# Every test in the suite. No dependencies beyond bash, python3 and jq.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pass=0; fail=0
run() {
  printf '\n\033[1m── %s\033[0m\n' "$1"
  if "${@:2}" > /tmp/coevolve-test.$$ 2>&1; then
    tail -3 /tmp/coevolve-test.$$; pass=$((pass+1))
  else
    cat /tmp/coevolve-test.$$; fail=$((fail+1))
  fi
  rm -f /tmp/coevolve-test.$$
}
for t in "$HERE"/test_*.py; do run "$(basename "$t")" python3 "$t"; done
for t in "$HERE"/test-*.sh; do run "$(basename "$t")" bash "$t"; done
printf '\n\033[1m%d suites passed, %d failed\033[0m\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
