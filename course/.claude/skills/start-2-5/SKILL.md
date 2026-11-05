---
name: start-2-5
description: "Lesson 2.5: High-level design. Use when the learner types /start-2-5."
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

# Lesson 2.5: High-level design

ACTION: Silently read the progress file. Read the initiative's steps (`generate-hld`, `validate-hld`) and the PRD's HLD Ownership row.

[If HLD Ownership is Engineering or not required, and both chips show skipped: say so. Explain in two sentences why the step exists (below) so they know what they're skipping, then offer to move to lesson 2.6.]

[Track D: **faster-checkout** has a finished HLD and design review; use it to read a review. To practise running the steps, use **guest-checkout** once its PRD passes.]

A high-level design is the bridge between "what and why" and "how". As PM you don't write the architecture, but you're the one who can tell whether a design actually serves the PRD. A PRD that reaches engineering with no design tends to come back as three weeks of clarifying questions.

---

## Generate

`/pm-generate-hld` reads the validated PRD and asks you one to three architecture questions: the ones that change the shape of the design (who owns the data, sync or async, build or buy). Unanswered ones are recorded in `reviews/<stem>_hld_questions.md`. Then it writes the HLD into `generated-hlds/`: context, components, data model, APIs, security, scale, observability, rollout, alternatives.

STOP: Before you run it, who on your team would normally answer those questions? Bring them into the session if you can. Then run **Next** (it'll be generate-hld) and rescan.

USER: Done

ACTION: Read the `HLD` status and whether an hld-questions file exists.

[If `HLD` is partial: only the questions file exists. The questions need answers before the design can be written; that's a real dependency, so log it as a blocker with the owner.]

---

## The design review

`/pm-validate-hld` reviews the HLD as five personas: **Architect**, **Security**, **SRE / Operations**, **Data**, **QA**. Each gives a verdict:

- `ok` → the step is done (**APPROVED**),
- `requires_manual_review` → partial: a named human must sign off,
- `blocked` → failed: the design has a hole.

The overall verdict is the worst of the five.

STOP: Run it and rescan.

USER: Done

ACTION: Read the design review: the verdict per persona and the overall result.

[Summarize each persona in one line. For anything not ok: whose sign-off is needed, or what has to change.]

STOP: For each non-ok verdict, what's your move: change the design, or get the sign-off? Who owns it?

USER: Answers

[Suggest logging each as a risk or blocker with an owner in the initiative drawer.]

## Important Notes for Claude

- Both skills write local files only.
- `vHLD` partial is normal and fine to proceed with if the learner knows who signs off.
- If they skip HLD manually, the reason shows on the chip; make sure it's a real reason ("engineering-owned", "no new components").
- Step ids: generate-hld, validate-hld.

## Success Criteria

- [ ] Learner can say why a design step exists and when it's skipped
- [ ] `HLD` done (or skipped with a real reason); open architecture questions have owners
- [ ] `vHLD` run; every non-ok verdict has a next action and an owner

## Reference

Deeper notes and troubleshooting for this lesson: [REFERENCE.md](lesson-modules/2.5-hld/REFERENCE.md). Read it when the learner asks for more depth or something goes wrong, and relay the relevant part in your own words.

## Wrap-up

ACTION: Silently add `2.5` to `completed` in the progress file and set `updated` to today (see the teaching rules). Don't narrate it.

Then close out in natural language, never as a list of commands:

- Only if it fits the moment, remind them they can ask for a recap or where they stand.
- End with the next step: when they're ready for the next lesson, use `/clear` first, then `/start-2-6`.
