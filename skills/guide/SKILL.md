---
name: pm-guide
description: Start or resume an initiative: orient on context, write pm-context.md and a refinement plan.
argument-hint: "[--initiative <slug>] [notes]"
---

# PM guide

Read `.claude/pm-conventions.md` first and follow its names, paths and formats exactly. Arguments: `$ARGUMENTS`.

1. Read `portfolio-context.md` and any existing files for the initiative (`<slug>/`, `prds/`, `research/`).
   With no `--initiative`, ask the PM for a one-line description and derive the slug.
2. Interview the PM, one question at a time, until you can fill: problem, target users, evidence so far,
   business goal and success metric, constraints, deadline, stakeholders, parent initiative key (if any).
3. Write `<slug>/pm-context.md` with those headings.
4. Write `<slug>/refinement-plan.md`: which journey steps this initiative needs, which can be skipped and why
   (e.g. no UX brief for a backend-only change; HLD owned by engineering), and the order.
Finish by writing the checkpoint `<slug>/checkpoints/pm-guide.md` and telling the PM the next step.
