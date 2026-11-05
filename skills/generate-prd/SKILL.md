---
name: pm-generate-prd
description: Draft a PRD from research, a concept or an idea bundle.
argument-hint: "--file <input> [--parent <key>]"
---

# Generate PRD

Read `.claude/pm-conventions.md` first and follow its names, paths and formats exactly. Arguments: `$ARGUMENTS`.

1. Read the input file plus everything for the initiative (`<slug>/`, `research/`, `concept-accepts/`).
2. Ask the PM only what you cannot infer (at most 5 questions, one at a time).
3. Write the PRD in the conventions format to `prds/<stem>_v1_<date>.md`. Put `--parent` into `bepic_key`.
   Every requirement must be testable; every goal needs a metric with baseline and target (write `TBD` and
   list it under open questions when unknown). Fill UX Required / Legal Required / HLD Ownership with your
   best judgment and say why in one line under the table.
4. Do not create anything in Jira.
Finish by writing the checkpoint `<slug>/checkpoints/generate-prd.md` and telling the PM the next step.
