"""Parse <pr_workspace>/portfolio-context.md (created by Settings → Create workspace).

Reads the 'Priority Tiers' and 'Program Jira Keys' markdown tables. Best-effort: the scaffold
ships with empty rows, so callers must handle zero results.
"""
import re
from pathlib import Path


def _table_rows(text: str, heading: str):
    """Rows (list of cell lists) of the first markdown table under `## <heading>`."""
    m = re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.M | re.I)
    if not m:
        return []
    body = text[m.end():]
    nxt = re.search(r"^##\s", body, re.M)
    body = body[:nxt.start()] if nxt else body
    lines = [l.strip() for l in body.splitlines() if l.strip().startswith("|")]
    if len(lines) < 2:
        return []
    out = []
    for l in lines[2:]:  # skip header + separator
        cells = [c.strip() for c in l.strip("|").split("|")]
        if any(cells):
            out.append(cells)
    return out


def parse(path: Path) -> dict:
    """{'tiers': [{tier, initiative, theme, program_epic, status}], 'programs': [{program, project, prefix, owner}]}"""
    if not path.exists():
        return {"tiers": [], "programs": []}
    text = path.read_text(errors="replace")
    tiers = []
    for c in _table_rows(text, "Priority Tiers"):
        c += [""] * (5 - len(c))
        if c[1]:
            tiers.append({"tier": c[0], "initiative": c[1], "theme": c[2], "program_epic": c[3], "status": c[4]})
    programs = []
    for c in _table_rows(text, "Program Jira Keys"):
        c += [""] * (4 - len(c))
        if c[0] or c[1]:
            programs.append({"program": c[0], "project": c[1], "prefix": c[2], "owner": c[3]})
    return {"tiers": tiers, "programs": programs}
