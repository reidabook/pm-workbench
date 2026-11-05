"""Find PRDs and their review / validation artifacts; derive a stage per PRD."""
import datetime as dt
import json
import re
from pathlib import Path

from . import db
from .paths import KEY_RE, is_epic_key, prd_dirs
# PRD metadata-table rows written by review-prd / validate-prd that drive downstream steps
META_ROWS = {"ux_required": r"UX\s*Required", "legal_required": r"Legal\s*(?:Review\s*)?Required",
             "hld_ownership": r"HLD\s*Ownership", "flag_intent": r"Flag\s*Intent", "flag_name": r"Flag\s*Name",
             "spec_status": r"Spec\s*Status"}


def base_slug(stem: str) -> str:
    """Initiative slug from a skill-generated file name: strips HLD_ prefix and any trailing _vN / _refined / date /
    _review / _design_review / _hld_questions / _epics suffixes (repeatedly); lowercases; '_' → '-'.
    'HLD_acme_x_v1_2026-09-21_design_review' → 'acme-x'."""
    s = re.sub(r"^HLD[_-]", "", stem or "", flags=re.I)
    suffix = re.compile(r"[_-](?:v\d+|refined|\d{4}-\d{2}-\d{2}|design_review|hld_questions|review|epics|stories|dependency_map|validation)$", re.I)
    prev = None
    while prev != s:
        prev, s = s, suffix.sub("", s)
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _meta_rows(text: str) -> dict:
    """Values of known `| **Label** | value |` rows in the first ~120 lines (metadata block)."""
    head = "\n".join(text.splitlines()[:120])
    out = {}
    for key, pat in META_ROWS.items():
        m = re.search(rf"\|\s*\**{pat}\**\s*\|\s*([^|\n]+?)\s*\|", head, re.I)
        if m:
            out[key] = m.group(1).strip().strip("*")
    return out


def _frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    fm = {}
    for line in text[3:end].splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm


def _title(text: str, fm: dict, path: Path) -> str:
    if fm.get("title"):
        return fm["title"]
    m = re.search(r"^#\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else path.stem


def _epic_keys(text: str, known: set = None, not_epics: set = frozenset()) -> set:
    """Epic keys named in the metadata block: an 'Epic Key' / 'Key' / 'Jira' table row, else any
    epic key in the first 80 lines (frontmatter + metadata table).
    `not_epics` (stories / defects added as Inbox sources) are never linked. When `known` epics are
    given, a key that is only mentioned in passing must be one of them; an explicit row is trusted."""
    keys = set()
    for m in re.finditer(r"\|\s*\*{0,2}(?:Epic Key|Key|Jira)\*{0,2}\s*\|\s*([^|]+)\|", text):
        keys |= {k for k in KEY_RE.findall(m.group(1)) if is_epic_key(k)}
    if not keys:
        head = "\n".join(text.splitlines()[:80])
        keys |= {k for k in KEY_RE.findall(head) if is_epic_key(k) and (not known or k in known)}
    return keys - set(not_epics)


TRACKED = {"skill:review-prd": "review_at", "skill:validate-prd": "validation_at"}
RUNNING_WINDOW_H = 2  # a launch with no output after this long is treated as abandoned, not running


def _mtime_iso(p: Path):
    return dt.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds") if p else None


def settle_runs(con) -> int:
    """A launched review / validate run is done once its report is newer than the launch. Runs are
    matched to a PRD by the file path in the command, so the skill can be re-run any number of times."""
    n = 0
    prds = db.rows(con, "SELECT path, review_at, validation_at FROM prds")
    for r in db.rows(con, f"SELECT id, kind, cmd, started FROM ai_runs WHERE status='launched' AND kind IN ({','.join('?' * len(TRACKED))})",
                     tuple(TRACKED)):
        col = TRACKED[r["kind"]]
        done = next((p[col] for p in prds if p[col] and p["path"] in (r["cmd"] or "") and p[col] >= r["started"]), None)
        if done:
            con.execute("UPDATE ai_runs SET status='done', finished=? WHERE id=?", (done, r["id"]))
            n += 1
    return n


def pending_runs(con) -> int:
    """Skill launches still waiting on their output (any skill), within the running window."""
    since = (dt.datetime.now() - dt.timedelta(hours=RUNNING_WINDOW_H)).isoformat(timespec="seconds")
    return con.execute("SELECT COUNT(*) FROM ai_runs WHERE status='launched' AND kind LIKE 'skill:%' AND started>=?", (since,)).fetchone()[0]


def run_summary(con, prds: list) -> None:
    """Attach per-PRD review / validate history: how many launches, and whether one is still running."""
    since = (dt.datetime.now() - dt.timedelta(hours=RUNNING_WINDOW_H)).isoformat(timespec="seconds")
    runs = db.rows(con, f"SELECT kind, cmd, status, started FROM ai_runs WHERE kind IN ({','.join('?' * len(TRACKED))}) ORDER BY id",
                   tuple(TRACKED))
    for p in prds:
        p["runs"] = {}
        for kind in TRACKED:
            mine = [r for r in runs if r["kind"] == kind and p["path"] in (r["cmd"] or "")]
            live = [r["started"] for r in mine if r["status"] == "launched" and r["started"] >= since]
            p["runs"][kind.split(":")[1]] = {"count": len(mine), "running_since": live[-1] if live else None}


STAGE_ORDER = ["drafted", "reviewed", "validated", "in-pr", "published"]


def collapse_refined(prds: list) -> None:
    """review-prd writes a refined copy into refined-prds/, so one PRD shows up as two files. Per
    initiative the newest refined file becomes the primary row and carries the family's review /
    validation status, runs and linked epics; the others get `superseded_by` and are listed on the
    primary as `versions` so the original stays one click away."""
    fam = {}
    for p in prds:
        if p.get("initiative") and p.get("source") != "github":
            fam.setdefault(p["initiative"], []).append(p)
    for members in fam.values():
        refined = [p for p in members if "refined-prds" in Path(p["path"]).parts]
        if not refined or len(members) < 2:
            continue
        main = max(refined, key=lambda p: p.get("mtime") or 0)
        rest = sorted((p for p in members if p is not main), key=lambda p: p.get("mtime") or 0, reverse=True)
        main["versions"] = [{"id": p["id"], "path": p["path"], "title": p["title"],
                             "label": "earlier refined" if p in refined else "original"} for p in rest]
        for p in rest:
            p["superseded_by"] = main["id"]
            for col in ("review_at", "validation_at"):
                if p.get(col) and p[col] > (main.get(col) or ""):
                    main[col] = p[col]
                    if col == "validation_at":
                        main["validation_result"] = p.get("validation_result")
            if STAGE_ORDER.index(p.get("stage") or "drafted") > STAGE_ORDER.index(main.get("stage") or "drafted"):
                main["stage"] = p["stage"]
            for f in ("note", "bepic_key", "pr_url", "pr_state", "github_url"):
                main[f] = main.get(f) or p.get(f)
            main["epics"] = sorted(set(main.get("epics") or []) | set(p.get("epics") or []))
            for k, r in (p.get("runs") or {}).items():
                m = main.setdefault("runs", {}).setdefault(k, {"count": 0, "running_since": None})
                m["count"] += r["count"]
                m["running_since"] = max(filter(None, [m["running_since"], r["running_since"]]), default=None)


def scan(cfg, link: dict = None) -> dict:
    ws = Path(cfg.get("pr_workspace") or "")
    if link is None:
        from .artifacts import checkpoint_aliases
        link = checkpoint_aliases(ws)
    aliases = link["aliases"]
    reviews = {p.stem.replace("_review", ""): p for p in (ws / "reviews").glob("*_review.md")} if ws.name else {}
    validations = sorted((ws / "prd-validations").glob("*.md")) if ws.name else []
    now = dt.datetime.now().isoformat(timespec="seconds")
    found = 0
    with db.tx() as con:
        known = {r["key"] for r in con.execute("SELECT key FROM epics")}
        # Jira stories / defects added as Inbox sources get quoted in PRDs; they are evidence, not epics
        not_epics = {r["url"].rsplit("/", 1)[-1] for r in con.execute("SELECT url FROM sources WHERE kind='jira' AND url IS NOT NULL")} - known
        if not_epics:
            con.execute(f"DELETE FROM prd_epics WHERE epic_key IN ({','.join('?' * len(not_epics))})", tuple(not_epics))
        for d in prd_dirs(cfg):
            if not d.exists():
                continue
            for p in sorted(d.rglob("*.md")):
                try:
                    text = p.read_text(errors="replace")
                except OSError:
                    continue
                fm = _frontmatter(text)
                if fm.get("type") != "prd" and "prd-validations" not in p.parts and not p.name.startswith("epic-"):
                    continue
                if "prd-validations" in p.parts or "reviews" in p.parts:
                    continue
                title = _title(text, fm, p)
                slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:50]
                review = reviews.get(p.stem) or next((v for k, v in reviews.items() if k.lower() == slug), None)
                val = next((v for v in reversed(validations) if v.stem.lower().startswith(slug)), None)
                result = None
                if val:
                    vt = val.read_text(errors="replace")[:4000]
                    result = "PASS" if re.search(r"\bPASS(ED)?\b", vt) and not re.search(r"\bFAIL(ED)?\b", vt[:800]) else \
                             ("FAIL" if re.search(r"\bFAIL(ED)?\b", vt) else "UNKNOWN")
                pr_url = fm.get("spec_pr_url") or None
                meta = _meta_rows(text)
                b = base_slug(p.stem)
                initiative = aliases.get(str(p)) or aliases.get(b) or aliases.get(re.sub(r"^epic-", "", b)) or re.sub(r"^epic-", "", b)
                # frontmatter PR link = pushed to a PR; only the GitHub sync can promote to 'published' (merged)
                stage = "in-pr" if pr_url else ("validated" if val else ("reviewed" if review else "drafted"))
                prev = db.one(con, "SELECT stage, pr_url, pr_state FROM prds WHERE path=?", (str(p),))
                if prev and prev["pr_url"]:
                    if prev["pr_state"] == "merged":
                        stage = "published"
                    elif stage != "in-pr" and prev["stage"] == "in-pr":
                        stage = "in-pr"
                con.execute(
                    "INSERT INTO prds(path,title,bepic_key,stage,review_path,validation_path,validation_result,pr_url,mtime,scanned_at,initiative,meta_json)"
                    " VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET title=excluded.title,"
                    "bepic_key=excluded.bepic_key,stage=excluded.stage,review_path=excluded.review_path,"
                    "validation_path=excluded.validation_path,validation_result=excluded.validation_result,"
                    "pr_url=COALESCE(excluded.pr_url,prds.pr_url),mtime=excluded.mtime,scanned_at=excluded.scanned_at,"
                    "initiative=excluded.initiative,meta_json=excluded.meta_json",
                    (str(p), title, fm.get("bepic_key") or None, stage, str(review) if review else None,
                     str(val) if val else None, result, pr_url, p.stat().st_mtime, now, initiative, json.dumps(meta)))
                con.execute("UPDATE prds SET review_at=?, validation_at=? WHERE path=?", (_mtime_iso(review), _mtime_iso(val), str(p)))
                pid = db.one(con, "SELECT id FROM prds WHERE path=?", (str(p),))["id"]
                for k in _epic_keys(text, known, not_epics) | (set(KEY_RE.findall(p.name)) - not_epics):
                    if is_epic_key(k):
                        con.execute("INSERT OR IGNORE INTO prd_epics(prd_id,epic_key) VALUES(?,?)", (pid, k))
                found += 1
        settle_runs(con)
        db.set_meta(con, "prd_scan_at", now)
    return {"found": found, "scanned_at": now}
