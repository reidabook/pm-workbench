---
name: pm-concept-accept
description: Go / pivot / no-go decision on a concept before writing the PRD.
argument-hint: "--file <research or concept>"
---

# Concept Accept

Read `.claude/pm-conventions.md` first and follow its names, paths and formats exactly. Arguments: `$ARGUMENTS`.

1. Read the research and `<slug>/pm-context.md`.
2. Score the concept on: problem severity, evidence strength, strategic fit (portfolio-context), reach,
   effort guess, risk. 1–5 each with one line of reasoning.
3. Decide **go**, **pivot** or **no-go**, with the conditions that would change the decision.
4. Write `concept-accepts/<stem>_<date>.md` with frontmatter `title`, `initiative: <slug>` and
   `type: go-ca`, `pivot-ca` or `no-go-ca`.
Finish by writing the checkpoint `<slug>/checkpoints/concept-accept.md` and telling the PM the next step.
