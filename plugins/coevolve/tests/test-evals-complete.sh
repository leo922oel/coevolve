#!/usr/bin/env bash
# An eval case that cannot be run, or cannot be graded, is worse than no case:
# it looks like coverage.
#
# Three things were true at once and none of them was visible from the tree:
# seven of twelve cases had no rubric section, so their runs produced answers
# with nothing to judge them against; the case→fixture mapping existed only in
# the rubric headings of the five cases that had one; and one case named a
# scenario no fixture could produce, so it could never have been run at all.
# All three are structural, so they are checked structurally.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EVALS="$HERE/../evals"
fail() { echo "FAIL: $1"; exit 1; }

known_fixtures="$(awk '/^case /,/^esac/' "$EVALS/fixtures/build.sh" \
                  | grep -oE '^[[:space:]]+[a-z][a-z0-9-]*\)' | tr -d ' )' | sort -u)"
[ -n "$known_fixtures" ] || fail "could not read the fixture list out of build.sh"

cases=0
for dir in "$EVALS"/cases/*/; do
  name="$(basename "$dir")"
  cases=$((cases + 1))

  [ -f "$dir/prompt.md" ] || fail "$name has no prompt.md"
  [ -s "$dir/prompt.md" ] || fail "$name has an empty prompt.md"

  # Which fixture a case runs against was tribal knowledge. A case that does not
  # say cannot be reproduced by anyone who was not in the room.
  [ -f "$dir/fixture" ] || fail "$name does not name its fixture (expected $dir/fixture)"
  fixture="$(tr -d '[:space:]' < "$dir/fixture")"
  [ -n "$fixture" ] || fail "$name has an empty fixture file"
  printf '%s\n' "$known_fixtures" | grep -qx "$fixture" \
    || fail "$name names fixture '$fixture', which build.sh does not know how to build"

  # A case with no assertions is an answer nobody can score.
  grep -q "^## Case: $name\b" "$EVALS/rubric.md" \
    || fail "$name has no '## Case: $name' section in rubric.md"

  # The rubric heading states the fixture too; the two must not drift apart.
  heading="$(grep -m1 "^## Case: $name\b" "$EVALS/rubric.md")"
  case "$heading" in
    *"fixture: $fixture"*) ;;
    *) fail "rubric heading for $name disagrees with cases/$name/fixture ($fixture): $heading" ;;
  esac
done

[ "$cases" -gt 0 ] || fail "no eval cases found"
echo "PASS all $cases eval cases name a buildable fixture and have rubric assertions"

# Every fixture build.sh ships should have a case, or be declared as a spare on
# purpose. An orphan fixture is either a case someone forgot to write or dead
# code, and the tree cannot tell you which.
spares="$EVALS/fixtures/UNUSED"
for fixture in $known_fixtures; do
  used=no
  for dir in "$EVALS"/cases/*/; do
    [ "$(tr -d '[:space:]' < "$dir/fixture" 2>/dev/null)" = "$fixture" ] && used=yes && break
  done
  if [ "$used" = no ]; then
    [ -f "$spares" ] && grep -qx "$fixture" "$spares" \
      || fail "fixture '$fixture' has no case and is not declared in fixtures/UNUSED"
  fi
done
echo "PASS every fixture is either used by a case or declared unused"
echo "PASS"
