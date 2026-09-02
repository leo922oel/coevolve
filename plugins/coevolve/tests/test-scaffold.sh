#!/usr/bin/env bash
# The scaffold must be safe to run twice: a coevolve home holds hand-written
# material (the denylist, the playbook's human zone) that no upgrade may clobber.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CLAUDE_PLUGIN_ROOT="$(cd "$HERE/.." && pwd)"
fail() { echo "FAIL: $1"; exit 1; }
home="$(mktemp -d)"; trap 'rm -rf "$home"' EXIT

out="$(bash "$CLAUDE_PLUGIN_ROOT/scripts/scaffold.sh" --home "$home/x" --dry-run)"
[ -d "$home/x" ] && fail "dry run must not create anything"
printf '%s' "$out" | grep -q 'would write' || fail "dry run should say what it would do"
echo "PASS scaffold: dry run writes nothing"

bash "$CLAUDE_PLUGIN_ROOT/scripts/scaffold.sh" --home "$home" >/dev/null
for f in config.md denylist.txt playbook.md vocabulary.md flag-moment.zsh salt inbox.md calibrate-log.md; do
  [ -f "$home/$f" ] || fail "missing $f"
done
for d in metrics episodes lessons patterns predictions inbox-archive; do
  [ -d "$home/$d" ] || fail "missing dir $d"
done
[ "$(stat -c '%a' "$home/salt")" = "600" ] || fail "salt must not be world-readable"
echo "PASS scaffold: creates the full home"

echo "my-employer-name" >> "$home/denylist.txt"
echo "MY HAND WRITTEN RULE" >> "$home/playbook.md"
salt_before="$(cat "$home/salt")"
bash "$CLAUDE_PLUGIN_ROOT/scripts/scaffold.sh" --home "$home" >/dev/null
grep -q 'my-employer-name' "$home/denylist.txt" || fail "re-run destroyed the denylist"
grep -q 'MY HAND WRITTEN RULE' "$home/playbook.md" || fail "re-run destroyed the playbook"
[ "$(cat "$home/salt")" = "$salt_before" ] || fail "re-run rotated the salt — project keys would all change"
echo "PASS scaffold: idempotent, never clobbers your own material"
echo "PASS"
