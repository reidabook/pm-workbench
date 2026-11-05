"""Filesystem anchors. Everything the app writes lives under data/ (gitignored)."""
import json
import os
import re
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent          # pm-workbench/
DATA = Path(os.environ.get("PMWB_DATA", APP_ROOT / "data"))
DATA.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA / "workbench.db"
CONFIG_PATH = DATA / "config.json"
ENV_FILE = DATA / ".env"                                    # optional JIRA_PAT=... (never shared)
PRIORITIZATION = APP_ROOT / "prioritization"               # legacy spreadsheet tooling (optional)

_DEFAULTS = json.loads((APP_ROOT / "config.example.json").read_text())
PR_WORKSPACE_DEFAULT = Path.home() / "pm-workspace"
SKILLS_DIR = APP_ROOT / "skills"                           # bundled PM Journey skills, synced into the workspace


def load_config() -> dict:
    cfg = json.loads(json.dumps(_DEFAULTS))  # deep copy so nested defaults are never mutated
    if CONFIG_PATH.exists():
        try:
            user = json.loads(CONFIG_PATH.read_text())
            fields = {**cfg.get("jira_fields", {}), **(user.get("jira_fields") or {})}
            cfg.update(user)
            cfg["jira_fields"] = fields
        except json.JSONDecodeError:
            pass
    if not cfg.get("pr_workspace"):
        cfg["pr_workspace"] = str(PR_WORKSPACE_DEFAULT)
    return cfg


def save_config(cfg: dict) -> dict:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    return cfg


def field(cfg, name: str) -> str:
    """Jira field id for a logical name (team, parent_link, outcome, ...). "" = not used on this Jira."""
    return (cfg.get("jira_fields") or {}).get(name) or _DEFAULTS["jira_fields"].get(name) or ""


# ---------- Jira key classification ----------
# Epics live in `jira_project`; their parents (initiatives / business epics) optionally in `parent_project`.
# With no prefix configured, any Jira-style key counts.
KEY_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d{1,8}\b")


_PREFIX_CACHE: dict = {}


def _prefix(name: str) -> str:
    stamp = CONFIG_PATH.stat().st_mtime if CONFIG_PATH.exists() else 0
    if _PREFIX_CACHE.get("_stamp") != stamp:
        cfg = load_config()
        _PREFIX_CACHE.clear()
        _PREFIX_CACHE.update({"_stamp": stamp, **{k: (cfg.get(k) or "").strip().upper() for k in ("jira_project", "parent_project")}})
    p = _PREFIX_CACHE.get(name, "")
    return f"{p}-" if p else ""


def is_epic_key(k: str) -> bool:
    pre, par = _prefix("jira_project"), _prefix("parent_project")
    if pre:
        return str(k).startswith(pre)
    return not (par and str(k).startswith(par))


def is_parent_key(k: str) -> bool:
    par = _prefix("parent_project")
    return bool(par) and str(k).startswith(par)


def prd_dirs(cfg) -> list:
    out = []
    for d in cfg.get("prd_dirs", []):
        p = Path(d).expanduser()
        out.append(p if p.is_absolute() else (APP_ROOT / p).resolve())
    ws = cfg.get("pr_workspace")
    if ws:
        out.append(Path(ws) / "refined-prds")
        out.append(Path(ws) / "prds")
    return out
