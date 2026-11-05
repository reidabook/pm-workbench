"""Import the legacy epic_prioritization.xlsx into SQLite; export a values-only copy."""
import datetime as dt
import shutil
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", module="openpyxl")
import openpyxl  # noqa: E402

from . import db
from .paths import DATA

PARAM_LABELS = {
    "Weight: Strategic Value": "w_sv", "Weight: User Impact": "w_ui", "Weight: Urgency": "w_urg",
    "Weight: Theme Priority": "w_theme", "Weight: Confidence": "w_conf",
    "Effort factor: S": "effort_S", "Effort factor: M": "effort_M", "Effort factor: L": "effort_L",
    "Band: P1 top fraction": "band_p1", "Band: P2 cumulative fraction": "band_p2",
    "Band: P3 cumulative fraction": "band_p3", "Confidence gap threshold (<=)": "conf_gap",
    "Weight: Validation": "w_val",
    "Validation pts: Usage data": "val_w_user_data", "Validation pts: Customer feedback": "val_w_customer",
    "Validation pts: Prospect feedback": "val_w_prospect", "Validation pts: Support / defects": "val_w_support",
    "Validation pts: Competitor": "val_w_competitor", "Validation pts: Internal ask": "val_w_internal",
}
HEADERS = {  # sheet header -> our field
    "Key": "key", "Summary": "summary", "BEPIC": "bepic", "Status": "status",
    "PRD": "prd_flag", "Theme": "theme", "Park (top/bottom)": "park",
    "Strategic Value (1-5)": "sv", "User Impact (1-5)": "ui", "Urgency (1-5)": "urg",
    "Confidence (1-5)": "conf", "Effort (S/M/L)": "effort", "Notes": "notes",
    "Raise to P1 (commitment/blocker)": "raise_p1", "Labels": "labels", "Portfolio Team": "team",
    "Weighted Score": "x_score", "Rank": "x_rank", "Computed Priority": "x_priority",
    "Gap Flag": "x_gap", "Theme Score": "x_theme_score",
}


def read_sheet(path: Path) -> dict:
    """Return {'params': {...}, 'themes': [(name, rank)], 'rows': [dict]} using cached values."""
    wb = openpyxl.load_workbook(path, data_only=True)
    cfg = wb["Config"]
    params, themes = {}, []
    for r in cfg.iter_rows(min_row=1, max_row=cfg.max_row, values_only=True):
        if r[0] in PARAM_LABELS and r[1] is not None:
            params[PARAM_LABELS[r[0]]] = float(r[1])
        if len(r) > 4 and r[3] and isinstance(r[4], (int, float)) and r[3] != "Theme":
            themes.append((str(r[3]).strip(), int(r[4])))
    ws = wb["Epics"]
    hdr = [str(c.value).strip() if c.value else "" for c in ws[1]]
    idx = {HEADERS[h]: i for i, h in enumerate(hdr) if h in HEADERS}
    rows = []
    for r in ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True):
        if not r[idx["key"]]:
            continue
        d = {f: r[i] for f, i in idx.items()}
        for k in ("sv", "ui", "urg", "conf"):
            v = d.get(k)
            d[k] = int(v) if isinstance(v, (int, float)) else None
        for k in ("theme", "park", "effort", "notes", "raise_p1", "labels", "bepic", "team",
                  "status", "prd_flag", "summary"):
            d[k] = (str(d[k]).strip() if d.get(k) not in (None, "") else "")
        rows.append(d)
    return {"params": params, "themes": themes, "rows": rows}


def import_sheet(path: Path, backup=True) -> dict:
    if backup and path.exists():
        bdir = DATA / "backups"
        bdir.mkdir(exist_ok=True)
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(path, bdir / f"epic_prioritization.pre-workbench.{stamp}.xlsx")
    data = read_sheet(path)
    now = dt.datetime.now().isoformat(timespec="seconds")
    with db.tx() as con:
        for k, v in data["params"].items():
            con.execute("INSERT OR REPLACE INTO config_params(key,value) VALUES(?,?)", (k, v))
        for name, rank in data["themes"]:
            con.execute("INSERT INTO themes(name,priority_rank) VALUES(?,?) "
                        "ON CONFLICT(name) DO UPDATE SET priority_rank=excluded.priority_rank",
                        (name, rank))
        theme_ids = {r["name"]: r["id"] for r in db.rows(con, "SELECT id,name FROM themes")}
        for d in data["rows"]:
            con.execute(
                "INSERT INTO epics(key,summary,status,labels,team,bepic,synced_at) VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET summary=COALESCE(epics.summary,excluded.summary)",
                (d["key"], d["summary"], d["status"], d["labels"], d["team"], d["bepic"], None))
            con.execute(
                "INSERT OR REPLACE INTO scores(epic_ref,theme_id,sv,ui,urg,conf,effort,park,raise_p1,notes,updated_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (d["key"], theme_ids.get(d["theme"]), d["sv"], d["ui"], d["urg"], d["conf"],
                 d["effort"] or None, d["park"] or None, d["raise_p1"] or None, d["notes"] or None, now))
            if d.get("prd_flag"):
                db.set_meta(con, f"prd_flag:{d['key']}", d["prd_flag"])
        db.set_meta(con, "imported_from", str(path))
        db.set_meta(con, "imported_at", now)
    return {"params": len(data["params"]), "themes": len(data["themes"]), "epics": len(data["rows"])}


EXPORT_HEADERS = ["Key", "Summary", "BEPIC", "Status", "PRD", "Theme", "Theme Score",
                  "Park (top/bottom)", "Strategic Value (1-5)", "User Impact (1-5)", "Urgency (1-5)",
                  "Confidence (1-5)", "Effort (S/M/L)", "Effort Factor", "Weighted Score", "Rank",
                  "Computed Priority", "Gap Flag", "Notes", "Raise to P1 (commitment/blocker)",
                  "Labels", "Portfolio Team", "Validation (1-5)", "Evidence"]


def export_sheet(computed: list, params: dict, themes: list, out: Path) -> Path:
    """Values-only workbook in the legacy layout (no formulas) so old tooling can still read it."""
    wb = openpyxl.Workbook()
    cfg = wb.active
    cfg.title = "Config"
    cfg.append(["Parameter", "Value", None, "Theme", "Priority"])
    inv = {v: k for k, v in PARAM_LABELS.items()}
    plist = [(inv[k], params[k]) for k in inv if k in params]
    for i in range(max(len(plist), len(themes))):
        row = list(plist[i]) if i < len(plist) else [None, None]
        row += [None]
        row += [themes[i]["name"], themes[i]["priority_rank"]] if i < len(themes) else [None, None]
        cfg.append(row)
    ws = wb.create_sheet("Epics")
    ws.append(EXPORT_HEADERS)
    for c in computed:
        ws.append([c["key"], c.get("summary"), c.get("bepic"), c.get("status"), c.get("prd_flag"),
                   c.get("theme_name"), c.get("theme_score"), c.get("park"), c.get("sv"), c.get("ui"),
                   c.get("urg"), c.get("conf"), c.get("effort"), c.get("effort_factor"), c.get("score"),
                   c.get("rank"), c.get("priority"), c.get("gap"), c.get("notes"), c.get("raise_p1"),
                   c.get("labels"), c.get("team"), c.get("validation"),
                   "; ".join(f"{e['type']}: {e['note']}" for e in (c.get("evidence") or []))])
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out
