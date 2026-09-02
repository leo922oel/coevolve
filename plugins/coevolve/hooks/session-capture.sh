#!/usr/bin/env bash
# Stop hook — the SENSE stage.
#
# Transcripts are retained for roughly 30 days. Whatever is not fingerprinted
# while it exists is gone for good, and with it any chance of answering "did my
# behaviour change after I enacted that lesson". So this runs on every session
# end, stays cheap, and never fails loudly enough to disturb the session.
#
# Two things happen here:
#   1. the session's deterministic fingerprint is appended to the metrics store
#   2. a substantial session is flagged for curation, and queued for a prediction
#
# Reads the Claude Code hook payload JSON on stdin. Otherwise read-only.
set -uo pipefail

HOME_DIR="${COEVOLVE_HOME:-${HOME}/.claude/coevolve}"
CFG="${HOME_DIR}/config.md"
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
[[ -f "$CFG" ]] || exit 0    # not set up yet → stay silent

cfg() { grep -m1 "^[[:space:]]*$1:" "$CFG" 2>/dev/null | sed -E "s/^[^:]*:[[:space:]]*//"; }

payload="$(cat || true)"
tp="$(printf '%s' "$payload" | jq -r '.transcript_path // empty' 2>/dev/null || true)"
[[ -n "$tp" && -f "$tp" ]] || exit 0

python_bin="$(command -v python3 || true)"
[[ -n "$python_bin" ]] || exit 0

metrics_dir="${HOME_DIR}/metrics"
mkdir -p "$metrics_dir"
fp="$("$python_bin" "${ROOT}/scripts/session_metrics.py" "$tp" 2>/dev/null || true)"
[[ -n "$fp" ]] || exit 0

# One line per capture. Repeats of the same transcript are expected — a long
# session stops many times — and the roll-up keeps the last one.
printf '%s\n' "$(printf '%s' "$fp" | tr -d '\n' | sed 's/  */ /g')" \
  >> "${metrics_dir}/$(date +%Y-%m).jsonl"

kind="$(printf '%s' "$fp" | jq -r '.transcript_kind // "unknown"')"
calls="$(printf '%s' "$fp" | jq -r '.counts.tool_calls // 0')"
tid="$(printf '%s' "$fp" | jq -r '.transcript_id // ""')"
[[ "$kind" == "session" ]] || exit 0     # subagent transcripts are not episodes

threshold="$(cfg flag_min_tool_calls)"; threshold="${threshold:-30}"
(( calls > threshold )) || exit 0

# Flag for curation, deduped by transcript so one session yields one inbox line.
hint="$(jq -r 'select(.type=="ai-title") | .aiTitle // empty' "$tp" 2>/dev/null | head -1 || true)"
[[ -z "$hint" ]] && hint="$(jq -r 'select(.type=="last-prompt") | .lastPrompt // empty' "$tp" 2>/dev/null | head -1 || true)"
hint="$(printf '%s' "$hint" | tr '\n' ' ' | sed -E 's/  +/ /g')"; hint="${hint:0:80}"
COEVOLVE_DEDUP_KEY="$tp" bash "${ROOT}/scripts/capture.sh" \
  "(auto) ${hint:+${hint} — }${calls} tool calls → review: ${tp}" >/dev/null 2>&1

# Queue a prediction. Recording what you EXPECTED before the outcome is known is
# the only thing that makes calibration non-circular later; estimating at
# curation time is hindsight wearing a prediction's clothes.
pend_dir="${HOME_DIR}/predictions"; mkdir -p "${pend_dir}/prompted"
if [[ -n "$tid" && ! -f "${pend_dir}/prompted/${tid}" ]] \
   && ! grep -qF "\"transcript_id\": \"${tid}\"" "${pend_dir}/pending.jsonl" 2>/dev/null; then
  printf '{"transcript_id": "%s", "queued": "%s", "tool_calls": %s, "hint": %s}\n' \
    "$tid" "$(date +%Y-%m-%d)" "$calls" "$(printf '%s' "$hint" | jq -R .)" \
    >> "${pend_dir}/pending.jsonl"
fi

# Asking at Stop is the highest-quality moment — the work is still in your head —
# but it interrupts, so it is opt-in. Default is to ask at the next session start.
mode="$(cfg prediction_prompt)"; mode="${mode:-next-session}"
if [[ "$mode" == "stop" && -n "$tid" && ! -f "${pend_dir}/prompted/${tid}" ]]; then
  active="$(printf '%s' "$payload" | jq -r '.stop_hook_active // false' 2>/dev/null || echo false)"
  if [[ "$active" != "true" ]]; then
    touch "${pend_dir}/prompted/${tid}"   # fire once per transcript, never loop
    echo "coevolve: this session ran ${calls} tool calls. Before it fades — ask the user for a 10-second prediction (time saved: <25/25-50/50-75/>75 %, confidence: high/medium/low), then record it with the coevolve:predict skill. If they decline, say so and stop." >&2
    exit 2
  fi
fi
exit 0
