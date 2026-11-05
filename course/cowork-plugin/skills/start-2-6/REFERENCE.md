# 2.6 Reference: epics, stories, specs

## Epics JSON
```json
{"initiative": "faster-checkout", "prd": "/abs/path", "parent": "INIT-10",
 "epics": [{"title": "", "description": "", "outcome": "", "acceptance_criteria": "", "labels": [], "jira_key": null,
            "stories": [{"title": "", "story": "As a …, I want …, so that …", "acceptance_criteria": ["Given … When … Then …"],
                         "points": 3, "labels": [], "dor_status": "PENDING", "dor_notes": "", "jira_key": null}]}]}
```

| Chip | Skill | Side effects |
|---|---|---|
| E&S | `/pm-generate-epics-and-stories --prd <prd> [--parent <key>]` | none |
| Push | `/pm-publish-specs --file <prd> --file <hld>` | branch + PR in `spec_repo` |

## Push statuses
done = PR merged · partial = PR open · optional when no `spec_repo` is set.
**Sync GitHub PRs** (Artifacts) reads PRs by `github_pr_authors` plus pinned `github_prs`.
