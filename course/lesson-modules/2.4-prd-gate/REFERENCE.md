# 2.4 Reference: the PRD gate

| Chip | Skill | Writes |
|---|---|---|
| Rev | `/pm-review-prd --file <prd>` | `reviews/<prd stem>_review.md`, `refined-prds/<stem>_v<N>_refined_<date>.md`, checkpoint |
| Val | `/pm-validate-prd --file <refined prd>` | `prd-validations/<stem>_validation_<date>.md` |

## Statuses
| Chip | done | partial | failed |
|---|---|---|---|
| Rev | refined PRD or review report exists | checkpoint exists, no refined PRD | – |
| Val | report says PASS | – | report says FAIL |

## PRD metadata rows and their effect
| Row | Effect |
|---|---|
| UX Required = Yes | `UX` brief becomes required |
| Legal Required = Yes | stories get `Legal::Required`; epic DoR expects it |
| HLD Ownership = Engineering | `HLD` and `vHLD` skipped |
| Flag Intent / Flag Name | carried into epics (Toggle Status) |

## Troubleshooting
- **Validate ran on the original**: rescan so the refined file is detected, then run again.
- **Chip missing though a report exists**: the report lacks the `Gate Result` row; open it.
- **"FAIL" detected on a pass**: the report mentions FAIL in its first lines; the skill is told not to.
