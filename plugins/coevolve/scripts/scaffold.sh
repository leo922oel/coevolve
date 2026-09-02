#!/usr/bin/env bash
# Create a coevolve home from the shipped templates. Idempotent and additive:
# it never overwrites a file you already have, because everything in there is
# yours and some of it (the denylist, the playbook's human zone) is expensive to
# recreate. Re-run it after an upgrade to pick up new template files.
#
# Usage: scaffold.sh [--home DIR] [--dry-run]
set -euo pipefail
ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
HOME_DIR="${COEVOLVE_HOME:-${HOME}/.claude/coevolve}"
DRY=0
while (( $# )); do
  case "$1" in
    --home) HOME_DIR="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    *) echo "scaffold: unknown argument: $1" >&2; exit 2 ;;
  esac
done

say() { printf '%s\n' "$1"; }
do_mkdir() { (( DRY )) && say "would create dir  $1" || { mkdir -p "$1"; say "created dir  $1"; }; }
do_copy() {  # src dst
  if [[ -e "$2" ]]; then say "kept existing  $2"; return; fi
  if (( DRY )); then say "would write  $2"; else mkdir -p "$(dirname "$2")"; cp "$1" "$2"; say "wrote  $2"; fi
}

for d in metrics episodes lessons patterns predictions inbox-archive; do
  do_mkdir "${HOME_DIR}/${d}"
done

do_copy "${ROOT}/templates/config.md"        "${HOME_DIR}/config.md"
do_copy "${ROOT}/templates/denylist.txt"     "${HOME_DIR}/denylist.txt"
do_copy "${ROOT}/templates/vocabulary.md"    "${HOME_DIR}/vocabulary.md"
do_copy "${ROOT}/templates/flag-moment.zsh" "${HOME_DIR}/flag-moment.zsh"
do_copy "${ROOT}/templates/playbook.seed.md" "${HOME_DIR}/playbook.md"

# The salt makes project keys stable on this machine and meaningless off it, so
# grouping "sessions on the same project" never requires exporting its name.
if [[ ! -f "${HOME_DIR}/salt" ]]; then
  if (( DRY )); then
    say "would write  ${HOME_DIR}/salt  (random)"
  else
    if command -v openssl >/dev/null 2>&1; then salt="$(openssl rand -hex 16)"
    elif [[ -r /dev/urandom ]];              then salt="$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    else                                          salt="$(date +%s%N)-$$"
    fi
    printf '%s\n' "$salt" > "${HOME_DIR}/salt"
    chmod 600 "${HOME_DIR}/salt"
    say "wrote  ${HOME_DIR}/salt"
  fi
else
  say "kept existing  ${HOME_DIR}/salt"
fi

for f in inbox.md calibrate-log.md; do
  if [[ -e "${HOME_DIR}/${f}" ]]; then say "kept existing  ${HOME_DIR}/${f}"
  elif (( DRY )); then say "would write  ${HOME_DIR}/${f}"
  else : > "${HOME_DIR}/${f}"; say "wrote  ${HOME_DIR}/${f}"; fi
done

(( DRY )) && say "" && say "dry run — nothing was written."
exit 0
