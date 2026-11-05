#!/usr/bin/env python3
"""Build the course for both platforms from one source.

Source (edit these):
  course-structure.json, lesson-modules/*/CLAUDE.md (+ REFERENCE.md), shared/teaching-rules.md,
  variants/<platform>/platform.md

Generated (never edit; committed so a clone works without building):
  .claude/skills/<command>/SKILL.md + .claude/rules/teaching-rules.md   Claude Code: cd course && claude, type /start
  cowork-plugin/                                                        Cowork plugin, unpacked
  releases/pm-workbench-course.plugin                                   the same, zipped for install

Tokens in lesson scripts:
  {{cc: text}} / {{cowork: text}}   kept on that platform, dropped on the other (may span lines)
  {{cmd:start-1-2}}                 how the learner invokes another lesson on this platform

Usage:  python3 scripts/build.py           write outputs
        python3 scripts/build.py --check   exit 1 if sources are invalid or outputs are stale
"""
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = "pm-workbench-course"
ZIP_PATH = ROOT / "releases" / f"{PLUGIN}.plugin"
CC_TOOLS = ["Read", "Write", "AskUserQuestion", "Bash(curl -s http://127.0.0.1:8765/api/*)", "Bash(ls:*)", "Bash(which:*)", "Bash(python3 --version)", "Bash(claude --version)", "Bash(gh auth status)", "Bash(../run.sh:*)"]
BLOCK_RE = re.compile(r"\{\{(cc|cowork):\s*(.*?)\}\}", re.S)
CMD_RE = re.compile(r"\{\{cmd:([a-z0-9-]+)\}\}")
TOKEN_RE = re.compile(r"\{\{.*?\}\}", re.S)

PLATFORMS = {
    "cc": {
        "variant": "claude-code",
        "cmd": lambda c: f"`/{c}`",
        "rules": "Read `.claude/rules/teaching-rules.md` and follow it for everything below.",
        "between": "use `/clear` first, then",
    },
    "cowork": {
        "variant": "cowork",
        "cmd": lambda c: f"`/{PLUGIN}:{c}`",
        "rules": "Read `teaching-rules.md` in this skill's folder and follow it for everything below.",
        "between": "start a new chat, then",
    },
}


def lessons(structure):
    out = [l for m in structure["modules"] for l in m["lessons"]]
    return out + [{**structure["assistant"], "assistant": True}]


def render(text, platform):
    text = CMD_RE.sub(lambda m: PLATFORMS[platform]["cmd"](m.group(1)), text)
    text = BLOCK_RE.sub(lambda m: m.group(2).strip() if m.group(1) == platform else "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def frontmatter(lesson, platform):
    cmd, title = lesson["command"], lesson["title"]
    if lesson.get("assistant"):
        desc = ("PM Workbench guide. Use when the user asks what to do next on an objective, initiative, PRD or epic "
                "in PM Workbench, or asks for help with a step of the PM Journey.")
    elif platform == "cc":
        desc = f"Lesson {lesson['id']}: {title}. Use when the learner types /{cmd}."
    elif cmd == "start":
        desc = "PM Workbench course: start here. Use when the user wants to start, resume or continue the PM Workbench course."
    else:
        desc = (f"PM Workbench course, lesson {lesson['id']}: {title}. Use when the user asks to start or continue "
                f"lesson {lesson['id']} of the PM Workbench course.")
    lines = ["---", f"name: {cmd}", f"description: {json.dumps(desc)}"]
    if platform == "cc":
        if not lesson.get("assistant"):
            lines.append("disable-model-invocation: true")
        lines.append("allowed-tools:")
        lines += [f"  - {json.dumps(t) if '(' in t else t}" for t in CC_TOOLS]
    return "\n".join(lines + ["---"]) + "\n"


def footer(lesson, platform, has_reference):
    p = PLATFORMS[platform]
    parts = []
    if has_reference:
        where = (f"[REFERENCE.md]({Path(lesson['path']).parent.as_posix()}/REFERENCE.md)" if platform == "cc"
                 else "`REFERENCE.md` in this skill's folder")
        parts.append(f"## Reference\n\nDeeper notes and troubleshooting for this lesson: {where}. Read it when the learner "
                     "asks for more depth or something goes wrong, and relay the relevant part in your own words.")
    if lesson.get("assistant"):
        return "\n\n".join(parts) + ("\n" if parts else "")
    nxt = lesson["next"]
    if isinstance(nxt, dict):
        step = " ".join(f"Track {t}: {p['cmd'](c)}." for t, c in sorted(nxt.items()))
        step = f"the next lesson depends on their track. {step} When they're ready, {p['between']} that command."
    elif nxt == "guide":
        step = (f"the course is complete. From here on {p['cmd']('guide')} tells them what to do next on any objective "
                "or initiative, any time.")
    else:
        step = f"when they're ready for the next lesson, {p['between']} {p['cmd'](nxt)}."
    parts.append(
        "## Wrap-up\n\n"
        f"ACTION: Silently add `{lesson['id']}` to `completed` in the progress file and set `updated` to today "
        "(see the teaching rules). Don't narrate it.\n\n"
        "Then close out in natural language, never as a list of commands:\n\n"
        "- Only if it fits the moment, remind them they can ask for a recap or where they stand.\n"
        f"- End with the next step: {step}")
    return "\n\n".join(parts) + "\n"


def build():
    """Return ({relative path: text}, [errors]) for everything generated except the zip."""
    errors, files = [], {}
    structure = json.loads((ROOT / "course-structure.json").read_text())
    shared = (ROOT / "shared" / "teaching-rules.md").read_text().strip()
    all_lessons = lessons(structure)
    commands = [l["command"] for l in all_lessons]
    if len(commands) != len(set(commands)):
        errors.append("duplicate command in course-structure.json")
    rules = {}
    for key, p in PLATFORMS.items():
        variant = ROOT / "variants" / p["variant"] / "platform.md"
        if not variant.exists():
            errors.append(f"missing {variant.relative_to(ROOT)}")
            continue
        rules[key] = shared + "\n\n" + variant.read_text().strip() + "\n"
    for lesson in all_lessons:
        src = ROOT / lesson["path"]
        if not src.exists():
            errors.append(f"{lesson['command']}: missing {lesson['path']}")
            continue
        script = src.read_text()
        ref = src.parent / "REFERENCE.md"
        if not lesson.get("assistant"):
            if not ref.exists():
                errors.append(f"{lesson['command']}: missing REFERENCE.md")
            if "## Success Criteria" not in script:
                errors.append(f"{lesson['command']}: no '## Success Criteria' section")
            if "## Important Notes for Claude" not in script:
                errors.append(f"{lesson['command']}: no '## Important Notes for Claude' section")
            for c in (lesson["next"].values() if isinstance(lesson["next"], dict) else [lesson["next"]]):
                if c not in commands:
                    errors.append(f"{lesson['command']}: next '{c}' is not a lesson command")
        for c in CMD_RE.findall(script):
            if c not in commands:
                errors.append(f"{lesson['command']}: {{{{cmd:{c}}}}} is not a lesson command")
        for key, p in PLATFORMS.items():
            if key not in rules:
                continue
            body = render(script, key)
            left = TOKEN_RE.search(body)
            if left:
                errors.append(f"{lesson['command']} ({key}): unresolved token {left.group(0)[:40]!r}")
            skill = (frontmatter(lesson, key) + f"\n## Setup\n\n{p['rules']}\n\n" + body + "\n"
                     + footer(lesson, key, ref.exists()))
            base = f".claude/skills/{lesson['command']}" if key == "cc" else f"cowork-plugin/skills/{lesson['command']}"
            files[f"{base}/SKILL.md"] = skill
            if key == "cowork":
                files[f"{base}/teaching-rules.md"] = rules[key]
                if ref.exists():
                    files[f"{base}/REFERENCE.md"] = ref.read_text()
    if "cc" in rules:
        files[".claude/rules/teaching-rules.md"] = rules["cc"]
    c = structure["course"]
    files["cowork-plugin/.claude-plugin/plugin.json"] = json.dumps(
        {"name": PLUGIN, "version": c["version"], "description": c["description"]}, indent=2) + "\n"
    return files, errors


def plugin_members(files):
    pre = "cowork-plugin/"
    return {k[len(pre):]: v for k, v in sorted(files.items()) if k.startswith(pre)}


def write_zip(members):
    ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in members.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, text)


def generated_on_disk():
    out = set()
    for d in (".claude/skills", ".claude/rules", "cowork-plugin"):
        base = ROOT / d
        if base.exists():
            out |= {p.relative_to(ROOT).as_posix() for p in base.rglob("*") if p.is_file() and p.name != ".DS_Store"}
    return out


def main():
    check = "--check" in sys.argv
    files, errors = build()
    if errors:
        print("\n".join(f"ERROR {e}" for e in errors))
        return 1
    stale_extra = sorted(generated_on_disk() - set(files))
    if check:
        stale = [k for k, v in files.items() if not (ROOT / k).exists() or (ROOT / k).read_text() != v]
        stale += [f"{k} (not generated; delete)" for k in stale_extra]
        members = plugin_members(files)
        try:
            with zipfile.ZipFile(ZIP_PATH) as z:
                if {n: z.read(n).decode() for n in z.namelist()} != members:
                    stale.append(str(ZIP_PATH.relative_to(ROOT)))
        except (OSError, zipfile.BadZipFile):
            stale.append(str(ZIP_PATH.relative_to(ROOT)))
        if stale:
            print("STALE (run python3 scripts/build.py):\n  " + "\n  ".join(stale))
            return 1
        print(f"OK {len(files)} generated files up to date")
        return 0
    for k in stale_extra:
        (ROOT / k).unlink()
    for k, v in files.items():
        p = ROOT / k
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(v)
    for d in sorted((p for b in (".claude/skills", "cowork-plugin") for p in (ROOT / b).rglob("*") if p.is_dir()), reverse=True):
        if not any(d.iterdir()):
            d.rmdir()
    write_zip(plugin_members(files))
    print(f"Wrote {len(files)} files + {ZIP_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
