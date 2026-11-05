"""PM Workbench API. GET routes never touch Claude; AI only behind explicit POSTs."""
import datetime as dt
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ai_runner, artifacts, db, dor, evidence, github_refs, ideas, jira_sync, journey, metrics, okr, portfolio_context, prd_pipeline, retro, scoring, worklog, xlsx_io
from .paths import APP_ROOT, DATA, ENV_FILE, KEY_RE, PR_WORKSPACE_DEFAULT, load_config, save_config

app = FastAPI(title="PM Workbench")
app.mount("/static", StaticFiles(directory=str(APP_ROOT / "static")), name="static")
NOW = lambda: dt.datetime.now().isoformat(timespec="seconds")  # noqa: E731


def err(e):
    raise HTTPException(status_code=400, detail=str(e))


@app.on_event("startup")
def _startup():
    db.init()
    threading.Thread(target=_poller, daemon=True).start()
    threading.Thread(target=_skill_watcher, daemon=True).start()


def _skill_watcher():
    """While a launched skill is still waiting on its output, rescan the workspace so the result
    shows up without the PM clicking Rescan. Idle (no file reads) when nothing is pending."""
    while True:
        time.sleep(10)
        try:
            with db.connect() as con:
                pending = prd_pipeline.pending_runs(con)
            if pending:
                _scan_all(load_config())
        except Exception:  # noqa: BLE001
            pass


def _poller():
    time.sleep(3)
    while True:
        cfg = load_config()
        mins = int(cfg.get("poll_minutes") or 0)
        if mins > 0:
            try:
                jira_sync.pull(cfg)
            except Exception as e:  # noqa: BLE001
                with db.tx() as con:
                    db.set_meta(con, "last_sync_error", f"{NOW()} {e}")
        time.sleep(max(mins, 1) * 60)


# ---------------- state ----------------
def compute_all(con, cfg):
    p = db.params(con)
    themes = db.rows(con, "SELECT * FROM themes ORDER BY priority_rank, name")
    max_rank = max([t["priority_rank"] for t in themes] or [1])
    trank = {t["id"]: t["priority_rank"] for t in themes}
    tname = {t["id"]: t["name"] for t in themes}
    epics = db.rows(con, "SELECT e.*, s.theme_id, s.sv, s.ui, s.urg, s.conf, s.effort, s.park, s.raise_p1, s.notes, s.val_override "
                         "FROM epics e LEFT JOIN scores s ON s.epic_ref=e.key WHERE e.in_scope=1")
    drafts = db.rows(con, "SELECT d.*, s.sv, s.ui, s.urg, s.conf, s.effort, s.park, s.raise_p1, s.notes, s.val_override "
                          "FROM draft_epics d LEFT JOIN scores s ON s.epic_ref='draft:'||d.id WHERE d.jira_key IS NULL")
    rows = []
    for e in epics:
        rows.append({**e, "priority_cur": e["priority"], "ref": e["key"], "is_draft": False, "theme_rank": trank.get(e["theme_id"]),
                     "theme_name": tname.get(e["theme_id"]), "prd_flag": db.get_meta(con, f"prd_flag:{e['key']}")})
    for d in drafts:
        rows.append({**d, "key": f"draft:{d['id']}", "ref": f"draft:{d['id']}", "is_draft": True, "status": "Draft",
                     "priority": None, "theme_rank": trank.get(d["theme_id"]), "theme_name": tname.get(d["theme_id"]),
                     "bepic": next((t["bepic_key"] for t in themes if t["id"] == d["theme_id"]), None)})
    ev = evidence.for_refs(con, [r["ref"] for r in rows])
    for r in rows:
        r["evidence"] = ev.get(r["ref"], [])
        r["validation_auto"] = evidence.validation_score(r["evidence"], p)
        r["validation"] = r["val_override"] if r.get("val_override") is not None else r["validation_auto"]
    comp = scoring.compute(rows, p, max_rank)
    prd_links = db.rows(con, "SELECT pe.epic_key, p.id, p.title, p.stage, p.validation_result, p.pr_url, p.path, p.github_url, p.note, p.source "
                             "FROM prd_epics pe JOIN prds p ON p.id=pe.prd_id")
    by_key = {}
    for l in prd_links:
        by_key.setdefault(l["epic_key"], []).append(l)
    for c in comp:
        c["prds"] = by_key.get(c["key"], [])
    return p, themes, comp


@app.get("/", response_class=HTMLResponse)
def index():
    return (APP_ROOT / "static" / "index.html").read_text()


@app.get("/api/state")
def state():
    cfg = load_config()
    with db.connect() as con:
        p, themes, comp = compute_all(con, cfg)
        counts = {}
        for c in comp:
            counts.setdefault(c["theme_id"], {"epics": 0, "drafts": 0})["drafts" if c["is_draft"] else "epics"] += 1
        for t in themes:
            t.update(counts.get(t["id"], {"epics": 0, "drafts": 0}))
            t["ideas"] = con.execute("SELECT COUNT(*) FROM ideas WHERE theme_id=? AND status!='archived'", (t["id"],)).fetchone()[0]
        committed = db.rows(con, "SELECT e.*, s.theme_id FROM epics e LEFT JOIN scores s ON s.epic_ref=e.key "
                                 "WHERE e.in_scope=0 AND e.scope_reason LIKE 'in flight%' ORDER BY e.rank_pos")
        meta = {r["key"]: r["value"] for r in con.execute("SELECT key,value FROM meta WHERE key NOT LIKE 'prd_flag:%'")}
        ideas_ = db.rows(con, "SELECT i.*, s.filename FROM ideas i LEFT JOIN sources s ON s.id=i.source_id "
                              "WHERE i.status!='archived' ORDER BY i.id DESC")
        ev_refs = [f"idea:{i['id']}" for i in ideas_] + [f"group:{g['id']}" for g in db.rows(con, "SELECT id FROM idea_groups")]
        ev_map = evidence.for_refs(con, ev_refs)
        groups = db.rows(con, "SELECT g.*, t.name AS theme_name, t.bepic_key, p.stage AS prd_stage, p.path AS prd_path, "
                              "p.title AS prd_title, p.validation_result FROM idea_groups g LEFT JOIN themes t ON t.id=g.theme_id "
                              "LEFT JOIN prds p ON p.id=g.prd_id ORDER BY g.id DESC")
        sources = db.rows(con, "SELECT id, filename, kind, evidence_type, url, ingested_at, LENGTH(text) AS chars FROM sources ORDER BY id DESC")
        prds = db.rows(con, "SELECT * FROM prds ORDER BY mtime DESC")
        prd_pipeline.run_summary(con, prds)
        skills_running = prd_pipeline.pending_runs(con)
        links = db.rows(con, "SELECT * FROM prd_epics")
        hlds = db.rows(con, "SELECT id,title,initiative,result,pr_url,pr_state,github_url,path,source FROM artifacts WHERE kind='hld'")
        hld_reviews = {a["initiative"]: a for a in db.rows(con, "SELECT initiative,result,path,id FROM artifacts WHERE kind='hld-review' ORDER BY mtime")}
        for pr in prds:
            pr["epics"] = [l["epic_key"] for l in links if l["prd_id"] == pr["id"]]
            pr["hld"] = next((h for h in hlds if h["initiative"] and h["initiative"] == pr.get("initiative")), None)
            pr["hld_review"] = hld_reviews.get(pr.get("initiative"))
        prd_pipeline.collapse_refined(prds)
        initiatives = journey.build(con, cfg)
        arts = db.rows(con, "SELECT id,path,kind,title,initiative,result,pr_url,pr_state,github_url,source,mtime FROM artifacts ORDER BY mtime DESC")
        dor_cache = {r["epic_key"]: json.loads(r["summary_json"] or "{}") | {"fetched_at": r["fetched_at"]}
                     for r in db.rows(con, "SELECT epic_key,fetched_at,summary_json FROM story_dor")}
        for c in comp:
            c["dor"] = dor_cache.get(c["key"])
            c["initiative"] = next((i["slug"] for i in initiatives if c["key"] in i["epic_keys"]), None)
        drafts_all = db.rows(con, "SELECT * FROM draft_epics ORDER BY id DESC")
        runs = db.rows(con, "SELECT * FROM ai_runs ORDER BY id DESC LIMIT 50")
        runs_today = ai_runner.runs_today(con)
        # OKR board for the selected quarter
        periods = db.rows(con, "SELECT * FROM okr_periods ORDER BY start")
        period = _current_period(con, periods)
        okr_epics = [{**c, "closed_at": c.get("closed_at")} for c in comp] + \
                    [{"key": c["key"], "theme_id": c.get("theme_id"), "closed_at": c.get("closed_at")} for c in committed]
        okr_epics += [{"key": e["key"], "theme_id": e["theme_id"], "closed_at": e["closed_at"]} for e in db.rows(
            con, "SELECT e.key, e.closed_at, s.theme_id FROM epics e LEFT JOIN scores s ON s.epic_ref=e.key "
                 "WHERE LOWER(e.status)='closed'")]
        board = okr.board(cfg, con, period, themes, okr_epics) if period else {"themes": {}, "epics": {}, "elapsed": 0}
        retros = db.rows(con, "SELECT r.*, e.summary, e.resolution, e.status AS epic_status, e.team, s.theme_id "
                              "FROM retros r LEFT JOIN epics e ON e.key=r.epic_key LEFT JOIN scores s ON s.epic_ref=r.epic_key "
                              "ORDER BY r.released_at DESC")
        for r in retros:
            r.pop("lifecycle_json", None); r.pop("scope_json", None)
            r["kr_count"] = con.execute("SELECT COUNT(*) FROM key_results WHERE epic_key=?", (r["epic_key"],)).fetchone()[0]
        log = worklog.recent(con, 30)
    return {"log": log,"config": cfg, "params": p, "themes": themes, "epics": comp, "committed": committed, "meta": meta,
            "ideas": ideas_, "groups": groups, "sources": sources, "prds": prds, "drafts": drafts_all,
            "ai_runs": runs, "runs_today": runs_today, "skills_running": skills_running, "now": NOW(),
            "periods": periods, "period": period, "okr": board, "retros": retros,
            "initiatives": initiatives, "artifacts": arts, "journey_steps": [{"id": i, "label": l, "phase": ph, "required": r} for i, l, ph, r in journey.STEPS],
            "write_skills": sorted(ai_runner.WRITE_SKILLS),
            "evidence": ev_map, "evidence_types": [{"key": k, "label": l} for k, l, _ in evidence.TYPES]}


def _current_period(con, periods):
    if not periods:
        return None
    cur = db.get_meta(con, "current_period_id")
    if cur:
        for p in periods:
            if str(p["id"]) == str(cur):
                return p
    today = dt.date.today().isoformat()
    for p in periods:
        if p["start"] <= today <= p["end"]:
            return p
    return periods[0]


# ---------------- scores / params / themes ----------------
class ScoreIn(BaseModel):
    theme_id: Optional[int] = None
    sv: Optional[int] = None
    ui: Optional[int] = None
    urg: Optional[int] = None
    conf: Optional[int] = None
    effort: Optional[str] = None
    park: Optional[str] = None
    raise_p1: Optional[str] = None
    notes: Optional[str] = None
    val_override: Optional[float] = None


@app.put("/api/scores/{ref}")
def put_score(ref: str, s: ScoreIn):
    fields = {k: v for k, v in s.dict().items()}
    for k in ("sv", "ui", "urg", "conf"):
        if fields[k] is not None and not 1 <= fields[k] <= 5:
            err(f"{k} must be 1-5")
    if fields["effort"] is not None and fields["effort"].upper() not in ("S", "M", "L", ""):
        err("effort must be S/M/L")
    with db.tx() as con:
        con.execute("INSERT OR IGNORE INTO scores(epic_ref) VALUES(?)", (ref,))
        sets = ", ".join(f"{k}=?" for k in fields)
        con.execute(f"UPDATE scores SET {sets}, updated_at=? WHERE epic_ref=?",
                    (*[(v.upper() if k == "effort" and v else (v or None)) if isinstance(v, str) else v
                       for k, v in fields.items()], NOW(), ref))
    return {"ok": True}


@app.put("/api/params")
def put_params(p: dict):
    with db.connect() as con:
        cur = db.params(con)
    merged = {**cur, **{k: float(v) for k, v in p.items() if k in db.DEFAULT_PARAMS}}
    if abs(sum(merged.get(k, 0) for k in db.WEIGHT_KEYS) - 1) > 1e-6:
        err("the six weights (SV, UI, Urgency, Theme, Confidence, Validation) must sum to 1.0")
    with db.tx() as con:
        for k, v in p.items():
            if k in db.DEFAULT_PARAMS:
                con.execute("INSERT OR REPLACE INTO config_params(key,value) VALUES(?,?)", (k, float(v)))
    return {"ok": True}


class ThemeIn(BaseModel):
    name: str
    description: Optional[str] = ""
    bepic_key: Optional[str] = None
    objective: Optional[str] = None
    assign_unthemed: bool = False    # also give this theme to the unthemed epics under bepic_key / in epic_keys
    epic_keys: Optional[list] = None


def _assign_unthemed(con, tid: int, bepic_key: str = None, epic_keys: list = None) -> int:
    """Set theme_id on in-scope epics under `bepic_key` or listed in `epic_keys` that have no theme yet. Never overwrites."""
    want = {str(k) for k in (epic_keys or [])}
    n = 0
    for e in _unthemed_epics(con):
        if e["key"] in want or (bepic_key and e["bepic"] == bepic_key):
            con.execute("INSERT OR IGNORE INTO scores(epic_ref) VALUES(?)", (e["key"],))
            n += con.execute("UPDATE scores SET theme_id=?, updated_at=? WHERE epic_ref=? AND theme_id IS NULL",
                             (tid, NOW(), e["key"])).rowcount
    return n


def _unthemed_epics(con):
    return db.rows(con, "SELECT e.key, e.summary, e.status, e.bepic FROM epics e LEFT JOIN scores s ON s.epic_ref=e.key "
                        "WHERE e.in_scope=1 AND s.theme_id IS NULL ORDER BY e.bepic, e.rank_pos")


@app.post("/api/themes")
def add_theme(t: ThemeIn):
    bepic = (t.bepic_key or "").strip() or None
    with db.tx() as con:
        nxt = (con.execute("SELECT COALESCE(MAX(priority_rank),0) FROM themes").fetchone()[0] or 0) + 1
        try:
            cur = con.execute("INSERT INTO themes(name,description,priority_rank,bepic_key,objective) VALUES(?,?,?,?,?)",
                              (t.name.strip(), t.description or "", nxt, bepic, (t.objective or "").strip() or None))
        except Exception as e:  # noqa: BLE001
            err(e)
        assigned = _assign_unthemed(con, cur.lastrowid, bepic, t.epic_keys) if t.assign_unthemed else 0
    return {"id": cur.lastrowid, "assigned": assigned}


@app.post("/api/themes/{tid}/assign-unthemed")
def theme_assign_unthemed(tid: int, body: dict):
    with db.tx() as con:
        db.one(con, "SELECT id FROM themes WHERE id=?", (tid,)) or err("theme not found")
        return {"assigned": _assign_unthemed(con, tid, None, body.get("epic_keys") or [])}


@app.get("/api/bepics/{key}")
def get_bepic(key: str):
    """Jira title/description of a Business Epic plus what the workbench already knows about it (Import from BEpic)."""
    key = key.strip().upper()
    try:
        b = jira_sync.fetch_bepic(load_config(), key)
    except Exception as e:  # noqa: BLE001
        err(f"Could not read {key} from Jira: {e}")
    with db.connect() as con:
        b["epics"] = con.execute("SELECT COUNT(*) FROM epics WHERE in_scope=1 AND bepic=?", (key,)).fetchone()[0]
        b["unthemed"] = sum(1 for e in _unthemed_epics(con) if e["bepic"] == key)
        b["claimed_by"] = [t["name"] for t in db.rows(con, "SELECT name FROM themes WHERE bepic_key=? ORDER BY priority_rank", (key,))]
    return b


@app.put("/api/themes/{tid}")
def edit_theme(tid: int, t: ThemeIn):
    with db.tx() as con:
        con.execute("UPDATE themes SET name=?, description=?, bepic_key=?, objective=COALESCE(?, objective) WHERE id=?",
                    (t.name.strip(), t.description or "", t.bepic_key or None, t.objective, tid))
    return {"ok": True}


@app.put("/api/themes/{tid}/objective")
def theme_objective(tid: int, body: dict):
    with db.tx() as con:
        con.execute("UPDATE themes SET objective=? WHERE id=?", ((body.get("objective") or "").strip() or None, tid))
    return {"ok": True}


# ---------------- OKR: periods, key results, metrics ----------------
@app.get("/api/periods")
def get_periods():
    with db.connect() as con:
        return {"periods": db.rows(con, "SELECT * FROM okr_periods ORDER BY start"), "current": db.get_meta(con, "current_period_id")}


class PeriodIn(BaseModel):
    id: Optional[int] = None
    name: str
    start: str
    end: str


@app.put("/api/periods")
def put_period(p: PeriodIn):
    with db.tx() as con:
        if p.id:
            con.execute("UPDATE okr_periods SET name=?, start=?, end=? WHERE id=?", (p.name, p.start, p.end, p.id))
        else:
            con.execute("INSERT INTO okr_periods(name,start,end) VALUES(?,?,?)", (p.name, p.start, p.end))
    return {"ok": True}


@app.put("/api/periods/current/{pid}")
def set_current_period(pid: int):
    with db.tx() as con:
        db.set_meta(con, "current_period_id", pid)
    return {"ok": True}


class KrIn(BaseModel):
    epic_key: Optional[str] = None   # epic KR; None + theme_id = objective-level KR
    theme_id: Optional[int] = None
    period_id: Optional[int] = None
    title: str
    metric_key: Optional[str] = None
    source: str = "manual"
    unit: Optional[str] = None
    direction: str = "up"
    baseline: Optional[float] = None
    target: Optional[float] = None
    current: Optional[float] = None
    notes: Optional[str] = None
    owner: Optional[str] = None
    due: Optional[str] = None       # YYYY-MM-DD; display only — never written to the Jira Outcome block


def _kr_fill_current(cfg, d: dict):
    if d.get("source") in ("baselines_jsonl", "data_js") and d.get("metric_key"):
        v, at = metrics.read_metric(cfg, d["source"], d["metric_key"])
        if v is not None:
            d["current"], d["current_at"] = v, at
            if d.get("baseline") is None:
                d["baseline"] = v
    elif d.get("current") is not None:
        d["current_at"] = dt.date.today().isoformat()
    return d


@app.post("/api/krs")
def add_kr(k: KrIn):
    cfg = load_config()
    d = _kr_fill_current(cfg, k.dict())
    with db.tx() as con:
        pid = d["period_id"] or (_current_period(con, db.rows(con, "SELECT * FROM okr_periods ORDER BY start")) or {}).get("id")
        if not pid:
            err("no OKR period defined")
        if not d.get("epic_key") and not d.get("theme_id"):
            err("epic_key or theme_id required")
        cur = con.execute("INSERT INTO key_results(epic_key,theme_id,period_id,title,metric_key,source,unit,direction,baseline,target,"
                          "current,current_at,notes,owner,due,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (d.get("epic_key"), None if d.get("epic_key") else d.get("theme_id"), pid, d["title"], d.get("metric_key"), d["source"], d.get("unit"), d["direction"],
                           d.get("baseline"), d.get("target"), d.get("current"), d.get("current_at"), d.get("notes"),
                           d.get("owner"), d.get("due"), NOW(), NOW()))
        if d.get("current") is not None:
            con.execute("INSERT INTO kr_snapshots(kr_id,taken_at,value,reason) VALUES(?,?,?,?)",
                        (cur.lastrowid, d.get("current_at") or dt.date.today().isoformat(), d["current"], "manual"))
    return {"id": cur.lastrowid, "warnings": okr.kr_lint(d)}


@app.put("/api/krs/{kid}")
def edit_kr(kid: int, k: KrIn):
    cfg = load_config()
    d = _kr_fill_current(cfg, k.dict())
    with db.tx() as con:
        con.execute("UPDATE key_results SET title=?, metric_key=?, source=?, unit=?, direction=?, baseline=?, target=?, "
                    "current=COALESCE(?,current), current_at=COALESCE(?,current_at), notes=?, period_id=COALESCE(?,period_id), "
                    "owner=?, due=?, updated_at=? WHERE id=?",
                    (d["title"], d.get("metric_key"), d["source"], d.get("unit"), d["direction"], d.get("baseline"), d.get("target"),
                     d.get("current"), d.get("current_at"), d.get("notes"), d.get("period_id"), d.get("owner"), d.get("due"), NOW(), kid))
    return {"ok": True, "warnings": okr.kr_lint(d)}


@app.delete("/api/krs/{kid}")
def del_kr(kid: int):
    with db.tx() as con:
        con.execute("DELETE FROM kr_snapshots WHERE kr_id=?", (kid,))
        con.execute("DELETE FROM key_results WHERE id=?", (kid,))
    return {"ok": True}


class SnapIn(BaseModel):
    value: float
    taken_at: Optional[str] = None
    reason: str = "manual"


@app.post("/api/krs/{kid}/snapshot")
def kr_snapshot(kid: int, s: SnapIn):
    at = s.taken_at or dt.date.today().isoformat()
    with db.tx() as con:
        con.execute("INSERT INTO kr_snapshots(kr_id,taken_at,value,reason) VALUES(?,?,?,?)", (kid, at, s.value, s.reason))
        con.execute("UPDATE key_results SET current=?, current_at=?, updated_at=? WHERE id=? AND (current_at IS NULL OR current_at<=?)",
                    (s.value, at, NOW(), kid, at))
    return {"ok": True}


@app.post("/api/krs/refresh")
def krs_refresh():
    cfg = load_config()
    with db.tx() as con:
        n = okr.refresh_current(cfg, con)
    return {"snapshots": n}


@app.post("/api/epics/{key}/push-outcome")
def push_outcome(key: str):
    cfg = load_config()
    with db.connect() as con:
        krs = db.rows(con, "SELECT * FROM key_results WHERE epic_key=? ORDER BY id", (key,))
    if not krs:
        err("no key results on this epic")
    try:
        merged = jira_sync.push_outcome(cfg, key, krs)
    except Exception as e:  # noqa: BLE001
        err(e)
    with db.tx() as con:
        con.execute("UPDATE epics SET outcome=? WHERE key=?", (merged, key))
    return {"outcome": merged}


@app.get("/api/metrics/keys")
def metric_keys():
    return metrics.list_metric_keys(load_config())


@app.get("/api/metrics/series")
def metric_series(source: str, key: str):
    return {"series": metrics.series(load_config(), source, key)}


# ---------------- Retros ----------------
@app.post("/api/retros/backfill")
def retros_backfill():
    with db.tx() as con:
        n = retro.backfill(con)
    return {"opened": n}


@app.get("/api/retros/{key}")
def retro_get(key: str):
    cfg = load_config()
    with db.tx() as con:
        r = db.one(con, "SELECT * FROM retros WHERE epic_key=?", (key,))
        if not r:
            err("no retro for this epic")
        d = retro.detail(cfg, con, r)
        d["epic"] = db.one(con, "SELECT * FROM epics WHERE key=?", (key,))
    return d


@app.post("/api/retros/{key}/build")
def retro_build(key: str):
    cfg = load_config()
    try:
        with db.tx() as con:
            d = retro.build(cfg, con, key)
            d["epic"] = db.one(con, "SELECT * FROM epics WHERE key=?", (key,))
        return d
    except Exception as e:  # noqa: BLE001
        err(e)


class RetroIn(BaseModel):
    status: Optional[str] = None
    omit_reason: Optional[str] = None
    released_at: Optional[str] = None
    context_metrics: Optional[str] = None
    links: Optional[str] = None
    what_shipped: Optional[str] = None
    impact: Optional[str] = None
    learnings: Optional[str] = None
    verdict: Optional[str] = None


@app.put("/api/retros/{key}")
def retro_put(key: str, r: RetroIn):
    fields = {k: v for k, v in r.dict().items() if v is not None}
    if fields.get("status") not in (None, "pending", "omitted", "in_progress", "done"):
        err("bad status")
    with db.tx() as con:
        if not db.one(con, "SELECT 1 FROM retros WHERE epic_key=?", (key,)):
            e = db.one(con, "SELECT resolution, closed_at FROM epics WHERE key=?", (key,)) or {}
            retro.open_for(con, key, e.get("resolution"), e.get("closed_at"))
        if fields:
            con.execute(f"UPDATE retros SET {', '.join(k+'=?' for k in fields)}, updated_at=? WHERE epic_key=?",
                        (*fields.values(), NOW(), key))
    return {"ok": True}


@app.post("/api/themes/reorder")
def reorder_themes(order: list):
    with db.tx() as con:
        for i, tid in enumerate(order, 1):
            con.execute("UPDATE themes SET priority_rank=? WHERE id=?", (i, tid))
    return {"ok": True}


@app.delete("/api/themes/{tid}")
def del_theme(tid: int):
    with db.tx() as con:
        used = con.execute("SELECT COUNT(*) FROM scores WHERE theme_id=?", (tid,)).fetchone()[0]
        if used:
            err(f"theme is used by {used} epics; reassign first")
        con.execute("DELETE FROM themes WHERE id=?", (tid,))
        con.execute("UPDATE ideas SET theme_id=NULL WHERE theme_id=?", (tid,))
        ranks = [r["id"] for r in db.rows(con, "SELECT id FROM themes ORDER BY priority_rank")]
        for i, t in enumerate(ranks, 1):
            con.execute("UPDATE themes SET priority_rank=? WHERE id=?", (i, t))
    return {"ok": True}


# ---------------- jira ----------------
@app.post("/api/jira/pull")
def jira_pull():
    try:
        return jira_sync.pull(load_config())
    except Exception as e:  # noqa: BLE001
        err(e)


@app.post("/api/jira/push/preview")
def jira_push_preview():
    cfg = load_config()
    with db.connect() as con:
        _, _, comp = compute_all(con, cfg)
        cur = {e["key"]: e for e in db.rows(con, "SELECT key, priority, rank_pos FROM epics WHERE in_scope=1")}
    comp = [c for c in comp if not c["is_draft"]]
    return jira_sync.push_preview(cfg, comp, cur)


class PushIn(BaseModel):
    priorities: bool = True
    rank: bool = True
    keys: Optional[list] = None   # restrict priority changes to these keys


@app.post("/api/jira/push/apply")
def jira_push_apply(p: PushIn):
    cfg = load_config()
    pv = jira_push_preview()
    if p.keys is not None:
        pv["priorities"] = [c for c in pv["priorities"] if c["key"] in set(p.keys)]
    try:
        done = jira_sync.push_apply(cfg, pv, p.priorities, p.rank)
        jira_sync.pull(cfg)
    except Exception as e:  # noqa: BLE001
        err(e)
    return done


@app.get("/api/jira/status")
def jira_status():
    return {"pat": bool(jira_sync.load_pat(load_config())), "sources": jira_sync.PAT_SOURCES}


@app.get("/api/jira/teams")
def jira_teams(q: str = ""):
    """Portfolio Team options matching q (id + name) via Jira's JQL autocomplete."""
    cfg = load_config()
    pat = jira_sync.load_pat(cfg)
    if not pat:
        err(f"No Jira token found ({jira_sync.PAT_SOURCES})")
    try:
        import requests
        r = requests.get(f"{cfg['jira_base']}/rest/api/2/jql/autocompletedata/suggestions",
                         headers=jira_sync._hdr(pat), params={"fieldName": "Portfolio Team", "fieldValue": q}, timeout=30)
        r.raise_for_status()
        out = []
        for it in r.json().get("results", []):
            name = it.get("displayName", "").replace("<b>", "").replace("</b>", "")
            out.append({"id": it.get("value"), "name": name})
        return out
    except Exception as e:  # noqa: BLE001
        err(e)


# ---------------- setup ----------------
@app.get("/api/setup/status")
def setup_status():
    cfg = load_config()
    ws = Path(cfg.get("pr_workspace") or "")
    gh_ok = False
    if shutil.which("gh"):
        try:
            gh_ok = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, timeout=15).returncode == 0
        except (OSError, subprocess.SubprocessError):
            gh_ok = False
    scope_ok = bool(cfg.get("jira_project") or (cfg.get("epic_jql") or "").strip() or cfg.get("portfolio_team_ids"))
    checks = [
        {"id": "config_exists", "label": "data/config.json exists", "ok": (DATA / "config.json").exists(),
         "fix": "Save config once from this page (or run ./run.sh, which copies config.example.json)."},
        {"id": "teams_configured", "label": "Jira scope configured (project, team ids or epic JQL)", "ok": scope_ok,
         "fix": "Set the Jira project key below. Optional: team ids (team lookup) or a custom epic JQL."},
        {"id": "pat_found", "label": "Jira token found", "ok": bool(jira_sync.load_pat(cfg)),
         "fix": f"Put JIRA_API_TOKEN=<token> in {ENV_FILE} (never shared) or export it before ./run.sh. "
                "Jira Cloud also needs your Atlassian email in Settings."},
        {"id": "claude_cli", "label": "claude CLI on PATH", "ok": bool(shutil.which("claude")),
         "fix": "Install Claude Code, then restart the workbench so PATH is picked up."},
        {"id": "pr_workspace_exists", "label": "PM workspace exists", "ok": bool(ws.name) and ws.exists(),
         "fix": f"Click *Create workspace* (creates {ws or '~/pm-workspace'} with the PM Journey skills), or set another path."},
        {"id": "portfolio_context_exists", "label": "portfolio-context.md present (optional)", "ok": bool(ws.name) and (ws / "portfolio-context.md").exists(),
         "fix": "Created with the workspace. Fill the Priority Tiers table, then import it below."},
        {"id": "gh_auth", "label": "gh CLI authenticated (optional: spec repo PR sync)", "ok": gh_ok or not cfg.get("spec_repo"),
         "fix": "gh auth login — only needed when spec_repo is set."},
    ]
    return {"checks": checks, "ready": bool(cfg.get("demo")) or all(c["ok"] for c in checks if c["id"] in ("teams_configured", "pat_found")),
            "env_file": str(ENV_FILE), "pr_workspace": str(ws) if ws.name else ""}


@app.post("/api/setup/workspace")
def setup_workspace():
    """Create the PM workspace: folders the scanners read, the step skills, and a portfolio-context.md stub."""
    cfg = load_config()
    ws = Path(cfg.get("pr_workspace") or PR_WORKSPACE_DEFAULT).expanduser()
    for d in ("prds", "refined-prds", "reviews", "prd-validations", "generated-hlds", "epics", "research",
              "concept-accepts", "risk-reviews", "ux-briefs"):
        (ws / d).mkdir(parents=True, exist_ok=True)
    pc = ws / "portfolio-context.md"
    if not pc.exists():
        pc.write_text(PORTFOLIO_STUB)
    synced = ai_runner.sync_skills(ws)
    return {"workspace": str(ws), "skills": synced}


PORTFOLIO_STUB = """# Portfolio Context

What the team owns and how work is prioritised. The PM Journey skills read this file.

## Priority Tiers

| Tier | Initiative | Investment Theme | Parent Key | Status |
|---|---|---|---|---|
| P0 | | | | |

## Program Jira Keys

| Program | Jira Project | Key Prefix | Owner |
|---|---|---|---|
| | | | |
"""


@app.post("/api/setup/import-portfolio")
def setup_import_portfolio():
    """Create themes from portfolio-context.md Priority Tiers (initiative → theme, Parent Key → bepic_key)."""
    cfg = load_config()
    ws = Path(cfg.get("pr_workspace") or "")
    if not ws.name:
        err("PM workspace not configured")
    parsed = portfolio_context.parse(ws / "portfolio-context.md")
    if not parsed["tiers"]:
        err("No rows found in the Priority Tiers table of portfolio-context.md")
    created = 0
    with db.tx() as con:
        rank = (db.one(con, "SELECT MAX(priority_rank) AS m FROM themes") or {}).get("m") or 0
        for t in parsed["tiers"]:
            if db.one(con, "SELECT 1 FROM themes WHERE name=?", (t["initiative"],)):
                continue
            rank += 1
            bepic = t["program_epic"] if KEY_RE.fullmatch(t["program_epic"] or "") else None
            con.execute("INSERT INTO themes(name,description,priority_rank,bepic_key) VALUES(?,?,?,?)",
                        (t["initiative"], f"{t['tier']} · {t['theme']}".strip(" ·"), rank, bepic))
            created += 1
    return {"created": created, "tiers": len(parsed["tiers"]), "programs": parsed["programs"]}


@app.get("/api/export/xlsx")
def export_xlsx():
    cfg = load_config()
    with db.connect() as con:
        p, themes, comp = compute_all(con, cfg)
    out = DATA / "exports" / f"epic_prioritization_{dt.datetime.now():%Y%m%d-%H%M%S}.xlsx"
    xlsx_io.export_sheet([c for c in comp if not c["is_draft"]], p, themes, out)
    return FileResponse(str(out), filename=out.name)


@app.post("/api/import/xlsx")
async def import_xlsx(file: UploadFile = File(...)):
    """Import a legacy epic_prioritization.xlsx (scores, themes, weights). Explicit upload only."""
    dest = DATA / "uploads" / f"{dt.datetime.now():%Y%m%d-%H%M%S}_{Path(file.filename or 'import.xlsx').name}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(await file.read())
    try:
        return xlsx_io.import_sheet(dest, backup=False)
    except Exception as e:  # noqa: BLE001
        err(e)


# ---------------- config ----------------
@app.post("/api/jira/publish-epics")
def publish_epics(body: dict):
    """Called by /pm-requirements-accept: create epics + DoR-PASS stories from an epics JSON file."""
    try:
        return jira_sync.publish_epics_file(load_config(), body.get("file") or "", bool(body.get("dry_run")))
    except Exception as e:  # noqa: BLE001
        err(e)


@app.put("/api/config")
def put_config(c: dict):
    cfg = load_config()
    cfg.update(c)
    return save_config(cfg)


# ---------------- sources / ideas / groups ----------------
@app.post("/api/sources/upload")
async def upload_source(file: UploadFile = File(...), evidence_type: str = Form(None)):
    sid = ideas.ingest_file(file.filename, await file.read())
    _set_source_type(sid, evidence_type)
    return {"id": sid}


def _set_source_type(sid, evidence_type):
    if evidence_type in evidence.TYPE_LABEL:
        with db.tx() as con:
            con.execute("UPDATE sources SET evidence_type=? WHERE id=?", (evidence_type, sid))
            evidence.sync_source(con, sid)  # typing a source later backfills its ideas


class PasteIn(BaseModel):
    title: str = ""
    text: str
    evidence_type: Optional[str] = None


@app.post("/api/sources/paste")
def paste_source(p: PasteIn):
    sid = ideas.ingest_text(p.title, p.text)
    _set_source_type(sid, p.evidence_type)
    return {"id": sid}


class JiraSrcIn(BaseModel):
    keys: str
    evidence_type: Optional[str] = None


@app.post("/api/sources/jira")
def jira_source(p: JiraSrcIn):
    """Stories / defects as sources. Defects default to the support signal; anything else takes the chosen type."""
    cfg = load_config()
    keys = jira_sync.issue_keys(p.keys)
    if not keys:
        err("No Jira keys found. Enter keys or links, e.g. ACME-1234, ACME-1240")
    added, failed = [], []
    for k in keys:
        try:
            issue = jira_sync.fetch_issue_source(cfg, k)
        except Exception as e:  # noqa: BLE001
            failed.append({"key": k, "error": str(e)})
            continue
        sid = ideas.ingest_jira(issue)
        _set_source_type(sid, "support" if issue["is_defect"] else p.evidence_type)
        added.append({"id": sid, "key": k, "type": issue["type"]})
    if not added:
        err("; ".join(f"{f['key']}: {f['error']}" for f in failed))
    return {"added": added, "failed": failed}


@app.put("/api/sources/{sid}")
def edit_source(sid: int, body: dict):
    _set_source_type(sid, body.get("evidence_type"))
    return {"ok": True}


# ---------------- evidence ----------------
class EvidenceIn(BaseModel):
    ref: str
    type: str
    note: str = ""
    link: Optional[str] = None
    occurred_at: Optional[str] = None


@app.post("/api/evidence")
def add_evidence(e: EvidenceIn):
    try:
        with db.tx() as con:
            eid = evidence.add(con, e.ref, e.type, e.note, e.link, None, e.occurred_at)
    except ValueError as ex:
        err(ex)
    return {"id": eid}


@app.put("/api/evidence/{eid}")
def edit_evidence(eid: int, e: EvidenceIn):
    if e.type not in evidence.TYPE_LABEL:
        err("unknown evidence type")
    with db.tx() as con:
        con.execute("UPDATE evidence SET type=?, note=?, link=?, occurred_at=? WHERE id=?",
                    (e.type, e.note.strip(), e.link or None, e.occurred_at or None, eid))
    return {"ok": True}


@app.delete("/api/evidence/{eid}")
def del_evidence(eid: int):
    with db.tx() as con:
        con.execute("DELETE FROM evidence WHERE id=?", (eid,))
    return {"ok": True}


@app.get("/api/evidence")
def get_evidence(ref: str):
    with db.connect() as con:
        return {"items": evidence.for_refs(con, [ref]).get(ref, [])}


@app.get("/api/sources/{sid}")
def get_source(sid: int):
    with db.connect() as con:
        return db.one(con, "SELECT * FROM sources WHERE id=?", (sid,)) or err("not found")


@app.delete("/api/sources/{sid}")
def del_source(sid: int):
    with db.tx() as con:
        con.execute("DELETE FROM sources WHERE id=?", (sid,))
        con.execute("UPDATE ideas SET source_id=NULL WHERE source_id=?", (sid,))
    return {"ok": True}


class IdeaIn(BaseModel):
    title: str
    body: str = ""
    theme_id: Optional[int] = None
    source_id: Optional[int] = None


@app.post("/api/ideas")
def add_idea(i: IdeaIn):
    ids = ideas.add_ideas([{"title": i.title, "body": i.body}], i.source_id, i.theme_id)
    if i.source_id:
        with db.tx() as con:
            evidence.sync_source(con, i.source_id, ids)
    return {"ids": ids}


@app.put("/api/ideas/{iid}")
def edit_idea(iid: int, i: dict):
    allowed = {k: v for k, v in i.items() if k in ("title", "body", "theme_id", "group_id", "status")}
    if "theme_id" in allowed and allowed["theme_id"] and "status" not in allowed:
        allowed["status"] = "themed"
    if not allowed:
        return {"ok": True}
    with db.tx() as con:
        con.execute(f"UPDATE ideas SET {', '.join(k+'=?' for k in allowed)} WHERE id=?", (*allowed.values(), iid))
    return {"ok": True}


class GroupIn(BaseModel):
    name: str
    idea_ids: list
    theme_id: Optional[int] = None


@app.post("/api/groups")
def add_group(g: GroupIn):
    with db.tx() as con:
        cur = con.execute("INSERT INTO idea_groups(name,theme_id,created_at) VALUES(?,?,?)", (g.name, g.theme_id, NOW()))
        gid = cur.lastrowid
        for iid in g.idea_ids:
            con.execute("UPDATE ideas SET group_id=?, status='grouped' WHERE id=?", (gid, iid))
    return {"id": gid}


@app.put("/api/groups/{gid}")
def edit_group(gid: int, g: dict):
    allowed = {k: v for k, v in g.items() if k in ("name", "theme_id", "prd_id", "draft_id")}
    with db.tx() as con:
        if allowed:
            con.execute(f"UPDATE idea_groups SET {', '.join(k+'=?' for k in allowed)} WHERE id=?", (*allowed.values(), gid))
        if "add_ideas" in g:
            for iid in g["add_ideas"]:
                con.execute("UPDATE ideas SET group_id=?, status='grouped' WHERE id=?", (gid, iid))
        if "remove_ideas" in g:
            for iid in g["remove_ideas"]:
                con.execute("UPDATE ideas SET group_id=NULL, status='themed' WHERE id=?", (iid,))
    return {"ok": True}


@app.delete("/api/groups/{gid}")
def del_group(gid: int):
    with db.tx() as con:
        con.execute("UPDATE ideas SET group_id=NULL, status='themed' WHERE group_id=?", (gid,))
        con.execute("DELETE FROM idea_groups WHERE id=?", (gid,))
    return {"ok": True}


# ---------------- drafts ----------------
class DraftIn(BaseModel):
    summary: str
    description: str = ""
    product_owner: str = ""
    acceptance_criteria: str = ""
    outcome: str = ""
    labels: str = ""
    theme_id: Optional[int] = None
    group_id: Optional[int] = None


@app.post("/api/drafts")
def add_draft(d: DraftIn):
    with db.tx() as con:
        cur = con.execute("INSERT INTO draft_epics(summary,description,product_owner,acceptance_criteria,outcome,labels,"
                          "theme_id,group_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                          (d.summary, d.description, d.product_owner, d.acceptance_criteria, d.outcome, d.labels,
                           d.theme_id, d.group_id, NOW(), NOW()))
        did = cur.lastrowid
        con.execute("INSERT OR IGNORE INTO scores(epic_ref, theme_id) VALUES(?,?)", (f"draft:{did}", d.theme_id))
        if d.group_id:
            con.execute("UPDATE idea_groups SET draft_id=? WHERE id=?", (did, d.group_id))
            evidence.carry_group(con, d.group_id, f"draft:{did}")
    return {"id": did}


@app.put("/api/drafts/{did}")
def edit_draft(did: int, d: DraftIn):
    with db.tx() as con:
        con.execute("UPDATE draft_epics SET summary=?,description=?,product_owner=?,acceptance_criteria=?,outcome=?,"
                    "labels=?,theme_id=?,updated_at=? WHERE id=?",
                    (d.summary, d.description, d.product_owner, d.acceptance_criteria, d.outcome, d.labels,
                     d.theme_id, NOW(), did))
        con.execute("UPDATE scores SET theme_id=? WHERE epic_ref=?", (d.theme_id, f"draft:{did}"))
    return {"ok": True}


@app.delete("/api/drafts/{did}")
def del_draft(did: int):
    with db.tx() as con:
        con.execute("DELETE FROM draft_epics WHERE id=?", (did,))
        con.execute("DELETE FROM scores WHERE epic_ref=?", (f"draft:{did}",))
        con.execute("UPDATE idea_groups SET draft_id=NULL WHERE draft_id=?", (did,))
    return {"ok": True}


@app.post("/api/drafts/{did}/create-jira")
def create_jira(did: int, body: dict = None):
    cfg = load_config()
    body = body or {}
    with db.connect() as con:
        d = db.one(con, "SELECT d.*, t.bepic_key FROM draft_epics d LEFT JOIN themes t ON t.id=d.theme_id WHERE d.id=?", (did,))
        if not d:
            err("draft not found")
        sc = db.one(con, "SELECT * FROM scores WHERE epic_ref=?", (f"draft:{did}",))
    missing = jira_sync.validate_draft(d, cfg)
    if missing:
        err("Missing mandatory fields: " + ", ".join(missing))
    team_id = body.get("team_id") or next(iter(cfg["portfolio_team_ids"]), None)
    with db.connect() as con:
        ev_items = evidence.for_refs(con, [f"draft:{did}"]).get(f"draft:{did}", [])
    if ev_items:  # validation trail travels with the epic into Jira
        d = {**d, "description": (d.get("description") or "").rstrip() + "\n\n" + evidence.render_wiki(ev_items)}
    try:
        res = jira_sync.create_epic(cfg, d, int(team_id) if team_id else None)
    except Exception as e:  # noqa: BLE001
        err(e)
    with db.tx() as con:
        con.execute("UPDATE draft_epics SET jira_key=?, updated_at=? WHERE id=?", (res["key"], NOW(), did))
        evidence.carry(con, f"draft:{did}", res["key"])
        if sc:
            con.execute("INSERT OR REPLACE INTO scores(epic_ref,theme_id,sv,ui,urg,conf,effort,park,raise_p1,notes,updated_at)"
                        " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (res["key"], sc["theme_id"], sc["sv"], sc["ui"], sc["urg"], sc["conf"], sc["effort"],
                         sc["park"], sc["raise_p1"], sc["notes"], NOW()))
            con.execute("DELETE FROM scores WHERE epic_ref=?", (f"draft:{did}",))
        con.execute("UPDATE ideas SET status='promoted' WHERE group_id=(SELECT group_id FROM draft_epics WHERE id=?)", (did,))
    try:
        jira_sync.pull(cfg)
    except Exception:  # noqa: BLE001
        pass
    return res


# ---------------- AI ----------------
EXTRACT_SYS = ("You extract distinct product ideas from PM notes or meeting transcripts. Answer with JSON only: "
               "a list of objects {\"title\": short imperative title, \"body\": 1-3 sentence description of the "
               "problem/opportunity, \"quote\": a short verbatim supporting quote or empty string}. "
               "Merge duplicates. Skip logistics and chit-chat. Max 25 items.")
CLUSTER_SYS = ("You assign product ideas to strategic themes. Answer with JSON only: "
               "{\"assignments\": [{\"idea_id\": int, \"theme\": existing theme name or null, \"confidence\": 0-1}], "
               "\"new_themes\": [{\"name\": str, \"description\": str, \"idea_ids\": [int]}]}. "
               "Prefer existing themes; propose a new theme only for 3+ ideas that fit none.")
DRAFT_SYS = ("You draft a Jira Epic for a product team. Answer with JSON only: {\"summary\": str (<=100 chars), "
             "\"description\": Jira wiki markup with h3. headings Problem, Proposal, Scope, \"acceptance_criteria\": "
             "wiki bullet list, \"outcome\": 1-2 sentences of measurable outcome, \"scores\": {\"sv\":1-5,\"ui\":1-5,"
             "\"urg\":1-5,\"conf\":1-5,\"effort\":\"S|M|L\",\"rationale\": str}}.")


OBJECTIVE_SYS = ("You write OKR Objectives for a product team. Answer with JSON only: {\"objective\": one inspiring, "
                 "outcome-focused sentence (<=140 chars) starting with a verb, no metrics}. Base it on the theme name, "
                 "description and the epics listed.")
KR_SYS = ("You propose Key Results for a Jira epic. Answer with JSON only: {\"krs\": [{\"title\": str, \"source\": "
          "\"baselines_jsonl\"|\"data_js\"|\"manual\", \"metric_key\": one of the AVAILABLE metric keys or null for manual, "
          "\"direction\": \"up\"|\"down\", \"unit\": str|null, \"target_hint\": str}]}. 2-3 KRs, measurable, prefer available "
          "metrics; use manual only when nothing available fits.")
RETRO_SYS = ("You write a concise product retrospective from Jira facts. Answer with JSON only: {\"what_shipped\": 2-3 sentences, "
             "\"impact\": 1-2 sentences referencing the KR readings if present, \"learnings\": 2-4 bullet-style sentences, "
             "\"verdict\": \"hit\"|\"partial\"|\"miss\"|\"too early\"}.")
PROPOSE_SYS = ("You propose OKR Objectives for a product team from Jira epics that have no objective yet, grouped by their "
               "parent issue (initiative / business epic, \"BEpic\"). Answer with JSON only: {\"proposals\": [{\"name\": short objective name (<=60 chars), "
               "\"description\": one sentence on what the work covers, \"objective\": one inspiring, outcome-focused sentence "
               "(<=140 chars) starting with a verb, no metrics, \"bepic_key\": the BEpic key or null, \"epic_keys\": [str], "
               "\"rationale\": one sentence on why these epics belong together}], \"assign_existing\": [{\"theme\": existing "
               "objective name, \"epic_keys\": [str]}]}. Rules: at most one proposal per UNCLAIMED BEpic, containing that "
               "BEpic's epics. Never propose a new objective for a BEpic that is claimed by an existing objective; list its "
               "epics under assign_existing for that objective instead. Group the epics with no BEpic by outcome into "
               "further proposals with bepic_key null, or into assign_existing when an existing objective clearly fits. "
               "Use each epic key at most once, only keys that are listed, and never reuse an existing objective name.")
PROPOSE_GROUP_CAP = 40   # epics shown per BEpic in the prompt
_BEPIC_CACHE: dict = {}  # key -> fetch_bepic result; preview and run both build the prompt


def _bepic_info(cfg, key: str) -> dict:
    """BEpic title for the prompt; any Jira failure (no PAT, 404, offline) degrades to the bare key."""
    if key not in _BEPIC_CACHE:
        try:
            _BEPIC_CACHE[key] = jira_sync.fetch_bepic(cfg, key)
        except Exception:  # noqa: BLE001
            return {"key": key, "summary": "", "description": ""}
    return _BEPIC_CACHE[key]


def _propose_context(cfg, con) -> dict:
    """Unthemed in-scope epics grouped by BEpic, each BEpic flagged claimed (on a theme's bepic_key) or not."""
    themes = db.rows(con, "SELECT id, name, description, bepic_key FROM themes ORDER BY priority_rank")
    claimed: dict = {}
    for t in themes:
        if t["bepic_key"]:
            claimed.setdefault(t["bepic_key"], t["name"])
    groups: dict = {}
    for e in _unthemed_epics(con):
        groups.setdefault(e["bepic"] or "", []).append(e)
    return {"themes": themes, "claimed": claimed, "groups": groups,
            "bepics": {k: _bepic_info(cfg, k) for k in groups if k and k not in claimed}}


def _propose_prompt(ctx: dict) -> str:
    out = ["Existing objectives:"] + [f"- {t['name']}" + (f" (BEpic {t['bepic_key']})" if t["bepic_key"] else "")
                                      + (f": {t['description']}" if t["description"] else "") for t in ctx["themes"]]
    if not ctx["themes"]:
        out.append("- none")
    out.append("\nEpics with no objective:")
    for key, eps in ctx["groups"].items():
        if not key:
            out.append("\nNo BEpic:")
        elif key in ctx["claimed"]:
            out.append(f"\nBEpic {key} [claimed by existing objective \"{ctx['claimed'][key]}\"]:")
        else:
            b = ctx["bepics"].get(key) or {}
            title = f" \"{b['summary']}\"" if b.get("summary") else ""
            desc = " ".join((b.get("description") or "").split())[:400]
            out.append(f"\nBEpic {key}{title} [UNCLAIMED]:" + (f"\n  About: {desc}" if desc else ""))
        out += [f"- {e['key']} {e['summary']} ({e['status']})" for e in eps[:PROPOSE_GROUP_CAP]]
        if len(eps) > PROPOSE_GROUP_CAP:
            out.append(f"- … and {len(eps) - PROPOSE_GROUP_CAP} more epics under this BEpic")
    return "\n".join(out)


def _sanitize_proposals(data, ctx: dict) -> dict:
    """Keep only what the rules allow: known unthemed epics used once, one new objective per unclaimed BEpic, new names."""
    data = data if isinstance(data, dict) else {}
    known = {e["key"]: e for eps in ctx["groups"].values() for e in eps}
    by_name = {t["name"].lower(): t for t in ctx["themes"]}
    used, names, bepics, proposals, existing = set(), set(by_name), set(), [], []

    def take(keys):
        got = [k for k in dict.fromkeys(str(k) for k in (keys or [])) if k in known and k not in used]
        used.update(got)
        return [{"key": k, "summary": known[k]["summary"]} for k in got]

    for p in data.get("proposals") or []:
        name = str((p or {}).get("name") or "").strip() if isinstance(p, dict) else ""
        bepic = (p.get("bepic_key") or None) if name else None
        if not name or name.lower() in names or (bepic and (bepic in ctx["claimed"] or bepic in bepics or bepic not in ctx["groups"])):
            continue
        eps = take(p.get("epic_keys"))
        if bepic:  # the whole BEpic comes along on create, so show every unthemed epic under it
            rest = [e["key"] for e in ctx["groups"][bepic] if e["key"] not in used]
            eps += take(rest)
            bepics.add(bepic)
        if not eps:
            continue
        names.add(name.lower())
        proposals.append({"name": name, "description": str(p.get("description") or ""), "objective": str(p.get("objective") or ""),
                          "bepic_key": bepic, "bepic_title": (ctx["bepics"].get(bepic) or {}).get("summary", "") if bepic else "",
                          "epics": eps, "rationale": str(p.get("rationale") or "")})
    for a in data.get("assign_existing") or []:
        t = by_name.get(str((a or {}).get("theme") or "").lower()) if isinstance(a, dict) else None
        eps = take(a.get("epic_keys")) if t else []
        if eps:
            existing.append({"theme_id": t["id"], "theme": t["name"], "epics": eps})
    return {"proposals": proposals, "assign_existing": existing, "unthemed": len(known), "leftover": len(known) - len(used)}


def _idea_prompt_block(con, idea_ids):
    q = ",".join("?" * len(idea_ids))
    rows = db.rows(con, f"SELECT id,title,body FROM ideas WHERE id IN ({q})", tuple(idea_ids))
    return "\n".join(f"- [{r['id']}] {r['title']}: {r['body']}" for r in rows)


class AiReq(BaseModel):
    kind: str            # extract | cluster | draft | objective | propose_objectives | suggest_krs | retro_summary
    source_id: Optional[int] = None
    idea_ids: Optional[list] = None
    group_id: Optional[int] = None
    theme_id: Optional[int] = None
    epic_key: Optional[str] = None
    confirm: bool = False


def _build_prompt(cfg, r: AiReq):
    with db.connect() as con:
        if r.kind == "extract":
            s = db.one(con, "SELECT * FROM sources WHERE id=?", (r.source_id,)) or err("source not found")
            return EXTRACT_SYS, f"Source: {s['filename']} ({s['kind']})\n\n{s['text'][:60000]}"
        if r.kind == "cluster":
            ids = r.idea_ids or [i["id"] for i in db.rows(con, "SELECT id FROM ideas WHERE theme_id IS NULL AND status!='archived'")]
            if not ids:
                err("no unthemed ideas")
            themes = db.rows(con, "SELECT name, description FROM themes ORDER BY priority_rank")
            tl = "\n".join(f"- {t['name']}: {t['description'] or ''}" for t in themes)
            return CLUSTER_SYS, f"Existing themes:\n{tl}\n\nIdeas:\n{_idea_prompt_block(con, ids)}"
        if r.kind == "draft":
            ids = r.idea_ids or [i["id"] for i in db.rows(con, "SELECT id FROM ideas WHERE group_id=?", (r.group_id,))]
            if not ids:
                err("no ideas selected")
            g = db.one(con, "SELECT g.*, t.name AS theme FROM idea_groups g LEFT JOIN themes t ON t.id=g.theme_id WHERE g.id=?",
                       (r.group_id,)) if r.group_id else None
            ctx = f"Group: {g['name']} (theme: {g['theme']})\n" if g else ""
            return DRAFT_SYS, ctx + "Ideas:\n" + _idea_prompt_block(con, ids)
        if r.kind == "objective":
            t = db.one(con, "SELECT * FROM themes WHERE id=?", (r.theme_id,)) or err("theme not found")
            eps = db.rows(con, "SELECT e.key, e.summary FROM epics e JOIN scores s ON s.epic_ref=e.key WHERE s.theme_id=? AND e.in_scope=1", (r.theme_id,))
            return OBJECTIVE_SYS, (f"Theme: {t['name']}\nDescription: {t['description'] or ''}\nCurrent objective: {t['objective'] or ''}\n"
                                   "Epics:\n" + "\n".join(f"- {e['key']} {e['summary']}" for e in eps[:25]))
        if r.kind == "propose_objectives":
            ctx = _propose_context(cfg, con)
            if not ctx["groups"]:
                err("no epics without an objective; every in-scope epic already has one")
            return PROPOSE_SYS, _propose_prompt(ctx)
        if r.kind == "suggest_krs":
            e = db.one(con, "SELECT * FROM epics WHERE key=?", (r.epic_key,)) or err("epic not found")
            keys = metrics.list_metric_keys(cfg)
            return KR_SYS, (f"Epic {e['key']}: {e['summary']}\nStatus: {e['status']}\nOutcome field: {(e['outcome'] or '')[:1500]}\n\n"
                            f"AVAILABLE metric keys:\nbaselines_jsonl: {', '.join(keys['baselines_jsonl'])}\n"
                            f"data_js: {', '.join(keys['data_js'][:80])}")
        if r.kind == "retro_summary":
            rr = db.one(con, "SELECT * FROM retros WHERE epic_key=?", (r.epic_key,)) or err("no retro")
            d = retro.detail(cfg, con, rr)
            e = db.one(con, "SELECT summary FROM epics WHERE key=?", (r.epic_key,)) or {}
            life = d.get("lifecycle") or {}
            readings = [{"kr": x["kr"]["title"], "baseline": x["kr"]["baseline"], "target": x["kr"]["target"],
                         "readings": {k: (v or {}).get("value") for k, v in x["readings"].items()}} for x in d["kr_readings"]]
            return RETRO_SYS, (f"Epic {r.epic_key}: {e.get('summary')}\nLifecycle: {json.dumps({k: life.get(k) for k in ('created','first_dev','closed','days_analysis','days_dev','reopens')})}\n"
                               f"Scope: {json.dumps(d.get('scope') and {k: d['scope'].get(k) for k in ('stories','done','added_after_dev_start')})}\n"
                               f"KR readings: {json.dumps(readings)}\nContext metrics: {json.dumps(d.get('context'))}\n"
                               f"Description: {life.get('description','')[:2500]}\nRecent comments: {json.dumps(life.get('comments', [])[-8:])[:3000]}")
    err("unknown kind")


@app.post("/api/ai/preview")
def ai_preview(r: AiReq):
    cfg = load_config()
    sysm, prompt = _build_prompt(cfg, r)
    return ai_runner.preview(cfg, r.kind, sysm + prompt)


@app.post("/api/ai/run")
def ai_run(r: AiReq):
    if not r.confirm:
        err("confirm required")
    cfg = load_config()
    sysm, prompt = _build_prompt(cfg, r)
    try:
        data = ai_runner.run_haiku(cfg, r.kind, prompt, sysm)
    except Exception as e:  # noqa: BLE001
        err(e)
    if r.kind == "extract":
        items = [d for d in data if isinstance(d, dict) and d.get("title")] if isinstance(data, list) else []
        ids = ideas.add_ideas(items, r.source_id)
        with db.tx() as con:  # the source itself is the first piece of evidence for each idea
            evidence.sync_source(con, r.source_id, ids)
        return {"ids": ids, "count": len(items)}
    if r.kind == "cluster":
        applied = 0
        with db.tx() as con:
            names = {t["name"].lower(): t["id"] for t in db.rows(con, "SELECT id,name FROM themes")}
            for a in data.get("assignments", []):
                tid = names.get((a.get("theme") or "").lower())
                if tid and a.get("idea_id"):
                    con.execute("UPDATE ideas SET theme_id=?, status='themed' WHERE id=? AND theme_id IS NULL", (tid, a["idea_id"]))
                    applied += 1
        return {"applied": applied, "new_themes": data.get("new_themes", [])}
    if r.kind == "objective":
        with db.tx() as con:
            con.execute("UPDATE themes SET objective=? WHERE id=?", (data.get("objective"), r.theme_id))
        return data
    if r.kind == "propose_objectives":  # nothing saved: the PM ticks proposals and the UI posts them to /api/themes
        with db.connect() as con:
            return _sanitize_proposals(data, _propose_context(cfg, con))
    return data  # draft / suggest_krs / retro_summary: UI fills the form


class SkillReq(BaseModel):
    skill: str
    file: str = ""
    files: list = []
    text: str = ""
    bepic: str = ""
    project: str = ""
    group_id: Optional[int] = None
    launch: bool = False


@app.post("/api/skills/command")
def skill_command(r: SkillReq):
    cfg = load_config()
    args = {"file": r.file, "files": r.files, "text": r.text, "bepic": r.bepic, "project": r.project or cfg.get("jira_project", "PS")}
    try:
        if r.skill == "generate-prd" and r.group_id:
            args["file"] = str(ideas.bundle_group(r.group_id))
            if not args["bepic"]:
                with db.connect() as con:
                    g = db.one(con, "SELECT t.bepic_key FROM idea_groups g LEFT JOIN themes t ON t.id=g.theme_id WHERE g.id=?", (r.group_id,))
                    args["bepic"] = (g or {}).get("bepic_key") or ""
        if not args["file"] and not args["files"] and r.skill not in ("pm-guide", "poc", "discovery", "requirements-accept"):
            err("file required")
        return ai_runner.launch_skill(cfg, r.skill, args) if r.launch else ai_runner.skill_command(cfg, r.skill, args)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        err(e)


# ---------------- PRDs ----------------
def _scan_all(cfg):
    link = artifacts.checkpoint_aliases(Path(cfg.get("pr_workspace") or ""))
    a = prd_pipeline.scan(cfg, link)
    b = artifacts.scan(cfg, link)
    return {"prds": a["found"], "artifacts": b["found"], "scanned_at": b["scanned_at"], "error": b.get("error")}


@app.post("/api/prds/scan")
@app.post("/api/artifacts/scan")
def prds_scan():
    """Rescan the PM workspace: PRDs first (so artifacts can link to them), then every other artifact."""
    try:
        return _scan_all(load_config())
    except Exception as e:  # noqa: BLE001
        err(e)


@app.get("/api/artifacts/{aid}/text")
def artifact_text(aid: int):
    with db.connect() as con:
        try:
            return artifacts.text_of(con, aid)
        except KeyError as e:
            err(e)


class InitiativeIn(BaseModel):
    poc_url: Optional[str] = None
    poc_branch: Optional[str] = None
    notes: Optional[str] = None
    title: Optional[str] = None
    bepic_key: Optional[str] = None
    owner: Optional[str] = None
    target_period_id: Optional[int] = None   # okr_periods.id; 0 clears
    skip: Optional[dict] = None      # {step_id: reason}; empty reason clears the skip


@app.put("/api/initiatives/{slug}")
def initiative_edit(slug: str, i: InitiativeIn):
    with db.tx() as con:
        con.execute("INSERT OR IGNORE INTO initiatives(slug,updated_at) VALUES(?,?)", (slug, NOW()))
        cur = db.one(con, "SELECT * FROM initiatives WHERE slug=?", (slug,))
        sk = json.loads(cur.get("skipped_json") or "{}")
        for k, v in (i.skip or {}).items():
            if v:
                sk[k] = v
            else:
                sk.pop(k, None)
        con.execute("UPDATE initiatives SET poc_url=COALESCE(?,poc_url), poc_branch=COALESCE(?,poc_branch), notes=COALESCE(?,notes), "
                    "title_override=COALESCE(?,title_override), title=COALESCE(?,title), bepic_override=COALESCE(?,bepic_override), "
                    "bepic_key=COALESCE(?,bepic_key), owner=COALESCE(?,owner), target_period_id=COALESCE(?,target_period_id), "
                    "skipped_json=?, updated_at=? WHERE slug=?",
                    (i.poc_url, i.poc_branch, i.notes, i.title, i.title, i.bepic_key, i.bepic_key, i.owner,
                     i.target_period_id, json.dumps(sk), NOW(), slug))
        if i.target_period_id == 0:
            con.execute("UPDATE initiatives SET target_period_id=NULL WHERE slug=?", (slug,))
    return {"ok": True}


# ---------------- decision / risk / blocker log ----------------
class LogIn(BaseModel):
    ref: Optional[str] = None        # initiative slug or epic key (required on POST)
    kind: Optional[str] = None       # decision | risk | blocker
    text: Optional[str] = None
    owner: Optional[str] = None
    due: Optional[str] = None
    status: Optional[str] = None     # open | closed


@app.post("/api/log")
def log_add(l: LogIn):
    if not l.ref:
        err("ref required")
    try:
        with db.tx() as con:
            lid = worklog.add(con, l.ref, l.kind or "decision", l.text or "", l.owner, l.due)
    except ValueError as e:
        err(e)
    return {"id": lid}


@app.put("/api/log/{lid}")
def log_edit(lid: int, l: LogIn):
    if l.status and l.status not in ("open", "closed"):
        err("status must be open or closed")
    try:
        with db.tx() as con:
            ok = worklog.update(con, lid, text=l.text, owner=l.owner, due=l.due, status=l.status, kind=l.kind)
    except ValueError as e:
        err(e)
    if not ok:
        raise HTTPException(status_code=404, detail="log entry not found")
    return {"ok": True}


@app.delete("/api/log/{lid}")
def log_del(lid: int):
    with db.tx() as con:
        worklog.delete(con, lid)
    return {"ok": True}


class ArtLink(BaseModel):
    table: str = "artifacts"   # artifacts | prds
    id: int


@app.post("/api/initiatives/{slug}/link")
def initiative_link(slug: str, l: ArtLink):
    """Manually assign an artifact / PRD to an initiative (sticky across rescans)."""
    if l.table not in ("artifacts", "prds"):
        err("table must be artifacts or prds")
    with db.tx() as con:
        con.execute("INSERT OR IGNORE INTO initiatives(slug,updated_at) VALUES(?,?)", (slug, NOW()))
        if l.table == "artifacts":
            con.execute("UPDATE artifacts SET initiative=?, initiative_override=? WHERE id=?", (slug, slug, l.id))
        else:
            con.execute("UPDATE prds SET initiative=? WHERE id=?", (slug, l.id))
    return {"ok": True}


# ---------------- story readiness (Definition of Ready) ----------------
@app.post("/api/epics/{key}/dor")
def epic_dor(key: str):
    """Fetch the epic + its stories from Jira and run the 7-point DoR heuristics. On demand only; cached."""
    cfg = load_config()
    try:
        epic = jira_sync.fetch_epic_fields(cfg, key)
        stories = jira_sync.fetch_children(cfg, key, full=True)
    except Exception as e:  # noqa: BLE001
        err(e)
    with db.connect() as con:
        published = dor.published_keys(con)
        prd_meta = dor.prd_meta_for_epic(con, key)
    res = dor.assess(epic, stories, published, prd_meta)
    with db.tx() as con:
        con.execute("INSERT OR REPLACE INTO story_dor(epic_key,fetched_at,summary_json,stories_json) VALUES(?,?,?,?)",
                    (key, NOW(), json.dumps(res["summary"]), json.dumps(res["stories"])))
    return {**res, "fetched_at": NOW()}


@app.get("/api/epics/{key}/dor")
def epic_dor_get(key: str):
    with db.connect() as con:
        r = db.one(con, "SELECT * FROM story_dor WHERE epic_key=?", (key,))
    if not r:
        return {"summary": None, "stories": [], "fetched_at": None}
    return {"summary": json.loads(r["summary_json"] or "{}"), "stories": json.loads(r["stories_json"] or "[]"), "fetched_at": r["fetched_at"]}


class LinkIn(BaseModel):
    epic_key: str
    remove: bool = False


@app.post("/api/prds/{pid}/link")
def prd_link(pid: int, l: LinkIn):
    with db.tx() as con:
        if l.remove:
            con.execute("DELETE FROM prd_epics WHERE prd_id=? AND epic_key=?", (pid, l.epic_key))
        else:
            con.execute("INSERT OR IGNORE INTO prd_epics(prd_id,epic_key) VALUES(?,?)", (pid, l.epic_key))
    return {"ok": True}


@app.post("/api/prds/sync-github")
def prds_sync_github():
    try:
        return github_refs.sync(load_config())
    except Exception as e:  # noqa: BLE001
        err(e)


class PrdEdit(BaseModel):
    note: Optional[str] = None
    github_url: Optional[str] = None
    pr_url: Optional[str] = None


@app.put("/api/prds/{pid}")
def prd_edit(pid: int, e: PrdEdit):
    fields = {k: v for k, v in e.dict().items() if v is not None}
    if not fields:
        return {"ok": True}
    with db.tx() as con:
        con.execute(f"UPDATE prds SET {', '.join(k+'=?' for k in fields)} WHERE id=?", (*[v or None for v in fields.values()], pid))
    return {"ok": True}


@app.get("/api/prds/{pid}/text")
def prd_text(pid: int):
    with db.connect() as con:
        p = db.one(con, "SELECT path, github_url FROM prds WHERE id=?", (pid,)) or err("not found")
    if p["path"].startswith("gh:"):
        return {"text": f"Stored in GitHub: {p['github_url']}"}
    return {"text": Path(p["path"]).read_text(errors="replace")[:20000]}


# ---------------- export / import JSON ----------------
@app.get("/api/export/json")
def export_json():
    with db.connect() as con:
        out = {t: db.rows(con, f"SELECT * FROM {t}") for t in
               ("themes", "config_params", "scores", "ideas", "idea_groups", "draft_epics", "sources")}
    out["exported_at"] = NOW()
    path = DATA / "exports" / f"workbench_{dt.datetime.now():%Y%m%d-%H%M%S}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1))
    return FileResponse(str(path), filename=path.name)


@app.post("/api/import/json")
async def import_json(file: UploadFile = File(...)):
    data = json.loads((await file.read()).decode())
    n = 0
    with db.tx() as con:
        for t in data.get("themes", []):
            con.execute("INSERT INTO themes(name,description,priority_rank,bepic_key) VALUES(?,?,?,?) "
                        "ON CONFLICT(name) DO UPDATE SET description=excluded.description, bepic_key=excluded.bepic_key",
                        (t["name"], t.get("description", ""), t["priority_rank"], t.get("bepic_key")))
            n += 1
        for p in data.get("config_params", []):
            con.execute("INSERT OR REPLACE INTO config_params(key,value) VALUES(?,?)", (p["key"], p["value"]))
        names = {r["name"]: r["id"] for r in db.rows(con, "SELECT id,name FROM themes")}
        old_theme = {t["id"]: t["name"] for t in data.get("themes", [])}
        for s in data.get("scores", []):
            if s["epic_ref"].startswith("draft:"):
                continue
            tid = names.get(old_theme.get(s.get("theme_id")))
            con.execute("INSERT OR IGNORE INTO scores(epic_ref) VALUES(?)", (s["epic_ref"],))
            con.execute("UPDATE scores SET theme_id=COALESCE(?,theme_id), sv=COALESCE(?,sv), ui=COALESCE(?,ui), urg=COALESCE(?,urg),"
                        " conf=COALESCE(?,conf), effort=COALESCE(?,effort), notes=COALESCE(?,notes) WHERE epic_ref=?",
                        (tid, s.get("sv"), s.get("ui"), s.get("urg"), s.get("conf"), s.get("effort"), s.get("notes"), s["epic_ref"]))
            n += 1
    return {"imported": n}
