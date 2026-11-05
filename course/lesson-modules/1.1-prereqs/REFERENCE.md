# 1.1 Reference: prerequisites

| Need | Why | Check |
|---|---|---|
| Python 3.9+ | runs the app | `python3 --version` |
| Claude Code | PM Journey skills, AI buttons | `claude --version` |
| Jira token (A/B) | pull epics, push priorities, create stories | Setup card: "Jira token found" |
| `gh` (optional) | spec repo pull requests | `gh auth status` |

## Where the token can live (first found wins)
1. `JIRA_API_TOKEN` or `JIRA_PAT` environment variable
2. `data/.env` (`JIRA_API_TOKEN=…`)
3. A file named in Settings → *Jira token file*
4. macOS Keychain item `pm-workbench-jira`

## Troubleshooting
- **Port in use**: `PORT=8770 ./run.sh`, then use that port (the course assumes 8765).
- **`pip` install fails**: install the packages in `requirements.txt` yourself, or use a virtualenv.
- **Page loads but is empty**: hard-refresh; check the terminal running the server for an error.
- **Demo data looks stale**: delete `demo/` and run `./run.sh --demo` again to reseed.
