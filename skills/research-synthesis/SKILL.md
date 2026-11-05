---
name: pm-research-synthesis
description: Synthesize interview notes, tickets and data into themed findings with evidence.
argument-hint: "--file <notes or bundle>"
---

# Research synthesis

Read `.claude/pm-conventions.md` first and follow its names, paths and formats exactly. Arguments: `$ARGUMENTS`.

1. Read the input (interview notes, support tickets, survey export or an Inbox bundle from PM Workbench).
2. Cluster observations into 3–7 themes. For each: the insight in one sentence, how many sources support it,
   2–3 verbatim quotes with their source, and the confidence (high / medium / low).
3. Separate what users *said* from what they *did*. Call out contradictions and gaps.
4. End with "Implications for the product" and "Open questions".
5. Write `research/<stem>_<date>.md`.
Finish by writing the checkpoint `<slug>/checkpoints/research-synthesis.md` and telling the PM the next step.
