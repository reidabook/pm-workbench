# 1.3b Reference: existing work

## How a PRD is found
- Any `.md` under `prds/`, `refined-prds/` or an *Extra PRD directory* with frontmatter `type: prd`.
- Title: frontmatter `title`, else the first `# heading`.
- Initiative: the file name with version / date / `_refined` / `_review` suffixes stripped, `_` → `-`.
- Epic links: `| **Epic Key** |`, `| Key |` or `| Jira |` table rows; else epic keys in the first 80 lines that
  match known epics.

## Fixing linkage
| Problem | Fix |
|---|---|
| PRD under the wrong initiative | rename the file, or **Link artifact…** in the initiative drawer |
| Epic not linked | Artifacts → **Link** on the PRD |
| Jira ticket quoted in the PRD shows as an epic | add that ticket as an Inbox source; sources are never linked as epics |

## Statuses on Journey
done · partial · failed · skipped (with reason) · optional · missing. *Required* steps change with the PRD's
metadata (UX Required, HLD Ownership) and whether a spec repo is configured.
