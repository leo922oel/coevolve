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

# ── A same-day re-install must not eat the only clean rollback point.
#
# The backup name used to be date-only, so a second install on the same day
# copied the *already modified* settings over the first install's backup. The
# pristine file was then unrecoverable, and nothing said so.
setup
run >/dev/null 2>&1 || fail "first install failed"
cp "$home/enforcement/guard.sh" "$home/enforcement/guard2.sh"
bash "$INSTALL" --lesson "$home/lessons/L-test.md" --guard "$home/enforcement/guard2.sh" \
     --event UserPromptSubmit --settings "$settings" >/dev/null 2>&1 \
     || fail "second install failed"
count="$(ls "$settings".bak.* 2>/dev/null | wc -l)"
[ "$count" -eq 2 ] || fail "expected 2 distinct backups after 2 installs, got $count"
pristine=0
for b in "$settings".bak.*; do grep -q 'guard' "$b" || pristine=$((pristine+1)); done
[ "$pristine" -eq 1 ] \
  || fail "no backup still holds the pre-install settings — the rollback point was overwritten"
echo "PASS same-day installs keep separate backups"
rm -rf "$home"

# ── The settings file and the coevolve home must belong to the same install.
#
# An eval subject running against a fixture home reached the real
# ~/.claude/settings.json and registered a hook there, because the settings
# target defaulted to $HOME while the home was a sandbox. Guessing across that
# boundary is never right; refuse and make the caller say which.
setup
mkdir -p "$home/sandbox-home" "$home/fakehome/.claude"
out="$(HOME="$home/fakehome" COEVOLVE_HOME="$home/sandbox-home" \
       bash "$INSTALL" --lesson "$home/lessons/L-test.md" --guard "$home/enforcement/guard.sh" \
            --event UserPromptSubmit 2>&1)"; rc=$?
[ "$rc" -ne 0 ] || fail "installer guessed a settings target across a home boundary: $out"
[ -e "$home/fakehome/.claude/settings.json" ] \
  && fail "installer wrote settings outside the coevolve home it was pointed at"
grep -q '^state: logged' "$home/lessons/L-test.md" \
  || fail "lesson was stamped even though nothing was registered"
case "$out" in *COEVOLVE_HOME*) ;; *) fail "refusal does not say which two paths disagree: $out" ;; esac
echo "PASS refuses to guess the settings target from a non-default home"

# Naming the target explicitly is always allowed — that is the escape hatch.
HOME="$home/fakehome" COEVOLVE_HOME="$home/sandbox-home" \
  bash "$INSTALL" --lesson "$home/lessons/L-test.md" --guard "$home/enforcement/guard.sh" \
       --event UserPromptSubmit --settings "$settings" >/dev/null 2>&1 \
  || fail "explicit --settings should still work from a non-default home"
grep -q 'guard.sh' "$settings" || fail "explicit --settings did not register"
echo "PASS an explicit --settings still works from a non-default home"
rm -rf "$home"

# ── CLAUDE_CONFIG_DIR is how Claude Code itself relocates the config directory
#    (`CLAUDE_CONFIG_DIR ?? ~/.claude`), so it is the honest answer to "which
#    settings file" — and the lever a sandbox should pull. Honouring it means an
#    isolated run does not have to know this installer exists.
setup
mkdir -p "$home/cfg" "$home/fakehome/.claude"
HOME="$home/fakehome" CLAUDE_CONFIG_DIR="$home/cfg" COEVOLVE_HOME="$home/cfg/coevolve" \
  bash "$INSTALL" --lesson "$home/lessons/L-test.md" --guard "$home/enforcement/guard.sh" \
       --event UserPromptSubmit >/dev/null 2>&1 \
  || fail "install should follow CLAUDE_CONFIG_DIR without being told"
grep -q 'guard.sh' "$home/cfg/settings.json" \
  || fail "hook was not registered in \$CLAUDE_CONFIG_DIR/settings.json"
[ -e "$home/fakehome/.claude/settings.json" ] \
  && fail "install wrote to \$HOME even though CLAUDE_CONFIG_DIR was set"
echo "PASS CLAUDE_CONFIG_DIR decides which settings file, without --settings"
rm -rf "$home"

# A relocated config dir moves the default coevolve home with it, so this pair
# agrees and must not trip the boundary check.
setup
mkdir -p "$home/cfg/coevolve" "$home/fakehome/.claude"
out="$(HOME="$home/fakehome" CLAUDE_CONFIG_DIR="$home/cfg" COEVOLVE_HOME="$home/cfg/coevolve" \
       bash "$INSTALL" --lesson "$home/lessons/L-test.md" --guard "$home/enforcement/guard.sh" \
            --event UserPromptSubmit --dry-run 2>&1)"; rc=$?
[ "$rc" -eq 0 ] || fail "a home matching a relocated config dir should not be refused: $out"
echo "PASS a relocated config dir moves the default home with it"
rm -rf "$home"

# A CLAUDE_CONFIG_DIR that does not exist yet is a new config dir, not an error.
setup
mkdir -p "$home/fakehome"
HOME="$home/fakehome" CLAUDE_CONFIG_DIR="$home/brand-new" COEVOLVE_HOME="$home/brand-new/coevolve" \
  bash "$INSTALL" --lesson "$home/lessons/L-test.md" --guard "$home/enforcement/guard.sh" \
       --event UserPromptSubmit >/dev/null 2>&1 \
  || fail "install failed against a config dir that did not exist yet"
grep -q 'guard.sh' "$home/brand-new/settings.json" || fail "settings not created in the new config dir"
echo "PASS a config dir that does not exist yet is created, not an error"
rm -rf "$home"

echo "PASS"
