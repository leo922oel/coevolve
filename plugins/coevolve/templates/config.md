# coevolve config

Flat `key: value` lines, read by the skills and by both hooks. Everything in
this directory is yours and stays on this machine.

## Where things live
inbox_path: inbox.md
playbook_path: playbook.md
profile_path: profile.json
denylist_path: denylist.txt

## Capture (① SENSE)
# A session below this many tool calls is fingerprinted but not queued for
# curation — it is rarely a work episode worth writing up.
flag_min_tool_calls: 30
# stop         → ask for the prediction the moment the session ends (best recall,
#                interrupts you once per substantial session)
# next-session → ask at the start of the next session (default, never interrupts)
# off          → never ask; predictions become optional
prediction_prompt: next-session

## Cadence
weekly_due_days: 7
monthly_due_days: 28
inbox_nudge_count: 10
calibrate_due_days: 14
calibrate_min_age_days: 5
# How long a high-severity lesson may sit in `logged` before the loop starts
# insisting. Short on purpose: this is the gap the system exists to close.
enact_due_days: 3
# Lower-severity lessons get a longer fuse, not silence. Filtering them out
# entirely means a lesson that costs you two days can sit unseen for weeks.
enact_due_days_medium: 21
# How long an enactment is left alone before the loop asks for verification.
# Verification takes weeks by nature; asking from day one is the same cry-wolf
# failure as never asking, arriving from the other direction.
verify_due_days: 14
distill_lookback_weeks: 4
# Sessions required on each side of a change before VERIFY will name a direction.
verify_min_sessions: 5

## Privacy
deidentify: true

## Optional Notion export (leave blank to stay entirely local)
notion_db_id:
notion_db_url:
