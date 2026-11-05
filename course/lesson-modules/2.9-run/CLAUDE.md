# Lesson 2.9: Run it week to week

ACTION: Silently read the progress file. Read state for Today: initiatives' next steps and gates, `log`, `okr` health and KR reading ages, epics with NEEDS INFO, drafts, retros pending, and `meta` freshness.

The tool only pays off if it's where your week starts. This lesson builds a 15-minute Monday routine around **Today**.

---

## Refresh first

Advice from stale data is worse than none. Today's *Freshness* card shows when Jira was pulled, the workspace scanned, and specs synced; anything older than a day is amber.

STOP: Refresh anything amber: **Pull from Jira**, **Rescan workspace**, and **Sync GitHub PRs** if you use a spec repo. Tell me when done.

USER: Done

---

## Read Today top to bottom

ACTION: Summarize each non-empty card in one line, in this order: next step per initiative, gates needing attention, story readiness, objectives at risk, blockers and risks, backlog hygiene, retros pending.

[Give the summary. Then name the single most important item and why.]

STOP: Of everything on Today, what's the one thing only you can unblock this week?

USER: Answers

---

## Key result readings

An objective with readings older than 14 days shows on *Objectives at risk*, because an unmeasured objective is invisible, not fine.

STOP: Record a fresh reading on your key result (the **+** next to it on Objectives), or click **Refresh key result values** if it comes from a metrics file.

USER: Done

ACTION: Read the KR: new current value, progress, health.

---

## The log

Every initiative and epic drawer has **Decisions · Risks · Blockers**. Three kinds, three uses:

- a **decision** keeps the *why* for later ("launch at 10% for a week");
- a **risk** has an owner and a date to check;
- a **blocker** has an owner and shows on Today until closed.

Decisions are the ones people skip and regret: six months later nobody remembers why.

STOP: Add one entry of each kind you actually have this week, with an owner. Tell me when done.

USER: Done

ACTION: Read `log` for the initiative.

---

## The weekly status

**Weekly status .md** on Today writes your status update from the state you just refreshed: objectives with health and KR movement, initiatives and their next step, open blockers and risks, recent decisions, story readiness, finished retros. **Journey readiness .md** is the same for initiatives only.

STOP: Generate it and read it as if you were your manager. What would you edit before sending?

USER: Answers

[Whatever they'd edit is usually missing data: a stale reading, an unlogged decision. Fix it at the source and regenerate, rather than editing the text.]

## Important Notes for Claude

- Don't produce the status report yourself; the button is the habit being taught.
- Suggest a calendar slot: Monday, 15 minutes: refresh → Today → readings → log → status.

## Success Criteria

- [ ] Learner refreshes before reading
- [ ] Learner can read every Today card and name the week's one unblock
- [ ] A fresh KR reading recorded
- [ ] Log entries exist with owners; learner knows why decisions get logged
- [ ] Weekly status generated; fixes made at the source
