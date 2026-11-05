---
name: start-2-7
description: "PM Workbench course, lesson 2.7: Requirements Accept and Ready. Use when the user asks to start or continue lesson 2.7 of the PM Workbench course."
---

## Setup

Read `teaching-rules.md` in this skill's folder and follow it for everything below.

# Lesson 2.7: Requirements Accept and Ready

ACTION: Silently read the progress file. Read the initiative's steps, `ready`, the epics JSON (stories and `dor_status`), and whether a Jira token is configured.

This is the last gate, and the only one that writes to Jira. Stories that pass it are clear enough that an engineer could start on them without a meeting. That's the bar.

---

## The Definition of Ready

Every story is checked on seven points:

1. **Story form**: "As a [persona], I want [capability], so that [benefit]."
2. **Given / When / Then** acceptance criteria.
3. The criteria cover five categories: **happy path, validations, permissions, edge cases, error handling** (or say why one doesn't apply).
4. **8 points or fewer.**
5. **No unresolved blocker** or dependency.
6. **No vague words**: fast, easy, intuitive, robust, seamless, user-friendly.
7. At least one criterion **traces to the epic's success metric.**

Point 7 is the one teams skip, and it's the one that makes the retro meaningful later.

STOP: Which of the seven do your team's stories most often miss today?

USER: Answers

---

## Run it

`/pm-requirements-accept` goes through the epics JSON story by story, fixes what it can with you (rewrites criteria, splits stories), and marks each **PASS** or **FAIL**. Then it asks the workbench to create the PASS stories in Jira, dry run first. Your Jira token stays in the workbench; the skill never sees it.

[Track D: there's no Jira behind the demo, so the create step will fail with "no Jira token". Run it to see the DoR check and the dry run; the faster-checkout row shows what done looks like.]

[Tracks A/B:] This creates real epics (if they don't exist yet) and stories in **[jira_project]**, under your name. Stories that fail stay out.

STOP: Are you ready for these stories to appear in Jira? If yes, run **Run requirements-accept** from the drawer (or **Next**). Confirm the dry run before it creates anything.

USER: Yes / not yet

[If not yet: fine. The DoR part is still worth running; they can stop before the create.]

STOP: Tell me when it's finished, and rescan.

USER: Done

ACTION: Read the epics JSON (`dor_status` per story, new `jira_key`s), `jira-manifest.json`, and the initiative's `RA` status and `ready`.

[Report: how many passed and were created (with keys), how many held back and why. If FAIL stories remain: each one needs a decision: fix and re-run, or drop from the release.]

---

## Ready

**Ready** = PRD gate PASS + specs merged (only if you use a spec repo) + Requirements Accept done. The badge shows on Journey, and Today stops nagging about this initiative. Engineering can pull stories.

[If ready: say so plainly. It's a milestone; most initiatives never get a clean one.]

[If not: name the condition that's outstanding and whose move it is.]

---

## The quick check

On **Backlog**, any epic's drawer has **Check stories in Jira**: a fast, heuristic version of the same seven points on stories already in Jira, including ones written by hand. It flags; it doesn't certify. Use it on old epics before planning.

## Important Notes for Claude

- `/pm-requirements-accept` is a write skill (Jira issues). Explicit yes first; the learner runs it.
- The skill calls `POST /api/jira/publish-epics` with `dry_run` first. If the app isn't running, the create fails safely.
- Epics already holding a `jira_key` are not re-created; only PASS stories without a key are.
- Step id: requirements-accept.

## Success Criteria

- [ ] Learner can name the seven DoR points and why point 7 matters
- [ ] Requirements Accept run; every FAIL story has a decision
- [ ] Tracks A/B: PASS stories exist in Jira (or the learner chose to stop at the dry run)
- [ ] Learner can say whether the initiative is Ready and, if not, what's outstanding
- [ ] Learner knows the heuristic check exists for stories written elsewhere

## Reference

Deeper notes and troubleshooting for this lesson: `REFERENCE.md` in this skill's folder. Read it when the learner asks for more depth or something goes wrong, and relay the relevant part in your own words.

## Wrap-up

ACTION: Silently add `2.7` to `completed` in the progress file and set `updated` to today (see the teaching rules). Don't narrate it.

Then close out in natural language, never as a list of commands:

- Only if it fits the moment, remind them they can ask for a recap or where they stand.
- End with the next step: when they're ready for the next lesson, start a new chat, then `/pm-workbench-course:start-2-8`.
