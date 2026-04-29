#!/usr/bin/env python3
"""issuepowers 静态结构 + 一致性测试"""
import os, re, sys, subprocess
from pathlib import Path
from datetime import datetime

# Minimal YAML-like parser for plugin.yaml structure (no yaml module dep)
def parse_provides(text):
    """Extract provides.{commands,skills,templates,hooks} lists from plugin.yaml-style text."""
    result = {"commands": [], "skills": [], "templates": [], "hooks": []}
    section = None
    for line in text.splitlines():
        m = re.match(r"^  (commands|skills|templates|hooks):\s*$", line)
        if m:
            section = m.group(1)
            continue
        if section and re.match(r"^    - ", line):
            result[section].append(line[6:].strip())
        elif re.match(r"^[a-z]", line) or re.match(r"^  [a-z]", line):
            # New top-level or second-level non-list line — exit current section
            if not re.match(r"^  (commands|skills|templates|hooks):\s*$", line):
                section = None
    return result

ROOT = Path(__file__).parent.parent
PASS, FAIL, WARN = [], [], []

def ok(msg):   PASS.append(msg);  print(f"\033[32m✅\033[0m {msg}")
def fail(msg): FAIL.append(msg);  print(f"\033[31m❌\033[0m {msg}")
def warn(msg): WARN.append(msg);  print(f"\033[33m⚠️ \033[0m {msg}")
def section(t): print(f"\n=== {t} ===")


# === Test 1: plugin manifest 引用完整性 ===
section("Test 1: plugin.yaml 引用完整性")
provides = parse_provides((ROOT / ".claude-plugin/plugin.yaml").read_text())

for cmd in provides.get("commands", []):
    p = ROOT / f"commands/{cmd}.md"
    ok(f"command /{cmd} → {p.relative_to(ROOT)}") if p.exists() else fail(f"/{cmd} → 缺 {p.relative_to(ROOT)}")

for skill in provides.get("skills", []):
    name = skill.split(":", 1)[1] if ":" in skill else skill
    p = ROOT / f"skills/{name}/SKILL.md"
    ok(f"skill {skill} → {p.relative_to(ROOT)}") if p.exists() else fail(f"{skill} → 缺 {p.relative_to(ROOT)}")

for tpl in provides.get("templates", []):
    p = ROOT / f"templates/{tpl}"
    ok(f"template {tpl}") if p.exists() else fail(f"{tpl} → 缺 templates/{tpl}")


# === Test 2: SKILL.md frontmatter ===
section("Test 2: SKILL.md frontmatter 完整性")
for skill_md in (ROOT / "skills").glob("*/SKILL.md"):
    txt = skill_md.read_text()
    has_open = txt.startswith("---\n")
    has_name = bool(re.search(r"^name:\s+\S", txt, re.M))
    has_desc = bool(re.search(r"^description:", txt, re.M))
    if has_open and has_name and has_desc:
        ok(f"{skill_md.relative_to(ROOT)}: frontmatter 完整")
    else:
        fail(f"{skill_md.relative_to(ROOT)}: 缺字段 (open={has_open} name={has_name} desc={has_desc})")


# === Test 3: Command frontmatter ===
section("Test 3: Command frontmatter 完整性")
for cmd_md in (ROOT / "commands").glob("*.md"):
    txt = cmd_md.read_text()
    has_open = txt.startswith("---\n")
    has_desc = bool(re.search(r"^description:", txt, re.M))
    if has_open and has_desc:
        ok(f"{cmd_md.relative_to(ROOT)}: frontmatter 完整")
    else:
        fail(f"{cmd_md.relative_to(ROOT)}: frontmatter 不完整")


# === Test 4: issuepowers:* 引用解析 ===
section("Test 4: issuepowers:* 引用解析")
defined = {f"issuepowers:{p.parent.name}" for p in (ROOT / "skills").glob("*/SKILL.md")}
referenced = set()
search_files_ip = [
    *(ROOT / "skills").rglob("*.md"),
    *(ROOT / "commands").glob("*.md"),
    *(p for p in (ROOT / "docs").glob("*.md") if p.name != "TEST-REPORT.md"),
]
for p in search_files_ip:
    for ref in re.findall(r"issuepowers:[a-z-]+", p.read_text()):
        referenced.add(ref)
for ref in sorted(referenced):
    if ref in defined:
        ok(f"{ref} 解析成功")
    else:
        fail(f"{ref} 找不到对应 skill")


# === Test 5: templates/* 引用 ===
section("Test 5: templates/* 引用")
referenced_t = set()
# Exclude TEST-REPORT.md (auto-generated, may contain stale refs from prior runs)
search_files = [
    *(ROOT / "skills").rglob("*.md"),
    *(ROOT / "commands").glob("*.md"),
    *(p for p in (ROOT / "docs").glob("*.md") if p.name != "TEST-REPORT.md"),
]
for p in search_files:
    for ref in re.findall(r"templates/([a-z-]+\.md)", p.read_text()):
        referenced_t.add(ref)
for tpl in sorted(referenced_t):
    p = ROOT / "templates" / tpl
    ok(f"templates/{tpl}") if p.exists() else fail(f"templates/{tpl} 缺")


# === Test 6: 状态机一致性 ===
section("Test 6: 状态机一致性 (design.md vs orchestration)")
design = (ROOT / "docs/design.md").read_text()
orch = (ROOT / "skills/orchestration/SKILL.md").read_text()

m4 = re.search(r"## 四、状态机.*?(?=^## )", design, re.S | re.M)
design_state_block = m4.group(0) if m4 else ""

mo = re.search(r"## State Machine.*?(?=^## )", orch, re.S | re.M)
orch_state_block = mo.group(0) if mo else ""

key_states = [
    "in-progress", "pending-validation", "done", "rolled-back",
    "understanding-needs-info", "split-into-children",
    "understanding-in-progress",
]

for s in key_states:
    in_design = s in design_state_block
    in_orch = s in orch_state_block
    if in_design and in_orch:
        ok(f"state '{s}': 两边都有")
    elif not in_design and not in_orch:
        warn(f"state '{s}': 两边都没 (设计可能漏)")
    else:
        fail(f"state '{s}': design={in_design} orch={in_orch} (不一致)")


# === Test 7: Modes 表 vs Mode sections 一致 ===
section("Test 7: Modes 表 vs Mode sections 一致")
table = re.search(r"^## Modes\s*$.*?(?=^## )", orch, re.S | re.M)
table_block = table.group(0) if table else ""
table_modes = set(re.findall(r"\|\s*`([a-z-]+)`", table_block))

section_modes = set(re.findall(r"^## Mode:\s+(\S+)", orch, re.M))

for m_name in sorted(table_modes | section_modes):
    in_t = m_name in table_modes
    in_s = m_name in section_modes
    if in_t and in_s:
        ok(f"mode '{m_name}': 表格 + section 一致")
    elif in_t and not in_s:
        fail(f"mode '{m_name}': 在表格但无 section")
    else:
        fail(f"mode '{m_name}': 有 section 但不在表格")


# === Test 8: 工作流链条 walkthrough ===
section("Test 8: 工作流 walkthrough")
solve_md = (ROOT / "commands/solve.md").read_text()
rollback_md = (ROOT / "commands/rollback.md").read_text()

checks = [
    ("/solve → orchestration", r"issuepowers:orchestration", solve_md),
    ("orchestration → requirements-understanding", r"issuepowers:requirements-understanding", orch),
    ("/rollback → rollback skill", r"issuepowers:rollback", rollback_md),
    ("merge → rollback (generate mode)", r"rollback.{0,80}generate", orch),
    ("deploy-check → deliverable-check", r"issuepowers:deliverable-check", orch),
    ("fix-forward → user-validation-feedback", r"user-validation-feedback", orch),
    ("implement → cross-issue conflict check", r"cross-issue conflict|D2.*Cross-issue", orch),
    ("implement → rollback rehearsal (D3)", r"rollback rehearsal", orch),
]
for label, pattern, hay in checks:
    if re.search(pattern, hay):
        ok(label)
    else:
        fail(label)


# === 汇总 ===
print("\n" + "=" * 40)
print(f"PASS: {len(PASS)}   FAIL: {len(FAIL)}   WARN: {len(WARN)}")
print("=" * 40)

# 写报告
sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT).decode().strip()
report_path = ROOT / "docs/TEST-REPORT.md"

passes_md = "\n".join(f"- {x}" for x in PASS)
fails_md = "\n".join(f"- {x}" for x in FAIL) if FAIL else "（无）"
warns_md = "\n".join(f"- {x}" for x in WARN) if WARN else "（无）"

report_path.write_text(f"""# issuepowers Test Report

**Date**: {datetime.now().isoformat(timespec='seconds')}
**Commit**: {sha}
**Script**: scripts/test.py

## Summary

- ✅ PASS: {len(PASS)}
- ❌ FAIL: {len(FAIL)}
- ⚠️ WARN: {len(WARN)}

## Failures

{fails_md}

## Warnings

{warns_md}

## All Passes

{passes_md}
""")
print(f"Report: {report_path.relative_to(ROOT)}")

sys.exit(len(FAIL))
