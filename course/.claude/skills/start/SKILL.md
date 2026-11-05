---
name: start
description: "Lesson 0.1: Welcome and choose your track. Use when the learner types /start."
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

# Lesson 0.1: Welcome and choose your track

ACTION: Silently read the progress file. [If it exists and lists completed lessons: welcome them back, say in one sentence what's done and what's next, and offer to jump there with that lesson's command. Stop here if they take it.]

Welcome. This course gets PM Workbench running and then takes one objective all the way through: from a signal in an interview note to a ranked, ready backlog in Jira, and finally to a retro on whether it worked.

PM Workbench is a local app. It sits next to Jira rather than replacing it, keeps every document as a plain markdown file in one folder (your PM workspace), and uses Claude Code skills to draft and review those documents when you ask.

STOP: Before we pick a route: what's the part of your PM week that eats the most time today?

USER: Answers

[Connect their answer to the part of the course that addresses it, in one sentence: prioritization → lesson 2.8; status updates → 2.9; PRDs that bounce back from engineering → 2.4 and 2.7; not knowing if shipped work mattered → 2.1 and 2.10.]

---

## How the course works

- Module 1 is setup, about an hour.
- Module 2 is one lesson per phase of an objective's life. Take each one when your work reaches that phase; it's fine to spread them over weeks.
- I read the workbench myself, so you won't be asked to report what's on screen. You'll be asked for decisions.
- Anything that writes to Jira or GitHub, you trigger yourself, after I've said exactly what it will do.

---

## Choose your track

There are three ways in:

- **A: your Jira, from scratch.** You have a Jira project but no PRDs or epics for this work yet.
- **B: your Jira, existing work.** You already have epics, and maybe PRDs, and want them in one view.
- **D: demo.** A fictional online shop (Acme Shop) with three initiatives at different stages. No Jira needed; nothing leaves your machine. Good for a first look, or if you're evaluating the tool.

STOP: Which track fits? [Use a structured choice with the three options.]

USER: A, B or D

ACTION: Create the progress file with `track`, `completed: []` and `updated` set to today.

[If D: "Good choice for a first pass. Everything you learn carries over; switching to your own Jira later is one settings change."]

## Important Notes for Claude

- This lesson only orients and records the track. Don't start setup here.
- If they're unsure between A and B: any existing epic or PRD for the work they care about means B.
- If they want to evaluate before committing: suggest D, then re-run lesson 1.2 with their own Jira later.

## Success Criteria

- [ ] Learner knows what PM Workbench is: local, beside Jira, files in a workspace, AI on demand
- [ ] Learner knows how the course is paced and that they trigger every external write
- [ ] Track chosen and saved in the progress file

## Reference

Deeper notes and troubleshooting for this lesson: [REFERENCE.md](lesson-modules/0.1-start/REFERENCE.md). Read it when the learner asks for more depth or something goes wrong, and relay the relevant part in your own words.

## Wrap-up

ACTION: Silently add `0.1` to `completed` in the progress file and set `updated` to today (see the teaching rules). Don't narrate it.

Then close out in natural language, never as a list of commands:

- Only if it fits the moment, remind them they can ask for a recap or where they stand.
- End with the next step: when they're ready for the next lesson, use `/clear` first, then `/start-1-1`.
