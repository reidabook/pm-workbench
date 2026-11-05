#!/usr/bin/env python3
"""Regression suite for PM Workbench. Exit 0 = all pass. Add a test for every bug fixed."""
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
os.environ["PMWB_DATA"] = tempfile.mkdtemp(prefix="pmwb-test-")  # isolated DB
# epics live in ACME, their parents (initiatives) in INIT
(Path(os.environ["PMWB_DATA"]) / "config.json").write_text(json.dumps({"jira_project": "ACME", "parent_project": "INIT"}))

from app import db, scoring, xlsx_io, jira_sync  # noqa: E402

# Author-specific fixtures: the legacy spreadsheet is gitignored, so parity tests skip when absent.
XLSX_LEGACY = ROOT / "prioritization" / "epic_prioritization.xlsx"

FAILS = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def sheet_rows():
    data = xlsx_io.read_sheet(XLSX_LEGACY)
    rank_of = dict(data["themes"])
    rows = []
    for d in data["rows"]:
        rows.append({**d, "theme_rank": rank_of.get(d["theme"])})
    return data, rows


def test_scoring_parity_with_xlsx():
    if not XLSX_LEGACY.exists():
        return check("test_scoring_parity_with_xlsx_skipped_no_sheet", True)
    data, rows = sheet_rows()
    comp = scoring.compute(rows, data["params"], max(r for _, r in data["themes"]))
    bad = []
    for c in comp:
        xs, xr, xp, xg = c["x_score"], c["x_rank"], c["x_priority"], c["x_gap"]
        if xs is not None and c["score"] is not None and abs(xs - c["score"]) > 1e-9:
            bad.append((c["key"], "score", xs, c["score"]))
        if (xs is None) != (c["score"] is None):
            bad.append((c["key"], "score-blank", xs, c["score"]))
        if (xr or None) != c["rank"]:
            bad.append((c["key"], "rank", xr, c["rank"]))
        if (xp or None) != c["priority"]:
            bad.append((c["key"], "priority", xp, c["priority"]))
        if (xg or None) != c["gap"]:
            bad.append((c["key"], "gap", xg, c["gap"]))
    check("test_scoring_parity_with_xlsx_all_rows", not bad, str(bad[:5]))
    check("test_scoring_parity_covers_every_sheet_row", len(comp) == len(data["rows"]) > 0, len(comp))


def test_band_math_with_parked_and_forced():
    p = dict(db.DEFAULT_PARAMS)
    rows = [{"key": f"K{i}", "theme_rank": 1, "sv": 5, "ui": 5, "urg": 5, "conf": 5,
             "effort": "S", "park": "", "raise_p1": ""} for i in range(10)]
    rows[0]["sv"] = 1                          # lowest score
    rows[1]["park"] = "bottom"                 # parked: excluded from N
    rows[2]["raise_p1"] = "customer commit"    # forced P1
    rows[2]["sv"] = 2
    comp = {c["key"]: c for c in scoring.compute(rows, p, 3)}
    check("test_parked_row_has_no_score_rank_priority_gap",
          comp["K1"]["score"] is None and comp["K1"]["priority"] is None and comp["K1"]["gap"] is None)
    check("test_forced_p1_overrides_band", comp["K2"]["priority"] == "P1" and comp["K2"]["rank"] is not None)
    check("test_lowest_score_is_p4", comp["K0"]["priority"] == "P4")
    n_scored = sum(1 for c in comp.values() if c["score"] is not None)
    check("test_n_scored_excludes_parked", n_scored == 9)
    ties = [c["rank"] for k, c in comp.items() if k not in ("K0", "K1", "K2")]
    check("test_tied_scores_share_min_rank", set(ties) == {1})
    order = scoring.push_order(list(comp.values()))
    check("test_push_order_forced_first_parked_bottom_last", order[0] == "K2" and order[-1] == "K1")


def test_gap_flag_rules():
    p = dict(db.DEFAULT_PARAMS)
    rows = [{"key": "A", "theme_rank": None, "sv": 5, "ui": 5, "urg": 5, "conf": 5, "effort": "S"},
            {"key": "B", "theme_rank": 1, "sv": 5, "ui": 5, "urg": 5, "conf": 2, "effort": "S"},
            {"key": "C", "theme_rank": 1, "sv": 5, "ui": None, "urg": 5, "conf": 5, "effort": "S"}]
    comp = {c["key"]: c for c in scoring.compute(rows, p, 3)}
    check("test_missing_theme_flags_needs_info_and_unscored", comp["A"]["gap"] == "NEEDS INFO" and comp["A"]["score"] is None)
    check("test_low_confidence_flags_needs_info_but_scores", comp["B"]["gap"] == "NEEDS INFO" and comp["B"]["score"] is not None)
    check("test_blank_input_flags_needs_info", comp["C"]["gap"] == "NEEDS INFO")


def test_xlsx_import_roundtrip():
    db.init()
    if not XLSX_LEGACY.exists():
        return check("test_xlsx_import_roundtrip_skipped_no_sheet", True)
    data = xlsx_io.read_sheet(XLSX_LEGACY)
    res = xlsx_io.import_sheet(XLSX_LEGACY, backup=False)
    check("test_import_counts", res["epics"] == len(data["rows"]) and res["themes"] == len(data["themes"])
          and res["params"] == len(data["params"]), res)
    with db.connect() as con:
        p = db.params(con)
        check("test_import_weights_sum_to_1", abs(sum(p[k] for k in ("w_sv", "w_ui", "w_urg", "w_theme", "w_conf")) - 1) < 1e-9)
        s = db.one(con, "SELECT * FROM scores WHERE epic_ref='ACME-501'")
        check("test_import_preserves_inputs", s and s["sv"] == 4 and s["effort"] == "S")
        themes = db.rows(con, "SELECT * FROM themes ORDER BY priority_rank")
        computed = [{"key": "X", "summary": "s", "theme_name": themes[0]["name"], "sv": 1, "ui": 1, "urg": 1,
                     "conf": 1, "effort": "S", "score": 1.0, "rank": 1, "priority": "P1"}]
        out = Path(os.environ["PMWB_DATA"]) / "exp.xlsx"
        xlsx_io.export_sheet(computed, p, themes, out)
        back = xlsx_io.read_sheet(out)
        check("test_export_reimports_same_params_and_themes",
              back["params"] == {k: float(v) for k, v in p.items()} and dict(back["themes"]) == {t["name"]: t["priority_rank"] for t in themes})


def test_scope_rules_standalone():
    """app.scope_rules must work without prioritization/ on sys.path (portability)."""
    from app.scope_rules import out_of_scope_reason, in_scope
    check("test_scope_rules_no_prioritization_import", "scope" not in sys.modules or sys.modules["scope"].__name__ != "scope")
    epics = [["ACME-1", "a", "Backlog", "To Do"], ["ACME-2", "b", "Waiting To Accept", "In Progress"],
             ["ACME-3", "c", "Closed", "Done"], ["ACME-4", "d", "Analysis", "To Do"]]
    kept = [e for e in epics if not out_of_scope_reason(e[2], e[3])]
    dropped = [e for e in epics if out_of_scope_reason(e[2], e[3])]
    check("test_snapshot_scope_split_nonempty", len(kept) == 2 and len(dropped) == 2)
    check("test_waiting_to_accept_is_out_of_scope", all(e[2] != "Waiting To Accept" for e in kept))
    check("test_closed_reason_says_closed", out_of_scope_reason("Closed", "Done").startswith("closed"))
    check("test_in_dev_reason_says_in_flight", out_of_scope_reason("In Dev", "In Progress").startswith("in flight") and not in_scope("In Dev"))


def test_push_preview_only_diffs_changed_priorities():
    comp = [{"key": "A", "priority": "P1", "rank": 1, "park": None, "forced_p1": False},
            {"key": "B", "priority": "P2", "rank": 2, "park": None, "forced_p1": False},
            {"key": "C", "priority": None, "rank": None, "park": "bottom", "forced_p1": False}]
    cur = {"A": {"priority": "P1", "rank_pos": 1}, "B": {"priority": "P4", "rank_pos": 2}, "C": {"priority": "P3", "rank_pos": 3}}
    pv = jira_sync.push_preview({}, comp, cur)
    check("test_preview_one_priority_change", [c["key"] for c in pv["priorities"]] == ["B"])
    check("test_preview_parked_never_gets_priority", all(c["key"] != "C" for c in pv["priorities"]))
    check("test_preview_rank_unchanged_when_order_same", pv["rank_changed"] is False)


def test_create_epic_payload_has_mandatory_fields():
    cfg = {"jira_project": "ACME", "default_labels": ["Acme"]}  # no jira_fields → example defaults (Cloud-style)
    d = {"summary": "S", "product_owner": "jdoe", "acceptance_criteria": "AC", "outcome": "O",
         "labels": "foo", "bepic_key": "INIT-1", "description": "D"}
    f = jira_sync.epic_payload(cfg, d, 7)["fields"]
    check("test_payload_no_custom_fields_by_default", not any(k.startswith("customfield_") for k in f))
    check("test_payload_ac_and_outcome_kept_in_description", f["description"].startswith("D") and "AC" in f["description"] and "O" in f["description"])
    check("test_payload_default_label_merged", set(f["labels"]) == {"foo", "Acme"})
    check("test_payload_parent_is_issue_ref", f["parent"] == {"key": "INIT-1"})
    check("test_validate_draft_reports_missing", jira_sync.validate_draft({"summary": "x"}, cfg) == ["Acceptance Criteria", "Outcome"])
    cfg_po = {**cfg, "jira_fields": {"product_owner": "customfield_1"}}
    check("test_validate_draft_needs_po_when_field_set", jira_sync.validate_draft({"summary": "x"}, cfg_po) ==
          ["Product Owner", "Acceptance Criteria", "Outcome"])


def test_jira_fields_from_config():
    """Custom-field ids are instance-specific; another PM's Jira must be able to override them."""
    cfg = {"jira_project": "X", "jira_fields": {"product_owner": "customfield_1", "outcome": "customfield_2",
                                                "acceptance_criteria": "customfield_3", "parent_link": "customfield_4",
                                                "portfolio_team": "customfield_5"}}
    d = {"summary": "S", "product_owner": "u", "acceptance_criteria": "AC", "outcome": "O", "bepic_key": "INIT-9"}
    f = jira_sync.epic_payload(cfg, d, 7)["fields"]
    check("test_jira_fields_override_used_in_payload", f["customfield_1"] == {"name": "u"} and f["customfield_2"] == "O"
          and f["customfield_3"] == "AC" and f["customfield_4"] == "INIT-9" and f["customfield_5"] == {"id": "7"})
    check("test_jira_fields_no_hardcoded_ids_left", "customfield_19001" not in f and "customfield_15604" not in f)
    from app.paths import field
    check("test_jira_field_partial_override_falls_back_to_default", field({"jira_fields": {"outcome": "cf_x"}}, "parent_link") == "parent")


def test_config_example_has_no_personal_defaults():
    ex = json.loads((ROOT / "config.example.json").read_text())
    check("test_config_example_no_user_key", "user" not in ex)
    check("test_config_example_empty_teams_labels_dirs_prs",
          ex["portfolio_team_ids"] == {} and ex["default_labels"] == [] and ex["prd_dirs"] == [] and ex["github_prs"] == [])
    check("test_config_example_has_owner_fields_pat_poc", all(k in ex for k in ("default_product_owner", "jira_fields", "jira_pat_file", "poc_repo", "analytics_dir")))
    check("test_config_example_no_acme_strings", "acme" not in json.dumps(ex).lower())
    gi = (ROOT / ".gitignore").read_text()
    check("test_gitignore_excludes_personal_data", all(x in gi for x in ("data/", "*.env", "prioritization/*.xlsx", "prioritization/backups/")))


def test_load_pat_reads_data_env():
    from app import paths
    env_backup = {k: os.environ.pop(k) for k in ("JIRA_PAT", "JIRA_API_TOKEN") if k in os.environ}
    try:
        paths.ENV_FILE.write_text('export JIRA_PAT="tok-from-data-env"\n')
        jira_sync.ENV_FILE.write_text('export JIRA_PAT="tok-from-data-env"\n')
        check("test_load_pat_data_env", jira_sync.load_pat({"jira_pat_file": ""}) == "tok-from-data-env")
        jira_sync.ENV_FILE.unlink()
        pf = Path(os.environ["PMWB_DATA"]) / "pat.txt"
        pf.write_text("bare-token\n")
        check("test_load_pat_cfg_file_bare_token", jira_sync.load_pat({"jira_pat_file": str(pf)}) == "bare-token")
        os.environ["JIRA_PAT"] = "from-env"
        check("test_load_pat_env_wins", jira_sync.load_pat({"jira_pat_file": str(pf)}) == "from-env")
    finally:
        os.environ.pop("JIRA_PAT", None)
        os.environ.update(env_backup)


def test_launch_skill_unknown_platform_returns_copy_only():
    from app import ai_runner
    r = ai_runner._open_terminal("echo hi", platform="plan9")
    check("test_open_terminal_unknown_platform_not_launched", r["launched"] is False and "Copy command" in r["error"])
    sh = ai_runner.skill_command({"pr_workspace": "/tmp/x"}, "review-prd", {"file": "a.md"})["shell"]
    check("test_skill_command_runs_bundled_skill", sh == "cd /tmp/x && claude '/pm-review-prd --file a.md'", sh)
    ws = Path(tempfile.mkdtemp(prefix="pmwb-ws-"))
    n = ai_runner.sync_skills(ws)
    check("test_sync_skills_installs_every_step", n == len(ai_runner.SKILLS) and (ws / ".claude/pm-conventions.md").exists()
          and all((ws / ".claude/skills" / ai_runner.SKILLS[k]({"file": "f", "files": ["f"], "text": "t"}).split()[0][1:] / "SKILL.md").exists()
                  for k in ai_runner.SKILLS), n)
    check("test_sync_skills_idempotent", ai_runner.sync_skills(ws) == 0)
    check("test_skill_command_has_copyable_shell", "claude" in ai_runner.skill_command({"pr_workspace": "/tmp/x"}, "validate-prd", {"file": "a b.md"})["shell"])


def test_portfolio_context_parser():
    from app import portfolio_context as pc
    md = """# Portfolio Context\n\n## Priority Tiers\n\n| Tier | Initiative | Investment Theme | Program Epic | Status |\n|---|---|---|---|---|\n| P0 | Saved carts GA | Trust | INIT-504 | active |\n| P1 |  |  |  |  |\n| P1 | Wishlist | Reach | n/a | idea |\n\n## Investment Themes\n\n| Theme | Description |\n|---|---|\n| Trust | x |\n\n## Program Jira Keys\n\n| Program | Jira Project | Epic Prefix | Owner |\n|---|---|---|---|\n| Acme | ACME | ACME- | me |\n"""
    f = Path(os.environ["PMWB_DATA"]) / "portfolio-context.md"
    f.write_text(md)
    r = pc.parse(f)
    check("test_portfolio_tiers_skip_blank_rows", [t["initiative"] for t in r["tiers"]] == ["Saved carts GA", "Wishlist"])
    check("test_portfolio_tier_fields", r["tiers"][0]["tier"] == "P0" and r["tiers"][0]["program_epic"] == "INIT-504")
    check("test_portfolio_programs_parsed", r["programs"] == [{"program": "Acme", "project": "ACME", "prefix": "ACME-", "owner": "me"}])
    check("test_portfolio_missing_file_is_empty", pc.parse(f.parent / "nope.md") == {"tiers": [], "programs": []})


def test_startup_has_no_xlsx_autoimport():
    src = (ROOT / "app" / "main.py").read_text()
    check("test_no_xlsx_legacy_reference_in_app", "XLSX_LEGACY" not in src)
    check("test_import_xlsx_is_upload", "async def import_xlsx(file: UploadFile" in src)


def test_prd_epic_key_extraction():
    from app import prd_pipeline as pp
    md = "---\ntitle: X\ntype: prd\nbepic_key: INIT-505\n---\n# Feature EPIC: X\n| Field | Value |\n|--|--|\n| **Epic Key** | [ACME-502](https://jira.example/browse/ACME-502) |\n"
    check("test_prd_epic_key_regex_returns_full_key", pp._epic_keys(md) == {"ACME-502"}, pp._epic_keys(md))
    check("test_prd_epic_key_ignores_bepic", "INIT-505" not in pp._epic_keys(md))
    check("test_prd_epic_key_jira_link_row", pp._epic_keys("| Jira | https://x/browse/ACME-506 |") == {"ACME-506"})
    check("test_prd_frontmatter_parsed", pp._frontmatter(md).get("bepic_key") == "INIT-505")


def test_github_artifact_detection():
    from app import github_refs as gr
    check("test_gh_matches_folder_prd", gr.ARTIFACT_RE.search("a/b/INIT-1-x/prd.md").group(1) == "prd")
    check("test_gh_matches_suffixed_prd", gr.ARTIFACT_RE.search("a/acme-retention--delete/acme-retention--delete-prd.md").group(1) == "prd")
    check("test_gh_hld_not_prd", gr.ARTIFACT_RE.search("a/x/hld.md").group(1) == "hld")
    check("test_gh_ignores_index_yaml", gr.ARTIFACT_RE.search("a/x/index.yaml") is None)
    check("test_gh_slug_title_strips_key", gr.slug_title("d/features/INIT-504-acme-search-observability-and-metrics/prd.md") == "Acme Search Observability And Metrics")
    check("test_github_title_normalisation_matches_quotes",
          gr.norm_title('Acme Answers “How to Use Acme” (End-User Self-Knowledge)') ==
          gr.norm_title('Acme Answers "How to Use Acme" (End User Self-Knowledge)'))
    check("test_github_title_normalisation_strips_leading_jira_key",
          gr.norm_title("ACME-510 — Acme user session traceability") == gr.norm_title("Acme user session traceability"))
    check("test_github_title_normalisation_strips_feature_epic_prefix",
          gr.norm_title("Feature EPIC: Contextual AI Authoring — Platform") == gr.norm_title("Contextual AI Authoring Platform"))


def test_prd_stage_semantics():
    from app import prd_pipeline as pp
    src = __import__("inspect").getsource(pp.scan)
    check("test_frontmatter_pr_link_means_in_pr_not_published", 'stage = "in-pr" if pr_url else' in src)
    check("test_only_merged_pr_state_promotes_to_published", 'prev["pr_state"] == "merged"' in src)


def test_prd_does_not_link_jira_sources_as_epics():
    from app import artifacts as A, prd_pipeline as pp
    check("test_epic_keys_skip_source_tickets", pp._epic_keys("# PRD\nFrom defect ACME-507 and epic ACME-508\n", None, {"ACME-507"}) == {"ACME-508"})
    check("test_epic_keys_passing_mention_must_be_known_epic", pp._epic_keys("# PRD\nSee ACME-509 and ACME-508\n", {"ACME-508"}) == {"ACME-508"}
          and pp._epic_keys("| **Epic Key** | ACME-509 |\n", {"ACME-508"}) == {"ACME-509"})
    db.init()
    ws, _ = _ws()
    prd = ws / "prds" / "defect-led_2026-10-01.md"
    prd.write_text('---\ntitle: "Defect led PRD"\ntype: "prd"\n---\n# Defect led PRD\n\nSource: ACME-507 upload fails\n')
    with db.tx() as con:
        con.execute("INSERT INTO sources(filename,kind,text,url) VALUES('ACME-507: upload fails','jira','x','https://jira.example/browse/ACME-507')")
        con.execute("INSERT OR IGNORE INTO prds(path,title) VALUES(?,?)", (str(prd), "Defect led PRD"))
        pid = db.one(con, "SELECT id FROM prds WHERE path=?", (str(prd),))["id"]
        con.execute("INSERT OR IGNORE INTO prd_epics(prd_id,epic_key) VALUES(?,'ACME-507')", (pid,))  # linked by the old scan
    pp.scan({"pr_workspace": str(ws), "prd_dirs": []}, A.checkpoint_aliases(ws))
    with db.tx() as con:
        got = [r["epic_key"] for r in db.rows(con, "SELECT epic_key FROM prd_epics WHERE prd_id=?", (pid,))]
        con.execute("DELETE FROM sources WHERE kind='jira' AND url LIKE '%ACME-507'")
    prd.unlink()
    check("test_scan_unlinks_and_skips_jira_source_keys", got == [], got)


def test_refined_prd_is_the_single_row():
    from app import prd_pipeline as pp
    R = lambda n, since=None: {"review-prd": {"count": n, "running_since": since}, "validate-prd": {"count": 0, "running_since": None}}  # noqa: E731
    prds = [
        {"id": 1, "path": "/w/prds/x_2026-10-01.md", "title": "X", "initiative": "x", "stage": "reviewed", "mtime": 1, "review_at": "2026-10-01T10:00:00",
         "validation_at": None, "epics": ["ACME-1"], "note": "Planned: Pod 2", "runs": R(2)},
        {"id": 2, "path": "/w/refined-prds/x_v1_refined_2026-10-01.md", "title": "X", "initiative": "x", "stage": "validated", "mtime": 2, "review_at": None,
         "validation_at": "2026-10-01T11:00:00", "validation_result": "PASS", "epics": ["ACME-2"], "note": None, "runs": R(1, "2026-10-01T12:00:00")},
        {"id": 3, "path": "/w/refined-prds/x_v2_refined_2026-10-02.md", "title": "X", "initiative": "x", "stage": "drafted", "mtime": 3, "review_at": None,
         "validation_at": None, "epics": [], "note": None, "runs": R(0)},
        {"id": 4, "path": "/w/prds/y.md", "title": "Y", "initiative": "y", "stage": "drafted", "mtime": 4, "epics": [], "runs": R(0)},
        {"id": 5, "path": "gh/x/prd.md", "title": "X", "initiative": "x", "source": "github", "stage": "published", "mtime": 5, "epics": [], "runs": R(0)},
    ]
    pp.collapse_refined(prds)
    m = prds[2]
    check("test_newest_refined_is_primary", [p.get("superseded_by") for p in prds] == [3, 3, None, None, None])
    check("test_primary_links_original_and_earlier_refined", [(v["id"], v["label"]) for v in m["versions"]] == [(2, "earlier refined"), (1, "original")])
    check("test_primary_carries_family_status", m["stage"] == "validated" and m["review_at"] == "2026-10-01T10:00:00" and m["validation_result"] == "PASS"
          and m["epics"] == ["ACME-1", "ACME-2"] and m["note"] == "Planned: Pod 2"
          and m["runs"]["review-prd"] == {"count": 3, "running_since": "2026-10-01T12:00:00"})
    check("test_unrefined_prd_untouched", "versions" not in prds[3] and "superseded_by" not in prds[3])


def test_prd_review_validate_tracking():
    """Launching review / validate is tracked per PRD, settles when the report appears, and can be repeated."""
    import datetime as dtm
    from app import artifacts as A, prd_pipeline as pp
    db.init()
    ws, _ = _ws()
    cfg = {"pr_workspace": str(ws), "prd_dirs": []}
    prd = ws / "prds" / "acme-loyalty-tiers_2026-09-11.md"
    rev = ws / "reviews" / "acme-loyalty-tiers_2026-09-11_review.md"
    rev.unlink(missing_ok=True)
    ago = lambda m: (dtm.datetime.now() - dtm.timedelta(minutes=m)).isoformat(timespec="seconds")  # noqa: E731

    def launch(kind, started):
        with db.tx() as con:
            return con.execute("INSERT INTO ai_runs(kind,cmd,status,started) VALUES(?,?,'launched',?)",
                               (kind, f"/product-refinement:{kind.split(':')[1]} {prd}", started)).lastrowid

    def state():
        with db.connect() as con:
            rows = db.rows(con, "SELECT * FROM prds WHERE path=?", (str(prd),))
            pp.run_summary(con, rows)
            return rows[0], pp.pending_runs(con)

    r1 = launch("skill:review-prd", ago(5))
    pp.scan(cfg, A.checkpoint_aliases(ws))
    p, pending = state()
    check("test_review_running_until_report_exists", p["review_at"] is None and p["runs"]["review-prd"] == {"count": 1, "running_since": p["runs"]["review-prd"]["running_since"]}
          and p["runs"]["review-prd"]["running_since"] and pending >= 1)
    rev.write_text("# Review\n")
    pp.scan(cfg, A.checkpoint_aliases(ws))
    p, _ = state()
    with db.connect() as con:
        st = db.one(con, "SELECT status, finished FROM ai_runs WHERE id=?", (r1,))
    check("test_review_settles_when_report_appears", p["review_at"] and p["stage"] == "reviewed" and st["status"] == "done"
          and st["finished"] == p["review_at"] and p["runs"]["review-prd"]["running_since"] is None)
    future = (dtm.datetime.now() + dtm.timedelta(minutes=1)).isoformat(timespec="seconds")
    r2 = launch("skill:review-prd", future)  # second run: the old report must not close it
    pp.scan(cfg, A.checkpoint_aliases(ws))
    p, _ = state()
    check("test_review_rerun_stays_running_on_old_report", p["runs"]["review-prd"]["count"] == 2 and p["runs"]["review-prd"]["running_since"] == future and p["review_at"])
    t = dtm.datetime.now().timestamp() + 120
    os.utime(rev, (t, t))
    pp.scan(cfg, A.checkpoint_aliases(ws))
    p, _ = state()
    check("test_review_rerun_settles_on_newer_report", p["runs"]["review-prd"] == {"count": 2, "running_since": None})
    launch("skill:validate-prd", ago(200))  # abandoned: older than the running window
    p, _ = state()
    check("test_stale_launch_not_shown_as_running", p["runs"]["validate-prd"] == {"count": 1, "running_since": None})
    with db.tx() as con:
        con.execute("DELETE FROM ai_runs WHERE kind LIKE 'skill:%'")
    rev.unlink()


def test_prd_note_roundtrip():
    db.init()
    with db.tx() as con:
        con.execute("INSERT OR IGNORE INTO prds(path,title,stage) VALUES('gh:test:x/prd.md','Note test','in-pr')")
        pid = db.one(con, "SELECT id FROM prds WHERE path='gh:test:x/prd.md'")["id"]
        con.execute("UPDATE prds SET note=? WHERE id=?", ("Planned: Pod 2", pid))
    with db.connect() as con:
        check("test_prd_note_roundtrip", db.one(con, "SELECT note FROM prds WHERE id=?", (pid,))["note"] == "Planned: Pod 2")
        cols = {r[1] for r in con.execute("PRAGMA table_info(prds)")}
        check("test_prd_migration_columns_present", {"github_url", "pr_state", "note", "source"} <= cols)


def test_okr_math():
    from app import okr
    check("test_kr_progress_direction_down", abs(okr.kr_progress({"baseline": 10, "target": 5, "current": 7.5}) - 0.5) < 1e-9)
    check("test_kr_progress_clamped", okr.kr_progress({"baseline": 0, "target": 10, "current": 15}) == 1.0
          and okr.kr_progress({"baseline": 0, "target": 10, "current": -3}) == 0.0)
    check("test_kr_progress_none_when_missing", okr.kr_progress({"baseline": 0, "target": 10, "current": None}) is None)
    tp = okr.theme_progress([0.5, None, 1.0])
    check("test_theme_progress_ignores_unmeasured", abs(tp["progress"] - 0.75) < 1e-9 and tp["unmeasured"] == 1)
    import datetime as dt
    per = {"start": "2027-01-01", "end": "2027-03-31"}
    mid = dt.date(2027, 2, 14)  # ~50% elapsed
    check("test_health_bands", okr.health(0.9, per, None, mid) == "ahead" and okr.health(0.5, per, None, mid) == "on_track"
          and okr.health(0.1, per, None, mid) == "behind" and okr.health(None, per, None, mid) == "unmeasured"
          and okr.health(0.1, per, "2027-02-01", mid) == "measuring")
    check("test_health_unmeasured_wins_over_measuring_when_no_progress", okr.health(None, per, "2027-02-01", mid) == "unmeasured")
    check("test_kr_lint_flags_bad_definitions",
          any("equals" in w for w in okr.kr_lint({"baseline": 5, "target": 5, "direction": "up", "title": "x 5%"}))
          and any("below" in w for w in okr.kr_lint({"baseline": 5, "target": 3, "direction": "up", "title": "x 5%"}))
          and any("above" in w for w in okr.kr_lint({"baseline": 5, "target": 9, "direction": "down", "title": "x 5%"}))
          and any("manual" in w for w in okr.kr_lint({"source": "manual", "baseline": None, "target": 3, "title": "x 5%"}))
          and any("measurable" in w for w in okr.kr_lint({"baseline": 1, "target": 2, "direction": "up", "title": "Make it better"}))
          and okr.kr_lint({"baseline": 1, "target": 2, "direction": "up", "title": "Help rate to 95%", "source": "manual"}) == [])
    krs = [{"title": "Help rate up", "metric_key": "help_rate", "baseline": 88.5, "target": 95, "unit": "%", "direction": "up"},
           {"title": "Latency down", "metric_key": "p50_latency", "baseline": 4, "target": 2.5, "direction": "down"}]
    existing = "Users can delete history.\n\nh3. Key Results\n* old — x: 1 → 2 (higher is better)\n_(managed by PM Workbench)_\n\nFooter note."
    merged = okr.merge_outcome(existing, krs)
    back = okr.parse_outcome_block(merged)
    check("test_outcome_block_roundtrip_preserves_outside_text", merged.startswith("Users can delete history.") and merged.endswith("Footer note.")
          and "old — x" not in merged)
    check("test_outcome_block_parses_back", len(back) == 2 and back[0]["metric_key"] == "help_rate" and back[0]["unit"] == "%"
          and back[1]["direction"] == "down" and back[1]["target"] == 2.5, back)
    check("test_outcome_block_appends_when_absent", okr.merge_outcome("plain text", krs).startswith("plain text\n\nh3. Key Results"))


def test_metric_sources():
    from app import metrics
    import json as _j, os as _o
    d = Path(_o.environ["PMWB_DATA"]) / "ba"
    d.mkdir(exist_ok=True)
    (d / "metrics-history.jsonl").write_text("\n".join(_j.dumps(r) for r in [
        {"date": "2026-09-01", "help_rate": 88.0}, {"date": "2026-09-15", "help_rate": 90.5}, {"date": "2026-09-29", "help_rate": 91.2}]))
    (d / "data.js").write_text('window.METRICS = {"lastUpdated": "2026-09-29T08:00:00Z", "usage": {"weekly_active_users": 36, "min_n": 30}, "flag": true};')
    cfg = {"analytics_dir": str(d)}
    check("test_baselines_jsonl_nearest_row_at_date", metrics.read_metric(cfg, "baselines_jsonl", "help_rate", at="2026-09-20") == (90.5, "2026-09-15"))
    check("test_baselines_jsonl_latest", metrics.read_metric(cfg, "baselines_jsonl", "help_rate") == (91.2, "2026-09-29"))
    check("test_data_js_dotted_lookup", metrics.read_metric(cfg, "data_js", "usage.weekly_active_users") == (36.0, "2026-09-29"))
    keys = metrics.list_metric_keys(cfg)
    check("test_metric_keys_listed", keys["baselines_jsonl"] == ["help_rate"] and "usage.weekly_active_users" in keys["data_js"] and "flag" not in keys["data_js"])
    check("test_series_len", len(metrics.series(cfg, "baselines_jsonl", "help_rate")) == 3)


def test_retro_lifecycle():
    from app import retro
    db.init()
    with db.tx() as con:
        con.execute("INSERT OR REPLACE INTO epics(key,summary,status,status_category,resolution,closed_at) VALUES('ACME-1','a','Closed','Done',\"Won't Do\",'2026-08-01')")
        con.execute("INSERT OR REPLACE INTO epics(key,summary,status,status_category,resolution,closed_at) VALUES('ACME-2','b','Closed','Done','Done','2026-08-02')")
        con.execute("INSERT OR REPLACE INTO epics(key,summary,status,status_category) VALUES('ACME-3','c','Analysis','To Do')")
        n1 = retro.backfill(con)
        n2 = retro.backfill(con)
        r1 = db.one(con, "SELECT * FROM retros WHERE epic_key='ACME-1'")
        check("test_retro_backfill_opens_closed_only", n1 == 2 and db.one(con, "SELECT 1 FROM retros WHERE epic_key='ACME-3'") is None)
        check("test_retro_backfill_idempotent", n2 == 0)
        check("test_retro_opens_on_closed_and_flags_wont_do", r1["status"] == "pending" and (r1["omit_reason"] or "").startswith("suggested"))
    issue = {"fields": {"created": "2026-05-01T10:00:00.000+0000", "resolutiondate": "2026-08-02T10:00:00.000+0000", "assignee": None,
                        "comment": {"comments": []}},
             "changelog": {"histories": [
                 {"created": "2026-06-01T09:00:00.000+0000", "items": [{"field": "status", "fromString": "Analysis", "toString": "In Dev"}]},
                 {"created": "2026-07-15T09:00:00.000+0000", "items": [{"field": "status", "fromString": "In Dev", "toString": "Closed"}]},
                 {"created": "2026-07-20T09:00:00.000+0000", "items": [{"field": "status", "fromString": "Closed", "toString": "In Dev"}]},
                 {"created": "2026-08-02T09:00:00.000+0000", "items": [{"field": "status", "fromString": "In Dev", "toString": "Closed"}]}]}}
    life = retro._lifecycle(issue)
    check("test_retro_lifecycle_days_and_reopens", life["first_dev"] == "2026-06-01" and life["days_analysis"] == 31
          and life["days_dev"] == 62 and life["reopens"] == 1 and life["status_changes"] == 4, life)
    scope = retro._scope([{"key": "S1", "summary": "", "status": "Done", "created": "2026-05-20", "resolved": "2026-07-01", "assignee": "A", "points": 3},
                          {"key": "S2", "summary": "", "status": "Done", "created": "2026-06-10", "resolved": None, "assignee": "B", "points": None}], "2026-06-01")
    check("test_snapshot_reason_windows", [w for w, _ in retro.WINDOWS] == ["release", "+30", "+60", "+90"])
    check("test_retro_scope_creep_counts_stories_after_dev_start", scope["stories"] == 2 and scope["added_after_dev_start"] == 1 and scope["story_points"] == 3)


def test_pull_gone_set_arithmetic():
    """Regression: `known` became a dict (key -> status_category); gone must use set(known)."""
    import inspect
    src = inspect.getsource(jira_sync.pull)
    check("test_pull_gone_uses_set_of_known", "gone = set(known) - seen" in src)


def test_validation_evidence():
    from app import evidence as ev
    p = dict(db.DEFAULT_PARAMS)
    check("test_validation_no_evidence_is_1", ev.validation_score([], p) == 1.0)
    comp_only = [{"type": "competitor"}, {"type": "competitor"}, {"type": "competitor"}]
    check("test_validation_competitor_only_capped_low", ev.validation_score(comp_only, p) == 1.5)
    mixed = [{"type": "competitor"}, {"type": "customer"}, {"type": "user_data"}]
    check("test_validation_breadth_beats_volume", ev.validation_score(mixed, p) == 5.0)
    two_customers = [{"type": "customer"}, {"type": "customer"}]
    check("test_validation_repeat_adds_little", ev.validation_score(two_customers, p) == 2.75)
    many_customers = [{"type": "customer"}] * 10
    check("test_validation_repeat_capped", ev.validation_score(many_customers, p) == 3.0)
    # scoring: w_val = 0 keeps parity; w_val > 0 lifts validated epics
    base = {"key": "A", "theme_rank": 1, "sv": 3, "ui": 3, "urg": 3, "conf": 3, "effort": "S"}
    s0 = scoring.compute([{**base, "validation": 5}], p, 3)[0]["score"]
    s1 = scoring.compute([{**base, "validation": 1}], p, 3)[0]["score"]
    check("test_validation_weight_zero_has_no_effect", s0 == s1)
    p2 = {**p, "w_conf": 0.05, "w_val": 0.10}
    hi = scoring.compute([{**base, "validation": 5}], p2, 3)[0]["score"]
    lo = scoring.compute([{**base, "validation": 1}], p2, 3)[0]["score"]
    check("test_validation_weight_lifts_validated_epic", hi > lo and abs((hi - lo) - 0.4) < 1e-9)
    check("test_validation_missing_defaults_to_1_not_blank", scoring.compute([base], p2, 3)[0]["score"] is not None)
    # carry-over idea -> group -> draft -> epic
    db.init()
    with db.tx() as con:
        con.execute("INSERT INTO ideas(id,title,group_id) VALUES(901,'i',77)")
        ev.add(con, "idea:901", "customer", "CAB said so", "https://x")
        ev.add(con, "group:77", "competitor", "Acme has it")
        n = ev.carry_group(con, 77, "draft:5")
        got = ev.for_refs(con, ["draft:5"])["draft:5"]
        check("test_evidence_carry_group_collects_ideas_and_group", n == 2 and {g["type"] for g in got} == {"customer", "competitor"})
        n2 = ev.carry(con, "draft:5", "ACME-1")
        n3 = ev.carry(con, "draft:5", "ACME-1")
        check("test_evidence_carry_idempotent", n2 == 2 and n3 == 0)
    # uploaded source -> evidence on its ideas (AI-extracted or hand-added), typed now or later
    with db.tx() as con:
        con.execute("INSERT INTO sources(id,filename,kind,text,ingested_at) VALUES(950,'cab.md','notes','x','2026-09-30T10:00:00')")
        con.execute("INSERT INTO ideas(id,title,quote,source_id,group_id) VALUES(951,'a','we need bulk delete',950,78)")
        con.execute("INSERT INTO ideas(id,title,source_id,group_id) VALUES(952,'b',950,78)")
        check("test_source_untyped_adds_no_evidence", ev.sync_source(con, 950) == 0)
        con.execute("UPDATE sources SET evidence_type='customer' WHERE id=950")
        n = ev.sync_source(con, 950)
        got_s = ev.for_refs(con, ["idea:951", "idea:952"])
        check("test_source_becomes_evidence_for_its_ideas", n == 2 and got_s["idea:951"][0]["note"] == "we need bulk delete"
              and got_s["idea:952"][0]["note"] == "From cab.md" and got_s["idea:951"][0]["source_id"] == 950
              and got_s["idea:951"][0]["occurred_at"] == "2026-09-30")
        ev.add(con, "idea:951", "internal", "by hand")
        con.execute("UPDATE sources SET evidence_type='prospect' WHERE id=950")
        n = ev.sync_source(con, 950)
        types = sorted(e["type"] for e in ev.for_refs(con, ["idea:951"])["idea:951"])
        check("test_source_retype_updates_not_duplicates", n == 0 and types == ["internal", "prospect"])
        con.execute("DELETE FROM evidence WHERE ref='idea:952'")
        check("test_source_sync_scoped_to_new_ideas", ev.sync_source(con, 950, []) == 0 and not ev.for_refs(con, ["idea:952"]))
        ev.sync_source(con, 950)
        n = ev.carry_group(con, 78, "draft:6")
        check("test_source_evidence_reaches_group_draft", n == 3 and {e["source_id"] for e in ev.for_refs(con, ["draft:6"])["draft:6"]} == {950, None})
    from app import main
    iid = main.add_idea(main.IdeaIn(title="by hand", source_id=950))["ids"][0]
    with db.connect() as con:
        check("test_hand_added_idea_inherits_source_evidence", [e["type"] for e in ev.for_refs(con, [f"idea:{iid}"]).get(f"idea:{iid}", [])] == ["prospect"])
    # Jira story / defect as a source
    from app import ideas as ideas_mod
    cfg = {"jira_base": "https://jira.example", "jira_fields": {"acceptance_criteria": "customfield_14400"}}
    check("test_jira_issue_keys_from_text_and_links", jira_sync.issue_keys("ACME-12, https://jira.example/browse/ACME-34 ps-9 ACME-12") == ["ACME-12", "ACME-34"])
    iss = jira_sync.issue_source(cfg, {"key": "ACME-12", "fields": {"summary": "Upload fails", "issuetype": {"name": "Defect"},
          "status": {"name": "Open"}, "description": "Steps to repro", "customfield_14400": "Upload works", "created": "2026-09-01T10:00:00.000+0000",
          "comment": {"comments": [{"author": {"displayName": "Ann"}, "created": "2026-09-02T00:00:00", "body": "Seen at 3 customers"}]}}})
    check("test_jira_issue_source_text", iss["is_defect"] and iss["url"] == "https://jira.example/browse/ACME-12" and all(
        x in iss["text"] for x in ("# ACME-12: Upload fails", "- Type: Defect", "## Description", "Steps to repro", "## Acceptance criteria", "Seen at 3 customers")))
    sid = ideas_mod.ingest_jira(iss)
    sid2 = ideas_mod.ingest_jira({**iss, "text": "refreshed"})
    with db.tx() as con:
        srow = db.one(con, "SELECT * FROM sources WHERE id=?", (sid,))
        check("test_jira_source_readd_refreshes_not_duplicates", sid == sid2 and srow["text"] == "refreshed" and srow["kind"] == "jira")
        con.execute("UPDATE sources SET evidence_type='support' WHERE id=?", (sid,))
        con.execute("INSERT INTO ideas(id,title,source_id) VALUES(960,'fix upload',?)", (sid,))
        ev.sync_source(con, sid)
        check("test_jira_source_evidence_links_to_ticket", ev.for_refs(con, ["idea:960"])["idea:960"][0]["link"] == iss["url"])
    with db.tx() as con:
        eid = ev.add(con, "group:78", "internal", "old note")
    main.edit_evidence(eid, main.EvidenceIn(ref="group:78", type="customer", note=" new note ", link="https://y"))
    with db.connect() as con:
        e2 = next(x for x in ev.for_refs(con, ["group:78"])["group:78"] if x["id"] == eid)
    check("test_evidence_edit", (e2["type"], e2["note"], e2["link"], e2["ref"]) == ("customer", "new note", "https://y", "group:78"))
    html = (ROOT / "static" / "index.html").read_text()
    fnames = __import__("re").findall(r"(?:^|[;}\n ])(?:async )?function (\w+)\(", html)
    check("test_ui_no_duplicate_function_names", not {n for n in fnames if fnames.count(n) > 1}, sorted({n for n in fnames if fnames.count(n) > 1}))
    # fresh data dir: bundles/ and uploads/ are created on demand
    import shutil
    from app.paths import DATA
    for d in ("bundles", "uploads"):
        shutil.rmtree(DATA / d, ignore_errors=True)
    with db.tx() as con:
        con.execute("INSERT INTO idea_groups(id,name) VALUES(78,'Bulk ops')")
    bp = ideas_mod.bundle_group(78)
    check("test_bundle_group_creates_dir_and_carries_evidence", bp.exists() and "## Validation" in bp.read_text() and "we need bulk delete" in bp.read_text())
    check("test_upload_creates_dir", ideas_mod.ingest_file("n.md", b"hi") > 0 and any((DATA / "uploads").iterdir()))
    wiki = ev.render_wiki(got)
    check("test_evidence_wiki_render", wiki.startswith("h3. Validation") and "* CAB said so [https://x]" in wiki)
    check("test_weight_keys_include_validation", "w_val" in db.WEIGHT_KEYS and abs(sum(db.DEFAULT_PARAMS[k] for k in db.WEIGHT_KEYS) - 1) < 1e-9)



# ---------------- P1: PM Journey artifacts ----------------
def _ws():
    """Scratch product-refinement workspace mirroring the real layout (plugin 2.24.0)."""
    ws = Path(os.environ["PMWB_DATA"]) / "ws"
    for d in ("saved-carts-ga/checkpoints", "research", "concept-accepts", "ux-briefs", "reviews", "prd-validations", "generated-hlds", "epics", "refined-prds", "prds"):
        (ws / d).mkdir(parents=True, exist_ok=True)
    src = Path(os.environ["PMWB_DATA"]) / "bepic" / "epic-saved-carts-ga.md"
    src.parent.mkdir(exist_ok=True)
    src.write_text("---\ntitle: Saved Carts — GA\ntype: prd\nbepic_key: INIT-503\n---\n# Saved Carts — GA\n\n| Field | Value |\n|---|---|\n| **Epic Key** | ACME-500 |\n| **UX Required** | Yes |\n| **Legal Review Required** | No |\n| **HLD Ownership** | Engineering |\n| **Flag Intent** | Toggle On |\n")
    (ws / "saved-carts-ga/checkpoints/review-prd-prd-review-qa.md").write_text(
        f'---\ncheckpoint_version: 3\nskill: product-refinement:review-prd\nplugin_version: 2.24.0\n\ninitiative:\n  slug: saved-carts-ga\n  tracker_ref: ACME-500\n  owner: Someone\n\nartifacts:\n  - role: input\n    path: "{src}"\n    sha256: x\n\ngate:\n  id: prd-review-qa\n  result: pass\n---\n')
    (ws / "refined-prds/epic-saved-carts-ga_v1_refined_2026-09-26.md").write_text("---\ntitle: Saved Carts — GA\ntype: prd\nbepic_key: INIT-503\nspec_pr_url: https://github.com/acme/product-specs/pull/17\n---\n# Saved Carts — GA\n| **UX Required** | Yes |\n")
    (ws / "prd-validations/epic_saved_carts_ga_2026-09-28.md").write_text(
        f"# PRD Validation Report: Saved Carts\n\n| Field | Value |\n|---|---|\n| Source | {src} |\n| Gate Result | PASS |\n| POC Confidence | 55/100 |\n")
    (ws / "research/acme-loyalty-tiers_2026-09-11.md").write_text('---\ntitle: "Research — Loyalty"\ntype: "research-synthesis"\n---\n# Research — Loyalty\n')
    (ws / "concept-accepts/acme-loyalty-tiers_2026-09-11.md").write_text('---\ntitle: "Technical Concept Accept: Loyalty"\ntype: "technical-ca"\n---\n# CA\n')
    (ws / "ux-briefs/acme-loyalty-tiers_2026-09-11.md").write_text('---\ntitle: "UX Brief — Loyalty"\ntype: "ux-brief"\n---\n# UX\n')
    (ws / "prds/acme-loyalty-tiers_2026-09-11.md").write_text('---\ntitle: "Loyalty Tiers PRD"\ntype: "prd"\n---\n# Loyalty Tiers PRD\n')
    (ws / "generated-hlds/HLD_acme_loyalty_tiers_v1_2026-09-21.md").write_text('---\ntitle: Loyalty Tiers PRD\ntype: hld\nbepic_key: INIT-505\n---\n# HLD\n')
    (ws / "reviews/HLD_acme_loyalty_tiers_v1_2026-09-21_design_review.md").write_text("# Design review\n\n## Persona Verdicts\n\n| Persona | Verdict |\n|---|---|\n| Product | ok |\n| Architect | requires_manual_review |\n| Security | ok |\n\n## Next\n")
    (ws / "epics/acme-loyalty-tiers_epics_2026-09-22.json").write_text(json.dumps({"epics": [{"title": "E1", "jira_key": "ACME-511", "stories": [
        {"title": "s1", "dor_status": "PASS", "jira_key": "ACME-512"}, {"title": "s2", "dor_status": "FAIL"}]}]}))
    (ws / "jira-manifest.json").write_text(json.dumps({"issues": [{"key": "ACME-512", "epic": "ACME-511"}]}))
    return ws, src


def test_artifact_kind_detection_and_linkage():
    from app import artifacts as A, prd_pipeline as pp
    db.init()
    ws, src = _ws()
    cfg = {"pr_workspace": str(ws), "prd_dirs": [str(src.parent)]}
    link = A.checkpoint_aliases(ws)
    check("test_checkpoint_alias_maps_input_stem_to_slug", link["aliases"].get("epic-saved-carts-ga") == "saved-carts-ga")
    check("test_checkpoint_tracker_ref_is_epic_key", link["trackers"] == {"saved-carts-ga": "ACME-500"})
    check("test_base_slug_strips_hld_version_date", pp.base_slug("HLD_acme_loyalty_tiers_v1_2026-09-21") == "acme-loyalty-tiers"
          and pp.base_slug("epic-saved-carts-ga_v1_refined_2026-09-26") == "epic-saved-carts-ga"
          and pp.base_slug("acme-loyalty-tiers_2026-09-11") == "acme-loyalty-tiers")
    pp.scan(cfg, link); A.scan(cfg, link)
    with db.connect() as con:
        kinds = {r["kind"]: r["n"] for r in db.rows(con, "SELECT kind, COUNT(*) n FROM artifacts GROUP BY kind")}
        check("test_artifact_kinds_detected", kinds.get("checkpoint") == 1 and kinds.get("research") == 1 and kinds.get("ca") == 1
              and kinds.get("ux-brief") == 1 and kinds.get("hld") == 1 and kinds.get("hld-review") == 1 and kinds.get("prd-validation") == 1
              and kinds.get("epics-json") == 1 and kinds.get("jira-manifest") == 1, kinds)
        prds = {r["path"]: r for r in db.rows(con, "SELECT * FROM prds")}
        orig = prds[str(src)]
        check("test_prd_initiative_from_checkpoint", orig["initiative"] == "saved-carts-ga")
        check("test_refined_prd_collapses_into_same_initiative", prds[str(ws / "refined-prds/epic-saved-carts-ga_v1_refined_2026-09-26.md")]["initiative"] == "saved-carts-ga")
        meta = json.loads(orig["meta_json"])
        check("test_prd_meta_rows_parsed", meta.get("ux_required") == "Yes" and meta.get("hld_ownership") == "Engineering" and meta.get("flag_intent") == "Toggle On", meta)
        val = db.one(con, "SELECT * FROM artifacts WHERE kind='prd-validation'")
        check("test_validation_report_parse", val["result"] == "PASS" and val["initiative"] == "saved-carts-ga" and json.loads(val["meta_json"])["poc_confidence"] == "55/100")
        hr = db.one(con, "SELECT * FROM artifacts WHERE kind='hld-review'")
        check("test_hld_review_verdict_aggregation", hr["result"] == "REQUIRES_MANUAL_REVIEW" and hr["initiative"] == "acme-loyalty-tiers")
        check("test_hld_review_blocked_wins", A.parse_hld_review("## Persona Verdicts\n| a | ok |\n| b | blocked |\n")["result"] == "BLOCKED"
              and A.parse_hld_review("## Persona Verdicts\n| a | ok |\n")["result"] == "APPROVED")
        ej = json.loads(db.one(con, "SELECT meta_json FROM artifacts WHERE kind='epics-json'")["meta_json"])
        check("test_epics_json_summary", ej["epics"] == 1 and ej["stories"] == 2 and ej["dor"] == {"PASS": 1, "FAIL": 1} and "ACME-512" in ej["jira_keys"])
        fab = db.one(con, "SELECT * FROM initiatives WHERE slug='acme-loyalty-tiers'")
        check("test_initiative_row_built_with_bepic_and_epics", fab and fab["bepic_key"] == "INIT-505" and "ACME-511" in fab["epic_keys"], fab)
        dug = db.one(con, "SELECT * FROM initiatives WHERE slug='saved-carts-ga'")
        check("test_initiative_epic_from_tracker_ref", dug and "ACME-500" in dug["epic_keys"])


def test_journey_status_and_next_cmd():
    from app import journey, ai_runner
    with db.connect() as con:
        J = {i["slug"]: i for i in journey.build(con, {"pr_workspace": "/tmp/x", "jira_project": "PS"})}
    d = J["saved-carts-ga"]; S = {s["id"]: s for s in d["steps"]}
    check("test_journey_pm_guide_done_from_checkpoint", S["pm-guide"]["status"] == "done")
    check("test_journey_review_prd_done_from_refined_copy", S["review-prd"]["status"] == "done")
    check("test_journey_validate_prd_pass", S["validate-prd"]["status"] == "done")
    check("test_journey_hld_skipped_when_owned_by_engineering", S["generate-hld"]["status"] == "skipped" and S["validate-hld"]["status"] == "skipped")
    check("test_journey_ux_brief_required_when_prd_says_so", S["ux-brief"]["required"] is True and S["ux-brief"]["status"] == "missing")
    check("test_journey_spec_partial_when_pr_open", S["publish-specs"]["status"] == "partial")
    check("test_journey_epics_partial_when_only_jira_link", S["generate-epics-and-stories"]["status"] == "partial")
    check("test_journey_not_ready", d["ready"] is False)
    check("test_journey_next_prefers_refinement_gate_over_ux_brief", d["next"]["skill"] == "generate-epics-and-stories" and "--prd" in d["next"]["slash"] and "refined" in d["next"]["slash"])
    f = J["acme-loyalty-tiers"]; SF = {s["id"]: s for s in f["steps"]}
    check("test_journey_discovery_steps_done", SF["research-synthesis"]["status"] == "done" and SF["concept-accept"]["status"] == "done" and SF["ux-brief"]["status"] == "done")
    check("test_journey_validate_hld_partial_on_manual_review", SF["generate-hld"]["status"] == "done" and SF["validate-hld"]["status"] == "partial")
    check("test_journey_requirements_accept_done_from_manifest", SF["requirements-accept"]["status"] == "done" and "1 stories" in SF["requirements-accept"]["note"])
    check("test_journey_optional_steps_marked_optional", SF["risk-review"]["status"] == "optional" and SF["poc"]["status"] == "optional")
    check("test_skills_cover_journey", all(sid in ai_runner.SKILLS for sid, *_ in journey.STEPS), [sid for sid, *_ in journey.STEPS if sid not in ai_runner.SKILLS])
    cp = ai_runner.SKILLS["publish-specs"]({"files": ["/a/prd.md", "/b/hld.md"], "bepic": "INIT-1"})
    check("test_spec_repeats_file_flag", cp.count("--file") == 2 and cp.endswith("--parent INIT-1"))
    ra = ai_runner.SKILLS["requirements-accept"]({"file": "/e.json", "project": "ACME", "bepic": "INIT-1"})
    check("test_requirements_accept_flags", "--epics /e.json" in ra and "--jira-project ACME" in ra and "--parent INIT-1" in ra)
    check("test_write_skills_flagged", {"publish-specs", "requirements-accept", "poc"} <= ai_runner.WRITE_SKILLS)


def test_journey_zz_manual_edits():  # runs after test_journey_status_and_next_cmd
    from app import journey
    with db.tx() as con:
        con.execute("UPDATE initiatives SET skipped_json=?, poc_url=? WHERE slug='saved-carts-ga'", (json.dumps({"ux-brief": "design owns it"}), "https://poc.example"))
    with db.connect() as con:
        d = next(i for i in journey.build(con, {"pr_workspace": "/tmp/x"}) if i["slug"] == "saved-carts-ga")
    S = {s["id"]: s for s in d["steps"]}
    check("test_journey_skip_recorded_with_reason", S["ux-brief"]["status"] == "skipped" and S["ux-brief"]["note"] == "design owns it")
    check("test_journey_poc_done_from_url", S["poc"]["status"] == "done")


def test_github_sync_keeps_hld():
    from app import github_refs as gr
    src = (ROOT / "app" / "github_refs.py").read_text()
    check("test_github_sync_no_longer_skips_hld", '!= "prd"' not in src and "_upsert_hld" in src)
    check("test_gh_hld_detected", gr.ARTIFACT_RE.search("d/features/INIT-1-x/hld.md").group(1) == "hld")


# ---------------- P2: story readiness (Definition of Ready) ----------------
def test_story_dor_checks():
    from app import dor
    good = {"key": "ACME-1", "summary": "Upload a file", "priority": "P2", "points": 3, "labels": [], "status": "To Do",
            "description": "As a payroll administrator, I want to upload a document so that Acme can answer from it.",
            "acceptance_criteria": "Happy path: Given a signed-in payroll administrator When they upload a PDF Then it is indexed.\n"
                                   "Validation: Given a 20 MB file When uploaded Then a size error message is shown.\n"
                                   "Permissions: Given a user without the entitlement When they open upload Then the control is hidden.\n"
                                   "Edge cases: Given an empty file When uploaded Then nothing is indexed.\n"
                                   "Error handling: Given the indexer times out When retry fails Then the user sees a retry option."}
    r = dor.story_checks(good, published={"ACME-1"})
    check("test_story_dor_gwt_and_categories", r["ready"] and r["passed"] == r["total"] == 7, [c for c in r["checks"] if not c["pass"]])
    bad = {**good, "key": "ACME-2", "points": 13, "priority": None, "description": "As a user, I want stuff [TBD]",
           "acceptance_criteria": "Should work quickly and handle errors appropriately."}
    r = dor.story_checks(bad)
    ids = {c["id"]: c for c in r["checks"]}
    check("test_story_dor_persona_and_points", not ids["persona"]["pass"] and not ids["points"]["pass"] and "13" in ids["points"]["detail"])
    check("test_story_dor_vague_and_todo", not ids["testable"]["pass"] and "quickly" in ids["testable"]["detail"] and not ids["description"]["pass"] and "TBD" in ids["description"]["detail"])
    check("test_story_dor_ac_not_gwt", not ids["ac_format"]["pass"] and "Given/When/Then" in ids["ac_format"]["detail"])
    check("test_story_dor_metric_link_from_manifest_only", not ids["metric_link"]["pass"] and dor.story_checks(good, {"ACME-1"})["checks"][-1]["pass"])
    check("test_story_dor_points_from_option_dict", dor.story_checks({**good, "points": {"value": "5"}})["points"] == 5)
    blocked = dor.story_checks({**good, "labels": ["DoR::Dependency_Risk"]})
    check("test_story_dor_blocker_label", not {c["id"]: c for c in blocked["checks"]}["no_blockers"]["pass"])


def test_epic_readiness_fields():
    from app import dor
    e = {"status": "In Dev", "bepic": "INIT-1", "labels": ["UX::Required"], "description": "Toggle Status When Deployed: Toggle On. Backout: flag off.", "acceptance_criteria": "", "outcome": ""}
    ec = {c["id"]: c for c in dor.epic_checks(e, {"ux_required": "Yes", "legal_required": "Yes"})}
    check("test_epic_checks_pass_set", ec["bepic"]["pass"] and ec["toggle"]["pass"] and ec["backout"]["pass"] and ec["in_dev"]["pass"] and ec["ux_label"]["pass"])
    check("test_epic_checks_legal_label_missing", not ec["legal_label"]["pass"])
    e2 = {"status": "Backlog", "bepic": "", "labels": [], "description": "", "acceptance_criteria": "", "outcome": ""}
    res = dor.assess(e2, [{"key": "ACME-9", "type": "Story", "summary": "x"}, {"key": "ACME-10", "type": "Sub-task", "summary": "y"}])
    check("test_assess_ignores_subtasks_and_counts", res["summary"]["stories"] == 1 and res["summary"]["ready"] == 0 and res["summary"]["epic_ok"] is False)
    check("test_assess_top_failing_listed", res["summary"]["top_failing"] and all(n == 1 for _, n in res["summary"]["top_failing"]))


def test_manifest_crossref_marks_published():
    from app import dor
    with db.connect() as con:
        pub = dor.published_keys(con)
        meta = dor.prd_meta_for_epic(con, "ACME-500")
    check("test_published_keys_from_manifest", pub == {"ACME-512"})
    check("test_prd_meta_for_epic_via_prd_epics", meta.get("ux_required") == "Yes")


def test_kr_owner_due_roundtrip():
    """KR owner/due are stored, surfaced on the OKR board, and kept out of the Jira Outcome block."""
    from app import okr
    db.init()
    with db.tx() as con:
        cols = {r[1] for r in con.execute("PRAGMA table_info(key_results)")}
        check("test_kr_table_has_owner_due_columns", {"owner", "due"} <= cols)
        per = db.one(con, "SELECT * FROM okr_periods ORDER BY start LIMIT 1")
        con.execute("INSERT OR REPLACE INTO epics(key,summary,status,in_scope) VALUES('ACME-KR1','KR epic','To Do',1)")
        con.execute("INSERT INTO key_results(epic_key,period_id,title,source,direction,baseline,target,current,owner,due) "
                    "VALUES('ACME-KR1',?,'Help rate to 95%','manual','up',90,95,92,'jdoe','2027-03-31')", (per["id"],))
    with db.connect() as con:
        b = okr.board({}, con, per, [], [{"key": "ACME-KR1", "theme_id": None, "closed_at": None}])
    kr = b["epics"]["ACME-KR1"]["krs"][0]
    check("test_kr_board_carries_owner_due", kr["owner"] == "jdoe" and kr["due"] == "2027-03-31")
    check("test_kr_outcome_block_excludes_owner_due", "jdoe" not in okr.outcome_block([kr]) and "2027-03-31" not in okr.outcome_block([kr]))
    with db.tx() as con:
        con.execute("DELETE FROM key_results WHERE epic_key='ACME-KR1'"); con.execute("DELETE FROM epics WHERE key='ACME-KR1'")


def test_log_entries_crud_in_state():
    from app import worklog
    db.init()
    with db.tx() as con:
        a = worklog.add(con, "saved-carts-ga", "blocker", "Waiting on spec owner to merge PR 17", owner="jdoe", due="2026-10-03")
        b = worklog.add(con, "ACME-500", "decision", "Ship behind flag", None, None)
        c = worklog.add(con, "saved-carts-ga", "risk", "Legal review may slip")
        bad = None
        try:
            worklog.add(con, "x", "todo", "nope")
        except ValueError as e:
            bad = str(e)
        check("test_log_rejects_unknown_kind", bad is not None)
        check("test_log_rejects_empty_text", _raises(lambda: worklog.add(con, "x", "risk", "   ")))
        worklog.update(con, c, status="closed")
        con.execute("UPDATE log_entries SET closed_at=? WHERE id=?", ("2020-01-01T00:00:00", b))  # pretend closed long ago
        worklog.update(con, b, status="closed")
        con.execute("UPDATE log_entries SET closed_at='2020-01-01T00:00:00' WHERE id=?", (b,))
    with db.connect() as con:
        rec = worklog.recent(con, 30)
        ids = [r["id"] for r in rec]
        check("test_log_recent_has_open_and_recently_closed", a in ids and c in ids)
        check("test_log_recent_excludes_old_closed", b not in ids)
        check("test_log_open_blockers_sort_first", rec[0]["id"] == a and rec[0]["status"] == "open")
        row = db.one(con, "SELECT * FROM log_entries WHERE id=?", (c,))
        check("test_log_close_sets_closed_at", row["status"] == "closed" and row["closed_at"])
    with db.tx() as con:
        worklog.update(con, c, status="open")
        check("test_log_reopen_clears_closed_at", db.one(con, "SELECT closed_at FROM log_entries WHERE id=?", (c,))["closed_at"] is None)
        check("test_log_update_unknown_id_false", worklog.update(con, 999999, text="x") is False)
        for i in (a, b, c):
            worklog.delete(con, i)
        check("test_log_delete", db.one(con, "SELECT COUNT(*) n FROM log_entries")["n"] == 0)
    src = (ROOT / "app" / "main.py").read_text()
    check("test_state_includes_log_and_routes", '"log": log' in src and '@app.post("/api/log")' in src and '@app.put("/api/log/{lid}")' in src and '@app.delete("/api/log/{lid}")' in src)


def _raises(fn):
    try:
        fn()
        return False
    except ValueError:
        return True


def test_initiative_owner_period_in_journey():
    from app import journey
    db.init()
    with db.tx() as con:
        cols = {r[1] for r in con.execute("PRAGMA table_info(initiatives)")}
        check("test_initiatives_table_has_owner_period_columns", {"owner", "target_period_id"} <= cols)
        per = db.one(con, "SELECT * FROM okr_periods ORDER BY start LIMIT 1")
        con.execute("INSERT OR REPLACE INTO initiatives(slug,title,owner,target_period_id,updated_at) VALUES('own-test','Owner test','jdoe',?,'2026-09-30T00:00:00')", (per["id"],))
    with db.connect() as con:
        i = next(x for x in journey.build(con, {"pr_workspace": "/tmp/x"}) if x["slug"] == "own-test")
    check("test_journey_output_carries_owner_and_period", i["owner"] == "jdoe" and i["target_period_id"] == per["id"])
    with db.tx() as con:
        con.execute("DELETE FROM initiatives WHERE slug='own-test'")
    src = (ROOT / "app" / "main.py").read_text()
    check("test_initiative_edit_accepts_owner_period", "owner=COALESCE(?,owner)" in src and "target_period_id=COALESCE(?,target_period_id)" in src)


def test_journey_steps_ids_and_order_unchanged():
    from app import journey
    ids = [s[0] for s in journey.STEPS]
    check("test_journey_step_ids_order_fixed", ids == ["pm-guide", "research-synthesis", "concept-accept", "generate-prd", "risk-review", "ux-brief", "poc",
          "review-prd", "validate-prd", "generate-hld", "validate-hld", "generate-epics-and-stories", "publish-specs", "requirements-accept"], ids)
    check("test_journey_required_flags_fixed", [s[3] for s in journey.STEPS] == [False, False, False, True, False, False, False, True, True, True, True, True, True, True])
    check("test_validate_prd_label_says_prd_gate", dict((s[0], s[1]) for s in journey.STEPS)["validate-prd"] == "Validate PRD (PRD gate)")


def test_ui_today_tab_and_chip_codes():
    html = (ROOT / "static" / "index.html").read_text()
    check("test_ui_today_tab_first", '[["today","Today"],["inbox","Inbox"],["themes","Objectives"],["journey","Journey"],["prds","Artifacts: PRDs & HLDs"],["backlog","Backlog"],["retros","Retros"],["settings","Settings"]]' in html)
    check("test_ui_tab_divs_present", all(f'id="tab-{t}"' in html for t in ("today", "backlog", "themes", "journey", "inbox", "prds", "retros", "settings")))
    check("test_ui_render_map_has_today", "today:rToday" in html and "function rToday()" in html)
    check("test_ui_default_tab_today", 'tab=localStorage.tab||"today"' in html)
    for sid, code in {"pm-guide": "G", "research-synthesis": "RS", "concept-accept": "CA", "generate-prd": "PRD", "risk-review": "RR", "ux-brief": "UX", "poc": "POC",
                      "review-prd": "Rev", "validate-prd": "Val", "generate-hld": "HLD", "validate-hld": "vHLD", "generate-epics-and-stories": "E&S", "publish-specs": "Push", "requirements-accept": "RA"}.items():
        if f'"{sid}":"{code}"' not in html:
            return check("test_ui_chip_codes_complete", False, sid)
    check("test_ui_chip_codes_complete", True)
    check("test_ui_chip_css_auto_width", ".chip{width:auto;min-width:22px;padding:0 5px" in html)
    for fn in ("stale(", "staleBadge(", "busy(", "drawerHead(", "reportMd(", "reportModal(", "glossary(", "logSection(", "journeyLegend(", "initTheme(", "initDor("):
        if f"function {fn}" not in html:
            return check("test_ui_helpers_defined", False, fn)
    check("test_ui_helpers_defined", True)
    check("test_ui_escape_closes_overlay", 'e.key==="Escape"' in html)
    check("test_ui_autoload_skips_when_typing", '["INPUT","TEXTAREA","SELECT"].includes(a.tagName)' in html)
    check("test_ui_no_apostrophe_paths_in_onclick", "onclick=\"skill('review-prd',{file:prdPath(" in html)


def test_theme_level_kr_progress():
    """Objective KRs (epic_key NULL + theme_id) drive theme progress; otherwise the epic mean is used."""
    from app import okr
    db.init()
    with db.tx() as con:
        per = db.one(con, "SELECT * FROM okr_periods ORDER BY start LIMIT 1")
        con.execute("INSERT OR IGNORE INTO themes(name,priority_rank) VALUES('OKR theme',99)")
        tid = db.one(con, "SELECT id FROM themes WHERE name='OKR theme'")["id"]
        con.execute("INSERT INTO key_results(epic_key,period_id,title,source,direction,baseline,target,current) VALUES('ACME-T1',?,'epic kr 50%','manual','up',0,10,5)", (per["id"],))
    themes = [{"id": tid}]
    epics = [{"key": "ACME-T1", "theme_id": tid, "closed_at": None}]
    with db.connect() as con:
        b = okr.board({}, con, per, themes, epics)
    t = b["themes"][tid]
    check("test_theme_progress_from_epics_when_no_objective_kr", abs(t["progress"] - 0.5) < 1e-9 and t["source"] == "epics" and t["krs"] == [])
    with db.tx() as con:
        con.execute("INSERT INTO key_results(epic_key,theme_id,period_id,title,source,direction,baseline,target,current) VALUES(NULL,?,?,'objective kr 100%','manual','up',0,10,10)", (tid, per["id"]))
    with db.connect() as con:
        b = okr.board({}, con, per, themes, epics)
    t = b["themes"][tid]
    check("test_theme_progress_prefers_objective_krs", abs(t["progress"] - 1.0) < 1e-9 and t["source"] == "objective" and len(t["krs"]) == 1
          and abs(t["epic_progress"] - 0.5) < 1e-9, t)
    check("test_objective_kr_not_counted_as_epic", "None" not in b["epics"] and None not in b["epics"])
    check("test_board_keys_unchanged", {"progress", "measured", "unmeasured", "health", "epics"} <= set(t.keys()))
    with db.tx() as con:
        con.execute("DELETE FROM key_results WHERE epic_key='ACME-T1' OR theme_id=?", (tid,))
        con.execute("DELETE FROM themes WHERE id=?", (tid,))


def test_new_objective_import_and_ai_proposals():
    """New objective: BEpic import / AI proposals assign only unthemed epics, one new objective per unclaimed BEpic."""
    from app import main
    db.init()
    epics = [("ACME-N1", "INIT-901"), ("ACME-N2", "INIT-901"), ("ACME-N3", "INIT-902"), ("ACME-N4", "INIT-902"), ("ACME-N5", "")]
    with db.tx() as con:
        con.execute("INSERT INTO themes(name,priority_rank,bepic_key) VALUES('Claimed objective',90,'INIT-902')")
        claimed = con.execute("SELECT id FROM themes WHERE name='Claimed objective'").fetchone()[0]
        for k, b in epics:
            con.execute("INSERT INTO epics(key,summary,status,bepic,in_scope) VALUES(?,?,?,?,1)", (k, f"summary {k}", "To Do", b))
        con.execute("INSERT INTO scores(epic_ref,theme_id) VALUES('ACME-N2',?)", (claimed,))  # already has an objective
    real, main._BEPIC_CACHE = jira_sync.fetch_bepic, {}
    jira_sync.fetch_bepic = lambda cfg, key: (_ for _ in ()).throw(RuntimeError("no PAT"))
    try:
        with db.connect() as con:
            ctx = main._propose_context({}, con)
        prompt = main._propose_prompt(ctx)
        check("test_propose_prompt_unthemed_only", "ACME-N1" in prompt and "ACME-N2" not in prompt, prompt)
        check("test_propose_prompt_flags_claimed", "BEpic INIT-901 [UNCLAIMED]" in prompt and 'BEpic INIT-902 [claimed by existing objective "Claimed objective"]' in prompt
              and "No BEpic:" in prompt, prompt)
        jira_sync.fetch_bepic = lambda cfg, key: {"key": key, "summary": "Faster onboarding", "description": "d"}
        with db.connect() as con:
            ctx = main._propose_context({}, con)
        check("test_propose_prompt_uses_bepic_title", 'BEpic INIT-901 "Faster onboarding" [UNCLAIMED]' in main._propose_prompt(ctx))
    finally:
        jira_sync.fetch_bepic = real
    out = main._sanitize_proposals({"proposals": [
        {"name": "Onboarding", "objective": "Make onboarding fast", "bepic_key": "INIT-901", "epic_keys": ["ACME-N1", "ACME-N2", "ACME-ZZ"]},
        {"name": "Second for same BEpic", "bepic_key": "INIT-901", "epic_keys": ["ACME-N1"]},
        {"name": "New for claimed", "bepic_key": "INIT-902", "epic_keys": ["ACME-N3"]},
        {"name": "claimed objective", "bepic_key": None, "epic_keys": ["ACME-N5"]},
        {"name": "Loose ends", "bepic_key": None, "epic_keys": ["ACME-N5", "ACME-N1"]}],
        "assign_existing": [{"theme": "Claimed objective", "epic_keys": ["ACME-N3", "ACME-N4"]}, {"theme": "Nope", "epic_keys": ["ACME-N5"]}]}, ctx)
    got = {p["name"]: [e["key"] for e in p["epics"]] for p in out["proposals"]}
    check("test_sanitize_proposals", got == {"Onboarding": ["ACME-N1"], "Loose ends": ["ACME-N5"]}, got)
    check("test_sanitize_assign_existing", [(a["theme_id"], [e["key"] for e in a["epics"]]) for a in out["assign_existing"]] == [(claimed, ["ACME-N3", "ACME-N4"])]
          and out["unthemed"] == 4 and out["leftover"] == 0, out)
    r = main.add_theme(main.ThemeIn(name="Onboarding", objective="Make onboarding fast", bepic_key="INIT-901", assign_unthemed=True))
    with db.connect() as con:
        t = db.one(con, "SELECT * FROM themes WHERE id=?", (r["id"],))
        themed = {s["epic_ref"]: s["theme_id"] for s in db.rows(con, "SELECT epic_ref, theme_id FROM scores WHERE epic_ref LIKE 'ACME-N%'")}
    check("test_add_theme_stores_objective", t["objective"] == "Make onboarding fast" and t["bepic_key"] == "INIT-901")
    check("test_add_theme_assigns_unthemed_only", r["assigned"] == 1 and themed == {"ACME-N1": r["id"], "ACME-N2": claimed}, themed)
    check("test_assign_unthemed_by_keys", main.theme_assign_unthemed(claimed, {"epic_keys": ["ACME-N3", "ACME-N1"]}) == {"assigned": 1})
    check("test_add_theme_manual_assigns_nothing", main.add_theme(main.ThemeIn(name="Manual one", bepic_key="INIT-902"))["assigned"] == 0)
    html = (ROOT / "static" / "index.html").read_text()
    check("test_ui_new_objective_modal", "<h3>New objective</h3>" in html and "<h3>Edit objective</h3>" in html and "New theme" not in html
          and all(l in html for l in ('"Manual"', '"Import from parent issue"', '"✦ Propose with AI"')))
    with db.tx() as con:
        con.execute("DELETE FROM scores WHERE epic_ref LIKE 'ACME-N%'")
        con.execute("DELETE FROM epics WHERE key LIKE 'ACME-N%'")
        con.execute("DELETE FROM themes WHERE name IN ('Claimed objective','Onboarding','Manual one')")


def test_compute_all_keeps_jira_priority():
    """Regression: computed priority must not overwrite the Jira mirror priority (priority_cur)."""
    import inspect
    from app import main
    src = inspect.getsource(main.compute_all)
    check("test_compute_all_sets_priority_cur", '"priority_cur": e["priority"]' in src)


def test_generic_jira():
    cloud = {"jira_base": "https://x.atlassian.net", "jira_email": "pm@example.com", "jira_project": "ACME"}
    h = jira_sync._hdr("tok", cloud)["Authorization"]
    check("test_cloud_uses_basic_auth", h.startswith("Basic ") and __import__("base64").b64decode(h[6:]).decode() == "pm@example.com:tok")
    check("test_server_uses_bearer", jira_sync._hdr("tok", {"jira_email": ""})["Authorization"] == "Bearer tok")
    check("test_jql_defaults_to_project", jira_sync.all_jql({"jira_project": "ACME"}) == 'project = "ACME" AND issuetype = Epic ORDER BY Rank ASC')
    check("test_jql_custom_wins", jira_sync.all_jql({"jira_project": "ACME", "epic_jql": "labels = x"}) == "labels = x")
    check("test_jql_team_clause", "cf[42] in (7)" in jira_sync.all_jql({"jira_fields": {"portfolio_team": "customfield_42"}, "portfolio_team_ids": {"7": "T"}}))
    check("test_parent_key_from_cloud_object", jira_sync._key_of({"key": "INIT-3", "id": "1"}) == "INIT-3" and jira_sync._key_of("INIT-4") == "INIT-4")
    s = {"title": "Pay with saved card", "story": "As a buyer, I want...", "acceptance_criteria": ["Given a, When b, Then c"], "points": 3}
    f = jira_sync.story_fields({"jira_project": "ACME"}, s, "ACME-9")
    check("test_story_fields_cloud_parent", f["parent"] == {"key": "ACME-9"} and f["issuetype"] == {"name": "Story"} and "Given a" in f["description"])
    f2 = jira_sync.story_fields({"jira_project": "ACME", "jira_fields": {"epic_link": "customfield_8", "story_points": "customfield_9"}}, s, "ACME-9")
    check("test_story_fields_server_epic_link", f2["customfield_8"] == "ACME-9" and "parent" not in f2 and f2["customfield_9"] == 3)
    from app.paths import is_epic_key, is_parent_key
    check("test_key_classification", is_epic_key("ACME-1") and not is_epic_key("INIT-1") and is_parent_key("INIT-1") and not is_parent_key("ACME-1"))


def test_publish_epics_dry_run():
    import json as _j
    d = Path(tempfile.mkdtemp(prefix="pmwb-ep-"))
    f = d / "x_epics_2026-11-01.json"
    f.write_text(_j.dumps({"epics": [{"title": "E", "jira_key": None, "stories": [
        {"title": "ok", "dor_status": "PASS"}, {"title": "no", "dor_status": "FAIL"}]}]}))
    r = jira_sync.publish_epics_file({"jira_project": "ACME", "pr_workspace": str(d)}, str(f), dry_run=True)
    check("test_publish_dry_run_plans_pass_only", r["plan"] == [{"epic": "E", "epic_key": None, "stories": ["ok"], "held_back": ["no"]}], r)
    check("test_publish_dry_run_writes_nothing", not (d / "jira-manifest.json").exists())


def test_no_internal_references():
    import re as _re
    bad = _re.compile("|".join(w[::-1] for w in ['gku', 'sonork', 'etyrb', 'remrofsnart', 'tnemenifer-tcudorp', 'clds.citnega', 'd\\ ecneulfnoc', 'hsup?.txetnoc', 'niamod?.txetnoc', 'gorfj', 'relacsz']), _re.I)
    hits = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file() and p.suffix in (".py", ".html", ".md", ".json", ".sh", ".ps1")
            and ".venv" not in p.parts and "data" not in p.parts and p.name != "validate_workbench.py" and bad.search(p.read_text(errors="replace"))]
    check("test_no_internal_references", not hits, hits)



def test_course_matches_app():
    """The course (course/) must cover every journey step and name every step that writes outside the machine."""
    import subprocess
    from app import ai_runner, journey
    course = ROOT / "course"
    structure = json.loads((course / "course-structure.json").read_text())
    covered = {s for m in structure["modules"] for l in m["lessons"] for s in l["steps"]}
    ids = [sid for sid, *_ in journey.STEPS]
    check("test_course_steps_exist_in_app", covered <= set(ids) | {"discovery"}, sorted(covered - set(ids)))
    check("test_course_covers_every_step", set(ids) <= covered, sorted(set(ids) - covered))
    rules = (course / "shared" / "teaching-rules.md").read_text()
    guide = (course / structure["assistant"]["path"]).read_text()
    for name, text in (("rules", rules), ("guide", guide)):
        check(f"test_course_{name}_names_write_skills", all(f"/pm-{s}" in text for s in ai_runner.WRITE_SKILLS),
              sorted(s for s in ai_runner.WRITE_SKILLS if f"/pm-{s}" not in text))
    scripts = "\n".join(p.read_text() for p in (course / "lesson-modules").glob("*/CLAUDE.md"))
    named = set(__import__("re").findall(r"(?<![~\w])/pm-([a-z-]+)", scripts))
    slashes = {ai_runner.SKILLS[k]({"file": "f", "files": ["f"], "text": "t"}).split()[0][4:] for k in ai_runner.SKILLS}
    check("test_course_skill_names_exist", named <= slashes, sorted(named - slashes))
    res = subprocess.run([sys.executable, str(course / "scripts" / "build.py"), "--check"], capture_output=True, text=True)
    check("test_course_build_is_current", res.returncode == 0, res.stdout.strip()[-400:])


if __name__ == "__main__":
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]:
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            check(fn.__name__ + "_raised", False, repr(e))
    print(f"\n{'ALL PASS' if not FAILS else f'{len(FAILS)} FAILED: {FAILS}'}")
    sys.exit(1 if FAILS else 0)
