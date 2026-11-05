"""Decision / risk / blocker log. ref = initiative slug or Jira epic key. Pure DB helpers (no HTTP) so tests can call them."""
import datetime as dt
from typing import List, Optional

from . import db

KINDS = ("decision", "risk", "blocker")
NOW = lambda: dt.datetime.now().isoformat(timespec="seconds")  # noqa: E731


def add(con, ref: str, kind: str, text: str, owner: Optional[str] = None, due: Optional[str] = None) -> int:
    if kind not in KINDS:
        raise ValueError("kind must be decision, risk or blocker")
    if not (text or "").strip():
        raise ValueError("text required")
    cur = con.execute("INSERT INTO log_entries(ref,kind,text,owner,due,status,created_at) VALUES(?,?,?,?,?,'open',?)",
                      (ref, kind, text.strip(), owner or None, due or None, NOW()))
    return cur.lastrowid


def update(con, lid: int, text=None, owner=None, due=None, status=None, kind=None) -> bool:
    cur = db.one(con, "SELECT * FROM log_entries WHERE id=?", (lid,))
    if not cur:
        return False
    if kind and kind not in KINDS:
        raise ValueError("bad kind")
    closed_at = cur.get("closed_at")
    if status and status != cur["status"]:
        closed_at = NOW() if status == "closed" else None
    con.execute("UPDATE log_entries SET text=COALESCE(?,text), owner=COALESCE(?,owner), due=COALESCE(?,due), "
                "status=COALESCE(?,status), kind=COALESCE(?,kind), closed_at=? WHERE id=?",
                (text, owner, due, status, kind, closed_at, lid))
    return True


def delete(con, lid: int) -> None:
    con.execute("DELETE FROM log_entries WHERE id=?", (lid,))


def recent(con, days: int = 30) -> List[dict]:
    """Open entries plus entries closed within the last `days`."""
    cutoff = (dt.datetime.now() - dt.timedelta(days=days)).isoformat(timespec="seconds")
    return db.rows(con, "SELECT * FROM log_entries WHERE status='open' OR (closed_at IS NOT NULL AND closed_at>=?) "
                        "ORDER BY status='closed', CASE kind WHEN 'blocker' THEN 0 WHEN 'risk' THEN 1 ELSE 2 END, id DESC", (cutoff,))
