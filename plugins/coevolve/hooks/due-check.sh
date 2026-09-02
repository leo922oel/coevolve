#!/usr/bin/env bash
# SessionStart hook — one short nudge when a stage of the loop is overdue.
#
# Offline and cheap: everything is derived from local artifacts, never a network
# call. Ordering is deliberate. A high-severity lesson that has been sitting in
# `logged` is put ABOVE curation and distillation, because the failure this
# whole system was rebuilt to fix was a lesson that got written down, filed, and
# then repeated two weeks later. Capturing more material while a known
# high-severity lesson goes unenforced is motion, not progress.
set -uo pipefail

HOME_DIR="${COEVOLVE_HOME:-${HOME}/.claude/coevolve}"
CFG="${HOME_DIR}/config.md"
[[ -f "$CFG" ]] || exit 0

cfg() { grep -m1 "^[[:space:]]*$1:" "$CFG" 2>/dev/null | sed -E "s/^[^:]*:[[:space:]]*//"; }
days_since() {  # ISO date -> whole days, or empty if unparseable
  local e; e="$(date -d "$1" +%s 2>/dev/null || echo 0)"
  [[ "$e" -gt 0 ]] && echo $(( ( $(date +%s) - e ) / 86400 ))
}

weekly="$(cfg weekly_due_days)";          weekly="${weekly:-7}"
monthly="$(cfg monthly_due_days)";        monthly="${monthly:-28}"
nudge="$(cfg inbox_nudge_count)";         nudge="${nudge:-10}"
cal_due="$(cfg calibrate_due_days)";      cal_due="${cal_due:-14}"
enact_due="$(cfg enact_due_days)";        enact_due="${enact_due:-3}"
playbook="${HOME_DIR}/playbook.md"

out=""

# ── ⑤ ENACT first: a high-severity lesson still only written down ──────────────
if [[ -d "${HOME_DIR}/lessons" ]]; then
  stuck=""; expired=""
  while IFS= read -r f; do
    grep -qE '^severity:[[:space:]]*high' "$f" || continue
    state="$(grep -m1 -E '^state:' "$f" | sed -E 's/^state:[ \t]*//')"
    name="$(basename "${f%.md}")"
    case "$state" in
      logged)
        logged="$(grep -m1 -E '^logged:' "$f" | sed -E 's/^logged:[ \t]*//')"
        age="$(days_since "$logged")"
        [[ -n "$age" && "$age" -ge "$enact_due" ]] && stuck+="${name} (${age}d) "
        ;;
      accepted)
        # Acceptance is a decision to carry a risk, not a way to make the alarm
        # stop. It must name a date to look again, and it comes back then —
        # otherwise `accepted` quietly becomes where lessons go to be forgotten.
        review="$(grep -m1 -E '^review_on:' "$f" | sed -E 's/^review_on:[ \t]*//')"
        if [[ -z "$review" ]]; then
          expired+="${name} (無 review_on) "
        else
          rdays="$(days_since "$review")"
          [[ -n "$rdays" && "$rdays" -ge 0 ]] && expired+="${name} (複審逾期 ${rdays}d) "
        fi
        ;;
    esac
  done < <(find "${HOME_DIR}/lessons" -maxdepth 1 -name '*.md' 2>/dev/null | sort)
  [[ -n "$stuck" ]] && out+="🚨 coevolve: high-severity lesson still only written down → 跑 coevolve:enact — ${stuck}"$'\n'
  [[ -n "$expired" ]] && out+="🚨 coevolve: 知情承擔的高嚴重度教訓該複審了 → 跑 coevolve:enact — ${expired}"$'\n'
fi

# ── pending predictions: cheap, and they expire in usefulness ──────────────────
pend="${HOME_DIR}/predictions/pending.jsonl"
if [[ -f "$pend" ]]; then
  n="$(grep -c '^{' "$pend" 2>/dev/null || true)"; n="${n:-0}"
  (( n > 0 )) && out+="🎯 coevolve: ${n} 場 session 待預測（10 秒）→ 跑 coevolve:predict。"$'\n'
fi

# ── ② CURATE ──────────────────────────────────────────────────────────────────
inbox="${HOME_DIR}/inbox.md"
pending=0
[[ -f "$inbox" ]] && pending="$(grep -c '^- ' "$inbox" 2>/dev/null || true)"
pending="${pending:-0}"
age_days=0
if (( pending > 0 )); then
  # Age from the OLDEST entry, not file mtime: mtime resets on every append and
  # would never trip for an active user. Sort rather than take the first line —
  # a hand-written flag can carry a back-dated note, and assuming chronological
  # order would silently stop the weekly trigger from ever firing.
  oldest="$(grep -oE '\[[0-9]{4}-[0-9]{2}-[0-9]{2}' "$inbox" 2>/dev/null | tr -d '[' | sort | head -1 || true)"
  [[ -n "$oldest" ]] && age_days="$(days_since "$oldest")" && age_days="${age_days:-0}"
fi
if (( pending >= nudge )); then
  out+="📓 coevolve: ${pending} 筆未策展（≥${nudge}）→ 跑 coevolve:curate。"$'\n'
elif (( pending > 0 && age_days >= weekly )); then
  out+="📓 coevolve: ${pending} 筆旗標、距今 ${age_days} 天 → 跑 coevolve:curate。"$'\n'
fi

# ── ③ CALIBRATE ───────────────────────────────────────────────────────────────
callog="${HOME_DIR}/calibrate-log.md"
if [[ -f "$callog" ]]; then
  cdate="$(grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' "$callog" 2>/dev/null | tail -1 || true)"
  if [[ -n "$cdate" ]]; then
    cdays="$(days_since "$cdate")"
    [[ -n "$cdays" ]] && (( cdays >= cal_due )) && out+="⚖️ coevolve: 距上次校準 ${cdays} 天 → 跑 coevolve:calibrate。"$'\n'
  fi
fi

# ── ④ DISTILL ─────────────────────────────────────────────────────────────────
if [[ -f "$playbook" ]]; then
  upd="$(grep -m1 '^updated:' "$playbook" | sed -E 's/^updated:[[:space:]]*//')"
  if [[ -n "$upd" ]]; then
    dd="$(days_since "$upd")"
    [[ -n "$dd" ]] && (( dd >= monthly )) && out+="🧭 coevolve: 距上次蒸餾 ${dd} 天 → 跑 coevolve:distill。"$'\n'
  fi
fi

# ── ⑥ VERIFY: enacted lessons whose effect has never been measured ────────────
if [[ -d "${HOME_DIR}/lessons" ]]; then
  unver="$(grep -lE '^state:[[:space:]]*enacted' "${HOME_DIR}"/lessons/*.md 2>/dev/null | wc -l | tr -d ' ')"
  (( unver > 0 )) && out+="🔬 coevolve: ${unver} 條已落實但未驗效 → 跑 coevolve:verify。"$'\n'
fi

[[ -n "$out" ]] && printf '%s' "$out"
exit 0
