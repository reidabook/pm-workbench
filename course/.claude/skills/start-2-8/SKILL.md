---
name: start-2-8
description: "Lesson 2.8: Prioritize the backlog. Use when the learner types /start-2-8."
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

# Lesson 2.8: Prioritize the backlog

ACTION: Silently read the progress file. Read `epics` (score inputs, score, rank, priority, gap vs Jira), `themes` (ranks), `params` (weights) and `committed`.

Ready work still has to be ranked against everything else. The Backlog tab turns a ranking argument into a few explicit ratings that anyone can challenge one at a time.

---

## How the score works

Each epic gets five ratings from 1 to 5 and an effort size:

- **Strategic value**: how much it moves the objective.
- **User impact**: how many users, how much.
- **Urgency**: cost of waiting.
- **Confidence**: how sure you are of the above.
- **Theme score**: comes from the objective's rank automatically.
- **Effort**: S, M or L, which divides the weighted total.

The highest scores become **P1** (top 15%), then P2, P3, P4. **Validation** (the evidence score from lesson 2.2) can be a sixth weight; it's 0 by default so nothing shifts until you decide.

ACTION: Pick the top three and bottom two in-scope epics and explain each in one line: which rating or the effort drives it.

STOP: [Give the five lines.] Does that order match your gut? Where doesn't it?

USER: Answers

[Where it doesn't match: find the rating that's wrong and fix it inline. If the ratings are right and the order still feels wrong, that's information: either the gut is wrong or a weight is.]

---

## Gaps and hygiene

- **NEEDS INFO** marks epics with ratings missing. They sink to the bottom until rated.
- **Confidence gap**: low confidence on a high score is flagged; that's an epic to research, not to commit.
- **Park** pins an epic to the top or bottom regardless of score; **Raise to P1** forces P1. Use both sparingly, and write why in *Notes*.
- Work already **In Dev** sits in *Already in flight*, out of the bands.

STOP: Rate anything marked NEEDS INFO in your objective. Tell me when done.

USER: Done

ACTION: Read again: remaining NEEDS INFO count, and any confidence gaps.

---

## Evidence as a weight

On **Settings** → *Scoring parameters*, **Weight: Validation** brings evidence into the ranking. The six weights must sum to 1; a reasonable start is strategic .25, impact .20, urgency .15, theme .15, confidence .10, validation .15.

STOP: Do you want evidence to count in your ranking? It's a team decision more than a PM one; you can leave it at 0.

USER: Answers

---

## Push to Jira

The workbench shows **Jira: P3** under any epic where its computed priority differs from Jira. **Push to Jira…** shows a dry run first: each priority change and the new rank order, with a tick box per change. Nothing is written until you click **Apply**.

[Track D: there's no Jira behind the demo; the dry run shows, Apply fails safely.]

This changes priority and rank on real Jira epics, which your team and other teams see.

STOP: Open **Push to Jira…** and read the dry run. Are there changes you'd want to talk to someone about before applying?

USER: Answers

[Encourage: untick anything contentious, apply the rest, and raise the contentious ones in planning with the ratings as the argument.]

## Important Notes for Claude

- *Push to Jira… → Apply* is a Jira write; the learner clicks it after reading the dry run.
- Score = Σ(weight × rating) / effort factor (S=1, M=2, L=3); theme score = 5 − 4·(rank−1)/(max−1).
- Ratings are edited inline on the Backlog; the learner does it.

## Success Criteria

- [ ] Learner can explain why an epic ranks where it does, from its ratings
- [ ] No NEEDS INFO left in their objective
- [ ] A deliberate decision on the validation weight
- [ ] Learner has read the Push to Jira dry run and applied or deferred each change on purpose

## Reference

Deeper notes and troubleshooting for this lesson: [REFERENCE.md](lesson-modules/2.8-backlog/REFERENCE.md). Read it when the learner asks for more depth or something goes wrong, and relay the relevant part in your own words.

## Wrap-up

ACTION: Silently add `2.8` to `completed` in the progress file and set `updated` to today (see the teaching rules). Don't narrate it.

Then close out in natural language, never as a list of commands:

- Only if it fits the moment, remind them they can ask for a recap or where they stand.
- End with the next step: when they're ready for the next lesson, use `/clear` first, then `/start-2-9`.
