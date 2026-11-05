---
name: pm-generate-epics-and-stories
description: Break a validated PRD into right-sized epics and stories (JSON, no Jira writes).
argument-hint: "--prd <prd> [--parent <key>]"
---

# Generate epics & stories

Read `.claude/pm-conventions.md` first and follow its names, paths and formats exactly. Arguments: `$ARGUMENTS`.

1. Read the PRD (and HLD if any).
2. Split into epics (one outcome each) and stories that meet the Definition of Ready in the conventions.
   Right-sizing gate: split any story above 8 points. Add the labels `UX::Required` / `Legal::Required`
   to stories when the PRD says so.
3. Write `epics/<stem>_epics_<date>.json`:
   ```json
   {"initiative": "<slug>", "prd": "<abs path>", "parent": "<--parent or empty>",
    "epics": [{"title": "", "description": "", "outcome": "", "acceptance_criteria": "", "labels": [], "jira_key": null,
               "stories": [{"title": "", "story": "As a ..., I want ..., so that ...", "acceptance_criteria": ["Given ... When ... Then ..."],
                            "points": 3, "labels": [], "dor_status": "PENDING", "dor_notes": "", "jira_key": null}]}]}
   ```
4. Show the PM a table of epics / stories / points. Nothing goes to Jira in this step.
Finish by writing the checkpoint `<slug>/checkpoints/generate-epics-and-stories.md` and telling the PM the next step.
