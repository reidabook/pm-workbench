"""All Claude usage goes through here. Nothing here runs unless a POST route calls it.

* run_haiku(): `claude -p` with no tools, JSON out, for extract / cluster / draft.
* launch_skill(): opens a terminal at the PM workspace with an interactive `claude "/pm-<step> ..."`
  command. The step skills ship in skills/ and are copied into <workspace>/.claude/skills/ before each launch.
* Mode: personal (default, your Claude Code login) | off (every AI button disabled).
"""
import datetime as dt
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from . import db
from .paths import PR_WORKSPACE_DEFAULT, SKILLS_DIR

TODAY = lambda: dt.date.today().isoformat()  # noqa: E731


def est_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _env(cfg) -> dict:
    return dict(os.environ)


def runs_today(con) -> int:
    return con.execute("SELECT COUNT(*) FROM ai_runs WHERE started LIKE ?", (TODAY() + "%",)).fetchone()[0]


def check_allowed(cfg, con):
    if cfg.get("claude_mode", "personal") == "off":
        raise RuntimeError("AI is turned off in Settings")
    if not shutil.which("claude"):
        raise RuntimeError("`claude` CLI not found on PATH")


def preview(cfg, kind: str, prompt: str) -> dict:
    return {"kind": kind, "model": cfg.get("haiku_model", "claude-haiku-4-5"),
            "account": cfg.get("claude_mode", "personal"), "est_input_tokens": est_tokens(prompt)}


def run_haiku(cfg, kind: str, prompt: str, system: str = "") -> dict:
    """Blocking `claude -p`. Returns parsed JSON (the model is told to answer with JSON only)."""
    model = cfg.get("haiku_model", "claude-haiku-4-5")
    with db.tx() as con:
        check_allowed(cfg, con)
        cur = con.execute("INSERT INTO ai_runs(kind,model,account,cmd,status,est_input_tokens,started) VALUES(?,?,?,?,?,?,?)",
                          (kind, model, cfg.get("claude_mode", "personal"), "claude -p", "running",
                           est_tokens(prompt + system), dt.datetime.now().isoformat(timespec="seconds")))
        run_id = cur.lastrowid
    cmd = ["claude", "-p", "--model", model, "--output-format", "json", "--tools", "",
           "--no-session-persistence"]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        res = subprocess.run(cmd, input=prompt, capture_output=True, text=True, env=_env(cfg), timeout=600)
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip()[:800] or f"claude exited {res.returncode}")
        outer = json.loads(res.stdout)
        text = outer.get("result", "") if isinstance(outer, dict) else str(outer)
        data = _extract_json(text)
        status, log = "done", json.dumps({"usage": outer.get("usage"), "cost_usd": outer.get("total_cost_usd")})
    except Exception as e:  # noqa: BLE001
        status, log, data = "failed", str(e)[:2000], None
        raise
    finally:
        with db.tx() as con:
            con.execute("UPDATE ai_runs SET status=?, finished=?, log=? WHERE id=?",
                        (status, dt.datetime.now().isoformat(timespec="seconds"), log, run_id))
    return data


def _extract_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("\n") + 1:] if "\n" in text else text
    start = min([i for i in (text.find("["), text.find("{")) if i >= 0] or [0])
    end = max(text.rfind("]"), text.rfind("}")) + 1
    return json.loads(text[start:end])


def _q(v):
    return shlex.quote(str(v))


def _opt(flag, v):
    return f" {flag} {_q(v)}" if v else ""


# One bundled skill per PM Journey step (skills/<step>/SKILL.md, invoked as /pm-<step>).
# Steps that need a file take a["file"]; multi-file steps take a["files"]; free text takes a["text"].
def _slash(step, *parts):
    return f"/pm-{step}" + "".join(parts)


SKILLS = {
    "pm-guide": lambda a: _slash("guide", f" {_q(a['text'])}" if a.get("text") else ""),
    "discovery": lambda a: _slash("discovery", _opt("--file", a.get("file")), f" {_q(a['text'])}" if a.get("text") else ""),
    "research-synthesis": lambda a: _slash("research-synthesis", _opt("--file", a.get("file"))),
    "concept-accept": lambda a: _slash("concept-accept", _opt("--file", a.get("file"))),
    "generate-prd": lambda a: _slash("generate-prd", _opt("--file", a.get("file")), _opt("--parent", a.get("bepic"))),
    "risk-review": lambda a: _slash("risk-review", _opt("--file", a.get("file"))),
    "ux-brief": lambda a: _slash("ux-brief", _opt("--file", a.get("file"))),
    "poc": lambda a: _slash("poc", f" {_q(a['text'])}" if a.get("text") else ""),
    "review-prd": lambda a: _slash("review-prd", _opt("--file", a.get("file"))),
    "validate-prd": lambda a: _slash("validate-prd", _opt("--file", a.get("file"))),
    "generate-hld": lambda a: _slash("generate-hld", _opt("--file", a.get("file"))),
    "validate-hld": lambda a: _slash("validate-hld", _opt("--file", a.get("file"))),
    "generate-epics-and-stories": lambda a: _slash("generate-epics-and-stories", _opt("--prd", a.get("file")), _opt("--parent", a.get("bepic"))),
    "publish-specs": lambda a: _slash("publish-specs", "".join(_opt("--file", f) for f in (a.get("files") or [a.get("file")]) if f),
                                      _opt("--parent", a.get("bepic"))),
    "requirements-accept": lambda a: _slash("requirements-accept", _opt("--epics", a.get("file")),
                                            _opt("--jira-project", a.get("project")), _opt("--parent", a.get("bepic"))),
}
# skills whose run has external side effects (PR, Jira, git branch) — the UI shows a warning first
WRITE_SKILLS = {"publish-specs", "requirements-accept", "poc"}


def sync_skills(ws: Path) -> int:
    """Copy bundled skills into <ws>/.claude/skills/pm-<step>/ so `claude` started in ws can run them."""
    n = 0
    if not SKILLS_DIR.exists():
        return 0
    conv = SKILLS_DIR / "CONVENTIONS.md"
    if conv.exists():
        dst = ws / ".claude" / "pm-conventions.md"
        if not dst.exists() or dst.read_text() != conv.read_text():
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(conv.read_text())
    for src in SKILLS_DIR.glob("*/SKILL.md"):
        dst = ws / ".claude" / "skills" / f"pm-{src.parent.name}" / "SKILL.md"
        text = src.read_text()
        if not dst.exists() or dst.read_text() != text:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(text)
            n += 1
    return n


def skill_command(cfg, skill: str, args: dict) -> dict:
    if skill not in SKILLS:
        raise ValueError("unknown skill")
    ws = cfg.get("pr_workspace") or str(PR_WORKSPACE_DEFAULT)
    slash = SKILLS[skill](args)
    shell = f'cd {shlex.quote(ws)} && claude {shlex.quote(slash)}'
    return {"skill": skill, "cwd": ws, "slash": slash, "shell": shell}


def launch_skill(cfg, skill: str, args: dict) -> dict:
    info = skill_command(cfg, skill, args)
    ws = Path(info["cwd"])
    ws.mkdir(parents=True, exist_ok=True)
    sync_skills(ws)
    with db.tx() as con:
        if cfg.get("claude_mode", "personal") == "off":
            raise RuntimeError("AI is turned off in Settings")
        con.execute("INSERT INTO ai_runs(kind,model,account,cmd,status,started) VALUES(?,?,?,?,?,?)",
                    (f"skill:{skill}", "interactive", cfg.get("claude_mode", "personal"), info["slash"],
                     "launched", dt.datetime.now().isoformat(timespec="seconds")))
    info.update(_open_terminal(info["shell"]))
    return info


def _open_terminal(shell: str, platform: str = None) -> dict:
    """Open an interactive terminal running `shell`. Falls back to copy-only where no launcher exists."""
    platform = platform or sys.platform
    try:
        if platform == "darwin":
            script = f'tell application "Terminal"\n activate\n do script {json.dumps(shell)}\nend tell'
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            return {"launched": res.returncode == 0, "error": res.stderr.strip() if res.returncode else ""}
        if platform.startswith("linux"):
            term = next((t for t in ("x-terminal-emulator", "gnome-terminal", "konsole", "xterm") if shutil.which(t)), None)
            if not term:
                return {"launched": False, "error": "no terminal emulator found; use Copy command"}
            args = [term, "--", "bash", "-lc", shell] if term == "gnome-terminal" else [term, "-e", f"bash -lc {shlex.quote(shell)}"]
            subprocess.Popen(args)
            return {"launched": True, "error": ""}
        if platform == "win32":
            subprocess.Popen(["cmd", "/c", "start", "", "cmd", "/k", shell], shell=False)
            return {"launched": True, "error": ""}
    except (OSError, subprocess.SubprocessError) as e:
        return {"launched": False, "error": f"{e}; use Copy command"}
    return {"launched": False, "error": f"no terminal launcher for {platform}; use Copy command"}
