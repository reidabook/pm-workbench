---
name: start-2-6
description: "PM Workbench course, lesson 2.6: Epics, stories and publishing specs. Use when the user asks to start or continue lesson 2.6 of the PM Workbench course."
---

## Setup

Read `teaching-rules.md` in this skill's folder and follow it for everything below.

# Lesson 2.6: Epics, stories and publishing specs

ACTION: Silently read the progress file. Read the initiative's steps (`generate-epics-and-stories`, `publish-specs`), its PRD and HLD paths, and `config.spec_repo`.

[Track D: **faster-checkout** shows a finished epics file; open it to see the shape. Run the step on **guest-checkout** if its PRD has passed.]

The PRD says what and why. Now it becomes work items. This is the step where scope gets cut into pieces small enough to ship, and where most estimation arguments are won or lost.

---

## Generate epics and stories

`/pm-generate-epics-and-stories` reads the PRD (and HLD) and writes `epics/<stem>_epics_<date>.json`: epics, each with an outcome, and stories with acceptance criteria and points. Two rules it enforces:

- **Right-sizing**: any story above 8 points is split.
- **Labels**: stories get `UX::Required` or `Legal::Required` when the PRD said so.

Nothing goes to Jira in this step. It's a draft you can argue with.

STOP: Run it from **Next** or the drawer (or **Create epics and stories** on Artifacts). Rescan when done.

USER: Done

ACTION: Read the epics JSON: number of epics, stories, total points, largest story.

[Summarize: "2 epics, 9 stories, 31 points; the biggest is 'Change card inline' at 5."]

STOP: Read the story list. Is there anything here you'd cut from the first release?

USER: Answers

[If yes: that's the most valuable PM decision in this lesson. They can edit the JSON, or re-run the skill with the cut stated. Encourage writing the cut down as a decision in the initiative log.]

---

## Publishing specs (optional)

Some teams keep approved PRDs and designs in a shared GitHub repository so engineers and other teams can find them. If yours does, set **Spec repo** on Settings, and `/pm-publish-specs` opens **one pull request** with the PRD and HLD. The step counts as done only once that PR is **merged**, because an open PR isn't agreement.

[If `spec_repo` is empty: "You don't have a spec repo configured, so this step is optional and Ready won't wait for it. If your team wants one later, it's one setting." Skip to the success criteria.]

[If `spec_repo` is set:]

This one writes outside your machine: it creates a branch and a pull request in [spec_repo] under your GitHub account.

STOP: Are the PRD and HLD ready to be read by people outside your team? If yes, run it; if not, come back later.

USER: Yes / not yet

[If yes, after they run it:] ACTION: Ask them to click **Sync GitHub PRs** on Artifacts, then read the PR state.

[Open → the `Push` chip is partial and Requirements Accept will wait. Their move: get a reviewer to merge it. Merged → done.]

## Important Notes for Claude

- `/pm-publish-specs` is a write skill: explicit yes first; the learner runs it.
- Epics JSON is the input to Requirements Accept; don't let them move on without having read it.
- Step ids: generate-epics-and-stories, publish-specs.

## Success Criteria

- [ ] `E&S` done; learner has read the stories and made at least one scope decision (even "keep all")
- [ ] Learner knows nothing reached Jira yet
- [ ] Spec repo: learner knows whether their team uses one; if so, the PR is open or merged and they know whose move it is

## Reference

Deeper notes and troubleshooting for this lesson: `REFERENCE.md` in this skill's folder. Read it when the learner asks for more depth or something goes wrong, and relay the relevant part in your own words.

## Wrap-up

ACTION: Silently add `2.6` to `completed` in the progress file and set `updated` to today (see the teaching rules). Don't narrate it.

Then close out in natural language, never as a list of commands:

- Only if it fits the moment, remind them they can ask for a recap or where they stand.
- End with the next step: when they're ready for the next lesson, start a new chat, then `/pm-workbench-course:start-2-7`.
