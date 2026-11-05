---
name: pm-poc
description: Build a throwaway prototype to test the riskiest assumption.
argument-hint: "[what to prototype]"
---

# Prototype (POC)

Read `.claude/pm-conventions.md` first and follow its names, paths and formats exactly. Arguments: `$ARGUMENTS`.

1. Ask which assumption the prototype must test and who will use it. Keep scope to one flow.
2. Build the smallest clickable prototype that tests it (a single HTML file is fine) on a branch
   `feat/poc-<slug>`. Never touch production code. Ask before pushing anywhere.
3. Write `<slug>/poc.md`: the assumption, how to run it, what to watch for, and the result once tested.
4. Tell the PM to paste the prototype URL or branch into the initiative drawer in PM Workbench.
Finish by writing the checkpoint `<slug>/checkpoints/poc.md` and telling the PM the next step.
