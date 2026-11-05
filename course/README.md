# PM Workbench Course

A hands-on course for product managers: set up PM Workbench, then take one objective through the whole
PM Journey, from a signal in an interview note to shipped work and a retro, with Claude as the guide.
Work on your own Jira and documents, or on the built-in demo team.

## Start

**Claude Code**
1. Clone the repository.
2. `cd course && claude`
3. Type `/start`

**Cowork**
1. Clone the repository (the workbench runs on your machine).
2. Install `releases/pm-workbench-course.plugin` in Cowork.
3. Share the repository folder and say "start the PM Workbench course" (or `/pm-workbench-course:start`).

## Tracks
- **A**: your Jira, starting from scratch
- **B**: your Jira, bringing existing PRDs and epics
- **D**: demo data (the fictional Acme Shop), no Jira needed

## Lessons

### Module 0: Start
- **`/start`** Welcome and choose a track

### Module 1: Setup (about an hour)
- **`/start-1-1`** Prerequisites and first run
- **`/start-1-2`** Configure: Jira connection and fields, workspace and skills, first pull, the tabs
- **`/start-1-3a`** Track A: portfolio context, objectives, a first signal
- **`/start-1-3b`** Track B: pull epics, bring PRDs into the workspace, read where each initiative stands

### Module 2: Lifecycle of an objective (take each lesson when your work reaches that phase)
- **`/start-2-1`** Define the objective and its key results
- **`/start-2-2`** Signals, ideas and evidence
- **`/start-2-3`** Discovery: from idea to PRD
- **`/start-2-4`** The PRD gate
- **`/start-2-5`** High-level design
- **`/start-2-6`** Epics, stories and publishing specs
- **`/start-2-7`** Requirements Accept and Ready
- **`/start-2-8`** Prioritize the backlog
- **`/start-2-9`** Run it week to week
- **`/start-2-10`** Close the loop: retro

### After the course
- **`/guide`** Ask what to do next on any objective, initiative or epic.

Each lesson has a `REFERENCE.md` with deeper notes and troubleshooting.

## How it's built

```
course-structure.json     modules, lessons, commands, which journey steps each lesson covers
lesson-modules/           SOURCE: one folder per lesson: CLAUDE.md (script) + REFERENCE.md
shared/teaching-rules.md  SOURCE: how Claude teaches every lesson
variants/                 SOURCE: per-platform rules (claude-code, cowork)
scripts/build.py          builds the outputs below
.claude/                  GENERATED: skills + rules for Claude Code
cowork-plugin/            GENERATED: the Cowork plugin, unpacked
releases/                 GENERATED: pm-workbench-course.plugin
```

Edit only the sources, then `python3 scripts/build.py` (`--check` verifies outputs are current).
Lesson scripts use `STOP:` (wait), `USER:` (expected reply), `ACTION:` (Claude does it) and `[bracketed]`
conditions; `{{cc: …}}` / `{{cowork: …}}` for platform differences and `{{cmd:start-2-1}}` for lesson commands.

The app's test suite checks that the lessons cover every journey step and name every step that writes outside
your machine. Progress is kept in `~/.pm-workbench-course/progress.json`; delete it to start over.
