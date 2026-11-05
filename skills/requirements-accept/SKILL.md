---
name: pm-requirements-accept
description: Definition-of-Ready gate on every story, then create passing stories in Jira via PM Workbench.
argument-hint: "--epics <epics json> [--jira-project <KEY>] [--parent <key>]"
---

# Requirements Accept

Read `.claude/pm-conventions.md` first and follow its names, paths and formats exactly. Arguments: `$ARGUMENTS`.

1. Find the epics JSON (`--epics`, else the newest `epics/<stem>_epics_*.json`).
2. Check every story against the 7-point Definition of Ready. Fix what you can with the PM (rewrite AC,
   split stories). Set `dor_status` to `PASS` or `FAIL` and `dor_notes` to the failed points. Save the file.
3. Show a summary table and ask the PM to confirm creating the PASS stories in Jira.
4. Dry run first, then create (PM Workbench must be running; it holds the Jira credentials):
   ```sh
   curl -s -X POST http://127.0.0.1:8765/api/jira/publish-epics -H 'Content-Type: application/json' \
        -d '{"file": "<abs path to epics json>", "dry_run": true}'
   curl -s -X POST http://127.0.0.1:8765/api/jira/publish-epics -H 'Content-Type: application/json' \
        -d '{"file": "<abs path to epics json>"}'
   ```
   The workbench writes the new keys back into the JSON and into `jira-manifest.json`.
5. Report the created keys and the stories held back with their reasons.
Finish by writing the checkpoint `<slug>/checkpoints/requirements-accept.md` and telling the PM the next step.
