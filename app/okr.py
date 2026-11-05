"""OKR math + Jira Outcome block. Theme = Objective; Key Results live on epics.

progress(KR) = clamp((current - baseline) / (target - baseline), 0, 1), direction-aware (works
for 'reduce X' KRs because target < baseline flips the sign). Epic = mean of KRs; theme = mean of
epics that have KRs (unmeasured epics are reported, not counted as 0).
"""
import datetime as dt
import re
from typing import Dict, List, Optional

from . import db, metrics

MARK_START = "h3. Key Results"
MARK_END = "_(managed by PM Workbench)_"
_BLOCK_RE = re.compile(re.escape(MARK_START) + r".*?" + re.escape(MARK_END), re.S)
_LINE_RE = re.compile(
    r"^\*\s*(?P<title>.+?)\s*[—-]\s*(?P<metric>[^:]+):\s*(?P<baseline>[-\d.]+)\s*→\s*(?P<target>[-\d.]+)"
    r"(?:\s*(?P<unit>[^\s(]+))?(?:\s*\((?P<dir>higher|lower) is better\))?", re.M)


def kr_progress(kr: dict) -> Optional[float]:
    b, t, c = kr.get("baseline"), kr.get("target"), kr.get("current")
    if b is None or t is None or c is None or t == b:
        return None
    p = (c - b) / (t - b)
    return max(0.0, min(1.0, p))


def epic_progress(krs: List[dict]) -> Optional[float]:
    ps = [p for p in (kr_progress(k) for k in krs) if p is not None]
    return sum(ps) / len(ps) if ps else None


def theme_progress(epic_progresses: List[Optional[float]]) -> dict:
    measured = [p for p in epic_progresses if p is not None]
    return {"progress": (sum(measured) / len(measured)) if measured else None,
            "measured": len(measured), "unmeasured": len(epic_progresses) - len(measured)}


def elapsed_fraction(period: dict, today: Optional[dt.date] = None) -> float:
    today = today or dt.date.today()
    s, e = dt.date.fromisoformat(period["start"]), dt.date.fromisoformat(period["end"])
    if today <= s:
        return 0.0
    if today >= e:
        return 1.0
    return (today - s).days / max((e - s).days, 1)


def health(progress: Optional[float], period: dict, closed_at: Optional[str] = None,
           today: Optional[dt.date] = None) -> str:
    """ahead | on_track | behind | measuring (released < 90d) | unmeasured.

    A KR-less epic is "unmeasured" even when recently closed: "measuring" only makes sense when there is a KR to read.
    """
    today = today or dt.date.today()
    if progress is None:
        return "unmeasured"
    if closed_at:
        try:
            days = (today - dt.date.fromisoformat(closed_at[:10])).days
        except ValueError:
            days = 999
        if days < 90:
            return "measuring"
    gap = progress - elapsed_fraction(period, today)
    if gap > 0.15:
        return "ahead"
    if gap < -0.15:
        return "behind"
    return "on_track"


def kr_lint(kr: dict) -> List[str]:
    """Non-blocking definition warnings for a Key Result (mirrored client-side in krForm)."""
    w = []
    b, t, d = kr.get("baseline"), kr.get("target"), kr.get("direction") or "up"
    if b is not None and t is not None:
        if t == b:
            w.append("target equals baseline — no movement to measure")
        elif d == "up" and t < b:
            w.append("direction is 'higher is better' but target is below baseline")
        elif d == "down" and t > b:
            w.append("direction is 'lower is better' but target is above baseline")
    if kr.get("source", "manual") == "manual" and (b is None or t is None):
        w.append("manual KR needs a baseline and a target")
    title = kr.get("title") or ""
    if title and not re.search(r"\d|%", title) and not kr.get("unit"):
        w.append("title has no number, % or unit — is it measurable?")
    return w


def refresh_current(cfg, con, period_id: Optional[int] = None) -> int:
    """Pull latest values for bound KRs; snapshot when the source date is newer than the last one."""
    q = "SELECT * FROM key_results WHERE source IN ('baselines_jsonl','data_js')"
    args = ()
    if period_id:
        q += " AND period_id=?"
        args = (period_id,)
    n = 0
    for kr in db.rows(con, q, args):
        v, d = metrics.read_metric(cfg, kr["source"], kr["metric_key"])
        if v is None:
            continue
        last = db.one(con, "SELECT taken_at FROM kr_snapshots WHERE kr_id=? ORDER BY taken_at DESC LIMIT 1", (kr["id"],))
        con.execute("UPDATE key_results SET current=?, current_at=?, updated_at=? WHERE id=?",
                    (v, d, dt.datetime.now().isoformat(timespec="seconds"), kr["id"]))
        if not last or last["taken_at"][:10] < d:
            con.execute("INSERT INTO kr_snapshots(kr_id,taken_at,value,reason) VALUES(?,?,?,?)", (kr["id"], d, v, "auto"))
            n += 1
    return n


# ---------- Jira Outcome block ----------
def outcome_block(krs: List[dict]) -> str:
    lines = [MARK_START]
    for k in krs:
        unit = f" {k['unit']}" if k.get("unit") else ""
        d = "lower" if k.get("direction") == "down" else "higher"
        lines.append(f"* {k['title']} — {k.get('metric_key') or 'manual'}: {_num(k.get('baseline'))} → {_num(k.get('target'))}{unit} ({d} is better)")
    lines.append(MARK_END)
    return "\n".join(lines)


def _num(v):
    if v is None:
        return "?"
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def merge_outcome(existing: str, krs: List[dict]) -> str:
    """Replace the managed block inside existing Outcome text, or append it; keep everything else."""
    block = outcome_block(krs)
    existing = existing or ""
    if _BLOCK_RE.search(existing):
        return _BLOCK_RE.sub(lambda _: block, existing)
    return (existing.rstrip() + "\n\n" + block) if existing.strip() else block


def parse_outcome_block(text: str) -> List[dict]:
    m = _BLOCK_RE.search(text or "")
    if not m:
        return []
    out = []
    for lm in _LINE_RE.finditer(m.group(0)):
        try:
            out.append({"title": lm["title"].strip(), "metric_key": lm["metric"].strip(),
                        "baseline": float(lm["baseline"]), "target": float(lm["target"]),
                        "unit": (lm["unit"] or "").strip() or None,
                        "direction": "down" if (lm["dir"] or "") == "lower" else "up"})
        except (TypeError, ValueError):
            continue
    return out


def board(cfg, con, period: dict, themes: List[dict], epics: List[dict]) -> Dict:
    """Per-theme and per-epic OKR summary for /api/state."""
    krs = db.rows(con, "SELECT * FROM key_results WHERE period_id=?", (period["id"],))
    snaps = db.rows(con, "SELECT s.* FROM kr_snapshots s JOIN key_results k ON k.id=s.kr_id WHERE k.period_id=? ORDER BY s.taken_at", (period["id"],))
    by_kr = {}
    for s in snaps:
        by_kr.setdefault(s["kr_id"], []).append([s["taken_at"], s["value"], s["reason"]])
    by_epic: Dict[str, List[dict]] = {}
    by_theme: Dict[int, List[dict]] = {}   # objective-level KRs: epic_key IS NULL AND theme_id set
    for k in krs:
        k["progress"] = kr_progress(k)
        k["snapshots"] = by_kr.get(k["id"], [])
        if k.get("epic_key"):
            by_epic.setdefault(k["epic_key"], []).append(k)
        elif k.get("theme_id"):
            by_theme.setdefault(k["theme_id"], []).append(k)
    epic_info = {}
    for e in epics:
        ks = by_epic.get(e["key"], [])
        p = epic_progress(ks)
        epic_info[e["key"]] = {"progress": p, "krs": ks, "health": health(p, period, e.get("closed_at"))}
    theme_info = {}
    for t in themes:
        eps = [e for e in epics if e.get("theme_id") == t["id"]]
        tp = theme_progress([epic_info[e["key"]]["progress"] for e in eps])
        okrs = by_theme.get(t["id"], [])
        op = epic_progress(okrs)
        tp["krs"] = okrs                      # objective-level KRs (may be empty)
        tp["epic_progress"] = tp["progress"]  # mean of measured epics, always reported
        if op is not None:                    # objective KRs take precedence over the epic mean
            tp["progress"], tp["source"] = op, "objective"
        else:
            tp["source"] = "epics"
        tp["health"] = health(tp["progress"], period)
        tp["epics"] = len(eps)
        theme_info[t["id"]] = tp
    return {"themes": theme_info, "epics": epic_info, "elapsed": elapsed_fraction(period)}
