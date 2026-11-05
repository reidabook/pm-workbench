"""SQLite schema + tiny helpers. One connection per call; WAL off (OneDrive-safe)."""
import sqlite3
from contextlib import contextmanager

from .paths import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS themes (
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, description TEXT DEFAULT '',
  priority_rank INTEGER NOT NULL, bepic_key TEXT);
CREATE TABLE IF NOT EXISTS config_params (key TEXT PRIMARY KEY, value REAL NOT NULL);
CREATE TABLE IF NOT EXISTS epics (
  key TEXT PRIMARY KEY, summary TEXT, status TEXT, status_category TEXT, priority TEXT,
  rank_pos INTEGER, labels TEXT DEFAULT '', team TEXT, bepic TEXT, url TEXT,
  in_scope INTEGER DEFAULT 1, scope_reason TEXT, synced_at TEXT);
CREATE TABLE IF NOT EXISTS scores (
  epic_ref TEXT PRIMARY KEY, theme_id INTEGER, sv INTEGER, ui INTEGER, urg INTEGER,
  conf INTEGER, effort TEXT, park TEXT, raise_p1 TEXT, notes TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY, filename TEXT, kind TEXT, text TEXT, ingested_at TEXT);
CREATE TABLE IF NOT EXISTS ideas (
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT DEFAULT '', quote TEXT DEFAULT '',
  source_id INTEGER, status TEXT DEFAULT 'new', theme_id INTEGER, group_id INTEGER,
  created_at TEXT);
CREATE TABLE IF NOT EXISTS idea_groups (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, theme_id INTEGER, prd_id INTEGER,
  draft_id INTEGER, created_at TEXT);
CREATE TABLE IF NOT EXISTS draft_epics (
  id INTEGER PRIMARY KEY, summary TEXT NOT NULL, description TEXT DEFAULT '',
  product_owner TEXT DEFAULT '', acceptance_criteria TEXT DEFAULT '', outcome TEXT DEFAULT '',
  labels TEXT DEFAULT '', theme_id INTEGER, group_id INTEGER, jira_key TEXT,
  created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS prds (
  id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, title TEXT, bepic_key TEXT,
  stage TEXT, review_path TEXT, validation_path TEXT, validation_result TEXT,
  pr_url TEXT, mtime REAL, scanned_at TEXT);
CREATE TABLE IF NOT EXISTS prd_epics (prd_id INTEGER, epic_key TEXT,
  PRIMARY KEY (prd_id, epic_key));
CREATE TABLE IF NOT EXISTS ai_runs (
  id INTEGER PRIMARY KEY, kind TEXT, model TEXT, account TEXT, cmd TEXT, status TEXT,
  est_input_tokens INTEGER, started TEXT, finished TEXT, output_path TEXT, log TEXT);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS evidence (
  id INTEGER PRIMARY KEY, ref TEXT NOT NULL, type TEXT NOT NULL, note TEXT DEFAULT '', link TEXT,
  source_id INTEGER, occurred_at TEXT, created_at TEXT);
CREATE INDEX IF NOT EXISTS evidence_ref ON evidence(ref);
CREATE TABLE IF NOT EXISTS okr_periods (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS key_results (
  id INTEGER PRIMARY KEY, epic_key TEXT, theme_id INTEGER, period_id INTEGER NOT NULL,
  title TEXT NOT NULL, metric_key TEXT, source TEXT DEFAULT 'manual', unit TEXT,
  direction TEXT DEFAULT 'up', baseline REAL, target REAL, current REAL, current_at TEXT,
  notes TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS kr_snapshots (
  id INTEGER PRIMARY KEY, kr_id INTEGER NOT NULL, taken_at TEXT NOT NULL, value REAL, reason TEXT);
CREATE TABLE IF NOT EXISTS artifacts (
  id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, kind TEXT NOT NULL, title TEXT, initiative TEXT,
  initiative_override TEXT, bepic_key TEXT, epic_keys TEXT DEFAULT '', result TEXT, pr_url TEXT, pr_state TEXT,
  github_url TEXT, source TEXT DEFAULT 'local', mtime REAL, scanned_at TEXT, meta_json TEXT);
CREATE INDEX IF NOT EXISTS artifacts_initiative ON artifacts(initiative);
CREATE TABLE IF NOT EXISTS initiatives (
  slug TEXT PRIMARY KEY, title TEXT, title_override TEXT, bepic_key TEXT, bepic_override TEXT,
  epic_keys TEXT DEFAULT '', poc_url TEXT, poc_branch TEXT, skipped_json TEXT, notes TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS story_dor (
  epic_key TEXT PRIMARY KEY, fetched_at TEXT, summary_json TEXT, stories_json TEXT);
CREATE TABLE IF NOT EXISTS retros (
  id INTEGER PRIMARY KEY, epic_key TEXT UNIQUE NOT NULL, status TEXT DEFAULT 'pending',
  omit_reason TEXT, released_at TEXT, lifecycle_json TEXT, scope_json TEXT, context_metrics TEXT,
  links TEXT, what_shipped TEXT, impact TEXT, learnings TEXT, verdict TEXT,
  created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS log_entries (
  id INTEGER PRIMARY KEY, ref TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('decision','risk','blocker')),
  text TEXT NOT NULL, owner TEXT, due TEXT, status TEXT DEFAULT 'open', created_at TEXT, closed_at TEXT);
CREATE INDEX IF NOT EXISTS log_entries_ref ON log_entries(ref);
"""

def _quarters(*years):
    ends = ("03-31", "06-30", "09-30", "12-31")
    return [(f"Q{q} {y}", f"{y}-{3 * q - 2:02d}-01", f"{y}-{ends[q - 1]}") for y in years for q in range(1, 5)]


_Y = __import__("datetime").date.today().year
DEFAULT_PERIODS = _quarters(_Y, _Y + 1)  # this year and next

DEFAULT_PARAMS = {
    "w_sv": 0.30, "w_ui": 0.25, "w_urg": 0.15, "w_theme": 0.15, "w_conf": 0.15,
    "effort_S": 1, "effort_M": 2, "effort_L": 3,
    "band_p1": 0.15, "band_p2": 0.40, "band_p3": 0.70, "conf_gap": 2,
    "w_val": 0.0,  # Validation weight; 0 keeps parity with the legacy sheet until the PM rebalances
    "val_w_user_data": 2.0, "val_w_customer": 1.5, "val_w_prospect": 1.0, "val_w_support": 1.0,
    "val_w_competitor": 0.5, "val_w_internal": 0.5,
}
WEIGHT_KEYS = ("w_sv", "w_ui", "w_urg", "w_theme", "w_conf", "w_val")


def connect():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    return con


@contextmanager
def tx():
    con = connect()
    try:
        yield con
        con.commit()
    finally:
        con.close()


MIGRATIONS = [
    "ALTER TABLE prds ADD COLUMN github_url TEXT",
    "ALTER TABLE prds ADD COLUMN pr_state TEXT",
    "ALTER TABLE prds ADD COLUMN note TEXT",
    "ALTER TABLE prds ADD COLUMN source TEXT DEFAULT 'local'",
    "ALTER TABLE themes ADD COLUMN objective TEXT",
    "ALTER TABLE epics ADD COLUMN resolution TEXT",
    "ALTER TABLE epics ADD COLUMN closed_at TEXT",
    "ALTER TABLE epics ADD COLUMN outcome TEXT",
    "ALTER TABLE epics ADD COLUMN created_at TEXT",
    "ALTER TABLE scores ADD COLUMN val_override REAL",
    "ALTER TABLE sources ADD COLUMN evidence_type TEXT",
    "ALTER TABLE prds ADD COLUMN initiative TEXT",
    "ALTER TABLE prds ADD COLUMN meta_json TEXT",
    "ALTER TABLE key_results ADD COLUMN owner TEXT",
    "ALTER TABLE key_results ADD COLUMN due TEXT",
    "ALTER TABLE initiatives ADD COLUMN owner TEXT",
    "ALTER TABLE initiatives ADD COLUMN target_period_id INTEGER",
    "ALTER TABLE sources ADD COLUMN url TEXT",
    "ALTER TABLE prds ADD COLUMN review_at TEXT",
    "ALTER TABLE prds ADD COLUMN validation_at TEXT",
]


def init():
    with tx() as con:
        con.executescript(SCHEMA)
        for m in MIGRATIONS:
            table = m.split("ALTER TABLE ")[1].split()[0]
            cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
            if m.split(" ADD COLUMN ")[1].split()[0] not in cols:
                con.execute(m)
        for name, s, e in DEFAULT_PERIODS:
            con.execute("INSERT OR IGNORE INTO okr_periods(name,start,end) VALUES(?,?,?)", (name, s, e))
        for k, v in DEFAULT_PARAMS.items():
            con.execute("INSERT OR IGNORE INTO config_params(key,value) VALUES(?,?)", (k, v))


def rows(con, sql, args=()):
    return [dict(r) for r in con.execute(sql, args).fetchall()]


def one(con, sql, args=()):
    r = con.execute(sql, args).fetchone()
    return dict(r) if r else None


def params(con) -> dict:
    return {r["key"]: r["value"] for r in con.execute("SELECT key,value FROM config_params")}


def set_meta(con, key, value):
    con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", (key, str(value)))


def get_meta(con, key, default=None):
    r = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default
