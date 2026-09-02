#!/usr/bin/env bash
# C6: the stamp and the activation are one operation.
#
# An `enacted:` date that precedes the enforcement actually firing gives VERIFY
# a split date with a dead window on one side of it, and every later comparison
# inherits the error silently. The only reliable fix is to make the two
# impossible to separate, which is what this installer is for.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL="$HERE/../templates/enforcement-install.sh"
fail() { echo "FAIL: $1"; exit 1; }

setup() {
  home="$(mktemp -d)"
  mkdir -p "$home/lessons" "$home/enforcement"
  cat > "$home/lessons/L-test.md" <<'LES'
---
id: L-test
severity: high
state: logged
enforcement: none
logged: 2026-08-10
enacted:
verified:
metric: observable:test
metric_direction: down
---

## History

- 2026-08-10 logged
LES
  printf '#!/usr/bin/env bash\nexit 0\n' > "$home/enforcement/guard.sh"
  chmod +x "$home/enforcement/guard.sh"
  settings="$home/settings.json"
  printf '{"hooks":{"PreToolUse":[{"matcher":"Bash","hooks":[{"type":"command","command":"pre-existing"}]}]}}\n' > "$settings"
}
run() { bash "$INSTALL" --lesson "$home/lessons/L-test.md" --guard "$home/enforcement/guard.sh" \
        --event UserPromptSubmit --settings "$settings" "$@"; }

setup
out="$(run --dry-run 2>&1)"; rc=$?
[ $rc -eq 0 ] || fail "dry run should succeed, got $rc: $out"
grep -q '^state: logged' "$home/lessons/L-test.md" || fail "dry run stamped the lesson"
grep -q 'pre-existing' "$settings" || fail "dry run touched settings"
if grep -q 'guard.sh' "$settings"; then fail "dry run registered the hook"; fi
echo "PASS dry run changes nothing"
rm -rf "$home"

setup
printf '#!/usr/bin/env bash\nexit 1\n' > "$home/enforcement/failing-test.sh"; chmod +x "$home/enforcement/failing-test.sh"
if run --test "$home/enforcement/failing-test.sh" >/dev/null 2>&1; then
  fail "install proceeded although the guard's own tests failed"
fi
grep -q '^state: logged' "$home/lessons/L-test.md" || fail "lesson stamped despite failing tests"
grep -q 'guard.sh' "$settings" && fail "hook registered despite failing tests"
echo "PASS a guard that fails its own tests is not installed"
rm -rf "$home"

setup
run >/dev/null 2>&1 || fail "install failed"
grep -q '^state: enacted' "$home/lessons/L-test.md" || fail "lesson not stamped after install"
grep -q "^enacted: $(date +%Y-%m-%d)$" "$home/lessons/L-test.md" || fail "enacted date missing or wrong"
grep -q 'guard.sh' "$settings" || fail "hook not registered"
grep -q 'pre-existing' "$settings" || fail "existing hooks were clobbered"
ls "$settings".bak.* >/dev/null 2>&1 || fail "settings were not backed up"
grep -q "$(date +%Y-%m-%d) enacted" "$home/lessons/L-test.md" || fail "History not appended"
echo "PASS install registers, backs up, preserves existing hooks, then stamps"

run >/dev/null 2>&1 || fail "second install failed"
[ "$(grep -c 'guard.sh' "$settings")" -eq 1 ] || fail "re-install duplicated the hook entry"
echo "PASS re-installing is idempotent"
rm -rf "$home"

setup
chmod -w "$settings"
if run >/dev/null 2>&1; then chmod +w "$settings"; fail "install reported success although settings could not be written"; fi
chmod +w "$settings"
grep -q '^state: logged' "$home/lessons/L-test.md" \
  || fail "lesson was stamped even though registration failed — the two must not be separable"
echo "PASS a failed registration leaves the lesson unstamped"
rm -rf "$home"
echo "PASS"
