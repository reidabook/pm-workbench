"""Jira pull / push / create. Scope rules from app.scope_rules; project, team + field ids from config.

Works with Jira Cloud (set `jira_email`; the token is an API token, sent as Basic auth) and
Jira Server / Data Center (leave `jira_email` empty; the token is a PAT, sent as Bearer)."""
import base64
import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

import requests

from . import db
from .paths import ENV_FILE, field, load_config
from .scope_rules import out_of_scope_reason

VALID_PRI = {"P1", "P2", "P3", "P4"}
PAT_SOURCES = "env JIRA_PAT, data/.env, Settings → PAT file, or Keychain item pm-workbench-jira"


def _pat_from_file(p: Path):
    if not p or not p.exists():
        return None
    for line in p.read_text(errors="replace").splitlines():
        line = line.strip()
        if line.startswith(("export JIRA_PAT=", "JIRA_PAT=", "export JIRA_API_TOKEN=", "JIRA_API_TOKEN=")):
            return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    txt = p.read_text(errors="replace").strip()
    return txt if txt and "=" not in txt and "\n" not in txt else None  # bare token file


def load_pat(cfg=None):
    """env JIRA_PAT / JIRA_API_TOKEN → data/.env → cfg.jira_pat_file → macOS Keychain (pm-workbench-jira)."""
    pat = os.environ.get("JIRA_PAT") or os.environ.get("JIRA_API_TOKEN")
    if pat:
        return pat
    pat = _pat_from_file(ENV_FILE)
    if pat:
        return pat
    cfg = cfg or load_config()
    if cfg.get("jira_pat_file"):
        pat = _pat_from_file(Path(cfg["jira_pat_file"]).expanduser())
        if pat:
            return pat
    if sys.platform == "darwin":
        try:
            r = subprocess.run(["security", "find-generic-password", "-s", "pm-workbench-jira", "-w"],
                               capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return None


def _cloud(cfg=None) -> bool:
    return bool(((cfg or load_config()).get("jira_email") or "").strip())


def _hdr(pat, cfg=None):
    cfg = cfg or load_config()
    email = (cfg.get("jira_email") or "").strip()
    auth = "Basic " + base64.b64encode(f"{email}:{pat}".encode()).decode() if email else f"Bearer {pat}"
    return {"Authorization": auth, "Content-Type": "application/json", "Accept": "application/json"}


def _key_of(v) -> str:
    """Parent fields are a bare key on Server custom fields, an issue object on Cloud's `parent`."""
    return (v.get("key") or "") if isinstance(v, dict) else (v or "")


def _fields(*names) -> str:
    return ",".join(n for n in names if n)


def search(cfg, pat, jql: str, fields: str, limit: int = 5000) -> List[dict]:
    """All issues for `jql`, in JQL order. Cloud: /search/jql + nextPageToken; Server: /search + startAt."""
    base, out = cfg["jira_base"], []
    if _cloud(cfg):
        token = None
        while len(out) < limit:
            params = {"jql": jql, "maxResults": 100, "fields": fields}
            if token:
                params["nextPageToken"] = token
            r = requests.get(f"{base}/rest/api/2/search/jql", headers=_hdr(pat, cfg), params=params, timeout=60)
            r.raise_for_status()
            data = r.json()
            out += data.get("issues") or []
            token = data.get("nextPageToken")
            if data.get("isLast", True) or not token or not data.get("issues"):
                break
        return out
    start = 0
    while len(out) < limit:
        r = requests.get(f"{base}/rest/api/2/search", headers=_hdr(pat, cfg), timeout=60,
                         params={"jql": jql, "startAt": start, "maxResults": 100, "fields": fields})
        r.raise_for_status()
        data = r.json()
        out += data["issues"]
        start += len(data["issues"])
        if start >= data.get("total", 0) or not data["issues"]:
            break
    return out


def all_jql(cfg) -> str:
    """Epics in scope: config `epic_jql` if set, else the configured team(s), else the whole Jira project."""
    if (cfg.get("epic_jql") or "").strip():
        return cfg["epic_jql"].strip()
    team = field(cfg, "portfolio_team")
    ids = ", ".join(str(i) for i in (cfg.get("portfolio_team_ids") or {}))
    if team and ids:
        num = team.replace("customfield_", "")
        return f"issuetype = Epic AND cf[{num}] in ({ids}) ORDER BY Rank ASC"
    if cfg.get("jira_project"):
        return f'project = "{cfg["jira_project"]}" AND issuetype = Epic ORDER BY Rank ASC'
    raise RuntimeError("Set a Jira project (or epic_jql / team ids) in Settings first")


def fetch(cfg, pat) -> List[dict]:
    """All epics for the configured teams (any status), ordered by Jira rank."""
    base = cfg["jira_base"]
    epics = []
    f_team, f_bepic, f_out = field(cfg, "portfolio_team"), field(cfg, "parent_link"), field(cfg, "outcome")
    fields = _fields("summary,status,priority,labels,resolution,resolutiondate,created", f_team, f_bepic, f_out)
    for it in search(cfg, pat, all_jql(cfg), fields):
        f = it["fields"]
        st = f.get("status") or {}
        name, cat = st.get("name", ""), (st.get("statusCategory") or {}).get("name", "")
        reason = out_of_scope_reason(name, cat)
        epics.append({
            "key": it["key"], "summary": (f.get("summary") or "").strip(), "status": name,
            "status_category": cat, "priority": (f.get("priority") or {}).get("name", "None"),
            "labels": "; ".join(sorted(f.get("labels") or [])),
            "team": ((f.get(f_team) or {}).get("name", "") if isinstance(f.get(f_team), dict) else (f.get(f_team) or "")) if f_team else "",
            "bepic": _key_of(f.get(f_bepic)) if f_bepic else "", "url": f"{base}/browse/{it['key']}",
            "in_scope": 0 if reason else 1, "scope_reason": reason,
            "resolution": (f.get("resolution") or {}).get("name") or None,
            "closed_at": (f.get("resolutiondate") or "")[:10] or None,
            "created_at": (f.get("created") or "")[:10] or None,
            "outcome": (f.get(f_out) or None) if f_out else None,
        })
    for i, e in enumerate(epics, 1):
        e["rank_pos"] = i
    return epics


def pull(cfg) -> dict:
    pat = load_pat(cfg)
    if not pat:
        raise RuntimeError(f"No Jira token found ({PAT_SOURCES})")
    epics = fetch(cfg, pat)
    now = dt.datetime.now().isoformat(timespec="seconds")
    with db.tx() as con:
        known = {r["key"]: r["status_category"] for r in db.rows(con, "SELECT key, status_category FROM epics")}
        seen = set()
        newly_closed = []
        for e in epics:
            seen.add(e["key"])
            con.execute(
                "INSERT INTO epics(key,summary,status,status_category,priority,rank_pos,labels,team,bepic,url,"
                "in_scope,scope_reason,synced_at,resolution,closed_at,created_at,outcome) VALUES(:key,:summary,:status,"
                ":status_category,:priority,:rank_pos,:labels,:team,:bepic,:url,:in_scope,:scope_reason,:now,"
                ":resolution,:closed_at,:created_at,:outcome) "
                "ON CONFLICT(key) DO UPDATE SET summary=excluded.summary,status=excluded.status,"
                "status_category=excluded.status_category,priority=excluded.priority,rank_pos=excluded.rank_pos,"
                "labels=excluded.labels,team=excluded.team,bepic=excluded.bepic,url=excluded.url,"
                "in_scope=excluded.in_scope,scope_reason=excluded.scope_reason,synced_at=excluded.synced_at,"
                "resolution=excluded.resolution,closed_at=excluded.closed_at,created_at=excluded.created_at,"
                "outcome=excluded.outcome",
                {**e, "now": now})
            con.execute("INSERT OR IGNORE INTO scores(epic_ref) VALUES(?)", (e["key"],))
            was = (known.get(e["key"]) or "").lower()
            if e["status"].lower() == "closed" and e["key"] in known and was != "done":
                newly_closed.append(e)
        # retro planner: open a retro for epics that just closed (backfill handles older ones)
        from . import retro
        for e in newly_closed:
            retro.open_for(con, e["key"], e.get("resolution"), e.get("closed_at"))
        # KRs teammates wrote into Jira Outcome: adopt into this install when we have none for that epic
        from . import okr
        cur_period = db.get_meta(con, "current_period_id")
        for e in epics:
            if e.get("outcome") and cur_period:
                parsed = okr.parse_outcome_block(e["outcome"])
                if parsed and not db.one(con, "SELECT 1 FROM key_results WHERE epic_key=?", (e["key"],)):
                    for k in parsed:
                        con.execute("INSERT INTO key_results(epic_key,period_id,title,metric_key,source,unit,direction,"
                                    "baseline,target,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                                    (e["key"], int(cur_period), k["title"], k["metric_key"],
                                     "manual" if k["metric_key"] == "manual" else "baselines_jsonl",
                                     k["unit"], k["direction"], k["baseline"], k["target"], now, now))
        # epics no longer returned at all (moved team / deleted): mark out of scope, keep scores
        gone = set(known) - seen
        for k in gone:
            con.execute("UPDATE epics SET in_scope=0, scope_reason='not in team query', synced_at=? WHERE key=?",
                        (now, k))
        db.set_meta(con, "last_sync", now)
        new = [e["key"] for e in epics if e["key"] not in known and e["in_scope"]]
        db.set_meta(con, "last_sync_new", ",".join(new))
    return {"total": len(epics), "in_scope": sum(e["in_scope"] for e in epics),
            "new": new, "gone": sorted(gone), "synced_at": now}


# ---------- push ----------
def push_preview(cfg, computed: List[dict], cur: Dict[str, dict]) -> dict:
    """Diff computed vs current Jira state. computed rows must have key/priority/rank/park/forced_p1."""
    from .scoring import push_order
    pri = []
    for c in computed:
        if c["priority"] in VALID_PRI and c["priority"] != cur.get(c["key"], {}).get("priority"):
            pri.append({"key": c["key"], "summary": c.get("summary"),
                        "from": cur.get(c["key"], {}).get("priority"), "to": c["priority"]})
    order = push_order(computed, {k: v.get("rank_pos", 0) for k, v in cur.items()})
    cur_order = [k for k, _ in sorted(cur.items(), key=lambda kv: kv[1].get("rank_pos") or 0)
                 if k in set(order)]
    return {"priorities": pri, "rank_order": order, "rank_changed": order != cur_order}


def push_apply(cfg, preview: dict, do_priorities=True, do_rank=True) -> dict:
    pat = load_pat(cfg)
    if not pat:
        raise RuntimeError(f"No Jira token found ({PAT_SOURCES})")
    base = cfg["jira_base"]
    done = {"priorities": 0, "rank": 0}
    if do_priorities:
        for ch in preview["priorities"]:
            r = requests.put(f"{base}/rest/api/2/issue/{ch['key']}", headers=_hdr(pat),
                             json={"fields": {"priority": {"name": ch["to"]}}}, timeout=60)
            r.raise_for_status()
            done["priorities"] += 1
    if do_rank and preview.get("rank_order"):
        order = preview["rank_order"]
        for i in range(1, len(order)):
            r = requests.put(f"{base}/rest/agile/1.0/issue/rank", headers=_hdr(pat),
                             json={"issues": [order[i]], "rankAfterIssue": order[i - 1]}, timeout=60)
            r.raise_for_status()
            done["rank"] += 1
    return done


def add_labels(cfg, key: str, want: List[str]) -> List[str]:
    pat = load_pat(cfg)
    base = cfg["jira_base"]
    cur = requests.get(f"{base}/rest/api/2/issue/{key}?fields=labels", headers=_hdr(pat),
                       timeout=60).json()["fields"].get("labels") or []
    merged = cur + [l for l in want if l not in cur]
    if merged != cur:
        requests.put(f"{base}/rest/api/2/issue/{key}", headers=_hdr(pat),
                     json={"fields": {"labels": merged}}, timeout=60).raise_for_status()
    return merged


# ---------- OKR / retro reads & writes ----------
def push_outcome(cfg, key: str, krs: List[dict]) -> str:
    """Write the managed Key Results block into the epic's Outcome field, keeping other text."""
    from .okr import merge_outcome
    pat = load_pat(cfg)
    if not pat:
        raise RuntimeError(f"No Jira token found ({PAT_SOURCES})")
    base = cfg["jira_base"]
    f_out = field(cfg, "outcome")
    if not f_out:
        raise RuntimeError("No Outcome field configured (Settings → Jira field ids → outcome)")
    cur = requests.get(f"{base}/rest/api/2/issue/{key}?fields={f_out}", headers=_hdr(pat), timeout=60)
    cur.raise_for_status()
    existing = cur.json()["fields"].get(f_out) or ""
    merged = merge_outcome(existing, krs)
    r = requests.put(f"{base}/rest/api/2/issue/{key}", headers=_hdr(pat),
                     json={"fields": {f_out: merged}}, timeout=60)
    r.raise_for_status()
    return merged


def fetch_changelog(cfg, key: str) -> dict:
    pat = load_pat(cfg)
    base = cfg["jira_base"]
    r = requests.get(f"{base}/rest/api/2/issue/{key}", headers=_hdr(pat), timeout=60,
                     params={"expand": "changelog", "fields": f"created,resolutiondate,status,assignee,{field(cfg, 'product_owner')},description,comment"})
    r.raise_for_status()
    return r.json()


ISSUE_KEY = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")


def issue_keys(text: str) -> List[str]:
    """Keys from free text: bare keys, browse URLs, comma / space / newline separated. Order kept, no repeats."""
    return list(dict.fromkeys(ISSUE_KEY.findall(text or "")))


def issue_source(cfg, issue: dict) -> dict:
    """A Jira story / defect as an Inbox source: readable text plus type and link."""
    f = issue.get("fields") or {}
    name = lambda v: (v or {}).get("name") or (v or {}).get("displayName") or ""  # noqa: E731
    typ = name(f.get("issuetype"))
    head = [("Type", typ), ("Status", name(f.get("status"))), ("Priority", name(f.get("priority"))),
            ("Resolution", name(f.get("resolution"))), ("Reporter", name(f.get("reporter"))),
            ("Assignee", name(f.get("assignee"))), ("Created", (f.get("created") or "")[:10]),
            ("Labels", ", ".join(f.get("labels") or [])),
            ("Components", ", ".join(c.get("name", "") for c in f.get("components") or []))]
    lines = [f"# {issue['key']}: {f.get('summary') or ''}", ""] + [f"- {k}: {v}" for k, v in head if v]
    for title, body in (("Description", f.get("description")), ("Acceptance criteria", f.get(field(cfg, "acceptance_criteria"))),
                        ("Environment", f.get("environment"))):
        if body and str(body).strip():
            lines += ["", f"## {title}", "", str(body).strip()]
    comments = ((f.get("comment") or {}).get("comments") or [])[-20:]
    if comments:
        lines += ["", "## Comments"]
        for c in comments:
            lines += ["", f"**{name(c.get('author'))}** ({(c.get('created') or '')[:10]}):", (c.get("body") or "").strip()]
    return {"key": issue["key"], "summary": f.get("summary") or "", "type": typ,
            "is_defect": typ.lower() in ("bug", "defect"), "created": (f.get("created") or "")[:10],
            "url": f"{cfg['jira_base']}/browse/{issue['key']}", "text": "\n".join(lines)}


def fetch_issue_source(cfg, key: str) -> dict:
    pat = load_pat(cfg)
    if not pat:
        raise RuntimeError(f"No Jira token found ({PAT_SOURCES})")
    r = requests.get(f"{cfg['jira_base']}/rest/api/2/issue/{key}", headers=_hdr(pat), timeout=60,
                     params={"fields": "summary,issuetype,status,priority,resolution,reporter,assignee,created,labels,"
                                       f"components,description,environment,comment,{field(cfg, 'acceptance_criteria')}"})
    if r.status_code == 404:
        raise RuntimeError(f"{key} not found (or no permission)")
    r.raise_for_status()
    return issue_source(cfg, r.json())


def fetch_children(cfg, key: str, full: bool = False) -> List[dict]:
    """Stories under the epic (Jira Server: 'Epic Link'; also try parent). full=True adds the DoR fields."""
    pat = load_pat(cfg)
    if not pat:
        raise RuntimeError(f"No Jira token found ({PAT_SOURCES})")
    base = cfg["jira_base"]
    f_pts, f_ac = field(cfg, "story_points"), field(cfg, "acceptance_criteria")
    fields = _fields("summary,status,created,resolutiondate,assignee,issuetype", f_pts)
    if full:
        fields = _fields(fields, "description,priority,labels", f_ac)
    out = []
    for jql in (f"parent = {key}", f'"Epic Link" = {key}'):
        try:
            try:
                issues = search(cfg, pat, jql, fields, limit=200)
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 400:
                    continue
                raise
            for it in issues:
                f = it["fields"]
                row = {"key": it["key"], "summary": f.get("summary"), "status": (f.get("status") or {}).get("name"),
                       "type": (f.get("issuetype") or {}).get("name"), "created": (f.get("created") or "")[:10],
                       "resolved": (f.get("resolutiondate") or "")[:10] or None,
                       "assignee": (f.get("assignee") or {}).get("displayName"),
                       "points": f.get(f_pts)}
                if full:
                    row.update({"description": f.get("description") or "", "acceptance_criteria": f.get(f_ac) or "",
                                "priority": (f.get("priority") or {}).get("name"), "labels": f.get("labels") or [],
                                "url": f"{base}/browse/{it['key']}"})
                out.append(row)
            if out:
                break
        except requests.RequestException:
            continue
    return out


def fetch_epic_fields(cfg, key: str) -> dict:
    """Epic-level readiness inputs: status, description, AC, outcome, labels, parent BEpic."""
    pat = load_pat(cfg)
    if not pat:
        raise RuntimeError(f"No Jira token found ({PAT_SOURCES})")
    base = cfg["jira_base"]
    f_ac, f_out, f_bepic = field(cfg, "acceptance_criteria"), field(cfg, "outcome"), field(cfg, "parent_link")
    r = requests.get(f"{base}/rest/api/2/issue/{key}", headers=_hdr(pat), timeout=60,
                     params={"fields": _fields("summary,status,description,labels", f_ac, f_out, f_bepic)})
    r.raise_for_status()
    f = r.json()["fields"]
    return {"key": key, "summary": f.get("summary"), "status": (f.get("status") or {}).get("name"),
            "description": f.get("description") or "", "labels": f.get("labels") or [],
            "acceptance_criteria": (f.get(f_ac) or "") if f_ac else "", "outcome": (f.get(f_out) or "") if f_out else "",
            "bepic": _key_of(f.get(f_bepic)) if f_bepic else ""}


def fetch_bepic(cfg, key: str) -> dict:
    """Parent issue (initiative / business epic) title + description, to seed an Objective."""
    pat = load_pat(cfg)
    if not pat:
        raise RuntimeError(f"No Jira token found ({PAT_SOURCES})")
    r = requests.get(f"{cfg['jira_base']}/rest/api/2/issue/{key}", headers=_hdr(pat), timeout=60,
                     params={"fields": "summary,status,description"})
    r.raise_for_status()
    f = r.json()["fields"]
    return {"key": key, "summary": f.get("summary") or "", "status": (f.get("status") or {}).get("name"),
            "description": f.get("description") or ""}


# ---------- create ----------
def epic_payload(cfg, d: dict, team_id: int = None) -> dict:
    labels = [l.strip() for l in (d.get("labels") or "").replace(";", ",").split(",") if l.strip()]
    for l in cfg.get("default_labels", []):
        if l not in labels:
            labels.append(l)
    f = {
        "project": {"key": cfg["jira_project"]},
        "issuetype": {"name": "Epic"},
        "summary": d["summary"],
        "description": d.get("description") or "",
        "labels": labels,
    }
    po, ac, out = field(cfg, "product_owner"), field(cfg, "acceptance_criteria"), field(cfg, "outcome")
    extra = []
    if po and d.get("product_owner"):
        f[po] = {"accountId": d["product_owner"]} if _cloud(cfg) else {"name": d["product_owner"]}
    for fid, label, val in ((ac, "Acceptance criteria", d.get("acceptance_criteria")), (out, "Outcome", d.get("outcome"))):
        if fid:
            f[fid] = val or ""
        elif val:
            extra.append(f"h3. {label}\n{val}")
    if extra:  # no custom field configured: keep the content in the description
        f["description"] = "\n\n".join([f["description"], *extra]).strip()
    pl = field(cfg, "parent_link")
    if d.get("bepic_key") and pl:
        f[pl] = {"key": d["bepic_key"]} if pl == "parent" else d["bepic_key"]
    if team_id and field(cfg, "portfolio_team"):
        f[field(cfg, "portfolio_team")] = {"id": str(team_id)}
    return {"fields": f}


def validate_draft(d: dict, cfg=None) -> List[str]:
    need = [("Summary", "summary"), ("Acceptance Criteria", "acceptance_criteria"), ("Outcome", "outcome")]
    if field(cfg or load_config(), "product_owner"):
        need.insert(1, ("Product Owner", "product_owner"))
    missing = [n for n, k in need if not (d.get(k) or "").strip()]
    return missing


def create_epic(cfg, d: dict, team_id: int = None) -> dict:
    """POST the epic; on field rejection drop the offending fields and retry once
    so a Jira with a different field scheme still gets the epic. Returns {key,url,dropped}."""
    pat = load_pat(cfg)
    if not pat:
        raise RuntimeError(f"No Jira token found ({PAT_SOURCES})")
    base = cfg["jira_base"]
    payload = epic_payload(cfg, d, team_id)
    dropped = []
    for _ in range(3):
        r = requests.post(f"{base}/rest/api/2/issue", headers=_hdr(pat), json=payload, timeout=60)
        if r.status_code < 300:
            key = r.json()["key"]
            return {"key": key, "url": f"{base}/browse/{key}", "dropped": dropped}
        try:
            errs = r.json().get("errors", {})
        except ValueError:
            errs = {}
        bad = [k for k in errs if k in payload["fields"] and k not in ("summary", "project", "issuetype")]
        if not bad:
            raise RuntimeError(f"Jira {r.status_code}: {r.text[:500]}")
        for k in bad:
            payload["fields"].pop(k)
            dropped.append(f"{k}: {errs[k]}")
    raise RuntimeError("Jira create failed after retries: " + "; ".join(dropped))


# ---------- publish generated epics & stories (used by /pm-requirements-accept) ----------
def _create(cfg, pat, fields: dict) -> str:
    """POST an issue; drop fields Jira rejects (other than the basics) and retry. Returns the key."""
    base, payload = cfg["jira_base"], {"fields": dict(fields)}
    for _ in range(3):
        r = requests.post(f"{base}/rest/api/2/issue", headers=_hdr(pat, cfg), json=payload, timeout=60)
        if r.status_code < 300:
            return r.json()["key"]
        try:
            errs = r.json().get("errors", {})
        except ValueError:
            errs = {}
        bad = [k for k in errs if k in payload["fields"] and k not in ("summary", "project", "issuetype")]
        if not bad:
            raise RuntimeError(f"Jira {r.status_code}: {r.text[:500]}")
        for k in bad:
            payload["fields"].pop(k)
    raise RuntimeError("Jira create failed after retries")


def story_fields(cfg, s: dict, epic_key: str) -> dict:
    ac = s.get("acceptance_criteria") or []
    ac_txt = "\n".join(f"* {a}" for a in ac) if isinstance(ac, list) else str(ac)
    desc = (s.get("description") or s.get("story") or "").strip()
    f = {"project": {"key": cfg["jira_project"]}, "issuetype": {"name": "Story"},
         "summary": s["title"][:250], "labels": list(dict.fromkeys((s.get("labels") or []) + cfg.get("default_labels", [])))}
    f_ac, f_pts, f_link = field(cfg, "acceptance_criteria"), field(cfg, "story_points"), field(cfg, "epic_link")
    if f_ac:
        f[f_ac] = ac_txt
    elif ac_txt:
        desc = f"{desc}\n\nh3. Acceptance criteria\n{ac_txt}".strip()
    f["description"] = desc
    if f_pts and s.get("points") is not None:
        f[f_pts] = s["points"]
    if f_link:   # Jira Server / DC: Epic Link custom field
        f[f_link] = epic_key
    else:        # Jira Cloud (and newer DC): parent
        f["parent"] = {"key": epic_key}
    return f


def publish_epics_file(cfg, path: str, dry_run: bool = False) -> dict:
    """Create Jira epics (when they have no jira_key) and every story with dor_status PASS under them.
    Writes the new keys back into the epics JSON and appends them to <workspace>/jira-manifest.json."""
    import json
    p = Path(path).expanduser()
    if not p.exists():
        raise RuntimeError(f"{p} not found")
    if not cfg.get("jira_project"):
        raise RuntimeError("Set the Jira project in Settings first")
    data = json.loads(p.read_text())
    epics = data.get("epics") if isinstance(data, dict) else data
    plan = [{"epic": e.get("title"), "epic_key": e.get("jira_key"),
             "stories": [s.get("title") for s in e.get("stories") or [] if str(s.get("dor_status", "")).upper() == "PASS" and not s.get("jira_key")],
             "held_back": [s.get("title") for s in e.get("stories") or [] if str(s.get("dor_status", "")).upper() != "PASS"]}
            for e in epics or []]
    if dry_run:
        return {"dry_run": True, "plan": plan}
    pat = load_pat(cfg)
    if not pat:
        raise RuntimeError(f"No Jira token found ({PAT_SOURCES})")
    parent = data.get("parent") or data.get("bepic") if isinstance(data, dict) else None
    created = []
    for e in epics or []:
        if not e.get("jira_key"):
            d = {"summary": e["title"], "description": e.get("description") or "", "acceptance_criteria": e.get("acceptance_criteria") or "",
                 "outcome": e.get("outcome") or "", "product_owner": cfg.get("default_product_owner") or "",
                 "labels": ",".join(e.get("labels") or []), "bepic_key": parent}
            e["jira_key"] = _create(cfg, pat, epic_payload(cfg, d)["fields"])
            created.append(e["jira_key"])
        for s in e.get("stories") or []:
            if str(s.get("dor_status", "")).upper() == "PASS" and not s.get("jira_key"):
                s["jira_key"] = _create(cfg, pat, story_fields(cfg, s, e["jira_key"]))
                created.append(s["jira_key"])
        p.write_text(json.dumps(data, indent=2))  # after each epic, so a failure keeps the keys made so far
    man_path = Path(cfg.get("pr_workspace") or "") / "jira-manifest.json"
    man = json.loads(man_path.read_text()) if man_path.exists() else {"issues": []}
    have = {i.get("key") for i in man.get("issues", [])}
    for e in epics or []:
        for s in e.get("stories") or []:
            if s.get("jira_key") and s["jira_key"] not in have:
                man["issues"].append({"key": s["jira_key"], "epic": e["jira_key"], "title": s.get("title")})
    man_path.write_text(json.dumps(man, indent=2))
    return {"created": created, "plan": plan, "manifest": str(man_path)}
