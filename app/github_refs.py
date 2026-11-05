"""Specs (PRD / HLD) published to the optional spec repo (config `spec_repo`, e.g. your-org/product-specs):
file on main (merged) or PR (open). Uses the `gh` CLI (already authenticated). Read-only against GitHub."""
import base64
import datetime as dt
import json
import re
import subprocess

from . import db
from .paths import is_epic_key, is_parent_key
from .prd_pipeline import KEY_RE, _frontmatter, _title

ARTIFACT_RE = re.compile(r"(?:/|-)(prd|hld)\.md$")


def _gh(*args) -> str:
    r = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=120)
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[:400] or "gh failed")
    return r.stdout


FIELDS = "number,title,state,url,mergedAt,headRefName,files"


def list_prs(repo: str, authors: list, extra: list = None, limit=60) -> list:
    """PRs by the given authors plus explicitly listed PR numbers/URLs (any author, any state)."""
    out, seen = [], set()

    def add(pr):
        files = [f["path"] for f in pr.get("files", []) if ARTIFACT_RE.search(f["path"])]
        if files and pr["number"] not in seen:
            pr["artifacts"] = files
            seen.add(pr["number"])
            out.append(pr)

    for a in authors or ["@me"]:
        for pr in json.loads(_gh("pr", "list", "-R", repo, "--author", a, "--state", "all", "--limit", str(limit), "--json", FIELDS)):
            add(pr)
    for n in extra or []:
        num = str(n).rstrip("/").split("/")[-1]
        add(json.loads(_gh("pr", "view", num, "-R", repo, "--json", FIELDS)))
    return out


def fetch_file(repo: str, path: str, ref: str) -> str:
    raw = _gh("api", f"repos/{repo}/contents/{path}?ref={ref}", "--jq", ".content")
    return base64.b64decode(raw).decode("utf-8", errors="replace")


def norm_title(t: str) -> str:
    """Match key for local ↔ GitHub titles: drop quotes/dashes/'Feature EPIC:' prefix, collapse space."""
    t = (t or "").lower()
    t = re.sub(r"^\s*feature epic:\s*", "", t)
    t = re.sub(r"^\s*[a-z][a-z0-9]{1,9}-\d+\s*[—–\-:]*\s*", "", t)
    t = re.sub(r"[\"“”'‘’`—–\-:(),.&/]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def slug_title(path: str) -> str:
    folder = path.split("/")[-2]
    folder = re.sub(r"^[A-Z][A-Z0-9]{1,9}-\d+-", "", folder)
    return folder.replace("-", " ").title()


def _upsert_hld(con, repo, pr, path, ref, pr_state, now):
    """HLDs in spec-repo PRs → artifacts(kind='hld'); matched to a local HLD by normalised title."""
    try:
        text = fetch_file(repo, path, ref)
        fm = _frontmatter(text)
        title = _title(text, fm, type("P", (), {"stem": slug_title(path)})())
    except Exception:  # noqa: BLE001
        text, fm, title = "", {}, slug_title(path)
    blob = f"https://github.com/{repo}/blob/{ref}/{path}"
    bepic = fm.get("bepic_key") or next((k for k in KEY_RE.findall(path) if is_parent_key(k)), None)
    nt = norm_title(title)
    local = [a for a in db.rows(con, "SELECT id,title FROM artifacts WHERE kind='hld' AND source='local'") if norm_title(a["title"]) == nt]
    if local:
        for a in local:
            con.execute("UPDATE artifacts SET pr_url=?, github_url=?, pr_state=?, result=?, bepic_key=COALESCE(bepic_key,?), scanned_at=? WHERE id=?",
                        (pr["url"], blob, pr_state, "merged" if pr_state == "merged" else "in-pr", bepic, now, a["id"]))
        return
    prd = db.one(con, "SELECT initiative FROM prds WHERE pr_url=? AND initiative IS NOT NULL", (pr["url"],))
    con.execute("INSERT INTO artifacts(path,kind,title,initiative,bepic_key,result,pr_url,pr_state,github_url,source,mtime,scanned_at,meta_json)"
                " VALUES(?,?,?,?,?,?,?,?,?,'github',0,?,'{}') ON CONFLICT(path) DO UPDATE SET title=excluded.title,pr_url=excluded.pr_url,"
                "pr_state=excluded.pr_state,result=excluded.result,github_url=excluded.github_url,bepic_key=COALESCE(artifacts.bepic_key,excluded.bepic_key),scanned_at=excluded.scanned_at",
                (f"gh:{repo}:{path}", "hld", title, (prd or {}).get("initiative"), bepic, "merged" if pr_state == "merged" else "in-pr",
                 pr["url"], pr_state, blob, now))


def sync(cfg) -> dict:
    repo = (cfg.get("spec_repo") or "").strip()
    if not repo:
        return {"prs": 0, "created": 0, "updated": 0, "synced_at": None, "skipped": "no spec_repo configured"}
    extra = list(cfg.get("github_prs") or [])
    with db.connect() as con:  # PRs already referenced by local PRD frontmatter (spec_pr_url)
        for r in db.rows(con, "SELECT DISTINCT pr_url FROM prds WHERE pr_url LIKE ?", (f"https://github.com/{repo}/pull/%",)):
            n = r["pr_url"].rstrip("/").split("/")[-1]
            if n.isdigit() and int(n) not in extra and n not in extra:
                extra.append(int(n))
    prs = list_prs(repo, cfg.get("github_pr_authors") or ["@me"], extra)
    now = dt.datetime.now().isoformat(timespec="seconds")
    created = updated = 0
    with db.tx() as con:
        local = {}
        for p in db.rows(con, "SELECT * FROM prds WHERE source IS NULL OR source='local'"):
            local.setdefault(norm_title(p["title"]), []).append(p)
        for pr in prs:
            merged = bool(pr.get("mergedAt"))
            ref = "main" if merged else pr["headRefName"]
            pr_state = "merged" if merged else pr["state"].lower()
            for path in pr["artifacts"]:
                m = ARTIFACT_RE.search(path)
                if not m:
                    continue
                if m.group(1) == "hld":
                    _upsert_hld(con, repo, pr, path, ref, pr_state, now)
                    continue
                try:
                    text = fetch_file(repo, path, ref)
                    fm = _frontmatter(text)
                    title = _title(text, fm, type("P", (), {"stem": slug_title(path)})())
                except Exception:  # noqa: BLE001
                    text, fm, title = "", {}, slug_title(path)
                blob = f"https://github.com/{repo}/blob/{ref}/{path}"
                keys = {k for k in KEY_RE.findall(path) if is_epic_key(k)}
                head = "\n".join(text.splitlines()[:80])
                keys |= {k for k in KEY_RE.findall(head) if is_epic_key(k)}
                bepic = fm.get("bepic_key") or next((k for k in KEY_RE.findall(path) if is_parent_key(k)), None)
                stage = "published" if merged else "in-pr"
                locs = local.get(norm_title(title), [])
                if locs:
                    pids = []
                    for loc in locs:  # original + refined copies all reference the same PR
                        con.execute("UPDATE prds SET pr_url=?, github_url=?, pr_state=?, stage=CASE WHEN ? THEN 'published' ELSE "
                                    "CASE WHEN stage IN ('validated','published') THEN stage ELSE 'in-pr' END END, "
                                    "bepic_key=COALESCE(bepic_key,?), scanned_at=? WHERE id=?",
                                    (pr["url"], blob, pr_state, merged, bepic, now, loc["id"]))
                        pids.append(loc["id"])
                        updated += 1
                    # link epic keys to every matched copy
                    for extra in pids[1:]:
                        for k in keys:
                            con.execute("INSERT OR IGNORE INTO prd_epics(prd_id,epic_key) VALUES(?,?)", (extra, k))
                    pid = pids[0]
                else:
                    gpath = f"gh:{repo}:{path}"
                    con.execute("INSERT INTO prds(path,title,bepic_key,stage,pr_url,github_url,pr_state,source,mtime,scanned_at) "
                                "VALUES(?,?,?,?,?,?,?,?,0,?) ON CONFLICT(path) DO UPDATE SET title=excluded.title,"
                                "stage=excluded.stage,pr_url=excluded.pr_url,github_url=excluded.github_url,"
                                "pr_state=excluded.pr_state,bepic_key=COALESCE(prds.bepic_key,excluded.bepic_key),scanned_at=excluded.scanned_at",
                                (gpath, title, bepic, stage, pr["url"], blob, pr_state, "github", now))
                    pid = db.one(con, "SELECT id FROM prds WHERE path=?", (gpath,))["id"]
                    created += 1
                for k in keys:
                    con.execute("INSERT OR IGNORE INTO prd_epics(prd_id,epic_key) VALUES(?,?)", (pid, k))
        db.set_meta(con, "github_sync_at", now)
    return {"prs": len(prs), "created": created, "updated": updated, "synced_at": now}
