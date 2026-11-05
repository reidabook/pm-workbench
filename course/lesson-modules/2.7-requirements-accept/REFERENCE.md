# 2.7 Reference: Requirements Accept

## Creating issues
`POST http://127.0.0.1:8765/api/jira/publish-epics {"file": "<epics json>", "dry_run": true|false}`
- Creates each epic without `jira_key` (project `jira_project`, parent from the file's `parent`).
- Creates each story with `dor_status: PASS` and no `jira_key`: type Story, parent = epic on Cloud, or the
  `jira_fields.epic_link` field on Server / DC; points and AC into their fields when configured, else the description.
- Writes keys back into the JSON after each epic; appends stories to `<workspace>/jira-manifest.json`.

## RA status
done = linked epic keys appear in `jira-manifest.json` · partial = epics JSON has DoR results but nothing created.

## Ready
validate-prd PASS ∧ (publish-specs merged, if `spec_repo` set) ∧ requirements-accept done.

## Heuristic check (Backlog drawer)
Given/When/Then, five AC categories, persona, points ≤ 8, priority, vague terms, blockers, TODO/TBD; epic
conventions: parent, Toggle Status When Deployed, Backout Strategy, `UX::Required` / `Legal::Required` labels.
Cached per epic; amber after 7 days.
