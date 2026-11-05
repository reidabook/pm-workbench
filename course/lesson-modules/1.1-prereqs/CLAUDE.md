# Lesson 1.1: Prerequisites and first run

ACTION: Silently read the progress file for the track.

Let's get the app running. I'll check what's already installed so we only do what's missing.

ACTION: Check, without narrating each command: `python3 --version` (needs 3.9+), whether `claude` is on PATH, and whether `gh` is on PATH. Then check whether the server answers at `http://127.0.0.1:8765`.

[Report in one or two sentences: what's present, what's missing. Only walk through what's missing.]

---

## Python and Claude Code

[If Python is missing or older than 3.9: point them to python.org or their package manager. Wait.]

[If `claude` is missing: Claude Code is what runs the PM Journey skills and the AI buttons. Install it from claude.com/claude-code and sign in once by running `claude` in a terminal. The app works without it, but most of Module 2 won't.]

`gh` (the GitHub CLI) is optional. You only need it if your team keeps specs in a GitHub repository and you want the workbench to open pull requests there.

---

## A Jira token (tracks A and B)

[Track D: skip this section; say they can come back to it when they connect a real Jira.]

The workbench talks to Jira with your own token, so it can only see and change what you can.

- **Jira Cloud** (your Jira address ends in `atlassian.net`): create an API token at id.atlassian.com → Security → API tokens. You'll also enter your Atlassian email in Settings next lesson.
- **Jira Server or Data Center**: create a personal access token from your Jira profile.

The token goes in one file on your machine, `data/.env` in the repository, as a single line: `JIRA_API_TOKEN=<your token>`. That folder is never committed or shared.

STOP: Create the token and save it in `data/.env`. Don't paste it here. Tell me when it's saved.

USER: Done

[If `data/` doesn't exist yet: it's created on the first run; they can create the folder by hand.]

---

## Start the app

[Track A or B: {{cc: ACTION: Start `../run.sh` in the background.}}{{cowork: Ask them to run `./run.sh` in a terminal opened in the repository folder.}}]

[Track D: {{cc: ACTION: Start `../run.sh --demo` in the background.}}{{cowork: Ask them to run `./run.sh --demo` in a terminal opened in the repository folder.}} The demo seeds a fictional team the first time.]

The first run installs a few Python packages, so give it a minute.

ACTION: Wait until `http://127.0.0.1:8765` answers, then read `/api/setup/status`.

STOP: Open http://127.0.0.1:8765 in your browser. Tell me when it's up.

USER: It's open

[Read the setup checks and summarize: which are green, which are red. Don't fix the red ones yet; that's the next lesson. Track D: the Jira token check is red by design.]

## Important Notes for Claude

- Never ask for or echo the token. If they paste one by accident, tell them to revoke it and make a new one.
- The server must keep running between lessons. If it stops, they rerun the same command.
- First-run package install uses the Python that runs `run.sh`. If they prefer a virtualenv, they can create one and run `PYTHON=.venv/bin/python ./run.sh`.

## Success Criteria

- [ ] Python 3.9+ present; Claude Code installed and signed in (or the learner knows what they lose without it)
- [ ] Tracks A/B: token saved in `data/.env`, not in the chat
- [ ] The workbench answers at http://127.0.0.1:8765 and the learner has it open
