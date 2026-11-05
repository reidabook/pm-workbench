---
name: pm-review-prd
description: Critical review of a PRD, then a refined version.
argument-hint: "--file <prd>"
---

# Review PRD

Read `.claude/pm-conventions.md` first and follow its names, paths and formats exactly. Arguments: `$ARGUMENTS`.

1. Read the PRD and its research.
2. Review as a skeptical engineering lead, designer and executive: unclear problem, missing evidence,
   untestable requirements, missing metrics, scope creep, hidden dependencies, unhandled edge cases.
3. Write the report to `reviews/<prd file stem>_review.md`: a verdict (ready / needs work), findings by
   severity, and the questions for the PM.
4. Ask the PM the blocking questions. Then write the improved PRD to
   `refined-prds/<stem>_v<N>_refined_<date>.md` (same title, same frontmatter, next version number).
Finish by writing the checkpoint `<slug>/checkpoints/review-prd.md` and telling the PM the next step.
Set `gate.result` to `pass` when the refined PRD has no blocking findings, else `fail`.
