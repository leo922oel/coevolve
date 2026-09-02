#!/usr/bin/env bash
# Activate an enforcement artifact and stamp its lesson — as one operation.
#
# The `enacted:` date is the split VERIFY compares across, so it has to be the
# day the enforcement actually started firing. Stamping it when the artifact was
# *written* puts a dead window on one side of every later comparison, and
# nothing downstream can tell. Keeping the stamp inside the installer is the
# only way the two cannot drift: if registration fails, nothing is stamped.
#
# Every enact run tends to write its own version of this. Shipping one means the
# ordering guarantee is the same every time instead of being re-derived under
# time pressure.
#
# Usage:
#   enforcement-install.sh --lesson <lesson.md> --guard <script> --event <HookEvent>
#                          [--matcher <regex>] [--test <command>]
#                          [--settings <path>] [--dry-run]
set -uo pipefail

lesson="" guard="" event="" matcher="" testcmd="" dry=0
settings="" settings_explicit=0
while (( $# )); do
  case "$1" in
    --lesson)   lesson="$2"; shift 2 ;;
    --guard)    guard="$2"; shift 2 ;;
    --event)    event="$2"; shift 2 ;;
    --matcher)  matcher="$2"; shift 2 ;;
    --test)     testcmd="$2"; shift 2 ;;
    --settings) settings="$2"; settings_explicit=1; shift 2 ;;
    --dry-run)  dry=1; shift ;;
    *) echo "enforcement-install: unknown argument: $1" >&2; exit 2 ;;
  esac
done
for req in lesson guard event; do
  [[ -n "${!req}" ]] || { echo "enforcement-install: --$req is required" >&2; exit 2; }
done
[[ -f "$lesson" ]] || { echo "enforcement-install: no such lesson: $lesson" >&2; exit 2; }
[[ -f "$guard"  ]] || { echo "enforcement-install: no such guard: $guard" >&2; exit 2; }
command -v jq >/dev/null || { echo "enforcement-install: jq is required" >&2; exit 2; }

# Which settings file, in descending order of how sure we are:
#   --settings          the caller said so
#   CLAUDE_SETTINGS     the caller said so, out of band
#   CLAUDE_CONFIG_DIR   Claude Code's own relocation switch (`?? ~/.claude`),
#                       so honouring it means a sandbox does not need to know
#                       this installer exists
#   $HOME/.claude       a guess, and the only one — checked below
if [[ -z "$settings" ]]; then
  if [[ -n "${CLAUDE_SETTINGS:-}" ]]; then
    settings="$CLAUDE_SETTINGS"; settings_explicit=1
  elif [[ -n "${CLAUDE_CONFIG_DIR:-}" ]]; then
    settings="$CLAUDE_CONFIG_DIR/settings.json"; settings_explicit=1
  else
    settings="$HOME/.claude/settings.json"
  fi
fi
config_home="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

abspath() { python3 -c 'import os,sys; print(os.path.realpath(os.path.expanduser(sys.argv[1])))' "$1"; }

# ── 0. The settings file and the coevolve home must belong to the same install.
#
#       A run against a sandbox, a fixture, or a second home would otherwise
#       register its hook in the real ~/.claude/settings.json, because the
#       target defaulted to $HOME while the home was somewhere else entirely.
#       That has happened: an eval subject working inside a fixture directory
#       installed a UserPromptSubmit hook pointing at a path under /tmp, which
#       would have blocked every prompt once the temp directory was reaped.
#       There is no safe way to guess which of the two the caller meant, so
#       don't — name it, and the ambiguity is gone.
if (( ! settings_explicit )) && [[ -n "${COEVOLVE_HOME:-}" ]]; then
  if [[ "$(abspath "$COEVOLVE_HOME")" != "$(abspath "$config_home/coevolve")" ]]; then
    {
      echo "enforcement-install: refusing to guess which settings file to write."
      echo "  COEVOLVE_HOME is : $(abspath "$COEVOLVE_HOME")"
      echo "  but would write  : $(abspath "$settings")"
      echo
      echo "  Those belong to different installations. Registering a hook in one"
      echo "  while the lesson lives in the other is never what you meant."
      echo "  Say which: --settings <path>, or set CLAUDE_SETTINGS."
    } >&2
    exit 2
  fi
fi

today="$(date +%Y-%m-%d)"
command="bash \"$guard\""
[[ "$guard" == *.py ]] && command="python3 \"$guard\""

# ── 1. The guard must pass its own tests before it is allowed anywhere near
#       your settings. A guard that does not fire is worse than none: it looks
#       like the lesson is handled.
if [[ -n "$testcmd" ]]; then
  if ! eval "$testcmd" >/dev/null 2>&1; then
    echo "enforcement-install: the guard's own tests failed — refusing to install." >&2
    echo "  ran: $testcmd" >&2
    exit 1
  fi
fi

if (( dry )); then
  echo "would register : $event${matcher:+ (matcher $matcher)} -> $command"
  echo "would back up  : $settings"
  echo "would stamp    : $(basename "$lesson")  state=enacted  enacted=$today"
  echo
  echo "dry run — nothing was written."
  exit 0
fi

# ── 2. Register. Existing hooks are preserved; a hook already pointing at this
#       guard is left alone so re-running is safe.
# A relocated config dir may not exist yet; failing on that would be a confusing
# way to say "your CLAUDE_CONFIG_DIR is new".
mkdir -p "$(dirname "$settings")" 2>/dev/null
[[ -f "$settings" ]] || echo '{}' > "$settings"
if jq -e --arg c "$command" --arg e "$event" \
     '[(.hooks[$e] // [])[] | .hooks[]? | .command] | index($c) != null' \
     "$settings" >/dev/null 2>&1; then
  echo "already registered: $event -> $command"
else
  # Date-only names collided: a second install on the same day copied the
  # already-modified settings over the first install's backup, destroying the
  # only pristine copy. Never reuse a name that exists.
  stamp="$(date +%Y%m%d-%H%M%S)"
  backup="$settings.bak.$stamp"
  n=0
  while [[ -e "$backup" ]]; do n=$((n+1)); backup="$settings.bak.$stamp-$n"; done
  cp "$settings" "$backup" || { echo "enforcement-install: could not back up $settings" >&2; exit 1; }
  entry="$(jq -n --arg c "$command" --arg m "$matcher" --arg d "installed by coevolve enact" \
    '{hooks: [{type: "command", command: $c, timeout: 10}], description: $d}
     + (if $m == "" then {} else {matcher: $m} end)')"
  if ! jq --arg e "$event" --argjson entry "$entry" \
       '.hooks = ((.hooks // {}) | .[$e] = ((.[$e] // []) + [$entry]))' \
       "$backup" > "$settings.tmp"; then
    rm -f "$settings.tmp"
    echo "enforcement-install: failed to build the new settings" >&2; exit 1
  fi
  if ! cat "$settings.tmp" > "$settings" 2>/dev/null; then
    rm -f "$settings.tmp"
    echo "enforcement-install: could not write $settings — nothing was stamped." >&2
    exit 1
  fi
  rm -f "$settings.tmp"
  echo "registered: $event -> $command   (backup: $backup)"
fi

# ── 3. Only now, with enforcement actually live, stamp the lesson.
tmp="$lesson.tmp"
awk -v today="$today" -v enf="$event" '
  /^state:[[:space:]]*logged/     { print "state: enacted"; next }
  /^enacted:[[:space:]]*$/        { print "enacted: " today; next }
  /^enforcement:[[:space:]]*none/ { print "enforcement: " enf; next }
  { print }
' "$lesson" > "$tmp" && mv "$tmp" "$lesson"
printf -- '- %s enacted — %s hook registered (%s); enforcement is live from today\n' \
  "$today" "$event" "$(basename "$guard")" >> "$lesson"
echo "stamped: $(basename "$lesson")  state=enacted  enacted=$today"
echo
echo "Restart Claude Code for the hook to load. It is enacted, not verified —"
echo "nothing has been measured yet. Come back with coevolve:verify."
