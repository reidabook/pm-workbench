"""Port of the Excel scoring formulas in prioritization/build_matrix.py (README §Scoring),
plus an optional sixth term: w_val · Validation (evidence-derived, 1-5). With w_val = 0 the
result is identical to the sheet.

Inputs per row: theme_rank (int|None), sv, ui, urg, conf (1-5|None), effort (S/M/L|None),
park ('top'|'bottom'|''), raise_p1 (str). Output adds theme_score, effort_factor, score,
rank, priority, gap. Semantics match Excel exactly:
  * parked rows: no score/rank/priority/gap
  * score blank if any input blank
  * RANK: 1 + number of strictly greater scores (ties share the min rank)
  * bands: rank <= band*N_SCORED where N_SCORED = COUNT of non-blank scores
  * raise_p1 non-blank => 'P1' regardless of score (still ranked/scored)
  * gap 'NEEDS INFO' if any input blank or conf <= threshold
"""
from typing import Dict, List, Optional


def theme_score(rank: Optional[int], max_rank: int) -> Optional[float]:
    if rank is None:
        return None
    if max_rank <= 1:
        return 5.0
    return 5 - 4 * (rank - 1) / (max_rank - 1)


def _num(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def compute(rows: List[dict], p: Dict[str, float], max_theme_rank: int) -> List[dict]:
    out = []
    for r in rows:
        c = dict(r)
        parked = (r.get("park") or "").strip().lower() in ("top", "bottom")
        c["park"] = (r.get("park") or "").strip().lower() or None
        ts = theme_score(r.get("theme_rank"), max_theme_rank)
        c["theme_score"] = ts
        eff = (r.get("effort") or "").strip().upper() or None
        c["effort"] = eff
        ef = p.get(f"effort_{eff}") if eff in ("S", "M", "L") else None
        c["effort_factor"] = ef
        sv, ui, urg, conf = (_num(r.get(k)) for k in ("sv", "ui", "urg", "conf"))
        # Validation (1-5) comes from evidence; absence is a real signal (1), not a blank input
        val = _num(r.get("validation"))
        c["validation"] = val if val is not None else 1.0
        w_val = p.get("w_val", 0.0) or 0.0
        inputs_blank = any(v is None for v in (ts, sv, ui, urg, conf, ef))
        if parked or inputs_blank:
            c["score"] = None
        else:
            c["score"] = (p["w_sv"] * sv + p["w_ui"] * ui + p["w_urg"] * urg
                          + p["w_theme"] * ts + p["w_conf"] * conf + w_val * c["validation"]) / ef
        if parked:
            c["gap"] = None
        elif inputs_blank or r.get("theme_rank") is None:
            c["gap"] = "NEEDS INFO"
        elif conf is not None and conf <= p["conf_gap"]:
            c["gap"] = "NEEDS INFO"
        else:
            c["gap"] = None
        c["forced_p1"] = bool((r.get("raise_p1") or "").strip())
        out.append(c)

    scored = [c["score"] for c in out if c["score"] is not None]
    n = len(scored)
    for c in out:
        s = c["score"]
        if s is None:
            c["rank"] = None
        else:
            c["rank"] = 1 + sum(1 for x in scored if x > s)
        if c["park"]:
            c["priority"] = None
        elif c["forced_p1"]:
            c["priority"] = "P1"
        elif c["rank"] is None:
            c["priority"] = None
        else:
            rk = c["rank"]
            if rk <= p["band_p1"] * n:
                c["priority"] = "P1"
            elif rk <= p["band_p2"] * n:
                c["priority"] = "P2"
            elif rk <= p["band_p3"] * n:
                c["priority"] = "P3"
            else:
                c["priority"] = "P4"
    return out


def push_order(computed: List[dict], cur_rank: Dict[str, int] = None) -> List[str]:
    """Total order for Jira rank write-back: parked-top, forced-P1, scored, parked-bottom.
    Mirrors write_back.apply_rank; cur_rank (Jira position) breaks ties."""
    cur_rank = cur_rank or {}

    def cr(c):
        return cur_rank.get(c["key"], 0)

    def by_rank(c):
        return (c["rank"] if c["rank"] is not None else float("inf"), cr(c))

    top = sorted([c for c in computed if c["park"] == "top"], key=cr)
    bottom = sorted([c for c in computed if c["park"] == "bottom"], key=cr)
    active = [c for c in computed if not c["park"]]
    forced = sorted([c for c in active if c["forced_p1"]], key=by_rank)
    scored = sorted([c for c in active if not c["forced_p1"] and c["rank"] is not None], key=by_rank)
    return [c["key"] for c in top + forced + scored + bottom]
