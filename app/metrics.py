"""Metric sources for Key Results. Read-only, no credentials, no Claude.

Sources:
  manual          — value typed by the PM.
  baselines_jsonl — <analytics_dir>/metrics-history.jsonl: one dated row per refresh with
                    headline numbers ({"date": "2026-10-01", "task_completion": 0.71, "p50_latency": 1.9, ...}).
                    Supports "value as of <date>" via nearest row at or before the date.
  data_js         — <analytics_dir>/metrics.json (or data.js holding `window.X = {...}`): dotted path into
                    numeric leaves, e.g. usage.weekly_active_users. Only "now" (dated by lastUpdated).
"""
import datetime as dt
import json
from pathlib import Path
from typing import List, Optional, Tuple

from .paths import APP_ROOT

_CACHE = {}


def analytics_dir(cfg) -> Path:
    """Directory holding metrics-history.jsonl / metrics.json. Empty → no file-backed metric sources."""
    d = cfg.get("analytics_dir")
    return Path(d).expanduser() if d else (APP_ROOT / "data" / "analytics")


def _baselines(cfg) -> List[dict]:
    p = analytics_dir(cfg) / "metrics-history.jsonl"
    if not p.exists():
        return []
    key = ("b", str(p), p.stat().st_mtime)
    if key not in _CACHE:
        rows = []
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("date"):
                rows.append(r)
        rows.sort(key=lambda r: r["date"])
        _CACHE.clear()
        _CACHE[key] = rows
    return _CACHE[key]


def _data_js(cfg) -> dict:
    p = next((q for q in (analytics_dir(cfg) / "metrics.json", analytics_dir(cfg) / "data.js") if q.exists()), None)
    if not p:
        return {}
    key = ("d", str(p), p.stat().st_mtime)
    if key not in _CACHE:
        s = p.read_text()
        if p.suffix == ".js":
            s = s[s.find("=") + 1:].strip().rstrip(";")
        try:
            d = json.loads(s)
        except json.JSONDecodeError:
            d = {}
        _CACHE[key] = d
    return _CACHE[key]


def _leaves(o, prefix="", depth=0, out=None):
    out = out if out is not None else []
    if depth > 3:
        return out
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                out.append(prefix + k)
            elif isinstance(v, dict):
                _leaves(v, prefix + k + ".", depth + 1, out)
    return out


def list_metric_keys(cfg) -> dict:
    b = _baselines(cfg)
    bkeys = sorted({k for r in b for k, v in r.items() if k != "date" and isinstance(v, (int, float))})
    return {"baselines_jsonl": bkeys, "data_js": _leaves(_data_js(cfg))}


def _lookup(d: dict, path: str):
    for part in path.split("."):
        if not isinstance(d, dict) or part not in d:
            return None
        d = d[part]
    return d if isinstance(d, (int, float)) and not isinstance(d, bool) else None


def read_metric(cfg, source: str, key: str, at: Optional[str] = None) -> Tuple[Optional[float], Optional[str]]:
    """Return (value, date_iso). `at` = ISO date; baselines_jsonl returns the nearest row <= at."""
    if source == "baselines_jsonl":
        rows = _baselines(cfg)
        if at:
            rows = [r for r in rows if r["date"][:10] <= at[:10]]
        for r in reversed(rows):
            v = r.get(key)
            if isinstance(v, (int, float)):
                return float(v), r["date"][:10]
        return None, None
    if source == "data_js":
        d = _data_js(cfg)
        v = _lookup(d, key)
        return (float(v), (d.get("lastUpdated") or "")[:10] or dt.date.today().isoformat()) if v is not None else (None, None)
    return None, None


def series(cfg, source: str, key: str) -> List[Tuple[str, float]]:
    if source == "baselines_jsonl":
        return [(r["date"][:10], float(r[key])) for r in _baselines(cfg) if isinstance(r.get(key), (int, float))]
    v, d = read_metric(cfg, source, key)
    return [(d, v)] if v is not None else []
