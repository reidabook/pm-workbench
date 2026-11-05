---
name: pm-generate-hld
description: Draft a high-level design from a validated PRD, with engineering.
argument-hint: "--file <prd>"
---

# Generate HLD

Read `.claude/pm-conventions.md` first and follow its names, paths and formats exactly. Arguments: `$ARGUMENTS`.

1. Read the PRD. If `HLD Ownership` is Engineering, say so and stop.
2. Ask 1–3 architecture questions that change the design (data ownership, sync vs async, build vs buy).
   Record unanswered ones in `reviews/<stem>_hld_questions.md`.
3. Write `generated-hlds/HLD_<stem>_v1_<date>.md` with frontmatter `title` (same as the PRD), `type: hld`,
   `initiative: <slug>`, and sections: Context · Goals / non-goals · Architecture overview (diagram in Mermaid) ·
   Components · Data model · APIs · Security & privacy · Performance & scale · Observability · Rollout & flags ·
   Alternatives considered · Open questions.
Finish by writing the checkpoint `<slug>/checkpoints/generate-hld.md` and telling the PM the next step.
