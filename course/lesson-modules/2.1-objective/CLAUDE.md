# Lesson 2.1: Define the objective and its key results

ACTION: Silently read the progress file (track, objective). Read `themes`, `okr` and `periods` from state.

Module 2 follows one objective through its whole life. Everything later (which ideas matter, what the PRD is for, how the backlog is ranked, whether the retro says "hit") traces back to what we write here.

[Track D: the demo has three objectives. Use **Merchant insights**: it's unmeasured, which is exactly what this lesson fixes.]

STOP: [Tracks A/B: list their objectives by rank.] Which one do you want to take through the course? Pick one you're actually working on this quarter.

USER: Names one

ACTION: Save `objective` in the progress file.

---

## The objective sentence

An objective is an outcome, not a project. "Launch weekly digest" is a project. "Merchants grow with their own data" is an outcome: it would still be true if the digest turned out to be the wrong idea.

On **Objectives**, click the objective line (or **Edit**) to write it. **Write objective with AI** drafts one from the theme and its epics if you want a starting point.

STOP: Write the sentence. One line, starts with a verb, no numbers yet. Tell me when it's saved.

USER: Done

ACTION: Read it back.

[If it names a feature, or contains a metric: push back once, kindly. The numbers belong in key results.]

---

## Rank and parent

Objectives are ranked, 1 is highest. The rank feeds the backlog score of every epic under it, so moving an objective up literally re-ranks the work. Use the arrows.

If your Jira has a parent issue above epics (an initiative or business epic), add its key in **Edit**. [Track D: Merchant insights already points to INIT-12.]

STOP: Is the rank right relative to the others? Adjust if not.

USER: Done / it's right

---

## A key result

A key result is how you'll know the objective is happening: a metric, its **baseline** today, a **target**, and a direction. Without a baseline, nobody can say later whether you moved it.

Expand the objective (**Show key results / epics**) and add one with **+ Key result**. If you've set up a metrics file, pick a metric from it; otherwise choose *manual* and record readings yourself. **Suggest key results** proposes a few from the epics.

STOP: Add one key result with a real baseline and target. What metric did you pick, and where does the baseline come from?

USER: Answers

ACTION: Read the KR from `okr`: title, baseline, target, direction, current.

[The form warns on target equal to baseline, a direction that contradicts the target, or a title with no number. Mention any warning it showed.]

[If they don't know the baseline: that's a real finding. Log it: they can add the KR with their best estimate and note "baseline to confirm", or come back once they've pulled the number.]

---

## How progress and health are calculated

- **Progress** = how far current has moved from baseline toward target.
- **Health** compares progress to how much of the quarter has passed: *ahead*, *on track* (within 15 points), or *behind*.
- Next to it, the **Delivery** strip shows epics closed / in dev / to do. Delivery is the leading signal; the key result is the lagging one. A team can be 100% delivered and 0% on outcome. That gap is the most useful thing on this tab.

STOP: Looking at your objective now, is it measured, and is it the right period?

USER: Answers

## Important Notes for Claude

- Don't create the KR for them; the form's lint is part of the lesson.
- Objective-level KRs (on the objective) override the epic mean for progress; epic KRs roll up otherwise.
- Writing KRs to Jira's Outcome field (*Write to Jira Outcome*) is a Jira write; not part of this lesson.

## Success Criteria

- [ ] One objective chosen and saved to progress
- [ ] Outcome sentence: a verb, no metric, survives a change of solution
- [ ] Rank deliberately set; parent key set if their Jira has one
- [ ] At least one key result with baseline, target, direction
- [ ] Learner can explain progress, health, and why delivery and outcome are shown side by side
