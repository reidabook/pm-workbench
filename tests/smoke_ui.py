#!/usr/bin/env python3
"""Browser smoke test for the Inbox and Artifacts tabs. Exit 0 = all pass.

Boots the real server on a scratch data dir and workspace, then clicks through with Playwright.
Uses no Claude tokens and touches nothing outside the scratch dir: AI is switched off in the
scratch config, no skill is launched, and Jira is never called.

    pip install -r requirements-dev.txt && python -m playwright install chromium
    python tests/smoke_ui.py            # HEADED=1 to watch it
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAILS = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def scratch() -> Path:
    """Data dir + a workspace holding one PRD that has been refined, reviewed and validated."""
    tmp = Path(tempfile.mkdtemp(prefix="pmwb-smoke-"))
    ws = tmp / "ws"
    for d in ("prds", "refined-prds", "reviews", "prd-validations"):
        (ws / d).mkdir(parents=True)
    fm = '---\ntitle: "Smoke PRD"\ntype: "prd"\n---\n# Smoke PRD\n\n'
    (ws / "prds" / "smoke_2026-10-01.md").write_text(fm + "ORIGINAL BODY\n")
    (ws / "refined-prds" / "smoke_v1_refined_2026-10-01.md").write_text(fm + "REFINED BODY\n")
    (ws / "reviews" / "smoke_2026-10-01_review.md").write_text("# Review\n")
    (ws / "prd-validations" / "smoke_prd_2026-10-01.md").write_text("# PRD Validation Report\n\n| Gate Result | PASS |\n")
    cfg = json.loads((ROOT / "config.example.json").read_text())
    cfg.update({"portfolio_team_ids": {"Smoke": 1}, "pr_workspace": str(ws), "poll_minutes": 0, "claude_mode": "off"})
    (tmp / "data").mkdir()
    (tmp / "data" / "config.json").write_text(json.dumps(cfg))
    return tmp


def serve(tmp: Path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
                            cwd=ROOT, env={**os.environ, "PMWB_DATA": str(tmp / "data")},
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    url = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            urllib.request.urlopen(url + "/api/state", timeout=1)
            return proc, url
        except Exception:  # noqa: BLE001
            if proc.poll() is not None:
                raise RuntimeError("server exited: " + proc.stderr.read().decode()[-600:])
            time.sleep(0.25)
    proc.kill()
    raise RuntimeError("server did not start")


def run(page, url):
    from playwright.sync_api import expect
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("dialog", lambda d: d.accept("Bulk ops"))  # the group-name prompt
    page.goto(url)
    nav = lambda label: page.locator("#nav a", has_text=label).click()  # noqa: E731
    overlay, inbox = page.locator("#overlay"), page.locator("#tab-inbox")

    def step(name, fn):
        try:
            fn()
            check(name, True)
        except Exception as e:  # noqa: BLE001
            check(name, False, str(e).splitlines()[0][:200])

    # ---- Inbox: source -> view -> idea -> evidence -> group ----
    nav("Inbox")
    source = inbox.locator(".card").first.locator(".idea", has_text="cab notes")  # Sources is the first card

    def add_source():
        page.fill("#paste", "Customers want bulk delete")
        page.fill("#pasteTitle", "cab notes")
        page.get_by_role("button", name="Add pasted text").click()
        expect(source).to_be_visible()
        expect(page.locator("#jiraKeys")).to_be_visible()
    step("smoke_inbox_paste_adds_source", add_source)

    def view_source():
        source.get_by_role("button", name="View").click()
        expect(overlay).to_contain_text("Customers want bulk delete")
        overlay.get_by_role("button", name="Close").click()
        expect(overlay).to_be_empty()
    step("smoke_inbox_view_source_content", view_source)

    def hand_idea():
        source.get_by_role("button", name="Add idea by hand").click()
        page.fill("#it", "Bulk delete")
        overlay.get_by_role("button", name="Add", exact=True).click()
        idea = inbox.locator(".idea", has_text="Bulk delete")
        expect(idea).to_contain_text("Evidence (1)")
        expect(source).to_contain_text("evidence for 1 idea")
    step("smoke_source_becomes_evidence_for_hand_added_idea", hand_idea)

    group = inbox.locator(".idea", has_text="Bulk ops")

    def make_group():
        inbox.locator(".idea", has_text="Bulk delete").locator("input.chk").check()
        page.get_by_role("button", name="Group 1 selected").click()
        expect(group).to_contain_text("Evidence (1)")
    step("smoke_group_inherits_idea_evidence", make_group)

    def expand():
        group.get_by_text("Evidence (1)").click()
        expect(group.locator(".evrow")).to_have_count(1)
        expect(group.locator(".evrow")).to_contain_text("from cab notes")
        expect(group.locator(".evrow")).to_contain_text("idea: Bulk delete")
    step("smoke_group_evidence_expands_with_source_and_idea", expand)

    def add_edit_remove():
        group.get_by_role("button", name="Add evidence").click()
        page.select_option("#ev_type", "competitor")
        page.fill("#ev_note", "Acme has it")
        overlay.get_by_role("button", name="Add", exact=True).click()
        expect(group).to_contain_text("Evidence (2)")
        group.locator(".evrow", has_text="Acme has it").get_by_role("button", name="Edit").click()
        expect(page.locator("#ev_note")).to_have_value("Acme has it")
        page.fill("#ev_note", "Acme ships it")
        overlay.get_by_role("button", name="Save").click()
        expect(group.locator(".evrow", has_text="Acme ships it")).to_be_visible()
        group.locator(".evrow", has_text="Acme ships it").get_by_title("Remove").click()
        expect(group).to_contain_text("Evidence (1)")
    step("smoke_group_evidence_add_edit_remove", add_edit_remove)

    # ---- Artifacts: one row per PRD, review / validate status, re-run ----
    nav("Artifacts")
    rows = page.locator("#tab-prds tbody tr")

    def one_row():
        page.locator("#tab-prds").get_by_role("button", name="Rescan workspace").click()
        expect(rows.filter(has_text="Smoke PRD")).to_have_count(1)
        row = rows.filter(has_text="Smoke PRD")
        expect(row).to_contain_text("refined-prds/smoke_v1_refined_2026-10-01.md")
        expect(row).to_contain_text("original: prds/smoke_2026-10-01.md")
    step("smoke_artifacts_refined_and_original_are_one_row", one_row)

    def status():
        row = rows.filter(has_text="Smoke PRD")
        expect(row).to_contain_text("Reviewed")
        expect(row).to_contain_text("Validated")
        expect(row).to_contain_text("PASS")
        expect(row.get_by_role("button", name="Review again")).to_be_visible()
        expect(row.get_by_role("button", name="Validate again")).to_be_visible()
    step("smoke_artifacts_show_reviewed_and_validated", status)

    def original_link():
        rows.filter(has_text="Smoke PRD").get_by_role("link", name="prds/smoke_2026-10-01.md").click()
        expect(overlay).to_contain_text("ORIGINAL BODY")
        overlay.get_by_title("Close (Esc)").click()
        rows.filter(has_text="Smoke PRD").get_by_role("link", name="Smoke PRD").click()
        expect(overlay).to_contain_text("REFINED BODY")
        overlay.get_by_title("Close (Esc)").click()
    step("smoke_artifacts_original_and_refined_both_open", original_link)

    def rerun_dialog():  # opens the confirmation only; Cancel, so nothing is launched
        rows.filter(has_text="Smoke PRD").get_by_role("button", name="Review again").click()
        expect(overlay).to_contain_text("Run skill: review-prd")
        expect(overlay.locator("#cmd")).to_contain_text("smoke_v1_refined_2026-10-01.md")
        overlay.get_by_role("button", name="Cancel").click()
        expect(overlay).to_be_empty()
    step("smoke_artifacts_review_again_targets_refined_file", rerun_dialog)

    check("smoke_no_javascript_errors", not errors, "; ".join(errors)[:300])


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("SKIP smoke_ui (playwright not installed: pip install -r requirements-dev.txt && python -m playwright install chromium)")
        return 0
    proc, url = serve(scratch())
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=not os.environ.get("HEADED"))
            page = browser.new_page()
            page.set_default_timeout(5000)
            run(page, url)
            browser.close()
    finally:
        proc.terminate()
    print(f"\n{'ALL PASS' if not FAILS else f'{len(FAILS)} FAILED: {FAILS}'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
