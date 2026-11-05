# 1.3a Reference: from scratch

## portfolio-context.md
```markdown
## Priority Tiers
| Tier | Initiative | Investment Theme | Parent Key | Status |
|---|---|---|---|---|
| P0 | Faster checkout | Conversion | SHOP-1 | active |
```
- Import creates one objective per row with an initiative name; rows already imported are skipped.
- *Parent Key* becomes the objective's parent issue (only if it looks like a Jira key).

## Inbox sources
| Way in | Notes |
|---|---|
| Upload | `.md`, `.txt`, `.docx` |
| Paste | any text; give it a name |
| Add from Jira | story or defect keys or links; pulls summary, description, AC and comments; re-adding refreshes |

A source's **signal type** makes it evidence for every idea taken from it. Types and default weights are in lesson 2.2's reference.
