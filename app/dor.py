"""Story readiness — heuristic subset of a 7-point Definition of Ready (see docs/WORKFLOW.md)
plus the epic conventions engineering expects before pulling a story.

Pure functions over Jira issue dicts; no I/O. Heuristics flag, they do not certify: the authoritative gate is
the `/pm-requirements-accept` skill. Check 7 (AC → epic success metric) is only reported from that skill's output.
"""
import json
import re

from . import db

GWT_RE = re.compile(r"\bgiven\b.*?\bwhen\b.*?\bthen\b", re.I | re.S)
AC_CATEGORIES = {  # the five AC categories requirements-accept expects
    "Happy Path": r"happy\s*path|primary\s*flow|main\s*flow|success(?:ful)?\s*(?:path|flow|case)",
    "Validations": r"validat|invalid|required\s*field|format",
    "Permissions": r"permission|authoriz|role|access|entitle",
    "Edge Cases": r"edge\s*case|boundary|empty|maximum|minimum|concurren|limit",
    "Error Handling": r"error|fail(?:ure|s|ed)?|exception|timeout|retry|fallback",
}
VAGUE = ["quickly", "fast", "easy", "easily", "intuitive", "robust", "seamless", "user[- ]friendly", "as appropriate",
         "appropriately", "handles? (?:it )?(?:gracefully|appropriately|properly)", "should work", "shows? (?:an )?error\\b(?![^.]*(?:message|code|text))",
         "etc\\.?", "and so on", "performant", "scalable"]
VAGUE_RE = re.compile("|".join(VAGUE), re.I)
TODO_RE = re.compile(r"\[(?:TODO|TBD|TBC|FIXME)\]|\bTBD\b|\bTODO\b", re.I)
PERSONA_RE = re.compile(r"\bas\s+an?\s+([^,\n]{2,60}?)\s*,", re.I)
FIB = {1, 2, 3, 5, 8}
BLOCKER_LABELS = {"dor::dependency_risk", "blocked", "dor::blocked"}


def _txt(*parts):
    return "\n".join(p for p in parts if p)


def story_checks(s: dict, published: set = None) -> dict:
    ac, desc, summary = s.get("acceptance_criteria") or "", s.get("description") or "", s.get("summary") or ""
    body = _txt(summary, desc, ac)
    pts = s.get("points")
    if isinstance(pts, dict):  # some Jira instances return option objects
        pts = pts.get("value", pts.get("name"))
    try:
        pts = float(pts) if pts not in (None, "") else None
    except (TypeError, ValueError):
        pts = None
    labels = {l.lower() for l in (s.get("labels") or [])}
    checks = []

    def add(cid, label, ok, detail=""):
        checks.append({"id": cid, "label": label, "pass": bool(ok), "detail": detail})

    # 1 AC structure & format — in the AC field, Given/When/Then, five categories
    gwt = bool(GWT_RE.search(ac))
    cats = [c for c, pat in AC_CATEGORIES.items() if re.search(pat, ac, re.I)]
    missing = [c for c in AC_CATEGORIES if c not in cats]
    add("ac_format", "AC in Jira AC field, Given/When/Then, 5 categories", bool(ac.strip()) and gwt and not missing,
        "no AC in the Acceptance Criteria field" if not ac.strip() else ("not Given/When/Then" if not gwt else ("missing: " + ", ".join(missing) if missing else "")))
    # 2 INVEST — role-qualified persona, ≤ 8 points
    m = PERSONA_RE.search(body)
    persona = (m.group(1).strip() if m else "")
    role_ok = bool(persona) and persona.lower() not in {"user", "a user", "an user", "customer", "person"} and not persona.lower().startswith("user ")
    add("persona", "Role-qualified persona (not bare 'user')", role_ok, f"persona: '{persona}'" if persona else "no 'As a <role>,' statement")
    pts_ok = isinstance(pts, (int, float)) and pts in FIB
    add("points", "Story points Fibonacci ≤ 8", pts_ok, "no points" if pts is None else (f"{pts:g} points" if not pts_ok else ""))
    pts = int(pts) if pts_ok else pts
    # 3 metadata
    add("priority", "Priority set", bool(s.get("priority")) and str(s.get("priority")).lower() not in ("none", "unprioritized"), str(s.get("priority") or "none"))
    # 4 testability — no vague terms
    vague = sorted({v.group(0).lower() for v in VAGUE_RE.finditer(ac or desc)})
    add("testable", "AC testable — no vague terms", not vague, ", ".join(vague[:5]))
    # 5 blockers
    blocked = bool(labels & BLOCKER_LABELS) or str(s.get("status") or "").lower() == "blocked"
    add("no_blockers", "No unresolved blockers", not blocked, "blocker label / Blocked status" if blocked else "")
    # 6 description clarity
    todo = TODO_RE.search(body)
    add("description", "Description present, no TODO/TBD", bool(desc.strip()) and not todo,
        "empty description" if not desc.strip() else (f"contains '{todo.group(0)}'" if todo else ""))
    # 7 AC ↔ epic success metric — only requirements-accept knows; report provenance
    pub = s.get("key") in (published or set())
    add("metric_link", "AC maps to epic success metric (from requirements-accept)", pub,
        "published via requirements-accept" if pub else "not published via requirements-accept — verify manually")
    hard = [c for c in checks if c["id"] != "metric_link"]
    return {"key": s.get("key"), "summary": summary, "status": s.get("status"), "points": pts, "type": s.get("type"),
            "assignee": s.get("assignee"), "checks": checks, "passed": sum(c["pass"] for c in hard), "total": len(hard),
            "ready": all(c["pass"] for c in hard), "published": pub}


def epic_checks(e: dict, prd_meta: dict = None) -> list:
    prd_meta = prd_meta or {}
    body = _txt(e.get("description"), e.get("acceptance_criteria"), e.get("outcome"))
    labels = {l for l in (e.get("labels") or [])}
    out = [
        {"id": "bepic", "label": "Parent Business Epic linked", "pass": bool(e.get("bepic")), "detail": e.get("bepic") or "no Parent Link"},
        {"id": "toggle", "label": "Toggle Status When Deployed stated", "pass": bool(re.search(r"toggle\s*status|toggle\s*(on|off)|no\s*toggle|feature\s*flag|flag\s*intent", body, re.I)),
         "detail": "team convention: Toggle On / Toggle Off / No Toggle, inherited by stories"},
        {"id": "backout", "label": "Backout strategy stated", "pass": bool(re.search(r"backout|back-out|rollback|roll back", body, re.I)) or bool(re.search(r"toggle\s*on", body, re.I)),
         "detail": "Backout Strategy + owner (waived when Flag Intent is Toggle On)"},
        {"id": "in_dev", "label": "Epic status In Dev (team convention before stories are pulled)", "pass": str(e.get("status") or "").lower() in ("in dev", "in development"),
         "detail": e.get("status") or ""},
    ]
    if str(prd_meta.get("ux_required", "")).lower().startswith("y"):
        out.append({"id": "ux_label", "label": "UX::Required label (PRD says UX required)", "pass": "UX::Required" in labels, "detail": ""})
    if str(prd_meta.get("legal_required", "")).lower().startswith("y"):
        out.append({"id": "legal_label", "label": "Legal::Required label (PRD says legal review required)", "pass": "Legal::Required" in labels, "detail": ""})
    return out


def assess(epic: dict, stories: list, published: set = None, prd_meta: dict = None) -> dict:
    stories = [s for s in stories if (s.get("type") or "").lower() not in ("epic", "sub-task", "subtask")]
    rows = [story_checks(s, published) for s in stories]
    ec = epic_checks(epic, prd_meta)
    fails = {}
    for r in rows:
        for c in r["checks"]:
            if not c["pass"] and c["id"] != "metric_link":
                fails[c["label"]] = fails.get(c["label"], 0) + 1
    return {"summary": {"stories": len(rows), "ready": sum(r["ready"] for r in rows), "published": sum(r["published"] for r in rows),
                        "epic_ok": all(c["pass"] for c in ec), "epic_checks": ec,
                        "top_failing": sorted(fails.items(), key=lambda kv: -kv[1])[:4], "epic_status": epic.get("status")},
            "stories": rows}


# ---------- DB helpers (read-only) ----------
def published_keys(con) -> set:
    """Story keys created by requirements-accept, from the jira-manifest artifact."""
    keys = set()
    for a in db.rows(con, "SELECT meta_json FROM artifacts WHERE kind='jira-manifest'"):
        try:
            for ks in json.loads(a["meta_json"] or "{}").get("epics", {}).values():
                keys |= set(ks)
        except ValueError:
            pass
    return keys


def prd_meta_for_epic(con, key: str) -> dict:
    meta = {}
    for p in db.rows(con, "SELECT p.meta_json FROM prds p JOIN prd_epics pe ON pe.prd_id=p.id WHERE pe.epic_key=?", (key,)):
        try:
            meta.update({k: v for k, v in json.loads(p["meta_json"] or "{}").items() if v})
        except ValueError:
            pass
    return meta
