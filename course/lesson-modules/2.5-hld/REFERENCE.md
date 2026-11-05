# 2.5 Reference: high-level design

| Chip | Skill | Writes |
|---|---|---|
| HLD | `/pm-generate-hld --file <prd>` | `generated-hlds/HLD_<stem>_v1_<date>.md`, `reviews/<stem>_hld_questions.md` |
| vHLD | `/pm-validate-hld --file <hld>` | `reviews/HLD_<stem>_v1_<date>_design_review.md` |

## Verdicts
The review must contain a `## Persona Verdicts` table: `| Persona | Verdict | Notes |`, verdict one of
`ok`, `requires_manual_review`, `blocked`. Overall = worst: APPROVED (done), REQUIRES_MANUAL_REVIEW (partial), BLOCKED (failed).

## Skipped automatically when
The PRD's `HLD Ownership` row says Engineering, not required, none, n/a or no.

## Linking
The HLD is matched to its PRD by title (same title in frontmatter), else by file name.
