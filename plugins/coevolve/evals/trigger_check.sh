#!/usr/bin/env bash
# Does a skill fire when nobody names it?
#
# This needs a *fresh* session with a neutral working directory. Measuring it
# from a subagent inside the repo does not work: the agent finds the plugin on
# disk, reads SKILL.md through the shell, and may then invoke the skill by name
# — which looks like triggering in the transcript and is not. Eighteen runs were
# spent learning that.
#
# Each case runs `claude -p` in an empty temp directory, then reads the resulting
# transcript for a Skill call. The sandbox will usually block the task from
# completing; that is fine and expected. The question here is only whether the
# skill was reached, and the strongest evidence for that is a Skill call as the
# *first* tool call, before any exploration could have revealed the plugin.
#
# Usage: trigger_check.sh [case-name ...]      (no arguments = all)
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL="${TRIGGER_MODEL:-opus}"

# name | fixture (or none) | expected skill (or NONE) | prompt
CASES=(
"profile|leaky-profile|coevolve:profile|我的 coevolve home 在 ./coevolve-home。平台團隊要接我的 cowork profile，幫我匯出一份給他們。"
"enact|enforcement-gap|coevolve:enact|我的 coevolve home 在 ./coevolve-home。開場提示跳出來說有一條 high severity 的教訓一直卡著沒處理。幫我看一下那條是什麼，然後把它真的處理掉——我不想再過兩個月又踩同一個坑。"
"verify|thin-evidence|coevolve:verify|我的 coevolve home 在 ./coevolve-home。我八月二十號落實了一條教訓，加了一條常駐規則。想知道到底有沒有用，幫我看一下數字。"
"status|enforcement-gap|coevolve:status|我的 coevolve home 在 ./coevolve-home。我最近都在幹嘛，有沒有什麼該處理的？"
"recurring|enforcement-gap|coevolve:enact|同樣的錯我這個月犯第三次了，到底要怎樣才能真的不要再犯？我的 coevolve home 在 ./coevolve-home。"
# Negatives. These are the ones worth getting right: a skill that fires on
# everything is as broken as one that never fires, and near-misses are where it
# happens. Each of these shares vocabulary with a coevolve skill and needs
# something else entirely.
"neg-debug|none|NONE|幫我看一下這段 python 為什麼會 IndexError：items = []; print(items[0])"
"neg-review|none|NONE|幫我 review 這個 diff，重點看有沒有把錯誤吞掉。"
"neg-metrics|none|NONE|幫我寫一支腳本統計這個 repo 每個作者的 commit 數，輸出 CSV。"
"neg-profile|none|NONE|幫我把使用者的個人資料表加一個 avatar 欄位，順便寫 migration。"
)

pass=0; fail=0
for entry in "${CASES[@]}"; do
  [[ "$entry" == \#* ]] && continue
  IFS='|' read -r name fixture expect prompt <<< "$entry"
  if (( $# > 0 )); then
    want=no; for a in "$@"; do [[ "$a" == "$name" ]] && want=yes; done
    [[ "$want" == yes ]] || continue
  fi
  dir="/tmp/coevolve-trigger-$name"
  rm -rf "$dir"; mkdir -p "$dir"
  [[ "$fixture" != "none" ]] && bash "$HERE/fixtures/build.sh" "$fixture" "$dir/coevolve-home" >/dev/null
  ( cd "$dir" && timeout 420 claude -p --model "$MODEL" "$prompt" >"$dir/out.txt" 2>&1 )

  slug="$(printf '%s' "$dir" | tr '/.' '--')"
  tr_file="$(ls -t "$HOME/.claude/projects/$slug"/*.jsonl 2>/dev/null | head -1)"
  if [[ -z "$tr_file" ]]; then
    printf '  %-12s NO TRANSCRIPT — cannot judge\n' "$name"; fail=$((fail+1)); continue
  fi
  fired="$(jq -r 'select(.type=="assistant")|.message.content[]?|select(.type=="tool_use" and .name=="Skill")|.input.skill' "$tr_file" 2>/dev/null | tr '\n' ' ' | sed 's/ *$//')"
  first="$(jq -r 'select(.type=="assistant")|.message.content[]?|select(.type=="tool_use")|.name' "$tr_file" 2>/dev/null | head -1)"

  if [[ "$expect" == "NONE" ]]; then
    if [[ -z "$fired" ]]; then ok=PASS; pass=$((pass+1)); else ok=FAIL; fail=$((fail+1)); fi
  else
    if [[ "$fired" == *"$expect"* ]]; then ok=PASS; pass=$((pass+1)); else ok=FAIL; fail=$((fail+1)); fi
  fi
  printf '  %-12s %s  fired=[%s]  first_tool=%s\n' "$name" "$ok" "${fired:-none}" "${first:-none}"
done
printf '\n%d passed, %d failed\n' "$pass" "$fail"
[[ "$fail" -eq 0 ]]
