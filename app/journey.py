"""Per-initiative view of the PM Journey (Step 0 pm-guide → Step 3 requirements-accept). See docs/WORKFLOW.md.

Pure computation over the prds / artifacts / initiatives tables. Each step gets a status:
done · partial · failed · skipped · optional (not done, not required) · missing (not done, required).
`ready` = validate-prd PASS ∧ (publish-specs merged, when a spec repo is configured) ∧ requirements-accept done —
the point where engineering can pull stories.
"""
import json

from . import db
from .ai_runner import skill_command

STEPS = [  # id, label, phase, required
    ("pm-guide", "PM guide", "0", False),
    ("research-synthesis", "Research synthesis", "1", False),
    ("concept-accept", "Concept Accept", "1", False),
    ("generate-prd", "PRD", "1", True),
    ("risk-review", "Risk review / NFRs", "1", False),
    ("ux-brief", "UX brief", "1", False),
    ("poc", "POC", "1a", False),
    ("review-prd", "Review PRD", "2", True),
    ("validate-prd", "Validate PRD (PRD gate)", "2", True),
    ("generate-hld", "HLD", "2", True),
    ("validate-hld", "Validate HLD", "2", True),
    ("generate-epics-and-stories", "Epics & stories", "2", True),
    ("publish-specs", "Publish specs (merged)", "2", True),
    ("requirements-accept", "Requirements Accept", "3", True),
]
HLD_NOT_REQUIRED = ("engineering", "not required", "none", "n/a", "no")


def _meta(row):
    try:
        return json.loads(row.get("meta_json") or "{}")
    except ValueError:
        return {}


def _ev(rows, **flt):
    out = []
    for r in rows:
        if all(r.get(k) == v for k, v in flt.items()):
            out.append({"id": r.get("id"), "table": r.get("_table", "artifacts"), "kind": r.get("kind"), "title": r.get("title"),
                        "path": r.get("path"), "result": r.get("result"), "pr_url": r.get("pr_url"), "pr_state": r.get("pr_state"),
                        "mtime": r.get("mtime")})
    return sorted(out, key=lambda e: e.get("mtime") or 0, reverse=True)


def build(con, cfg) -> list:
    inits = db.rows(con, "SELECT * FROM initiatives ORDER BY updated_at DESC")
    arts = db.rows(con, "SELECT * FROM artifacts")
    prds = db.rows(con, "SELECT * FROM prds")
    manifest = next((a for a in arts if a["kind"] == "jira-manifest"), None)
    manifest_epics = _meta(manifest).get("epics", {}) if manifest else {}
    out = []
    for it in inits:
        slug = it["slug"]
        A = [a for a in arts if a["initiative"] == slug]
        P = [{**p, "_table": "prds", "kind": "prd", "result": p.get("validation_result")} for p in prds if p.get("initiative") == slug]
        skipped = json.loads(it.get("skipped_json") or "{}")
        prd_meta = {}
        for p in P:
            prd_meta.update({k: v for k, v in _meta(p).items() if v})
        ux_required = str(prd_meta.get("ux_required", "")).lower().startswith("y")
        hld_owner = str(prd_meta.get("hld_ownership", "")).lower()
        cps = {_meta(a).get("skill"): a for a in sorted(A, key=lambda x: x.get("mtime") or 0) if a["kind"] == "checkpoint"}
        epic_keys = [k for k in (it.get("epic_keys") or "").split(",") if k]
        steps = []
        latest_prd = next((p for p in sorted(P, key=lambda x: x.get("mtime") or 0, reverse=True)), None)
        refined = next((p for p in sorted(P, key=lambda x: x.get("mtime") or 0, reverse=True) if "refined-prds" in (p.get("path") or "")), None)
        hlds = _ev(A, kind="hld")
        spec_repo = bool((cfg or {}).get("spec_repo"))
        for sid, label, phase, required in STEPS:
            st, ev, note = "missing", [], ""
            if sid == "publish-specs":
                required = spec_repo
            if sid == "pm-guide":
                ev = _ev(A, kind="pm-context") + _ev(A, kind="refinement-plan") + _ev(A, kind="checkpoint")
                st = "done" if ev else "missing"
            elif sid in ("research-synthesis", "concept-accept", "risk-review", "ux-brief"):
                kind = {"research-synthesis": "research", "concept-accept": "ca", "risk-review": "risk-review", "ux-brief": "ux-brief"}[sid]
                ev = _ev(A, kind=kind)
                st = "done" if ev else "missing"
                if sid == "ux-brief" and ux_required:
                    required, note = True, "PRD metadata: UX Required = Yes"
            elif sid == "generate-prd":
                ev = _ev(P)
                st = "done" if ev else "missing"
            elif sid == "poc":
                st = "done" if (it.get("poc_url") or it.get("poc_branch")) else "missing"
                ev = [{"title": "POC", "path": it.get("poc_url") or it.get("poc_branch"), "kind": "poc"}] if st == "done" else []
            elif sid == "review-prd":
                ev = _ev(A, kind="prd-review") + (_ev([refined]) if refined else [])
                cp = cps.get("review-prd")
                if cp:
                    ev = ev + _ev([cp])
                    st = "done" if (cp.get("result") == "pass" or refined or any(p.get("review_path") for p in P)) else "partial"
                else:
                    st = "done" if (refined or any(p.get("review_path") for p in P) or _ev(A, kind="prd-review")) else "missing"
            elif sid == "validate-prd":
                vals = _ev(A, kind="prd-validation")
                res = (vals[0]["result"] if vals else None) or next((p["validation_result"] for p in P if p.get("validation_result")), None)
                ev = vals or [e for e in _ev(P) if e["result"]]
                st = "done" if res == "PASS" else ("failed" if res == "FAIL" else "missing")
            elif sid == "generate-hld":
                ev = hlds + _ev(A, kind="hld-questions")
                if hlds:
                    st = "done"
                elif any(h in hld_owner for h in HLD_NOT_REQUIRED) and hld_owner:
                    st, note = "skipped", f"PRD metadata: HLD Ownership = {prd_meta.get('hld_ownership')}"
                elif _ev(A, kind="hld-questions"):
                    st = "partial"
            elif sid == "validate-hld":
                ev = _ev(A, kind="hld-review")
                res = ev[0]["result"] if ev else None
                if not hlds and not ev:
                    st = "skipped" if any(s["id"] == "generate-hld" and s["status"] == "skipped" for s in steps) else "missing"
                    if st == "skipped":
                        note = "no HLD"
                else:
                    st = {"APPROVED": "done", "REQUIRES_MANUAL_REVIEW": "partial", "BLOCKED": "failed"}.get(res, "missing")
            elif sid == "generate-epics-and-stories":
                ev = _ev(A, kind="epics-json")
                if ev:
                    st = "done"
                elif epic_keys:
                    st, note = "partial", f"{len(epic_keys)} Jira epic(s) linked, no generated artifact"
            elif sid == "publish-specs":
                pr = [e for e in _ev(P) + hlds if e.get("pr_url") or e.get("pr_state")]
                ev = pr
                states = {e.get("pr_state") for e in pr}
                stages = {p.get("stage") for p in P}
                if "merged" in states or "published" in stages:
                    st = "done"
                elif pr or "in-pr" in stages:
                    st, note = "partial", "PR open, not merged — requirements-accept blocks until merged"
            elif sid == "requirements-accept":
                pushed = [k for k in epic_keys if k in manifest_epics]
                ej = _ev(A, kind="epics-json")
                dor = _meta(next((a for a in A if a["kind"] == "epics-json"), {})).get("dor", {}) if ej else {}
                if pushed:
                    st, note = "done", f"{sum(len(manifest_epics[k]) for k in pushed)} stories published via requirements-accept"
                    ev = _ev([manifest]) if manifest else []
                elif dor:
                    st, note = "partial", "DoR: " + ", ".join(f"{k} {v}" for k, v in dor.items())
                    ev = ej
            if skipped.get(sid) and st not in ("done",):
                st, note = "skipped", skipped[sid]
            if st == "missing" and not required:
                st = "optional"
            steps.append({"id": sid, "label": label, "phase": phase, "required": required, "status": st, "note": note, "evidence": ev[:6]})
        S = {s["id"]: s["status"] for s in steps}
        ready = S["validate-prd"] == "done" and (S["publish-specs"] == "done" or not spec_repo) and S["requirements-accept"] == "done"
        todo = [s for s in steps if s["required"] and s["status"] in ("missing", "partial", "failed")]
        # gates first (Refinement / Requirements Accept), then Discovery follow-ups such as a required UX brief
        # no PRD yet → that comes first (the gates need it)
        nxt = next((s for s in todo if s["id"] == "generate-prd"), None) or \
            next((s for s in todo if s["phase"] in ("2", "3")), None) or (todo[0] if todo else None)
        next_cmd = None
        if nxt:
            inputs = [a for a in sorted(A, key=lambda x: x.get("mtime") or 0, reverse=True)
                      if a["kind"] in ("ca", "research", "pm-context") and a.get("path")]
            args = _args_for(nxt["id"], it, latest_prd, refined, hlds, cfg, inputs[0]["path"] if inputs else "")
            try:
                next_cmd = {"skill": nxt["id"], **skill_command(cfg, nxt["id"], args), "args": args}
            except (ValueError, KeyError):
                next_cmd = None
        out.append({"slug": slug, "title": it.get("title") or slug, "bepic_key": it.get("bepic_key"), "epic_keys": epic_keys,
                    "poc_url": it.get("poc_url"), "poc_branch": it.get("poc_branch"), "notes": it.get("notes"),
                    "owner": it.get("owner"), "target_period_id": it.get("target_period_id"),
                    "skipped": skipped, "prd_meta": prd_meta, "steps": steps, "ready": ready, "next": next_cmd,
                    "done_required": sum(1 for s in steps if s["required"] and s["status"] in ("done", "skipped")),
                    "total_required": sum(1 for s in steps if s["required"]), "updated_at": it.get("updated_at")})
    return out


def _args_for(step, it, prd, refined, hlds, cfg, input_path=""):
    prd_path = (refined or prd or {}).get("path") or ""
    if prd_path.startswith("gh:"):
        prd_path = ""
    a = {"file": prd_path, "bepic": it.get("bepic_key") or "", "project": cfg.get("jira_project", "")}
    if step == "validate-hld":
        a["file"] = hlds[0]["path"] if hlds else ""
    if step == "publish-specs":
        a["files"] = [p for p in [prd_path, hlds[0]["path"] if hlds else ""] if p]
    if step == "requirements-accept":
        a["file"] = ""  # epics-json path filled by the UI if present
    if step == "generate-prd":
        a["file"] = input_path
    if step == "pm-guide":
        a["text"] = f"--initiative {it['slug']}"
    return a
