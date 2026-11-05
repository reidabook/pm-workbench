---
name: start-2-2
description: "PM Workbench course, lesson 2.2: Signals, ideas and evidence. Use when the user asks to start or continue lesson 2.2 of the PM Workbench course."
---

## Setup

Read `teaching-rules.md` in this skill's folder and follow it for everything below.

# Lesson 2.2: Signals, ideas and evidence

ACTION: Silently read the progress file. Read `sources`, `ideas`, `groups` and `evidence` from state.

Every good roadmap item can answer "how do we know?". This lesson turns raw signals into ideas, ideas into groups, and makes sure each carries its evidence so the backlog can weigh it.

[Track D: the demo Inbox has one source (checkout interviews) and four ideas.]

---

## Sources become ideas

[Report what's in the Inbox: sources and their signal types, ideas so far.]

On **Inbox**, open a source and click **Extract ideas**. Claude reads it and proposes ideas, each with a title, a short description and a supporting quote. You see the model and size before it runs. **Add idea by hand** works too.

STOP: Extract ideas from your source (or add two or three by hand). Tell me when done.

USER: Done

ACTION: Read `ideas`: the new ones, their quotes, and their evidence.

[Comment on quality in a sentence: are they problems ("re-entering card details is slow") or solutions ("add Apple Pay")? Problem-shaped ideas survive discovery better.]

---

## Ideas to objectives

**Assign themes** asks Claude to place unthemed ideas under your objectives and to propose a new one only when three or more ideas fit nothing.

STOP: Run it, and look at where your ideas landed. Any that went to the wrong objective? Fix them by hand.

USER: Answers

---

## Evidence and the validation score

Each idea from a source inherits its signal type as **evidence**. Types count differently:

- usage data counts most,
- customer feedback next,
- prospect feedback and support tickets,
- an internal ask or a competitor feature count least, and *competitor-only* is capped low.

Each epic ends up with a **validation score** from 1 to 5 from the distinct kinds of evidence behind it. It can feed the backlog ranking (lesson 2.8). The point isn't the number. It's that "the loudest stakeholder asked for it" has to sit next to "14 of 20 users struggled with it".

STOP: For your strongest idea, what other kind of evidence could you add? Add it with **Add evidence** if you have it.

USER: Answers

---

## Groups

Select the ideas that belong together and click **Group**. A group is the seed of an initiative: from it you can **Generate PRD** (next lesson) or **Draft epic** for something small enough to skip a PRD.

STOP: Make one group for the work your objective needs most. Name it as the outcome, not the feature.

USER: Done

ACTION: Read `groups`: name, objective, idea count, combined evidence.

## Important Notes for Claude

- Extract and Assign themes call Claude (Haiku); the learner clicks them after seeing the preview.
- Changing a source's signal type re-types the evidence of every idea taken from it.
- Track D: AI must be set to `personal` in Settings for Extract; if they kept it off, use **Add idea by hand**.

## Success Criteria

- [ ] Ideas exist from at least one real source, problem-shaped where possible
- [ ] Ideas are placed under objectives; misplacements corrected
- [ ] Learner can explain evidence types and why the validation score exists
- [ ] One group exists for the chosen objective, named as an outcome

## Reference

Deeper notes and troubleshooting for this lesson: `REFERENCE.md` in this skill's folder. Read it when the learner asks for more depth or something goes wrong, and relay the relevant part in your own words.

## Wrap-up

ACTION: Silently add `2.2` to `completed` in the progress file and set `updated` to today (see the teaching rules). Don't narrate it.

Then close out in natural language, never as a list of commands:

- Only if it fits the moment, remind them they can ask for a recap or where they stand.
- End with the next step: when they're ready for the next lesson, start a new chat, then `/pm-workbench-course:start-2-3`.
