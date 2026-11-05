# Lesson 2.4: The PRD gate

ACTION: Silently read the progress file for the initiative. Read its steps, its PRDs (stage, validation result) and whether a refined PRD exists.

[Track D: use **guest-checkout**. Its PRD was reviewed and failed validation, so we start at "If it fails".]

[If validate-prd already shows PASS: say so, check they've read the gate's decisions (see "If it passes"), and offer to move on.]

A drafted PRD goes through two steps before anyone designs or builds from it: a **review** that improves it, and a **validation** that decides whether it's ready. The second is a real gate. Most PRDs that bounce back from engineering would have failed it.

STOP: We're on [initiative], PRD at stage [stage]. Ready to review it?

USER: Yes

---

## Review

`/pm-review-prd` reads the PRD as a skeptical engineering lead, designer and executive would. It writes a review report, asks you the blocking questions, then writes a **refined PRD** into `refined-prds/` with the same title.

From now on the refined copy is the one every later step uses; the workbench passes it automatically.

On **Artifacts**, click **Review** on the PRD (or **Next** on its Journey row).

STOP: Run it. Answer its questions properly: this is where vague requirements get caught cheaply. Rescan when done.

USER: Done

ACTION: Read the `Rev` status and whether a refined PRD is detected.

STOP: What changed most between your draft and the refined version?

USER: Answers

---

## The gate

`/pm-validate-prd` checks the refined PRD against a definition of ready for requirements:

- problem and users stated, evidence cited,
- every goal has a metric, baseline and target,
- every requirement is testable,
- non-goals, risks, rollout and backout present,
- the UX, Legal and HLD-ownership decisions made,
- no open blocking question.

It returns **PASS** or **FAIL** in a report in `prd-validations/`. It only writes local files.

STOP: Run **Validate** on the PRD from Artifacts. Rescan when done.

USER: Done

ACTION: Read validate-prd status, the PRD stage, and the metadata rows.

[Say the result plainly, then take the matching section.]

---

## If it passes

Your `Val` chip is done and the PRD's stage is **validated**. Now read the three decisions the PRD carries:

[UX Required = Yes and no brief: "UX is required. Your `UX` chip is now required and missing; run the brief before or alongside design."]

[HLD Ownership = Engineering: "Engineering owns the design, so `HLD` and `vHLD` show skipped. You can skip lesson 2.5."]

[Legal Required = Yes: "Bring your legal partner in now. Stories will carry a `Legal::Required` label."]

STOP: Do any of those decisions surprise you?

USER: Answers

---

## If it fails

A FAIL isn't a verdict on the idea. It means the document doesn't yet give engineering enough to build from. It also shows on **Today** under *Gates needing attention*.

ACTION: Read the validation report (the evidence under Validate PRD in the initiative drawer) and list the failed checks in plain words, one line each.

Sort them into two piles:

- **Fix in the document now**: edit the refined PRD, or re-run review, then validate again.
- **Need to find something out**: real discovery work. Log it as a **Blocker** in the initiative drawer so it shows on Today and in your status report.

Re-validating is normal. Most PRDs take two goes.

STOP: Fix and re-validate now, or log what's outstanding and come back?

USER: Answers

[If they come back later with a PASS, do "If it passes" then.]

## Important Notes for Claude

- Validation is local (no PR, no Jira). Publishing specs is a separate, optional step in lesson 2.6.
- PASS is detected from the `| Gate Result | **PASS** |` row. A report without it shows as missing.
- The lesson is complete on PASS, or on FAIL when the learner understands each failure and has a plan.
- PRD stages: drafted → reviewed → validated → in-pr → published.
- Step ids: review-prd, validate-prd.

## Success Criteria

- [ ] `Rev` done and a refined PRD exists
- [ ] Learner can name what the gate checks
- [ ] `Val` PASS, or FAIL with every failure understood and a plan (blockers logged)
- [ ] Learner has read the UX, Legal and HLD decisions and knows what each changes
