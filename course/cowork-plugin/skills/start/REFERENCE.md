# 0.1 Reference: welcome

## What the workbench is
| Piece | Where it lives | Source of truth for |
|---|---|---|
| Jira | your Jira (Cloud or Server) | epics, stories, status, priority, rank |
| PM workspace | `~/pm-workspace` (markdown + JSON files) | PRDs, research, designs, epics drafts, checkpoints |
| Workbench database | `<repo>/data/workbench.db` (local) | objectives, scores, key results, ideas, evidence, log, retros |
| Skills | `<repo>/skills/`, copied to `<workspace>/.claude/skills/` | how each journey step is done |

## Tracks
| Track | Needs | Module 1 lessons |
|---|---|---|
| A | Jira project + token | 1.1, 1.2, 1.3a |
| B | Jira project + token, existing epics / PRDs | 1.1, 1.2, 1.3b |
| D | nothing beyond Python | 1.1, 1.2 (then straight to 2.1) |

## Starting over
Delete the progress file (`~/.pm-workbench-course/progress.json` in Claude Code) and run the start lesson again.
