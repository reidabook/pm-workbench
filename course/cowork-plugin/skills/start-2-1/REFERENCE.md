# 2.1 Reference: objectives and key results

## Maths
- KR progress = clamp((current − baseline) / (target − baseline), 0, 1)
- Epic progress = mean of its KRs. Objective = mean of objective-level KRs if any, else mean of measured epics.
- Health vs elapsed fraction of the period: ahead / on track (±15 pts) / behind; *unmeasured* with no reading;
  *released · measuring* for epics closed in the last 90 days.

## KR sources
| Source | Where values come from |
|---|---|
| manual | readings you record with `+` |
| metrics history | `<analytics_dir>/metrics-history.jsonl`, one dated JSON row per refresh |
| metrics snapshot | `<analytics_dir>/metrics.json`, dotted path, e.g. `usage.weekly_active_users` |

*Refresh key result values* pulls the latest from files and snapshots changes.

## Lint warnings (shown, never blocking)
target = baseline · direction contradicts target · title without a number, % or unit.

## Writing to Jira
*Write to Jira Outcome* writes a block between `h3. Key Results` and `_(managed by PM Workbench)_` into the epic's
Outcome field (needs `jira_fields.outcome`). Owner and due stay local.
