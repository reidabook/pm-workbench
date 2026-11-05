# PM Journey workspace conventions

Every `/pm-*` skill reads and writes files in the current directory (the PM workspace). PM Workbench scans
these exact paths and formats, so follow them precisely. Today's date is `<date>` (YYYY-MM-DD).

## Names
- **Initiative slug**: the initiative title in kebab-case, e.g. `faster-checkout`.
- **File stem**: the same words in snake_case, e.g. `faster_checkout`. Use it in every file name below.
- Jira keys look like `ACME-123`. Never invent a key: leave it empty until Jira returns one.

## Layout
| Path | Written by |
|---|---|
| `portfolio-context.md` | the PM (priority tiers, programs) — read it for context |
| `<slug>/pm-context.md`, `<slug>/refinement-plan.md` | pm-guide |
| `<slug>/checkpoints/<step>.md` | every step (see Checkpoint) |
| `research/<stem>_<date>.md` | research-synthesis, discovery |
| `competitive-research/<stem>_<date>.md` | discovery (optional) |
| `concept-accepts/<stem>_<date>.md` | concept-accept |
| `prds/<stem>_v1_<date>.md` | generate-prd |
| `risk-reviews/<stem>_<date>.md` | risk-review |
| `ux-briefs/<stem>_<date>.md` | ux-brief |
| `reviews/<prd file stem>_review.md` | review-prd (the report) |
| `refined-prds/<stem>_v<N>_refined_<date>.md` | review-prd (the improved PRD) |
| `prd-validations/<stem>_validation_<date>.md` | validate-prd |
| `generated-hlds/HLD_<stem>_v1_<date>.md` | generate-hld |
| `reviews/<stem>_hld_questions.md` | generate-hld (open questions) |
| `reviews/HLD_<stem>_v1_<date>_design_review.md` | validate-hld |
| `epics/<stem>_epics_<date>.json` | generate-epics-and-stories, requirements-accept |
| `jira-manifest.json` | PM Workbench (never edit by hand) |

## PRD format (prds/ and refined-prds/)
```markdown
---
title: "Faster Checkout"
type: prd
initiative: faster-checkout
bepic_key: ""          # parent initiative / business epic key, if any
---
# Faster Checkout

| Field | Value |
|---|---|
| **Epic Key** | |
| **Owner** | |
| **UX Required** | Yes / No |
| **Legal Required** | Yes / No |
| **HLD Ownership** | Product / Engineering |
| **Flag Intent** | Release toggle / Experiment / None |
| **Flag Name** | |
| **Spec Status** | Not published |
```
Sections: Problem · Users & jobs to be done · Evidence · Goals & success metrics (baseline → target) · Non-goals ·
Requirements (numbered, each testable) · UX notes · Risks & open questions · Rollout & backout · Dependencies.
The refined PRD keeps the **same title** as the original.

## Checkpoint (`<slug>/checkpoints/<step>.md`)
```markdown
---
checkpoint_version: 1
skill: <step id, e.g. review-prd>
updated_at: <ISO timestamp>
initiative:
  slug: <slug>
  tracker_ref: <epic key or empty>
gate:
  result: pass | fail | n/a
artifacts:
  - role: input
    path: "<absolute path of the input file>"
  - role: output
    path: "<absolute path of the output file>"
---
One paragraph: what was done, what is left, the next step.
```

## Definition of Ready (stories)
1. User story form: "As a <persona>, I want <capability>, so that <benefit>".
2. Acceptance criteria in Given / When / Then.
3. AC cover the five categories: Happy Path, Validations, Permissions, Edge Cases, Error Handling (or say why one does not apply).
4. Sized at 8 points or fewer.
5. No unresolved blocker or dependency.
6. No vague terms (fast, easy, intuitive, robust, seamless, user-friendly, as appropriate).
7. At least one AC traces to the epic's success metric.
