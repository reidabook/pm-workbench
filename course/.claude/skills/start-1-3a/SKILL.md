---
name: start-1-3a
description: "Lesson 1.3a: Track A: start from scratch. Use when the learner types /start-1-3a."
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

# Lesson 1.3a: Start from scratch

ACTION: Silently read the progress file. Read `themes` and `sources` from state, and read `portfolio-context.md` in the workspace.

You don't have PRDs or epics for this work yet, which is the cleanest start. Two things to set up: what your team is trying to achieve, and your first piece of evidence.

---

## Portfolio context

Open `portfolio-context.md` in your workspace. [Give the clickable path.] It's short on purpose: a **Priority Tiers** table (P0, P1, P2: the initiatives your team has committed to, most important first) and a **Program Jira Keys** table.

Every skill in the journey reads this file. It's how a PRD knows what matters more than what, without you repeating it in every session.

STOP: Fill in the Priority Tiers table with what your team is working on this quarter, even roughly. A parent key is optional. Tell me when it's saved.

USER: Done

ACTION: Read the file back and summarize the tiers in one line.

[If the tiers look like features rather than outcomes, e.g. "Build export button": say so gently. A tier is an outcome you'd still care about if the solution changed: "Merchants can see weekly sales without exporting".]

---

## Objectives

On **Settings**, *Portfolio context* → **Import Priority Tiers as objectives**. Each tier becomes an objective, ranked in the same order.

STOP: Import them, then open the **Objectives** tab.

USER: Done

ACTION: Read `themes`: names and ranks.

[Report what was created. If none: the table rows were empty or the heading was changed.]

We'll sharpen one of these into a real objective with key results in lesson 2.1.

---

## A first signal

Ideas should start from evidence: something a customer said, a number that moved, a ticket that keeps coming back. On **Inbox**, add one source: upload interview notes or a doc, paste text, or **Add from Jira** with a support ticket key.

STOP: Add one real source. When you choose its signal type, pick what it actually is (customer feedback, usage data, support…). Tell me when it's in.

USER: Done

ACTION: Read `sources`: confirm the new one and its evidence type.

We'll turn it into ideas in lesson 2.2.

## Important Notes for Claude

- Don't create objectives by hand for them; the import teaches the portfolio-context link.
- If they don't have a source handy, a recent support ticket via *Add from Jira* is the fastest real one.

## Success Criteria

- [ ] `portfolio-context.md` has at least one tier, phrased as an outcome
- [ ] Objectives imported and visible on the Objectives tab
- [ ] One real source in the Inbox with a deliberate signal type

## Reference

Deeper notes and troubleshooting for this lesson: [REFERENCE.md](lesson-modules/1.3a-from-scratch/REFERENCE.md). Read it when the learner asks for more depth or something goes wrong, and relay the relevant part in your own words.

## Wrap-up

ACTION: Silently add `1.3a` to `completed` in the progress file and set `updated` to today (see the teaching rules). Don't narrate it.

Then close out in natural language, never as a list of commands:

- Only if it fits the moment, remind them they can ask for a recap or where they stand.
- End with the next step: when they're ready for the next lesson, use `/clear` first, then `/start-2-1`.
