# PM Workbench reference

Tab-by-tab detail. Start with the [README](../README.md).

## Tabs
Tab order follows the journey: Today · Inbox · Objectives · Journey · Artifacts · Backlog · Retros · Settings.
The `?` button in the header opens a glossary of the PM Journey terms used in the app (Parent / BEpic, Parent Key,
Objective/theme, Initiative, PRD gate, HLD verdicts, publish-specs, Requirements Accept, Ready, DoR heuristics vs
authoritative gate, Toggle Status / Backout Strategy, UX::Required / Legal::Required).
- **Today** — the home tab once setup is complete. Cards built from the current state, each linking to its tab
  or drawer: *Next step per initiative* (grouped by skill, one-click run), *Gates needing attention*
  (validate-prd FAIL, validate-hld BLOCKED / manual review, spec PR open but unmerged, UX brief required
  but missing), *Story readiness* (sum of cached DoR checks + epics past the PRD gate never checked), *Objectives
  at risk* (health `behind`, KRs without baseline/target or with readings older than 14 days), *Open blockers &
  risks* (from the log), *Backlog hygiene* (NEEDS INFO, drafts), *Retros pending*, *Freshness* (Jira pull,
  workspace scan, GitHub sync — amber when older than a day). Header buttons export the weekly status and journey
  readiness reports as Markdown.
- **Backlog** — the matrix. Inline Theme / SV / UI / Urg / Conf / Effort / Park / Raise-to-P1 /
  Notes; live Score, Rank, P1–P4, NEEDS INFO. "Jira: Px" shows where computed ≠ Jira.
  *Pull from Jira* (header), *Push to Jira…* (dry-run diff → tick changes → Apply; rank is global),
  *Export xlsx* (legacy layout, values only). Drafts (not yet in Jira) appear with a purple badge.
- **Objectives** (tab id `themes`) — ranked list of Objectives (themes; imported from portfolio-context
  Priority Tiers or created here), 1 = highest. ↑↓ re-scores every epic in the theme. Optional parent key per
  theme; many themes may share a parent. Expanding an objective lists its **initiatives** (journey chips, Ready
  badge, next skill; click → initiative drawer) above its epics and key results. An initiative belongs to the
  objective of its linked epics, or failing that to the objective sharing its parent.
  *New objective* has three tabs: **Manual** (name, description, parent key), **Import from parent issue** (type a
  parent key, e.g. `INIT-42`; its Jira title and description prefill the form) and **Propose with AI** (Haiku reads the
  in-scope epics that have no theme, grouped by parent, and proposes at most one objective per parent no
  objective uses yet, plus epics to add to existing objectives; tick, edit, *Create selected*; nothing is
  saved before that). Import and AI also assign the epics that have no theme; an existing theme is never
  overwritten.
- **Journey** — one row per initiative (= PM workspace slug), with a chip per PM
  Journey step using short codes (legend under the header): **Step 0** `G` pm-guide · **Step 1** `RS`
  research synthesis, `CA` Concept Accept, `PRD`, `RR` risk review, `UX` brief · **1a** `POC` · **Step 2**
  `Rev` review-prd, `Val` validate-prd (PRD gate), `HLD`, `vHLD` validate-hld, `E&S` epics & stories, `Push`
  publish specs · **Step 3** `RA` Requirements Accept. Statuses: done / partial / failed / skipped (with
  reason) / optional / missing. Columns also show the initiative's Objective, *Stories ready* (sum of cached
  per-epic DoR checks, stale badge after 7 days), Owner / target period (filters), and a `30 d+` badge when
  the workspace has not changed in a month. **Ready** = validate-prd PASS + spec PR merged (when `spec_repo` is set) + Requirements Accept done, i.e.
  engineering can pull stories. *Next* launches the first outstanding gate skill with the right file
  arguments. The drawer shows the evidence file for every step, lets you run or skip a step, record
  the POC URL, set owner and target period, log decisions / risks / blockers, export a one-pager,
  link a mis-matched artifact, and run a per-epic **DoR** check. Initiatives are
  detected from checkpoints (`<slug>/checkpoints/*.md`), validation reports, frontmatter and file
  names; PRD metadata rows (`UX Required`, `Legal Review Required`, `HLD Ownership`, `Flag Intent`)
  drive which steps are required.
- **Inbox** — upload `.md/.txt/.docx`, paste, or *Add from Jira* (story / defect keys or links; pulls
  summary, description, acceptance criteria, comments; re-adding a key refreshes it). *View* shows a source's content. *Extract ideas* (Haiku) splits a source into ideas.
  *Cluster unthemed* (Haiku) assigns themes / proposes new ones. Select ideas → *Group*. A group
  → *Generate PRD* (skill) or *Draft epic* (form; *Draft with AI* prefills it).
- **Artifacts: PRDs & HLDs** (tab id `prds`) — every PRD found in `<pr_workspace>/prds`, `refined-prds` and `prd_dirs`, with
  stage drafted → reviewed → validated PASS/FAIL → in-pr → published, plus the initiative's **HLD**
  (generate-hld) and its validate-hld verdict. Buttons: Review / Validate / Epics & stories.
  A PRD that review-prd has refined shows as **one row**: the newest file in `refined-prds/` is the
  primary document, with links to the original and any earlier refined versions.
  Under the stage, each PRD shows **Reviewed** / **Validated** with when and how many runs. After you
  launch a skill the app rescans the workspace every 10 s until its report appears (up to 2 h), so the
  row updates by itself; re-run a skill as often as you like.
  Link epics by key. Free-text **Note** per PRD (e.g. `Planned: Pod 2`).
  *Sync GitHub PRs* reads the optional spec repo (`spec_repo`) via `gh`: PRs by `github_pr_authors`
  plus pinned `github_prs`. Each `prd.md` in a PR gets a **file ↗** link (blob at the PR head, or
  `main` once merged) and a **PR #n (open/closed/merged) ↗** link, attached to the matching local
  PRD by normalised title, or stored as a GitHub-only row when there is no local copy. Epic keys in
  the path and metadata are linked to epics. `in-pr` = in an unmerged PR; `published` = merged.
- **Settings** — Setup card (prerequisite checks, team lookup, portfolio-context import), config,
  scoring weights/bands, Claude mode, JSON export/import, legacy xlsx import, AI run log.

## Story readiness (Definition of Ready)
Backlog column **Stories ready** and the epic drawer run heuristic checks against the 7-point
DoR on the epic's stories (fetched from Jira on demand, cached): AC in the *Acceptance Criteria*
field as Given/When/Then across Happy Path / Validations / Permissions / Edge Cases / Error
Handling; role-qualified persona; Fibonacci points ≤ 8; priority; no vague terms; no blockers; no
TODO/TBD. Epic conventions: parent issue, Toggle Status When Deployed, Backout Strategy, In Dev,
`UX::Required` / `Legal::Required` labels when the PRD says so. The authoritative gate remains
`/pm-requirements-accept`; stories it published are marked as such.

## OKR board (Objectives tab)
Themes are **Objectives**: click the objective line to write it, or *Rewrite as Objective* (Haiku).
Epics carry **Key Results** (metric, baseline → current → target, direction, unit, owner, due). Manual KRs
require a baseline and a target; the form lints definitions inline (target = baseline, direction contradicts
target, title with no number / % / unit) and the API returns the same `warnings` without blocking. Owner and
due are workbench-only — the Jira Outcome block is unchanged. Add them from the
epic drawer or the expanded theme (`+ KR`, *Suggest KRs* proposes KRs bound to real metric keys).
- **Period**: quarters (`okr_periods`, Settings). KRs belong to a period; themes persist.
- **Sources**: `manual` (record readings with `+`), `baselines_jsonl`
  (`<analytics_dir>/metrics-history.jsonl`: one JSON row per date, e.g. `{"date": "2026-10-01",
  "checkout_completion": 63.1}`, so readings "as of" a date work), `data_js` (dotted path into
  `<analytics_dir>/metrics.json`, e.g. `usage.weekly_active_users`). *Refresh KR values* pulls the latest
  and snapshots when the source date is newer. Set `analytics_dir` in config.
- **Objective-level KRs**: `+ Key result` in an expanded objective creates a KR with `theme_id` and no
  `epic_key`. When an objective has any, its progress is the mean of those (lagging outcome) and the epic
  mean is still shown alongside; otherwise progress is the epic mean. Each objective also shows a
  **Delivery** strip (leading indicator: epics Closed / In Dev / To Do + Ready initiatives) next to the
  outcome percentage.
- **Math**: KR = clamp((current−baseline)/(target−baseline)); epic = mean of KRs; theme = mean of objective
  KRs if any, else mean of measured epics (unmeasured shown, not counted). Health vs time elapsed in the quarter:
  ahead / on track (±15 pts) / behind; "unmeasured" when there is no KR reading (even if recently closed);
  closed < 90 days with a reading = "released · measuring".
- **Jira**: *Sync KRs to Jira* writes a block into the epic's **Outcome** field between
  `h3. Key Results` and `_(managed by PM Workbench)_`, keeping other text. Pull parses the block back
  into an install that has no KRs for that epic, so teammates see each other's KRs.

## Decision / risk / blocker log
Every initiative drawer (ref = slug) and epic drawer (ref = epic key) has a **Decisions · Risks · Blockers**
section: add an entry (kind, text, owner, optional due date), close / reopen, delete. Open entries plus
anything closed in the last 30 days come back in `/api/state` as `log`. Open blockers and risks appear on
**Today** and in the weekly status report; decisions keep the "why" for later. Table `log_entries`;
routes `POST /api/log`, `PUT /api/log/{id}`, `DELETE /api/log/{id}`; helpers in `app/worklog.py`.
The free-text initiative *Notes* field remains for everything else.

## Markdown reports
Built client-side from the data on screen; modal with **Copy** and **Download .md**.
- **Weekly status** (Today header) — objectives with health and KR movement, initiatives with Ready / next
  step, open blockers and risks, recent decisions, DoR summary, retros completed in the last 7 days.
- **Journey readiness** (Today and Journey headers) — initiatives × parent issue, objective, Ready, blocking step,
  next skill.
- **Initiative one-pager** (initiative drawer) — PRD stage and gate result, HLD and verdict, epics with story
  readiness, key results, POC URL, decisions / risks / blockers, journey steps, notes.

## Staleness and busy states
`stale(iso, days)` drives amber badges: DoR check older than 7 days (Backlog *Stories ready*, epic drawer,
Journey), workspace scan / GitHub sync / Jira pull older than 1 day (Journey and Artifacts headers, Today
*Freshness*, header sync label), initiative unchanged for 30 days (Journey row). Long-running buttons (Pull
from Jira, Rescan workspace, Sync GitHub PRs, DoR checks, portfolio import, KR refresh) disable themselves
while running. The 60-second auto-refresh pauses while a drawer/modal is open or an input has focus;
`Esc` closes any drawer or modal.

## Retros tab
A retro opens automatically when an epic reaches **Closed** (detected on pull). *Backfill closed
epics* opens one for every already-closed epic. Resolutions Won't Do / Duplicate / Cancelled are
pre-flagged (red) so you can **Omit** them with a reason; omitted retros can be restored.
*Open retro* fetches once from Jira: lifecycle (created → first In Dev → Closed, days in analysis vs
development, status changes, reopens, PO, assignee), scope (child stories, resolved, added after dev
start, story points, team), then shows each KR at release / +30 / +60 / +90 days, and any
**context metrics** (comma-separated `baselines_jsonl` keys) 30 days before vs after release.
Fill in what shipped, impact, learnings and a verdict (hit / partial / miss / too early); *Draft retro
summary* (Haiku) prefills them from the facts. *Save & mark done* closes the retro.

## Validation evidence
Every idea, group, draft epic and Jira epic can carry **evidence**: where the signal came from.
Types: usage data / analytics, customer feedback, prospect feedback, support tickets / defects,
competitor does it, internal ask. Add it from the Inbox (idea or group), the draft form, or the epic
drawer. A source's signal type (set when you upload, or later on the source) makes that source
evidence for every idea taken from it, whether extracted by AI or added by hand; changing the type
re-types those entries. A group shows its own evidence plus its ideas'; click the chips to see the
list and which source each entry came from. Evidence follows the work: idea → group → draft → Jira epic (rendered as an
`h3. Validation` block in the description) and into the PRD bundle handed to `generate-prd`.

**Validation score (1–5)** per epic: 1 with no evidence; each distinct type adds its points
(defaults: data 2, customer 1.5, prospect 1, support 1, competitor 0.5, internal 0.5); repeats add
+0.25 each up to +0.5; ceiling 5; **competitor-only is capped at 1.5**. Override per epic in the
drawer. It is the sixth weight in the matrix (`Weight: Validation`), **default 0** so existing
priorities don't shift until you rebalance in Settings (suggested: SV .25, UI .20, Urgency .15,
Theme .15, Confidence .10, Validation .15). The six weights must sum to 1.0.

## Epic creation (two-step)
Draft locally → score it → *Create in Jira…*. Mandatory: Summary, Acceptance Criteria, Outcome
(and Product Owner when `jira_fields.product_owner` is set). Acceptance criteria and outcome go to their
custom fields when configured, otherwise into the description. Also sets the parent from the theme's
parent key, labels (+`default_labels`) and team (when configured). Fields Jira rejects are dropped and
reported. Priority is written on the next Push once scored.
An unvalidated PRD only warns.

## Scoring
`Score = (0.30·SV + 0.25·UI + 0.15·Urg + 0.15·Theme + 0.15·Conf) / Effort(S=1,M=2,L=3)`;
`ThemeScore = 5 − 4·(rank−1)/(max−1)`; rank desc, ties share the min rank; bands by rank
quantile 15% / 40% / 70%; parked rows excluded and pinned; Raise-to-P1 forces P1.
