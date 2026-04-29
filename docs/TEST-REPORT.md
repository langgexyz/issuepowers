# issuepowers Test Report

**Date**: 2026-04-29T11:29:54
**Commit**: 86f2c2f
**Script**: scripts/test.py

## Summary

- ✅ PASS: 47
- ❌ FAIL: 0
- ⚠️ WARN: 0

## Failures

（无）

## Warnings

（无）

## All Passes

- command /solve → commands/solve.md
- command /rollback → commands/rollback.md
- skill issuepowers:orchestration → skills/orchestration/SKILL.md
- skill issuepowers:requirements-understanding → skills/requirements-understanding/SKILL.md
- skill issuepowers:deliverable-check → skills/deliverable-check/SKILL.md
- skill issuepowers:rollback → skills/rollback/SKILL.md
- template understanding.md
- template split-proposal.md
- template user-validation-feedback.md
- template deliverable-report.md
- template rollback.md
- skills/deliverable-check/SKILL.md: frontmatter 完整
- skills/orchestration/SKILL.md: frontmatter 完整
- skills/requirements-understanding/SKILL.md: frontmatter 完整
- skills/rollback/SKILL.md: frontmatter 完整
- commands/solve.md: frontmatter 完整
- commands/rollback.md: frontmatter 完整
- issuepowers:deliverable-check 解析成功
- issuepowers:orchestration 解析成功
- issuepowers:requirements-understanding 解析成功
- issuepowers:rollback 解析成功
- templates/deliverable-report.md
- templates/rollback.md
- templates/split-proposal.md
- templates/understanding.md
- state 'in-progress': 两边都有
- state 'pending-validation': 两边都有
- state 'done': 两边都有
- state 'rolled-back': 两边都有
- state 'understanding-needs-info': 两边都有
- state 'split-into-children': 两边都有
- state 'understanding-in-progress': 两边都有
- mode 'deploy-check': 表格 + section 一致
- mode 'fix-forward': 表格 + section 一致
- mode 'implement': 表格 + section 一致
- mode 'merge': 表格 + section 一致
- mode 'resume': 表格 + section 一致
- mode 'rollback': 表格 + section 一致
- mode 'solve': 表格 + section 一致
- /solve → orchestration
- orchestration → requirements-understanding
- /rollback → rollback skill
- merge → rollback (generate mode)
- deploy-check → deliverable-check
- fix-forward → user-validation-feedback
- implement → cross-issue conflict check
- implement → rollback rehearsal (D3)
