#!/usr/bin/env python3
"""Seed a demo install: a fictional online shop ("Acme Shop") with three initiatives at different journey
stages, scored epics, OKRs, Inbox ideas and a decision log. No Jira, GitHub or Claude calls.

    python scripts/seed_demo.py            # writes demo/data + demo/workspace (both gitignored)
    PMWB_DATA=demo/data ./run.sh           # or: ./run.sh --demo
"""
import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
DATA, WS = DEMO / "data", DEMO / "workspace"
TODAY = dt.date.today()
D = TODAY.isoformat()


def ago(days):
    return (TODAY - dt.timedelta(days=days)).isoformat()


def write(rel, text):
    p = WS / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + "\n")
    return p


def checkpoint(slug, step, inp, out, result="pass", tracker=""):
    write(f"{slug}/checkpoints/{step}.md", f"""---
checkpoint_version: 1
skill: {step}
updated_at: {D}T09:00:00
initiative:
  slug: {slug}
  tracker_ref: {tracker}
gate:
  result: {result}
artifacts:
  - role: input
    path: "{inp}"
  - role: output
    path: "{out}"
---
{step} done for {slug}.""")


def prd(rel, title, slug, epic="", parent="", ux="Yes", hld="Product"):
    return write(rel, f"""---
title: "{title}"
type: prd
initiative: {slug}
bepic_key: "{parent}"
---
# {title}

| Field | Value |
|---|---|
| **Epic Key** | {epic} |
| **Owner** | Demo PM |
| **UX Required** | {ux} |
| **Legal Required** | No |
| **HLD Ownership** | {hld} |
| **Flag Intent** | Release toggle |
| **Flag Name** | {slug.replace('-', '_')} |
| **Spec Status** | Not published |

## Problem
Shoppers abandon checkout when it asks for too much. 38% of mobile carts that reach checkout are not completed.

## Goals & success metrics
- Mobile checkout completion 62% → 70% within one quarter of launch.
- Median checkout time 94 s → 60 s.

## Requirements
1. Returning shoppers see their saved address and payment preselected.
2. Guest shoppers can pay without creating an account.
3. Every error message says what to fix.

## Rollout & backout
Behind `{slug.replace('-', '_')}`; 10% → 50% → 100% over two weeks. Backout: flag off.
""")


def workspace():
    if WS.exists():
        shutil.rmtree(WS)
    write("portfolio-context.md", """
# Portfolio Context

Acme Shop — direct-to-consumer storefront. Team: Checkout & Payments.

## Priority Tiers

| Tier | Initiative | Investment Theme | Parent Key | Status |
|---|---|---|---|---|
| P0 | Faster checkout | Conversion | INIT-10 | active |
| P1 | Trust & safety | Retention | INIT-11 | active |
| P2 | Merchant insights | Growth | INIT-12 | idea |

## Program Jira Keys

| Program | Jira Project | Key Prefix | Owner |
|---|---|---|---|
| Checkout | ACME | ACME- | Demo PM |
""")
    # 1) faster-checkout: through every gate → Ready
    s = "faster-checkout"
    write(f"{s}/pm-context.md", "# Faster checkout\n\nProblem, users, evidence, goal: mobile completion 62% → 70%.")
    r = write(f"research/faster_checkout_{ago(30)}.md", "# Research synthesis: Faster checkout\n\n## Themes\n1. Re-entering card details (14 of 20 interviews).")
    ca = write(f"concept-accepts/faster_checkout_{ago(25)}.md", f'---\ntitle: "Faster checkout"\ninitiative: {s}\ntype: go-ca\n---\n# Concept Accept: go')
    p1 = prd(f"prds/faster_checkout_v1_{ago(20)}.md", "Faster Checkout", s, "ACME-101", "INIT-10")
    write("reviews/" + p1.stem + "_review.md", "# PRD review: Faster Checkout\n\nVerdict: ready after edits.")
    p2 = prd(f"refined-prds/faster_checkout_v2_refined_{ago(15)}.md", "Faster Checkout", s, "ACME-101", "INIT-10")
    write(f"prd-validations/faster_checkout_validation_{ago(12)}.md", f"""
# PRD validation: Faster Checkout
Initiative `{s}`

| Field | Value |
|---|---|
| Gate Result | **PASS** |
| Source | {p2} |
| POC Confidence | High |
""")
    write(f"ux-briefs/faster_checkout_{ago(14)}.md", "# UX brief: Faster checkout")
    h = write(f"generated-hlds/HLD_faster_checkout_v1_{ago(10)}.md", f'---\ntitle: "Faster Checkout"\ntype: hld\ninitiative: {s}\n---\n# HLD: Faster Checkout')
    write(f"reviews/HLD_faster_checkout_v1_{ago(9)}_design_review.md", """
# Design review
## Persona Verdicts
| Persona | Verdict | Notes |
|---|---|---|
| Architect | ok | |
| Security | ok | tokenised cards only |
| SRE / Operations | ok | |
| Data | ok | |
| QA | ok | |
""")
    epics = {"initiative": s, "prd": str(p2), "parent": "INIT-10", "epics": [
        {"title": "Saved payment preselect", "jira_key": "ACME-101", "stories": [
            {"title": "Preselect last used card", "points": 3, "dor_status": "PASS", "jira_key": "ACME-111"},
            {"title": "Change card inline", "points": 5, "dor_status": "PASS", "jira_key": "ACME-112"}]}]}
    write(f"epics/faster_checkout_epics_{ago(7)}.json", json.dumps(epics, indent=2))
    write("jira-manifest.json", json.dumps({"issues": [{"key": "ACME-111", "epic": "ACME-101"}, {"key": "ACME-112", "epic": "ACME-101"}]}, indent=2))
    for step, i, o in (("pm-guide", "", f"{WS}/{s}/pm-context.md"), ("review-prd", p1, p2), ("validate-prd", p2, p2)):
        checkpoint(s, step, i, o, tracker="ACME-101")
    # 2) guest-checkout: PRD reviewed, validation failed
    s = "guest-checkout"
    g1 = prd(f"prds/guest_checkout_v1_{ago(6)}.md", "Guest Checkout", s, "ACME-104", "INIT-10", ux="Yes", hld="Engineering")
    write("reviews/" + g1.stem + "_review.md", "# PRD review: Guest Checkout\n\nVerdict: needs work — fraud controls unclear.")
    write(f"prd-validations/guest_checkout_validation_{ago(2)}.md", f"""
# PRD validation: Guest Checkout
Initiative `{s}`

| Field | Value |
|---|---|
| Gate Result | **FAIL** |
| Source | {g1} |
| POC Confidence | Medium |

✗ Success metric has no baseline.
""")
    checkpoint(s, "review-prd", g1, g1, result="fail", tracker="ACME-104")
    # 3) merchant-insights: just started
    write("merchant-insights/pm-context.md", "# Merchant insights\n\nEarly idea: weekly sales digest for merchants.")
    write(f"research/merchant_insights_{ago(3)}.md", "# Merchant insights\n\nDiscovery plan: interview 6 merchants about weekly reporting.")


EPICS = [  # key, summary, status, category, theme, sv, ui, urg, conf, effort, parent
    ("ACME-101", "Saved payment preselect", "In Dev", "In Progress", "Faster checkout", 5, 5, 4, 4, "M", "INIT-10"),
    ("ACME-102", "Apple Pay / Google Pay", "To Do", "To Do", "Faster checkout", 4, 5, 3, 3, "L", "INIT-10"),
    ("ACME-103", "Address autocomplete", "To Do", "To Do", "Faster checkout", 3, 4, 2, 4, "S", "INIT-10"),
    ("ACME-104", "Guest checkout", "Analysis", "To Do", "Faster checkout", 5, 4, 4, 2, "M", "INIT-10"),
    ("ACME-105", "Fraud score at payment", "To Do", "To Do", "Trust & safety", 4, 3, 5, 3, "L", "INIT-11"),
    ("ACME-106", "Clear refund status page", "In Dev", "In Progress", "Trust & safety", 3, 4, 3, 4, "S", "INIT-11"),
    ("ACME-107", "Two-factor login for merchants", "To Do", "To Do", "Trust & safety", 3, 2, 4, 4, "M", "INIT-11"),
    ("ACME-108", "Weekly sales digest email", "To Do", "To Do", "Merchant insights", 3, 3, 2, 2, "S", "INIT-12"),
    ("ACME-109", "Top products dashboard", "To Do", "To Do", "Merchant insights", 2, 3, 1, 3, "M", "INIT-12"),
    ("ACME-110", "One-click reorder", "Closed", "Done", "Faster checkout", 4, 4, 3, 4, "S", "INIT-10"),
]
THEMES = [("Faster checkout", "Conversion", "Make buying on mobile effortless", "INIT-10"),
          ("Trust & safety", "Retention", "Shoppers and merchants trust every transaction", "INIT-11"),
          ("Merchant insights", "Growth", "Merchants grow with their own data", "INIT-12")]


def database():
    if DATA.exists():
        shutil.rmtree(DATA)
    DATA.mkdir(parents=True)
    (DATA / "analytics").mkdir()
    rows = [{"date": ago(d), "checkout_completion": c, "median_checkout_s": t}
            for d, c, t in ((60, 61.5, 96), (45, 62.0, 94), (30, 63.1, 88), (15, 64.4, 81), (1, 65.2, 77))]
    (DATA / "analytics" / "metrics-history.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    (DATA / "config.json").write_text(json.dumps({
        "jira_base": "https://acme.atlassian.net", "jira_email": "demo@example.com", "jira_project": "ACME",
        "parent_project": "INIT", "pr_workspace": str(WS), "analytics_dir": str(DATA / "analytics"),
        "poll_minutes": 0, "claude_mode": "off", "demo": True}, indent=2))
    os.environ["PMWB_DATA"] = str(DATA)
    sys.path.insert(0, str(ROOT))
    from app import artifacts, db, prd_pipeline
    from app.paths import load_config
    db.init()
    now = dt.datetime.now().isoformat(timespec="seconds")
    with db.tx() as con:
        tid = {}
        for i, (name, desc, obj, parent) in enumerate(THEMES, 1):
            cur = con.execute("INSERT INTO themes(name,description,priority_rank,bepic_key,objective) VALUES(?,?,?,?,?)", (name, desc, i, parent, obj))
            tid[name] = cur.lastrowid
        for n, (k, summ, st, cat, th, sv, ui, urg, conf, eff, parent) in enumerate(EPICS, 1):
            closed = ago(20) if cat == "Done" else None
            con.execute("INSERT INTO epics(key,summary,status,status_category,priority,rank_pos,labels,team,bepic,url,in_scope,synced_at,"
                        "resolution,closed_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (k, summ, st, cat, "P3", n, "", "Checkout", parent, f"https://acme.atlassian.net/browse/{k}",
                         0 if cat == "Done" else 1, now, "Done" if closed else None, closed, ago(90)))
            con.execute("INSERT INTO scores(epic_ref,theme_id,sv,ui,urg,conf,effort,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                        (k, tid[th], sv, ui, urg, conf, eff, now))
        q = (TODAY.month - 1) // 3 + 1
        pid = db.one(con, "SELECT id FROM okr_periods WHERE name=?", (f"Q{q} {TODAY.year}",))["id"]
        for epic, theme, title, key, src, unit, dirn, base, tgt, cur_v in (
                ("ACME-101", None, "Mobile checkout completion to 70%", "checkout_completion", "baselines_jsonl", "%", "up", 62, 70, 65.2),
                ("ACME-101", None, "Median checkout time under 60 s", "median_checkout_s", "baselines_jsonl", "s", "down", 94, 60, 77),
                ("ACME-106", None, "Refund 'where is my money' tickets -40%", None, "manual", "tickets/wk", "down", 120, 72, 101),
                (None, "Trust & safety", "Chargeback rate below 0.4%", None, "manual", "%", "down", 0.7, 0.4, 0.6)):
            con.execute("INSERT INTO key_results(epic_key,theme_id,period_id,title,metric_key,source,unit,direction,baseline,target,current,"
                        "current_at,owner,due,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (epic, tid.get(theme), pid, title, key, src, unit, dirn, base, tgt, cur_v, D, "Demo PM", None, now, now))
        cur = con.execute("INSERT INTO sources(filename,kind,text,ingested_at,evidence_type) VALUES(?,?,?,?,?)",
                          ("checkout-interviews.md", "md", "Interview notes (demo).", now, "customer"))
        sid = cur.lastrowid
        for title, body, quote, theme in (
                ("Remember my card", "Returning shoppers re-enter card details every time.", "Why do I have to type this again?", "Faster checkout"),
                ("Show delivery date before payment", "Shoppers abandon when delivery date appears late.", "I need to know it arrives Friday.", "Faster checkout"),
                ("Explain refund timing", "Shoppers contact support to ask where refunds are.", "", "Trust & safety"),
                ("Weekly numbers for merchants", "Merchants export CSVs to see weekly sales.", "I just want Monday's email.", None)):
            con.execute("INSERT INTO ideas(title,body,quote,source_id,status,theme_id,created_at) VALUES(?,?,?,?,?,?,?)",
                        (title, body, quote, sid, "new", tid.get(theme), now))
        for ref, kind, text, owner, due in (
                ("faster-checkout", "decision", "Launch behind a flag at 10% for one week before ramping", "Demo PM", None),
                ("faster-checkout", "risk", "Payment provider rate limits during peak", "Eng lead", ago(-14)),
                ("guest-checkout", "blocker", "Fraud team has not signed off on guest limits", "Demo PM", ago(-5))):
            con.execute("INSERT INTO log_entries(ref,kind,text,owner,due,status,created_at) VALUES(?,?,?,?,?,'open',?)",
                        (ref, kind, text, owner, due, now))
        con.execute("INSERT INTO evidence(ref,type,note,created_at) VALUES('ACME-101','user_data','Funnel: 38% mobile drop at payment',?)", (now,))
        con.execute("INSERT INTO evidence(ref,type,note,created_at) VALUES('ACME-101','customer','14 of 20 interviews',?)", (now,))
        db.set_meta(con, "last_sync", now)
        db.set_meta(con, "current_period_id", pid)
    cfg = load_config()
    prd_pipeline.scan(cfg)
    artifacts.scan(cfg)
    with db.tx() as con:
        con.execute("UPDATE initiatives SET owner='Demo PM', target_period_id=? WHERE slug IN ('faster-checkout','guest-checkout')", (pid,))


if __name__ == "__main__":
    workspace()
    database()
    print(f"Demo ready: data {DATA}, workspace {WS}\nRun: ./run.sh --demo")
