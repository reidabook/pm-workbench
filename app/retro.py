"""Retro planner: a retro opens when an epic closes; it gathers Jira lifecycle + scope facts,
KR readings at release / +30 / +60 / +90 days, and context metrics before vs after release."""
import datetime as dt
import json
from typing import Optional

from .paths import field, load_config
from . import db, jira_sync, metrics, okr

OMIT_RESOLUTIONS = {"won't do", "wont do", "won't fix", "duplicate", "cancelled", "canceled", "obsolete", "rejected"}
WINDOWS = [("release", 0), ("+30", 30), ("+60", 60), ("+90", 90)]
NOW = lambda: dt.datetime.now().isoformat(timespec="seconds")  # noqa: E731


def open_for(con, key: str, resolution: Optional[str], closed_at: Optional[str]) -> bool:
    flag = (resolution or "").strip().lower() in OMIT_RESOLUTIONS
    cur = db.one(con, "SELECT released_at, omit_reason, status FROM retros WHERE epic_key=?", (key,))
    if cur:
        # fill in facts that were unknown when the retro was first opened (e.g. backfill before a full pull)
        if not cur["released_at"] and closed_at:
            con.execute("UPDATE retros SET released_at=? WHERE epic_key=?", (closed_at, key))
        if flag and not cur["omit_reason"] and cur["status"] == "pending":
            con.execute("UPDATE retros SET omit_reason=? WHERE epic_key=?", (f"suggested: resolution {resolution}", key))
        return False
    con.execute("INSERT INTO retros(epic_key,status,omit_reason,released_at,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (key, "pending", f"suggested: resolution {resolution}" if flag else None, closed_at, NOW(), NOW()))
    return True


def backfill(con) -> int:
    n = 0
    for e in db.rows(con, "SELECT key, resolution, closed_at FROM epics WHERE LOWER(status)='closed' OR LOWER(status_category)='done'"):
        n += open_for(con, e["key"], e["resolution"], e["closed_at"])
    return n


def _lifecycle(issue: dict) -> dict:
    f = issue["fields"]
    created = (f.get("created") or "")[:10]
    closed = (f.get("resolutiondate") or "")[:10] or None
    first_dev = None
    changes = reopens = 0
    downstream = {"in dev", "in development", "in progress", "development"}
    prev_done = False
    for h in (issue.get("changelog") or {}).get("histories", []):
        for it in h.get("items", []):
            if it.get("field") != "status":
                continue
            changes += 1
            to = (it.get("toString") or "").lower()
            if to in downstream and not first_dev:
                first_dev = h["created"][:10]
            if to == "closed":
                prev_done = True
            elif prev_done:
                reopens += 1
                prev_done = False

    def days(a, b):
        try:
            return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days
        except (TypeError, ValueError):
            return None
    return {"created": created, "first_dev": first_dev, "closed": closed,
            "days_total": days(created, closed), "days_analysis": days(created, first_dev),
            "days_dev": days(first_dev, closed), "status_changes": changes, "reopens": reopens,
            "assignee": (f.get("assignee") or {}).get("displayName"),
            "product_owner": (f.get(field(load_config(), "product_owner")) or {}).get("displayName"),
            "description": (f.get("description") or "")[:4000],
            "comments": [{"who": (c.get("author") or {}).get("displayName"), "when": (c.get("created") or "")[:10],
                          "body": (c.get("body") or "")[:600]}
                         for c in ((f.get("comment") or {}).get("comments") or [])[-15:]]}


def _scope(children: list, first_dev: Optional[str]) -> dict:
    late = [c for c in children if first_dev and c["created"] and c["created"] > first_dev]
    pts = [c["points"] for c in children if isinstance(c.get("points"), (int, float))]
    return {"stories": len(children), "done": sum(1 for c in children if c.get("resolved")),
            "added_after_dev_start": len(late), "story_points": sum(pts) if pts else None,
            "assignees": sorted({c["assignee"] for c in children if c.get("assignee")}),
            "items": [{k: c[k] for k in ("key", "summary", "status", "created", "resolved")} for c in children[:60]]}


def build(cfg, con, key: str) -> dict:
    """Fetch (once) and store lifecycle + scope facts; compute KR readings and context metrics."""
    r = db.one(con, "SELECT * FROM retros WHERE epic_key=?", (key,))
    if not r:
        e = db.one(con, "SELECT resolution, closed_at FROM epics WHERE key=?", (key,)) or {}
        open_for(con, key, e.get("resolution"), e.get("closed_at"))
        r = db.one(con, "SELECT * FROM retros WHERE epic_key=?", (key,))
    if not r["lifecycle_json"]:
        issue = jira_sync.fetch_changelog(cfg, key)
        life = _lifecycle(issue)
        children = jira_sync.fetch_children(cfg, key)
        con.execute("UPDATE retros SET lifecycle_json=?, scope_json=?, released_at=COALESCE(released_at,?), "
                    "status=CASE WHEN status='pending' THEN 'in_progress' ELSE status END, updated_at=? WHERE epic_key=?",
                    (json.dumps(life), json.dumps(_scope(children, life["first_dev"])), life["closed"], NOW(), key))
        r = db.one(con, "SELECT * FROM retros WHERE epic_key=?", (key,))
    return detail(cfg, con, r)


def detail(cfg, con, r: dict) -> dict:
    out = dict(r)
    out["lifecycle"] = json.loads(r["lifecycle_json"]) if r["lifecycle_json"] else None
    out["scope"] = json.loads(r["scope_json"]) if r["scope_json"] else None
    released = r["released_at"]
    out["kr_readings"] = []
    for kr in db.rows(con, "SELECT * FROM key_results WHERE epic_key=?", (r["epic_key"],)):
        row = {"kr": kr, "readings": {}}
        for name, off in WINDOWS:
            if not released:
                break
            at = (dt.date.fromisoformat(released) + dt.timedelta(days=off)).isoformat()
            if at > dt.date.today().isoformat():
                row["readings"][name] = None
                continue
            if kr["source"] in ("baselines_jsonl", "data_js"):
                v, d = metrics.read_metric(cfg, kr["source"], kr["metric_key"], at=at)
            else:
                s = db.one(con, "SELECT value, taken_at FROM kr_snapshots WHERE kr_id=? AND taken_at<=? ORDER BY taken_at DESC LIMIT 1", (kr["id"], at))
                v, d = (s["value"], s["taken_at"]) if s else (None, None)
            row["readings"][name] = {"value": v, "date": d, "progress": okr.kr_progress({**kr, "current": v}) if v is not None else None}
        out["kr_readings"].append(row)
    out["context"] = []
    if released:
        before = (dt.date.fromisoformat(released) - dt.timedelta(days=30)).isoformat()
        after = (dt.date.fromisoformat(released) + dt.timedelta(days=30)).isoformat()
        for k in [k.strip() for k in (r["context_metrics"] or "").split(",") if k.strip()]:
            vb, db_ = metrics.read_metric(cfg, "baselines_jsonl", k, at=before)
            va, da = metrics.read_metric(cfg, "baselines_jsonl", k, at=min(after, dt.date.today().isoformat()))
            out["context"].append({"metric": k, "before": vb, "before_date": db_, "after": va, "after_date": da,
                                   "delta": (va - vb) if (va is not None and vb is not None) else None})
    return out
