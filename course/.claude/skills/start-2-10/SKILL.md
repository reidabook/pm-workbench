---
name: start-2-10
description: "Lesson 2.10: Close the loop: retro. Use when the learner types /start-2-10."
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

# Lesson 2.10: Close the loop: retro

ACTION: Silently read the progress file. Read `retros` (pending, done, omitted) and closed epics with their key results.

Shipping isn't the end. The retro asks whether the work did what the objective needed, and it's the step most teams skip, so the next objective gets planned on hope instead of evidence.

[If no epic has closed yet: say so. Explain how retros open (below), and that they should come back to this lesson when one closes. Track D: **ACME-110 One-click reorder** is closed; open its retro.]

---

## How retros start

A retro opens automatically when an epic reaches **Closed** on a Jira pull. **Open retros for earlier closures** does it for epics that closed before you started. Epics closed as *Won't Do*, *Duplicate* or *Cancelled* are flagged so you can **Omit** them with a reason.

ACTION: [List pending retros, one line each.]

STOP: Which one do you want to do? Pick one where you had a key result.

USER: Names one

---

## The facts

**Open retro** fetches the facts once from Jira:

- **Lifecycle**: created → first in development → closed; days in analysis vs development; reopens.
- **Scope**: stories, stories added after development started, points.
- **Key results** at release, +30, +60 and +90 days.

ACTION: Read the retro (`/api/retros/<key>`) and summarize the facts in three lines: how long it took and where the time went, how much scope moved, and what the key results did.

STOP: Anything in there you didn't expect?

USER: Answers

---

## The judgement

Four fields, each a sentence or two: **what shipped**, **impact** (refer to the KR numbers), **learnings**, and a **verdict**: *hit*, *partial*, *miss* or *too early*. **Draft retro summary** proposes them from the facts; you edit.

"Too early" is a real answer at +30 days. Come back at +90.

STOP: Write it, then **Save & mark done**. What's the one learning you'd carry into the next objective?

USER: Answers

[Suggest recording that learning as a decision on the objective, or as a source in the Inbox (an internal learning is evidence too).]

---

## The loop

That's the full circle: a signal became an idea, the idea an objective's initiative, the initiative a validated PRD, the PRD ready stories, the stories shipped work, and the work a measured result. The next objective starts in the Inbox with better evidence than this one did.

## Important Notes for Claude

- Opening a retro reads Jira; saving writes only to the local database.
- The verdict should follow the KR numbers; if they say "hit" with a flat KR, ask about it.
- After this lesson the course is complete; point them to the guide.

## Success Criteria

- [ ] Learner knows how retros open and when to omit one
- [ ] One retro has facts fetched and read
- [ ] What shipped, impact, learnings and a verdict saved, consistent with the KR numbers
- [ ] One learning carried forward into the workbench

## Reference

Deeper notes and troubleshooting for this lesson: [REFERENCE.md](lesson-modules/2.10-close/REFERENCE.md). Read it when the learner asks for more depth or something goes wrong, and relay the relevant part in your own words.

## Wrap-up

ACTION: Silently add `2.10` to `completed` in the progress file and set `updated` to today (see the teaching rules). Don't narrate it.

Then close out in natural language, never as a list of commands:

- Only if it fits the moment, remind them they can ask for a recap or where they stand.
- End with the next step: the course is complete. From here on `/guide` tells them what to do next on any objective or initiative, any time.
