"""Validation evidence: where the signal for an idea / epic came from, and a 1-5 Validation score.

Evidence attaches to a `ref`: 'idea:<id>', 'group:<id>', 'draft:<id>' or a Jira key. It follows
the work as it is promoted (idea -> group -> draft -> epic). Breadth of source types counts more
than volume, and competitor-only evidence is capped low.
"""
import datetime as dt
from typing import Dict, List

TYPES = [  # key, label, default weight (distinct-type contribution)
    ("user_data", "Usage data / analytics", 2.0),
    ("customer", "Customer / user feedback", 1.5),
    ("prospect", "Prospective customer feedback", 1.0),
    ("support", "Support tickets / defects", 1.0),
    ("competitor", "Competitor does it", 0.5),
    ("internal", "Internal / leadership ask", 0.5),
]
TYPE_LABEL = {k: l for k, l, _ in TYPES}
DEFAULT_TYPE_WEIGHTS = {f"val_w_{k}": w for k, _, w in TYPES}
COMPETITOR_ONLY_CAP = 1.5
EXTRA_PER_ITEM = 0.25
EXTRA_CAP = 0.5


def validation_score(items: List[dict], p: Dict[str, float]) -> float:
    """1 = no evidence. Each distinct type adds its weight; repeats add a little; ceiling 5."""
    if not items:
        return 1.0
    by_type: Dict[str, int] = {}
    for it in items:
        by_type[it["type"]] = by_type.get(it["type"], 0) + 1
    if set(by_type) <= {"competitor"}:
        return min(COMPETITOR_ONLY_CAP, 1.0 + p.get("val_w_competitor", 0.5))
    score = 1.0
    for t, n in by_type.items():
        score += p.get(f"val_w_{t}", 0.5) + min(EXTRA_CAP, EXTRA_PER_ITEM * (n - 1))
    return round(min(5.0, score), 2)


def for_refs(con, refs: List[str]) -> Dict[str, List[dict]]:
    if not refs:
        return {}
    q = ",".join("?" * len(refs))
    out: Dict[str, List[dict]] = {}
    for r in con.execute(f"SELECT * FROM evidence WHERE ref IN ({q}) ORDER BY occurred_at DESC, id DESC", tuple(refs)):
        out.setdefault(r["ref"], []).append(dict(r))
    return out


def add(con, ref: str, type_: str, note: str, link: str = None, source_id: int = None, occurred_at: str = None) -> int:
    if type_ not in TYPE_LABEL:
        raise ValueError("unknown evidence type")
    cur = con.execute("INSERT INTO evidence(ref,type,note,link,source_id,occurred_at,created_at) VALUES(?,?,?,?,?,?,?)",
                      (ref, type_, (note or "").strip(), link or None, source_id,
                       occurred_at or dt.date.today().isoformat(), dt.datetime.now().isoformat(timespec="seconds")))
    return cur.lastrowid


def sync_source(con, source_id: int, idea_ids: List[int] = None) -> int:
    """A typed source is evidence for every idea that came from it (one entry per idea, tagged with
    source_id). Re-typing the source re-types those entries; hand-added evidence is never touched.
    `idea_ids` limits the pass to new ideas so entries the PM removed are not put back."""
    src = con.execute("SELECT filename, evidence_type, ingested_at, url FROM sources WHERE id=?", (source_id,)).fetchone()
    if not src or src["evidence_type"] not in TYPE_LABEL:
        return 0
    con.execute("UPDATE evidence SET type=? WHERE source_id=? AND ref LIKE 'idea:%'", (src["evidence_type"], source_id))
    have = {r["ref"] for r in con.execute("SELECT ref FROM evidence WHERE source_id=?", (source_id,))}
    sql, args = "SELECT id, quote FROM ideas WHERE source_id=?", [source_id]
    if idea_ids is not None:
        sql += f" AND id IN ({','.join('?' * len(idea_ids)) or 'NULL'})"
        args += idea_ids
    n = 0
    for i in con.execute(sql, args).fetchall():
        if f"idea:{i['id']}" in have:
            continue
        add(con, f"idea:{i['id']}", src["evidence_type"], i["quote"] or f"From {src['filename']}",
            src["url"], source_id, (src["ingested_at"] or "")[:10] or None)
        n += 1
    return n


def carry(con, from_ref: str, to_ref: str) -> int:
    """Copy evidence from one ref to another (skip exact duplicates already on the target)."""
    have = {(e["type"], e["note"], e["link"]) for e in for_refs(con, [to_ref]).get(to_ref, [])}
    n = 0
    for e in for_refs(con, [from_ref]).get(from_ref, []):
        if (e["type"], e["note"], e["link"]) in have:
            continue
        con.execute("INSERT INTO evidence(ref,type,note,link,source_id,occurred_at,created_at) VALUES(?,?,?,?,?,?,?)",
                    (to_ref, e["type"], e["note"], e["link"], e["source_id"], e["occurred_at"],
                     dt.datetime.now().isoformat(timespec="seconds")))
        n += 1
    return n


def carry_group(con, group_id: int, to_ref: str) -> int:
    """Group evidence = its own entries + every member idea's entries."""
    n = carry(con, f"group:{group_id}", to_ref)
    for r in con.execute("SELECT id FROM ideas WHERE group_id=?", (group_id,)):
        n += carry(con, f"idea:{r['id']}", to_ref)
    return n


def render_md(items: List[dict]) -> str:
    if not items:
        return "## Validation\n\n_No evidence recorded yet._\n"
    lines = ["## Validation", ""]
    for t, label, _ in TYPES:
        sub = [i for i in items if i["type"] == t]
        if not sub:
            continue
        lines.append(f"### {label}")
        for i in sub:
            link = f" ([source]({i['link']}))" if i.get("link") else ""
            lines.append(f"- {i['occurred_at'] or ''} {i['note']}{link}".strip())
        lines.append("")
    return "\n".join(lines)


def render_wiki(items: List[dict]) -> str:
    if not items:
        return ""
    lines = ["h3. Validation"]
    for t, label, _ in TYPES:
        sub = [i for i in items if i["type"] == t]
        if sub:
            lines.append(f"*{label}*")
            for i in sub:
                link = f" [{i['link']}]" if i.get("link") else ""
                lines.append(f"* {i['note']}{link}")
    return "\n".join(lines)
