#!/usr/bin/env bash
# Deterministic de-identification gate for the coevolve loop.
# Reads text on stdin; if any denylist term occurs (case-insensitive),
# lists each matched term on its own line (stdout) and exits 1.
# Clean text → exit 0, no output. Denylist: one term per line,
# blank lines and #-comments ignored. Local only — never synced to Notion.
set -euo pipefail
DENYLIST="${COEVOLVE_DENYLIST:-${COEVOLVE_HOME:-${HOME}/.claude/coevolve}/denylist.txt}"

# Fail open: this gate is a backstop above LLM de-identification — a missing
# denylist must not paralyze curation, but it must be loud about it.
if [ ! -f "$DENYLIST" ]; then
  echo "deid-check warning: denylist not found at ${DENYLIST} — passing everything. Create it to enable the guard." >&2
  cat > /dev/null
  exit 0
fi

text="$(cat)"
hits=""
while IFS= read -r term; do
  case "$term" in ''|\#*) continue ;; esac
  if printf '%s' "$text" | grep -qiF -- "$term"; then
    hits+="${term}"$'\n'
  fi
done < "$DENYLIST"

if [ -n "$hits" ]; then
  printf '%s' "$hits"
  exit 1
fi
exit 0
