---
name: start-1-2
description: "PM Workbench course, lesson 1.2: Configure the workbench. Use when the user asks to start or continue lesson 1.2 of the PM Workbench course."
---

## Setup

Read `teaching-rules.md` in this skill's folder and follow it for everything below.

# Lesson 1.2: Configure the workbench

ACTION: Silently read the progress file for the track. Read `/api/setup/status` and the `config` part of `/api/state`.

Now we point the workbench at your Jira and create your PM workspace. Everything here lives on the **Settings** tab.

[Track D: skip to "Turn on Claude". The demo is already configured for a fictional Jira at acme.atlassian.net.]

---

## Connect Jira (tracks A and B)

On **Settings**, in *Install config*, fill in:

- **Jira base URL**: the address you open Jira at, e.g. `https://yourcompany.atlassian.net`.
- **Atlassian email**: Jira Cloud only. Leave it empty on Server / Data Center; that's how the workbench knows which login to use.
- **Jira project key**: the project your epics live in, e.g. `SHOP`.

Leave the rest for now and click **Save config**.

STOP: Save it, then tell me.

USER: Done

ACTION: Read `/api/setup/status` again.

[If "Jira token found" is still red: the token file wasn't found. Check the file is `data/.env` inside the repository and the line starts `JIRA_API_TOKEN=`. Restart the app after fixing.]

---

## Which epics, and which fields

By default the workbench pulls every epic in your project. Two optional settings narrow or enrich that:

- **Custom epic JQL**: if your team shares a project with others, a query like `project = SHOP AND component = Checkout AND issuetype = Epic ORDER BY Rank` keeps your view yours.
- **Jira field ids**: if your Jira has custom fields for acceptance criteria, outcome or story points, put their ids here (a small JSON object). Without them, acceptance criteria and outcome are written into the description instead. Nothing breaks.

STOP: Does your team share the Jira project with other teams?

USER: Yes / no

[If yes: help them write the JQL with a component, label or team filter. If they use an Advanced Roadmaps team field, the *Team lookup* on Settings finds the team id for them.]

[If they don't know their field ids: tell them to skip it for now; the reference explains how to find them.]

---

## Turn on Claude

[Track D: the demo starts with AI switched off so nothing runs by accident.] On Settings, *Claude* → **Mode**: `personal` uses your Claude Code login; `off` disables every AI button. Nothing calls Claude until you click, and every AI button shows the model and an estimated size first.

STOP: Set Mode to `personal` and save, unless you'd rather keep AI off for now.

USER: Done

---

## Create the workspace

[Track D: the demo workspace already exists, in the repository's `demo/workspace`. Skip to the tour.]

The **PM workspace** is the folder where every document for your initiatives lives: PRDs, research, designs, generated epics. Click **Create workspace** on the Setup card. It creates `~/pm-workspace` with its folders, a `portfolio-context.md` to fill in, and copies the 15 PM Journey skills into it.

STOP: Click it and tell me.

USER: Done

ACTION: Confirm the workspace exists and `.claude/skills/` inside it holds the `pm-*` skills.

[Say where it is as a clickable path.]

---

## First pull

[Tracks A and B] Click **Pull from Jira** at the top right. It's on every tab.

STOP: Pull, then tell me.

USER: Done

ACTION: Read state: how many epics came back, how many are in scope, and when the pull ran.

[Report it. If zero epics: the project key or JQL is off; check them. If an error: read `meta.last_sync_error` and explain it.]

---

## A tour, in order

The tabs follow the life of an objective, left to right:

- **Today**: what needs a decision or action this week.
- **Inbox**: signals in, ideas out.
- **Objectives**: what you're trying to achieve, and the key results that prove it.
- **Journey**: every initiative, step by step, and what's next.
- **Artifacts**: the PRDs and designs in your workspace.
- **Backlog**: scoring, ranking, and pushing priorities to Jira.
- **Retros**: did shipped work move the numbers?

The `?` in the header explains every term.

STOP: Click through the tabs once. Which one do you expect to live in?

USER: Answers

[Track D: point out that Today already has things on it: a failed PRD gate on Guest Checkout and an open blocker. That's what a real week looks like.]

## Important Notes for Claude

- The learner edits Settings themselves; don't PUT config for them.
- A wrong base URL usually shows as a connection error on pull; a wrong token as 401; a wrong project as zero epics or a JQL error.
- Track D: the demo config has `"demo": true`, so the app opens on Today even without a token.

## Success Criteria

- [ ] Tracks A/B: Jira URL, project (and email on Cloud) saved; token found; a pull returned epics
- [ ] Learner knows the custom JQL and field ids exist and whether they need them
- [ ] Claude mode chosen deliberately
- [ ] The workspace exists with the `pm-*` skills in it
- [ ] Learner has seen each tab and knows the order follows an objective's life

## Reference

Deeper notes and troubleshooting for this lesson: `REFERENCE.md` in this skill's folder. Read it when the learner asks for more depth or something goes wrong, and relay the relevant part in your own words.

## Wrap-up

ACTION: Silently add `1.2` to `completed` in the progress file and set `updated` to today (see the teaching rules). Don't narrate it.

Then close out in natural language, never as a list of commands:

- Only if it fits the moment, remind them they can ask for a recap or where they stand.
- End with the next step: the next lesson depends on their track. Track A: `/pm-workbench-course:start-1-3a`. Track B: `/pm-workbench-course:start-1-3b`. Track D: `/pm-workbench-course:start-2-1`. When they're ready, start a new chat, then that command.
