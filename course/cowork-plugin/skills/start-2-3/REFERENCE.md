# 2.3 Reference: discovery

| Chip | Skill | Writes | Required |
|---|---|---|---|
| G | `/pm-guide` | `<slug>/pm-context.md`, `refinement-plan.md`, checkpoint | no |
| RS | `/pm-research-synthesis --file <notes>` | `research/<stem>_<date>.md` | no |
| — | `/pm-discovery` | `research/` plan, `competitive-research/` | no (not a chip) |
| CA | `/pm-concept-accept --file <research>` | `concept-accepts/` with `type: go-ca / pivot-ca / no-go-ca` | no |
| PRD | `/pm-generate-prd --file <input>` | `prds/<stem>_v1_<date>.md` | yes |
| RR | `/pm-risk-review --file <prd>` | `risk-reviews/` | no |
| UX | `/pm-ux-brief --file <prd>` | `ux-briefs/` | if UX Required = Yes |
| POC | `/pm-poc` | branch `feat/poc-<slug>`, `<slug>/poc.md` | no; **may push a branch** |

File formats: `skills/CONVENTIONS.md` in the repository (copied to `<workspace>/.claude/pm-conventions.md`).

## Troubleshooting
- **Terminal didn't open**: use *Copy command* and paste it into a terminal.
- **Skill says it doesn't exist**: open Settings → *Create workspace* again; it re-copies the skills.
- **PRD found under another initiative**: the file name decides; rename, or *Link artifact…*.
