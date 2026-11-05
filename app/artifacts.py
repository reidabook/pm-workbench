"""Scan the PM workspace for every PM Journey artifact except PRDs (prd_pipeline owns those).

Kinds: checkpoint · pm-context · refinement-plan · research · ca · competitive · risk-review · ux-brief ·
prd-review · prd-validation · hld · hld-questions · hld-review · epics-json · jira-manifest.

Initiative linkage (strongest first): checkpoint frontmatter (initiative.slug + input artifact paths) →
validation report `| Source |` path → `<slug>/` directory → base slug of the file name. Manual override via
initiatives table (artifact_links).
"""
import datetime as dt
import json
import re
from pathlib import Path

from . import db
from .paths import is_epic_key
from .prd_pipeline import KEY_RE, _epic_keys, _frontmatter, _title, base_slug

DETECTORS = [  # (glob relative to workspace, kind)
    ("*/checkpoints/*.md", "checkpoint"),
    ("*/pm-context.md", "pm-context"),
    ("*/refinement-plan.md", "refinement-plan"),
    ("research/*.md", "research"),
    ("concept-accepts/*.md", "ca"),
    ("competitive-research/*.md", "competitive"),
    ("risk-reviews/*.md", "risk-review"),
    ("ux-briefs/*.md", "ux-brief"),
    ("reviews/*.md", "prd-review"),          # refined by name: *_design_review → hld-review, *hld_questions* → hld-questions
    ("prd-validations/*.md", "prd-validation"),
    ("generated-hlds/*.md", "hld"),
    ("hlds/*.md", "hld"),
    ("epics/*.json", "epics-json"),
    ("jira-manifest.json", "jira-manifest"),
]
HLD_VERDICT_RANK = {"ok": 0, "requires_manual_review": 1, "blocked": 2}
HLD_RESULT = ["APPROVED", "REQUIRES_MANUAL_REVIEW", "BLOCKED"]


# ---------- parsers ----------
def parse_checkpoint(text: str) -> dict:
    """Light YAML-ish reader for PM Journey checkpoint files (no yaml dependency)."""
    fm = text[3:text.find("\n---", 3)] if text.startswith("---") else text
    g = lambda k: (re.search(rf"^{k}:\s*(.+)$", fm, re.M) or [None, ""])[1].strip().strip('"')  # noqa: E731
    slug = (re.search(r"^initiative:\s*\n(?:.*\n)*?\s+slug:\s*(\S+)", fm, re.M) or [None, ""])[1]
    tracker = (re.search(r"^\s+tracker_ref:\s*(\S+)", fm, re.M) or [None, ""])[1]
    gate = (re.search(r"^gate:\s*\n(?:.*\n)*?\s+result:\s*(\S+)", fm, re.M) or [None, ""])[1]
    inputs = re.findall(r"^\s+-\s+role:\s*input\s*\n\s+path:\s*\"?([^\"\n]+)\"?", fm, re.M)
    return {"skill": re.sub(r"^[\w-]+:", "", g("skill")), "plugin_version": g("plugin_version"),
            "slug": slug, "tracker_ref": tracker if KEY_RE.match(tracker or "") else "", "gate": gate.lower(),
            "inputs": [i.strip() for i in inputs], "updated_at": g("updated_at")}


def parse_validation(text: str) -> dict:
    head = text[:6000]
    res = re.search(r"\|\s*Gate Result\s*\|\s*\**\s*(PASS|FAIL)", head, re.I)
    src = re.search(r"\|\s*Source\s*\|\s*([^|\n]+?)\s*\|", head)
    poc = re.search(r"\|\s*POC Confidence\s*\|\s*([^|\n]+?)\s*\|", head)
    init = re.search(r"initiative\s*`([a-z0-9-]+)`", head, re.I)
    return {"result": res.group(1).upper() if res else None, "source": (src.group(1).strip() if src else ""),
            "poc_confidence": poc.group(1).strip() if poc else None, "slug": init.group(1) if init else ""}


def parse_hld_review(text: str) -> dict:
    """Aggregate `## Persona Verdicts` rows: any blocked → BLOCKED; any requires_manual_review → that; else APPROVED."""
    m = re.search(r"^##\s+Persona Verdicts\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    verdicts = {}
    if m:
        for row in re.findall(r"^\|([^|\n]+)\|([^|\n]*)\|", m.group(1), re.M):
            v = row[1].strip().lower().replace(" ", "_").strip("*`")
            if v in HLD_VERDICT_RANK:
                verdicts[row[0].strip().strip("*")] = v
    if not verdicts:
        return {"result": None, "verdicts": {}}
    return {"result": HLD_RESULT[max(HLD_VERDICT_RANK[v] for v in verdicts.values())], "verdicts": verdicts}


def summarize_epics_json(data) -> dict:
    epics = data.get("epics") if isinstance(data, dict) else (data if isinstance(data, list) else [])
    epics = epics or []
    stories = [s for e in epics for s in (e.get("stories") or [])] if epics and isinstance(epics[0], dict) else []
    dor = {}
    for s in stories:
        k = (s.get("dor_status") or s.get("dor") or "unknown")
        k = k if isinstance(k, str) else str(k.get("status", "unknown"))
        dor[k.upper()] = dor.get(k.upper(), 0) + 1
    keys = sorted({s.get("jira_key") for s in stories if s.get("jira_key")} | {e.get("jira_key") for e in epics if isinstance(e, dict) and e.get("jira_key")})
    return {"epics": len(epics), "stories": len(stories), "dor": dor, "jira_keys": keys,
            "bepic": (data.get("bepic") or data.get("business_epic") or "") if isinstance(data, dict) else ""}


def summarize_manifest(data) -> dict:
    """jira-manifest.json → {epics: {EPIC_KEY: [story keys]}, stories: n}. Tolerates several shapes."""
    out = {}
    items = data.get("issues") or data.get("stories") or data.get("created") or [] if isinstance(data, dict) else data
    if isinstance(items, dict):
        items = [{"key": k, **(v if isinstance(v, dict) else {"title": v})} for k, v in items.items()]
    for it in items or []:
        if not isinstance(it, dict):
            continue
        key = it.get("key") or it.get("jira_key") or it.get("issue_key")
        parent = it.get("epic") or it.get("epic_key") or it.get("parent") or it.get("epic_link") or ""
        if key and KEY_RE.match(str(key)):
            out.setdefault(str(parent), []).append(str(key))
    return {"epics": out, "stories": sum(len(v) for v in out.values())}


# ---------- linkage ----------
def checkpoint_aliases(ws: Path) -> dict:
    """{base_slug(input file) or initiative dir → initiative slug} from every checkpoint; plus tracker refs."""
    aliases, trackers = {}, {}
    if not ws.name or not ws.exists():
        return {"aliases": aliases, "trackers": trackers}
    for p in ws.glob("*/checkpoints/*.md"):
        try:
            cp = parse_checkpoint(p.read_text(errors="replace"))
        except OSError:
            continue
        slug = cp["slug"] or p.parent.parent.name
        aliases[p.parent.parent.name] = slug
        for i in cp["inputs"]:
            aliases[base_slug(Path(i).stem)] = slug
            aliases[str(Path(i))] = slug
        if cp["tracker_ref"]:
            trackers[slug] = cp["tracker_ref"]
    return {"aliases": aliases, "trackers": trackers}


def initiative_for(path: Path, title: str, aliases: dict, explicit: str = "") -> str:
    if explicit:
        return aliases.get(explicit, explicit)
    if str(path) in aliases:
        return aliases[str(path)]
    b = base_slug(path.stem)
    return aliases.get(b) or aliases.get(re.sub(r"^epic-", "", b)) or re.sub(r"^epic-", "", b)


# ---------- scan ----------
def scan(cfg, link: dict = None) -> dict:
    ws = Path(cfg.get("pr_workspace") or "")
    link = link or checkpoint_aliases(ws)
    aliases = link["aliases"]
    now = dt.datetime.now().isoformat(timespec="seconds")
    found, seen = 0, set()
    if not ws.name or not ws.exists():
        return {"found": 0, "scanned_at": now, "error": "workspace not found"}
    with db.tx() as con:
        prd_titles = {}
        for r in db.rows(con, "SELECT path, title, initiative FROM prds WHERE initiative IS NOT NULL"):
            prd_titles[base_slug(r["title"])] = r["initiative"]
        for glob, kind in DETECTORS:
            for p in sorted(ws.glob(glob)):
                if not p.is_file() or str(p) in seen:
                    continue
                seen.add(str(p))
                try:
                    text = p.read_text(errors="replace")
                except OSError:
                    continue
                fm = _frontmatter(text) if p.suffix == ".md" else {}
                title = _title(text, fm, p) if p.suffix == ".md" else p.stem
                k, result, initiative, meta, epic_keys, bepic = kind, None, None, {}, set(), fm.get("bepic_key")
                if kind == "checkpoint":
                    cp = parse_checkpoint(text)
                    k, result, initiative = "checkpoint", cp["gate"] or None, cp["slug"] or p.parent.parent.name
                    meta = {"skill": cp["skill"], "plugin_version": cp["plugin_version"], "inputs": cp["inputs"], "updated_at": cp["updated_at"]}
                    title = f"{cp['skill'] or p.stem} checkpoint"
                    if cp["tracker_ref"]:
                        epic_keys.add(cp["tracker_ref"])
                elif kind in ("pm-context", "refinement-plan"):
                    initiative = aliases.get(p.parent.name, p.parent.name)
                elif kind == "prd-review":
                    n = p.stem.lower()
                    k = "hld-review" if "design_review" in n else ("hld-questions" if "hld_questions" in n else "prd-review")
                    if k == "hld-review":
                        hr = parse_hld_review(text)
                        result, meta = hr["result"], {"verdicts": hr["verdicts"]}
                    initiative = initiative_for(p, title, aliases)
                elif kind == "prd-validation":
                    v = parse_validation(text)
                    result, meta = v["result"], {"source": v["source"], "poc_confidence": v["poc_confidence"]}
                    src = Path(v["source"]) if v["source"] else None
                    initiative = initiative_for(src, title, aliases, v["slug"]) if src else initiative_for(p, title, aliases, v["slug"])
                    epic_keys |= _epic_keys(text)
                elif kind == "hld":
                    if fm.get("type") and fm["type"] != "hld":
                        continue
                    meta = {kk: vv for kk, vv in fm.items() if kk.startswith("spec_")}
                    bepic = bepic or fm.get("spec_parent_key")
                    initiative = prd_titles.get(base_slug(title)) or initiative_for(p, title, aliases)
                    epic_keys |= _epic_keys(text)
                    result = "in-pr" if fm.get("spec_pr_url") else None
                elif kind == "epics-json":
                    try:
                        meta = summarize_epics_json(json.loads(text))
                    except ValueError:
                        continue
                    result = f"{meta['epics']} epics / {meta['stories']} stories"
                    epic_keys |= {x for x in meta["jira_keys"] if is_epic_key(x)}
                    bepic = bepic or (meta["bepic"] or None)
                    initiative = initiative_for(p, title, aliases)
                elif kind == "jira-manifest":
                    try:
                        meta = summarize_manifest(json.loads(text))
                    except ValueError:
                        continue
                    result, initiative = f"{meta['stories']} stories", "_workspace"
                else:  # research / ca / competitive / risk-review / ux-brief
                    if kind == "ca":
                        result = (fm.get("type") or "").replace("-ca", "").upper() or None
                    initiative = initiative_for(p, title, aliases)
                    epic_keys |= _epic_keys(text)
                con.execute(
                    "INSERT INTO artifacts(path,kind,title,initiative,bepic_key,epic_keys,result,pr_url,source,mtime,scanned_at,meta_json)"
                    " VALUES(?,?,?,?,?,?,?,?,'local',?,?,?) ON CONFLICT(path) DO UPDATE SET kind=excluded.kind,title=excluded.title,"
                    "initiative=COALESCE(artifacts.initiative_override,excluded.initiative),bepic_key=COALESCE(excluded.bepic_key,artifacts.bepic_key),"
                    "epic_keys=excluded.epic_keys,result=excluded.result,pr_url=COALESCE(excluded.pr_url,artifacts.pr_url),"
                    "mtime=excluded.mtime,scanned_at=excluded.scanned_at,meta_json=excluded.meta_json",
                    (str(p), k, title, initiative, bepic, ",".join(sorted(epic_keys)), result, fm.get("spec_pr_url") or None,
                     p.stat().st_mtime, now, json.dumps(meta)))
                found += 1
        # initiatives: ensure a row per slug, fill title/bepic/epic keys from artifacts + prds
        slugs = {r["initiative"] for r in db.rows(con, "SELECT DISTINCT initiative FROM artifacts WHERE initiative IS NOT NULL AND initiative!='_workspace'")}
        slugs |= {r["initiative"] for r in db.rows(con, "SELECT DISTINCT initiative FROM prds WHERE initiative IS NOT NULL")}
        for s in slugs:
            con.execute("INSERT OR IGNORE INTO initiatives(slug,updated_at) VALUES(?,?)", (s, now))
            t = db.one(con, "SELECT title FROM prds WHERE initiative=? ORDER BY mtime DESC LIMIT 1", (s,)) or \
                db.one(con, "SELECT title FROM artifacts WHERE initiative=? AND kind IN ('pm-context','ca','research','hld') ORDER BY mtime DESC LIMIT 1", (s,))
            bep = db.one(con, "SELECT bepic_key AS b FROM prds WHERE initiative=? AND bepic_key IS NOT NULL LIMIT 1", (s,)) or \
                db.one(con, "SELECT bepic_key AS b FROM artifacts WHERE initiative=? AND bepic_key IS NOT NULL LIMIT 1", (s,))
            keys = set()
            for r in db.rows(con, "SELECT epic_keys FROM artifacts WHERE initiative=?", (s,)):
                keys |= {x for x in (r["epic_keys"] or "").split(",") if x and is_epic_key(x)}
            for r in db.rows(con, "SELECT pe.epic_key FROM prd_epics pe JOIN prds p ON p.id=pe.prd_id WHERE p.initiative=?", (s,)):
                keys.add(r["epic_key"])
            if link["trackers"].get(s):
                keys.add(link["trackers"][s])
            con.execute("UPDATE initiatives SET title=COALESCE(title_override,?), bepic_key=COALESCE(bepic_override,?), epic_keys=?, updated_at=? WHERE slug=?",
                        ((t or {}).get("title") or s.replace("-", " ").title(), (bep or {}).get("b"), ",".join(sorted(keys)), now, s))
        db.set_meta(con, "artifact_scan_at", now)
    return {"found": found, "scanned_at": now}


def text_of(con, aid: int) -> dict:
    r = db.one(con, "SELECT path FROM artifacts WHERE id=?", (aid,))
    if not r:
        raise KeyError("artifact not found")
    p = Path(r["path"])
    return {"path": r["path"], "text": p.read_text(errors="replace")[:200000] if p.exists() else "(file missing)"}
