# 1.2 Reference: configuration

All settings are stored in `data/config.json` (never shared). Every key has a default in `config.example.json`.

| Setting | Purpose |
|---|---|
| `jira_base`, `jira_email`, `jira_project` | connection; email present = Jira Cloud (Basic auth), empty = Server/DC (Bearer PAT) |
| `parent_project` | project of parent issues (initiatives / business epics), so their keys are told apart from epics |
| `epic_jql` | overrides the default `project = X AND issuetype = Epic ORDER BY Rank ASC` |
| `jira_fields` | `parent_link` (default `parent`), `acceptance_criteria`, `outcome`, `story_points`, `product_owner`, `portfolio_team`, `epic_link` (Server only) |
| `portfolio_team_ids` | Advanced Roadmaps team ids → names, for team-scoped JQL |
| `pr_workspace` | the PM workspace (default `~/pm-workspace`) |
| `spec_repo`, `spec_path` | optional GitHub repo for published specs |
| `analytics_dir` | folder with `metrics-history.jsonl` / `metrics.json` for key results |
| `claude_mode` | `personal` or `off` |

## Finding a custom field id
- Jira Cloud: Settings → Issues → Custom fields → *…* → the URL ends `id=10042` → the id is `customfield_10042`.
- Any Jira: open `<jira>/rest/api/2/field` while signed in and search for the field name.

## Pull errors
| Error | Cause |
|---|---|
| 401 / 403 | wrong token, or Cloud email missing / wrong |
| 400 with JQL message | bad `epic_jql` or project key |
| 0 epics | project has none, or JQL too narrow |
