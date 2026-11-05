---
name: pm-validate-hld
description: Five-persona design review of an HLD.
argument-hint: "--file <hld>"
---

# Validate HLD

Read `.claude/pm-conventions.md` first and follow its names, paths and formats exactly. Arguments: `$ARGUMENTS`.

1. Read the HLD and its PRD.
2. Review it as five personas: Architect, Security, SRE / Operations, Data, QA. For each, list findings and give
   a verdict: `ok`, `requires_manual_review` or `blocked`.
3. Write `reviews/HLD_<stem>_v1_<date>_design_review.md` containing exactly this section:
   ```
   ## Persona Verdicts
   | Persona | Verdict | Notes |
   |---|---|---|
   | Architect | ok | ... |
   ```
   followed by the detailed findings.
Finish by writing the checkpoint `<slug>/checkpoints/validate-hld.md` and telling the PM the next step.
