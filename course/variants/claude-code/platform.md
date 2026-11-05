## Platform: Claude Code

You are running in Claude Code on the learner's machine, in the `course/` folder of the pm-workbench
repository. The app is the parent folder (`..`).

- **Starting the workbench:** run `../run.sh` (or `../run.sh --demo` on track D) as a background command,
  then confirm `http://127.0.0.1:8765` answers. On Windows they run `..\run.ps1` themselves. Offer to open
  the page in their browser.
- **Reading state** (summarize; never dump raw JSON):
  - `curl -s http://127.0.0.1:8765/api/setup/status`: the Setup card checks.
  - `curl -s http://127.0.0.1:8765/api/state`: nearly everything the tabs show: `themes` (objectives: rank,
    parent key, objective sentence), `okr` (progress, health, key results), `epics` (score inputs, score, rank,
    priority, `dor`), `committed`, `drafts`, `sources`, `ideas`, `groups`, `evidence`, `prds` (stage, validation
    result, PR state, linked epics), `artifacts`, `initiatives` (each with `steps`, `ready`, `next`), `retros`,
    `log`, `config`, `meta` (when the Jira pull, workspace scan and GitHub sync last ran).
  - Detail: `/api/epics/<key>/dor`, `/api/retros/<key>`, `/api/prds/<id>/text`, `/api/artifacts/<id>/text`.
  - Files the skills wrote can be read straight from the workspace (`config.pr_workspace`, default `~/pm-workspace`).
  - If the server is down, read the workspace folders directly and say the app isn't running.
- **Read only through the API.** Never POST, PUT or DELETE to change their data; they change things in the UI
  so they learn where things are.
- **PM Journey skills** run in a separate session: the workbench's buttons, or
  `cd <workspace> && claude "/pm-<step> …"` in another terminal.
- **Progress file:** `~/.pm-workbench-course/progress.json` (create the folder if needed). Notes:
  `~/.pm-workbench-course/notes.md`.
- **Files to open:** give the path as a clickable markdown link.
- **Structured choices:** use AskUserQuestion, at most four options.
- **Between lessons:** suggest `/clear`, then the next command.
