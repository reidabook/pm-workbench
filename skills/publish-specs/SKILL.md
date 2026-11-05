---
name: pm-publish-specs
description: Open one pull request with the PRD (and HLD) in the team's spec repo.
argument-hint: "--file <prd> [--file <hld>] [--parent <key>]"
---

# Publish specs

Read `.claude/pm-conventions.md` first and follow its names, paths and formats exactly. Arguments: `$ARGUMENTS`.

1. Read `spec_repo` and `spec_path` from the PM Workbench config (`curl -s http://127.0.0.1:8765/api/config`,
   or ask the PM). If there is no spec repo, say the step is optional and stop.
2. Show the PM what will be published and ask to confirm.
3. With `gh`, clone or update the repo, create branch `spec/<slug>`, copy the files to
   `<spec_path>/<slug>/prd.md` and `<spec_path>/<slug>/hld.md`, commit, push and open one PR.
4. Add `spec_pr_url: <PR url>` to the frontmatter of the local PRD and HLD and set the PRD row
   `Spec Status` to `In review`. PM Workbench marks the step done once the PR is merged.
Finish by writing the checkpoint `<slug>/checkpoints/publish-specs.md` and telling the PM the next step.
