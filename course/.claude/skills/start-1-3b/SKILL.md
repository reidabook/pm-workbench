---
name: start-1-3b
description: "Lesson 1.3b: Track B: bring your existing PRDs and epics. Use when the learner types /start-1-3b."
disable-model-invocation: true
allowed-tools:
  - Read
  - Write
  - AskUserQuestion
  - "Bash(curl -s http://127.0.0.1:8765/api/*)"
  - "Bash(ls:*)"
  - "Bash(which:*)"
  - "Bash(python3 --version)"
  - "Bash(claude --version)"
  - "Bash(gh auth status)"
  - "Bash(../run.sh:*)"
---

## Setup

Read `.claude/rules/teaching-rules.md` and follow it for everything below.

# Lesson 1.3b: Bring your existing PRDs and epics

ACTION: Silently read the progress file. Read state: `epics` (count, in scope), `prds`, `initiatives`, `artifacts`, `meta`.

You already have work in flight. The goal of this lesson is one view of it: every epic, every PRD, and where each initiative stands, without retyping anything.

---

## Epics

[Report what the last pull brought in: how many epics, how many in scope, how many already closed.]

Epics that are closed or cancelled are kept out of the ranking but stay available for retros later.

STOP: Glance at **Backlog**. Is that the set of epics you'd call "ours"?

USER: Yes / no

[If no: tighten the custom epic JQL on Settings (lesson 1.2's reference) and pull again.]

---

## PRDs

The workbench reads PRDs from the workspace. A PRD is any markdown file with `type: prd` in its frontmatter.

- **Already markdown**: copy the files into `~/pm-workspace/prds/`, or add their folder under *Extra PRD directories* on Settings.
- **In Confluence, Google Docs or Word**: export or paste each into a `.md` file in `prds/`. Name it after the initiative in snake_case, e.g. `guest_checkout_v1_2026-11-04.md`. That name is how the workbench groups everything for one initiative.

At the top of each file add:

```
---
title: "Guest Checkout"
type: prd
---
```

and, if you know it, a table row `| **Epic Key** | SHOP-104 |` so the PRD links to its epic.

STOP: Bring in at least one PRD that matters this quarter. Then click **Rescan workspace** on Journey. Tell me when done.

USER: Done

ACTION: Read `prds` and `initiatives`: what was found, which initiative each landed under, which epics linked.

[Report it. If a PRD was found but no epic linked: on **Artifacts**, use **Link** on the PRD with the epic key. If it landed under an odd initiative name: rename the file, or use **Link artifact…** in the initiative drawer.]

---

## Where each initiative stands

Open **Journey**. Each row is one initiative; each chip is one step of the PM Journey. An imported PRD shows `PRD` done and most of the rest missing. That's honest: the workbench only counts what it can see evidence for.

ACTION: For each initiative, read its `steps`, `ready` and `next`.

[Summarize: for each, one line with the next step. E.g. "Guest Checkout: has a PRD, next is review-prd."]

STOP: Some of the steps may have happened outside the tool, say a design review in a meeting. For those, open the initiative and **Skip** the step with a short reason. Is there one like that?

USER: Answers

[Skipping with a reason keeps the record honest; it shows on the chip and in status reports.]

## Important Notes for Claude

- Don't copy or edit their files for them; they bring PRDs in so they know where things live.
- Initiative = base of the file name: version, date and suffixes like `_refined` are stripped.
- If many PRDs: one or two is enough for the course; the rest can follow.

## Success Criteria

- [ ] The epics in the Backlog are the team's set (JQL adjusted if needed)
- [ ] At least one existing PRD is in the workspace, detected, under a sensible initiative, linked to its epic
- [ ] Learner can read a Journey row and name the next step
- [ ] Learner knows how to skip a step that happened elsewhere, with a reason

## Reference

Deeper notes and troubleshooting for this lesson: [REFERENCE.md](lesson-modules/1.3b-existing-work/REFERENCE.md). Read it when the learner asks for more depth or something goes wrong, and relay the relevant part in your own words.

## Wrap-up

ACTION: Silently add `1.3b` to `completed` in the progress file and set `updated` to today (see the teaching rules). Don't narrate it.

Then close out in natural language, never as a list of commands:

- Only if it fits the moment, remind them they can ask for a recap or where they stand.
- End with the next step: when they're ready for the next lesson, use `/clear` first, then `/start-2-1`.
