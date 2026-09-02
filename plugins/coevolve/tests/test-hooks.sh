#!/usr/bin/env bash
# Integration tests for the two hooks. These are the only components that touch
# a user's real machine, so every one of them runs against a throwaway
# COEVOLVE_HOME (acceptance F4) and never reads the caller's data.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CLAUDE_PLUGIN_ROOT="$(cd "$HERE/.." && pwd)"
fail() { echo "FAIL: $1"; exit 1; }

export COEVOLVE_HOME="$(mktemp -d)"
trap 'rm -rf "$COEVOLVE_HOME"' EXIT
cat > "$COEVOLVE_HOME/config.md" <<'CFG'
flag_min_tool_calls: 2
enact_due_days: 3
weekly_due_days: 7
monthly_due_days: 28
inbox_nudge_count: 10
calibrate_due_days: 14
prediction_prompt: next-session
CFG

# ── a transcript with 3 tool calls ────────────────────────────────────────────
tp="$COEVOLVE_HOME/session-abc.jsonl"
{
  for i in 1 2 3; do
    printf '{"type":"assistant","timestamp":"2026-08-20T0%s:00:00.000Z","sessionId":"S1","cwd":"/x","message":{"model":"m","content":[{"type":"tool_use","name":"Bash","input":{}}]}}\n' "$i"
  done
  printf '{"type":"ai-title","aiTitle":"a test session"}\n'
} > "$tp"
payload="{\"transcript_path\":\"$tp\",\"stop_hook_active\":false}"

echo "$payload" | bash "$CLAUDE_PLUGIN_ROOT/hooks/session-capture.sh" >/dev/null 2>&1
[ -s "$COEVOLVE_HOME/metrics/$(date +%Y-%m).jsonl" ] || fail "no fingerprint written"
grep -q '"tool_calls": 3' "$COEVOLVE_HOME/metrics/$(date +%Y-%m).jsonl" \
  || grep -q '"tool_calls":3' "$COEVOLVE_HOME/metrics/$(date +%Y-%m).jsonl" \
  || fail "fingerprint missing tool_calls"
[ "$(wc -l < "$COEVOLVE_HOME/metrics/$(date +%Y-%m).jsonl")" -eq 1 ] || fail "fingerprint must be one line"
grep -q 'a test session' "$COEVOLVE_HOME/inbox.md" || fail "session not flagged for curation"
[ "$(grep -c '^{' "$COEVOLVE_HOME/predictions/pending.jsonl")" -eq 1 ] || fail "prediction not queued"

# ── a long session stops repeatedly; the inbox and the queue must not grow ─────
echo "$payload" | bash "$CLAUDE_PLUGIN_ROOT/hooks/session-capture.sh" >/dev/null 2>&1
[ "$(grep -c '^- ' "$COEVOLVE_HOME/inbox.md")" -eq 1 ] || fail "repeat Stop duplicated the inbox line"
[ "$(grep -c '^{' "$COEVOLVE_HOME/predictions/pending.jsonl")" -eq 1 ] || fail "repeat Stop duplicated the prediction"
[ "$(wc -l < "$COEVOLVE_HOME/metrics/$(date +%Y-%m).jsonl")" -eq 2 ] || fail "each capture should append; the roll-up dedups"
echo "PASS capture: fingerprint + flag + prediction, idempotent under repeat Stop"

# ── a subagent transcript is fingerprinted but is not an episode ───────────────
ag="$COEVOLVE_HOME/agent-zzz.jsonl"
printf '{"type":"assistant","isSidechain":true,"timestamp":"2026-08-20T01:00:00.000Z","sessionId":"S1","message":{"model":"m","content":[{"type":"tool_use","name":"Read","input":{}}]}}\n' > "$ag"
echo "{\"transcript_path\":\"$ag\"}" | bash "$CLAUDE_PLUGIN_ROOT/hooks/session-capture.sh" >/dev/null 2>&1
[ "$(grep -c '^- ' "$COEVOLVE_HOME/inbox.md")" -eq 1 ] || fail "subagent transcript must not create an episode"
grep -q '"transcript_kind": "subagent"' "$COEVOLVE_HOME/metrics/$(date +%Y-%m).jsonl" || fail "subagent fingerprint missing"
echo "PASS capture: subagent transcripts measured but not curated"

# ── an unenforced high-severity lesson outranks everything else ────────────────
mkdir -p "$COEVOLVE_HOME/lessons"
old="$(date -d '30 days ago' +%Y-%m-%d)"
cat > "$COEVOLVE_HOME/lessons/L-credentials.md" <<LES
---
id: L-credentials
severity: high
state: logged
enforcement: none
logged: $old
---
Credentials pasted into a transcript.
LES
printf -- '- [%s] older flag\n' "$(date -d '20 days ago' +'%Y-%m-%d %H:%M')" >> "$COEVOLVE_HOME/inbox.md"
out="$(bash "$CLAUDE_PLUGIN_ROOT/hooks/due-check.sh" 2>/dev/null)"
[ -n "$out" ] || fail "due-check produced nothing"
printf '%s' "$out" | head -1 | grep -q '🚨' \
  || fail "enforcement gap must be the FIRST line, got: $(printf '%s' "$out" | head -1)"
printf '%s' "$out" | grep -q 'L-credentials' || fail "stuck lesson not named"
printf '%s' "$out" | grep -q 'coevolve:curate' || fail "curation nudge missing"
printf '%s' "$out" | grep -q 'coevolve:predict' || fail "prediction nudge missing"
echo "PASS due-check: unenforced high-severity lesson ranks above capture work"

# ── once enacted it stops nagging, and starts asking to be verified ────────────
sed -i 's/^state: logged/state: enacted/; s/^enforcement: none/enforcement: hook/' "$COEVOLVE_HOME/lessons/L-credentials.md"
out="$(bash "$CLAUDE_PLUGIN_ROOT/hooks/due-check.sh" 2>/dev/null)"
printf '%s' "$out" | grep -q '🚨' && fail "enacted lesson must stop nagging"
printf '%s' "$out" | grep -q 'coevolve:verify' || fail "enacted lesson should now ask to be verified"
echo "PASS due-check: lesson state machine drives what gets recommended"

# ── a lesson nothing can enforce needs somewhere to go ────────────────────────
# Leaving it `logged` makes the alarm cry wolf forever, which teaches the user to
# ignore the one mechanism this system depends on. Marking it `enacted` is a lie
# that also sends VERIFY looking for a change that never happened. `accepted`
# says what actually happened — we looked, nothing fits, the risk is carried
# knowingly — and it comes back on its review date so it cannot be a graveyard.
export COEVOLVE_HOME="$(mktemp -d)"
cp "$COEVOLVE_HOME/../$(basename "$COEVOLVE_HOME")/../"/dev/null /dev/null 2>/dev/null || true
mkdir -p "$COEVOLVE_HOME/lessons"
cat > "$COEVOLVE_HOME/config.md" <<'CFG'
enact_due_days: 3
weekly_due_days: 7
monthly_due_days: 28
inbox_nudge_count: 10
calibrate_due_days: 14
CFG
old="$(date -d '30 days ago' +%Y-%m-%d)"
future="$(date -d '60 days' +%Y-%m-%d)"
past="$(date -d '2 days ago' +%Y-%m-%d)"
mk() { cat > "$COEVOLVE_HOME/lessons/$1.md" <<LES
---
id: $1
severity: high
state: $2
enforcement: none
logged: $old
review_on: $3
---
LES
}
mk L-accepted accepted "$future"
out="$(bash "$CLAUDE_PLUGIN_ROOT/hooks/due-check.sh" 2>/dev/null)"
printf '%s' "$out" | grep -q 'L-accepted' && fail "an accepted lesson must not keep raising the alarm"
printf '%s' "$out" | grep -q 'coevolve:verify' && fail "an accepted lesson has nothing to verify"
echo "PASS due-check: an accepted lesson stops nagging"

mk L-accepted accepted "$past"
out="$(bash "$CLAUDE_PLUGIN_ROOT/hooks/due-check.sh" 2>/dev/null)"
printf '%s' "$out" | grep -q 'L-accepted' || fail "an accepted lesson past its review date must come back"
echo "PASS due-check: acceptance expires on its review date"

mk L-noreview accepted ""
rm -f "$COEVOLVE_HOME/lessons/L-accepted.md"
out="$(bash "$CLAUDE_PLUGIN_ROOT/hooks/due-check.sh" 2>/dev/null)"
printf '%s' "$out" | grep -q 'L-noreview' || fail "accepted without a review date must not be a way to silence a lesson"
echo "PASS due-check: acceptance without a review date does not silence anything"
rm -rf "$COEVOLVE_HOME"

# ── no config anywhere → both hooks stay completely silent ─────────────────────
export COEVOLVE_HOME="$(mktemp -d)"
[ -z "$(bash "$CLAUDE_PLUGIN_ROOT/hooks/due-check.sh" 2>/dev/null)" ] || fail "must be silent before setup"
[ -z "$(echo "$payload" | bash "$CLAUDE_PLUGIN_ROOT/hooks/session-capture.sh" 2>/dev/null)" ] || fail "capture must be silent before setup"
rm -rf "$COEVOLVE_HOME"
echo "PASS hooks: silent until the user has actually set the loop up"
echo "PASS"
