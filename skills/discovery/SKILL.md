---
name: pm-discovery
description: Plan and run discovery for an initiative: questions, interview guide, competitor scan.
argument-hint: "[--file <input>] [topic]"
---

# Discovery

Read `.claude/pm-conventions.md` first and follow its names, paths and formats exactly. Arguments: `$ARGUMENTS`.

1. Read the input file (or `<slug>/pm-context.md`). List the riskiest assumptions (value, usability, feasibility, viability).
2. For each, propose the cheapest test (data pull, 5 interviews, fake door, prototype) and what result would change the plan.
3. Write an interview guide (open questions, no leading questions) and, when useful, a short competitor scan
   to `competitive-research/<stem>_<date>.md` (mark anything you could not verify).
4. Write the plan to `research/<stem>_<date>.md` under the heading `# Discovery plan: <title>`.
Finish by writing the checkpoint `<slug>/checkpoints/discovery.md` and telling the PM the next step.
