#!/usr/bin/env bash
# Single capture entry point for the coevolve loop: append a timestamped one-liner to the inbox.
# Front-ends (flag-moment zsh fn, Stop hook, in-session Claude) all call this — one format source.
# Usage: capture.sh "a lesson, a win, a gotcha"     (or: echo "note" | capture.sh)
set -euo pipefail
inbox="${COEVOLVE_INBOX:-${COEVOLVE_HOME:-${HOME}/.claude/coevolve}/inbox.md}"

if (( $# > 0 )); then
  note="$*"
elif [[ ! -t 0 ]]; then
  note="$(cat || true)"
else
  note=""
fi
note="${note//$'\n'/ }"   # keep the one-line contract even for multi-line stdin

if [[ -z "${note// /}" ]]; then
  echo "usage: capture.sh <one-line note>   (or pipe the note on stdin)" >&2
  exit 1
fi

mkdir -p "$(dirname "$inbox")"

# Optional upsert: if COEVOLVE_DEDUP_KEY is set, drop any prior inbox line containing that key
# before appending — so repeated flags for the same session collapse to ONE entry (latest wins).
# Manual flags pass no key, so they always append and are never deduped.
if [[ -n "${COEVOLVE_DEDUP_KEY:-}" && -s "$inbox" ]]; then
  if grep -vF -- "$COEVOLVE_DEDUP_KEY" "$inbox" > "$inbox.tmp" 2>/dev/null; then
    mv -f "$inbox.tmp" "$inbox"          # ≥1 line kept
  elif [[ $? -eq 1 ]]; then
    mv -f "$inbox.tmp" "$inbox"          # all prior lines were this key → now empty, fine
  else
    rm -f "$inbox.tmp"                   # grep error → abort dedup, keep inbox intact
  fi
fi

printf -- '- [%s] %s\n' "$(date '+%Y-%m-%d %H:%M')" "$note" >> "$inbox"
echo "flagged → $inbox"
