# Append a timestamped one-line note to the coevolve inbox, from anywhere.
#
# The hooks capture sessions automatically, but the things most worth keeping —
# "that worked", "never do that again" — usually land between sessions, at the
# terminal. This is the thirty-second path for those.
#
# Usage:  flag-moment "a lesson, a win, a gotcha"
# Install: source this file from your shell rc.
flag-moment() {
  local home="${COEVOLVE_HOME:-$HOME/.claude/coevolve}"
  local capture=""
  # The installed plugin lives in a version-pinned cache directory, so resolve
  # the newest one instead of hard-coding a version that the next upgrade breaks.
  if [ -n "${COEVOLVE_PLUGIN_ROOT:-}" ] && [ -f "$COEVOLVE_PLUGIN_ROOT/scripts/capture.sh" ]; then
    capture="$COEVOLVE_PLUGIN_ROOT/scripts/capture.sh"
  else
    capture=$(ls -d "$HOME"/.claude/plugins/cache/coevolve/coevolve/*/scripts/capture.sh 2>/dev/null \
              | sort -V | tail -1)
  fi
  if [ -z "$capture" ]; then
    echo "flag-moment: coevolve plugin not found. Install it, or set COEVOLVE_PLUGIN_ROOT." >&2
    return 1
  fi
  COEVOLVE_HOME="$home" bash "$capture" "$@"
}
