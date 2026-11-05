---
name: pm-validate-prd
description: PRD gate: Definition-of-Ready check on a PRD (PASS / FAIL).
argument-hint: "--file <refined prd>"
---

# Validate PRD (PRD gate)

Read `.claude/pm-conventions.md` first and follow its names, paths and formats exactly. Arguments: `$ARGUMENTS`.

1. Read the PRD (prefer the newest file in `refined-prds/`).
2. Check: problem and users stated; evidence cited; every goal has metric + baseline + target; every
   requirement testable; non-goals present; risks and rollout / backout present; UX Required, Legal Required
   and HLD Ownership rows filled; no open blocking question.
3. Write `prd-validations/<stem>_validation_<date>.md`, starting with:
   ```
   # PRD validation: <title>
   Initiative `<slug>`

   | Field | Value |
   |---|---|
   | Gate Result | **PASS** |   (or **FAIL**)
   | Source | <absolute path of the PRD> |
   | POC Confidence | High / Medium / Low / n/a |
   ```
   On PASS do not write the word "FAIL" anywhere in the first 20 lines. Then list every check with ✓ / ✗ and the fix.
4. Update the PRD metadata rows (UX Required, Legal Required, HLD Ownership) if the review changed them.
Finish by writing the checkpoint `<slug>/checkpoints/validate-prd.md` and telling the PM the next step.
