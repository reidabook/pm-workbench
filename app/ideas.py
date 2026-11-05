"""Source ingestion (.md/.txt/.docx/paste), idea CRUD helpers, group → PRD bundle."""
import datetime as dt
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from . import db
from .paths import DATA

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    paras = []
    for p in root.iter(W_NS + "p"):
        t = "".join(n.text or "" for n in p.iter(W_NS + "t"))
        if t.strip():
            paras.append(t.strip())
    return "\n".join(paras)


def ingest_file(filename: str, content: bytes) -> int:
    now = dt.datetime.now()
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)
    dest = DATA / "uploads" / f"{now.strftime('%Y%m%d-%H%M%S')}_{safe}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    ext = dest.suffix.lower()
    if ext == ".docx":
        text, kind = docx_text(dest), "transcript"
    else:
        text, kind = content.decode("utf-8", errors="replace"), "notes"
    return _insert_source(filename, kind, text, now)


def ingest_text(title: str, text: str, kind="paste") -> int:
    return _insert_source(title or "pasted text", kind, text, dt.datetime.now())


def ingest_jira(issue: dict) -> int:
    """One source per ticket: adding the same key again refreshes its text instead of duplicating."""
    title, now = f"{issue['key']}: {issue['summary']}", dt.datetime.now().isoformat(timespec="seconds")
    with db.tx() as con:
        old = db.one(con, "SELECT id FROM sources WHERE kind='jira' AND url=?", (issue["url"],))
        if old:
            con.execute("UPDATE sources SET filename=?, text=? WHERE id=?", (title, issue["text"], old["id"]))
            return old["id"]
        cur = con.execute("INSERT INTO sources(filename,kind,text,ingested_at,url) VALUES(?,?,?,?,?)",
                          (title, "jira", issue["text"], now, issue["url"]))
        return cur.lastrowid


def _insert_source(filename, kind, text, now) -> int:
    with db.tx() as con:
        cur = con.execute("INSERT INTO sources(filename,kind,text,ingested_at) VALUES(?,?,?,?)",
                          (filename, kind, text, now.isoformat(timespec="seconds")))
        return cur.lastrowid


def add_ideas(items: list, source_id=None, theme_id=None) -> list:
    now = dt.datetime.now().isoformat(timespec="seconds")
    ids = []
    with db.tx() as con:
        for it in items:
            cur = con.execute(
                "INSERT INTO ideas(title,body,quote,source_id,status,theme_id,created_at) VALUES(?,?,?,?,?,?,?)",
                (it["title"].strip(), (it.get("body") or "").strip(), (it.get("quote") or "").strip(),
                 source_id, "themed" if theme_id else "new", theme_id, now))
            ids.append(cur.lastrowid)
    return ids


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50] or "group"


def bundle_group(group_id: int) -> Path:
    """Write a markdown bundle for generate-prd --file: group name, theme, BEPIC, ideas, source excerpts."""
    with db.connect() as con:
        g = db.one(con, "SELECT g.*, t.name AS theme_name, t.bepic_key FROM idea_groups g "
                        "LEFT JOIN themes t ON t.id=g.theme_id WHERE g.id=?", (group_id,))
        if not g:
            raise ValueError("group not found")
        ideas = db.rows(con, "SELECT i.*, s.filename FROM ideas i LEFT JOIN sources s ON s.id=i.source_id "
                             "WHERE i.group_id=? ORDER BY i.id", (group_id,))
        src_ids = {i["source_id"] for i in ideas if i["source_id"]}
        sources = db.rows(con, f"SELECT * FROM sources WHERE id IN ({','.join('?'*len(src_ids)) or 'NULL'})",
                          tuple(src_ids)) if src_ids else []
        from . import evidence
        ev_refs = [f"group:{group_id}"] + [f"idea:{i['id']}" for i in ideas]
        ev_items = [e for lst in evidence.for_refs(con, ev_refs).values() for e in lst]
    lines = [f"# Idea bundle: {g['name']}", "",
             f"- Theme: {g['theme_name'] or 'unassigned'}",
             f"- Business Epic: {g['bepic_key'] or 'none'}",
             f"- Generated: {dt.datetime.now():%Y-%m-%d}", "", "## Ideas", ""]
    for i in ideas:
        lines += [f"### {i['title']}", i["body"] or "", ""]
        if i["quote"]:
            lines += [f"> {i['quote']}", ""]
        if i["filename"]:
            lines += [f"_Source: {i['filename']}_", ""]
    lines += [evidence.render_md(ev_items), ""]
    if sources:
        lines += ["## Source excerpts", ""]
        for s in sources:
            lines += [f"### {s['filename']} ({s['kind']}, {s['ingested_at']})", "", s["text"][:6000], ""]
    out = DATA / "bundles" / f"{slugify(g['name'])}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))
    return out
