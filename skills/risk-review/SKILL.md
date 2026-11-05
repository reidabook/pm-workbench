---
name: pm-risk-review
description: Risk and non-functional requirements review of a PRD.
argument-hint: "--file <prd>"
---

# Risk review

Read `.claude/pm-conventions.md` first and follow its names, paths and formats exactly. Arguments: `$ARGUMENTS`.

1. Read the PRD.
2. Review: security & privacy (data collected, PII, permissions), legal / compliance, accessibility,
   performance & scale, reliability, observability, localization, migration, support load, rollout & backout.
3. For each finding: severity (high / medium / low), the requirement or NFR to add, an owner role.
4. Write `risk-reviews/<stem>_<date>.md`. Suggest exact PRD edits but do not change the PRD.
Finish by writing the checkpoint `<slug>/checkpoints/risk-review.md` and telling the PM the next step.
