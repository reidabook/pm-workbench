---
name: start-2-3
description: "PM Workbench course, lesson 2.3: Discovery: from idea to PRD. Use when the user asks to start or continue lesson 2.3 of the PM Workbench course."
---

## Setup

Read `teaching-rules.md` in this skill's folder and follow it for everything below.

# Lesson 2.3: Discovery: from idea to PRD

ACTION: Silently read the progress file. Read `initiatives`, `groups` and `artifacts` from state.

This is where an idea becomes something engineering could build. The journey's first phase is discovery: understand the problem, decide it's worth solving, then write it down.

[Track D: use **merchant-insights**: it has a discovery plan and nothing else yet.]

---

## How journey steps run

Every step is a Claude Code skill with a name like `/pm-generate-prd`. The workbench launches it for you: **Next** on a Journey row, **run** in the initiative drawer, or **Generate PRD** on an Inbox group. Each opens a terminal in your workspace with the command filled in. If a terminal can't open, **Copy command** gives you the line to paste.

Each skill writes a file into the workspace with a fixed name. Afterwards you click **Rescan workspace** and the chip turns green. That's the whole loop.

STOP: Any questions about that loop before we use it?

USER: Answers / no

---

## Start the initiative: pm-guide

`/pm-guide` interviews you about the problem, users, evidence, goal and constraints, and writes `pm-context.md` and a **refinement plan**: which steps this initiative needs and which it can skip. **PM guide** is on the Journey header.

STOP: Run PM guide for your initiative. Answer like you would a sharp manager. Tell me when it's done and you've rescanned.

USER: Done

ACTION: Read the initiative: `G` status, and the refinement plan from the workspace.

[Summarize the plan in two sentences: which optional steps it recommends and why.]

ACTION: Save `initiative` (the slug) in the progress file.

---

## Research and the go / no-go

Two optional steps, worth doing on anything bigger than a week of work:

- `/pm-research-synthesis` turns notes, tickets and data into themes with quotes and confidence (`RS`).
- `/pm-concept-accept` scores the concept and decides **go**, **pivot** or **no-go** (`CA`).

The cheapest time to kill an idea is before the PRD. Concept Accept is where you give yourself permission to.

STOP: Do you have enough evidence to skip research, or do you want to run it? Either is fine, say why.

USER: Answers

[If they run them: wait, rescan, read the CA verdict and discuss it. If no-go: that's a good outcome; log the decision in the drawer and pick another initiative.]

---

## The PRD

`/pm-generate-prd` drafts the PRD from your inputs into `prds/`. The fastest route: **Generate PRD** on the Inbox group, which hands the skill the ideas, quotes and evidence together.

It asks only what it can't infer. Every goal needs a metric with baseline and target, and every requirement needs to be testable. It also proposes three decisions at the top: **UX Required**, **Legal Required**, **HLD Ownership**. Those decide which later steps are required.

STOP: Generate the PRD. Tell me when it's written and rescanned.

USER: Done

ACTION: Read the PRD (`/api/prds/<id>/text`): title, goals and their metrics, the three metadata rows.

[Give feedback in three lines: the strongest part, the weakest requirement, and any goal without a baseline.]

---

## Risk, UX and prototypes

Three optional follow-ups, each one chip:

- `RR` `/pm-risk-review`: security, privacy, accessibility, performance, rollout and backout. Do it whenever user data or payments are involved.
- `UX` `/pm-ux-brief`: a brief for design. **Required** if the PRD says UX Required = Yes.
- `POC` `/pm-poc`: a throwaway prototype on a branch to test the riskiest assumption. It may push a branch, so you'll be asked first.

ACTION: Check which of these the PRD metadata makes required.

STOP: [Name the required ones.] Which will you run now, and which will you skip with a reason?

USER: Answers

## Important Notes for Claude

- The learner launches every skill; never run `/pm-*` skills in this conversation.
- `/pm-poc` can push a git branch: explain that and get an explicit yes before they run it.
- If a chip doesn't turn green after a run: no rescan, the file name doesn't match the initiative, or the skill stopped early.
- Step ids: pm-guide, discovery, research-synthesis, concept-accept, generate-prd, risk-review, ux-brief, poc.

## Success Criteria

- [ ] Learner can launch a skill from the workbench and close the loop with Rescan
- [ ] `G` done; initiative saved to progress
- [ ] A deliberate decision on research and Concept Accept
- [ ] `PRD` done; learner has had feedback on its metrics and requirements
- [ ] Learner knows which of RR / UX / POC are required for this PRD and why

## Reference

Deeper notes and troubleshooting for this lesson: `REFERENCE.md` in this skill's folder. Read it when the learner asks for more depth or something goes wrong, and relay the relevant part in your own words.

## Wrap-up

ACTION: Silently add `2.3` to `completed` in the progress file and set `updated` to today (see the teaching rules). Don't narrate it.

Then close out in natural language, never as a list of commands:

- Only if it fits the moment, remind them they can ask for a recap or where they stand.
- End with the next step: when they're ready for the next lesson, start a new chat, then `/pm-workbench-course:start-2-4`.
