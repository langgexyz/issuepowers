---
description: 解决一个 Gitee issue —— 启动 issuepowers 工作流
argument-hint: <gitee-id> [slug]
---

# /solve

User invoked: `/solve $1 $2`

- `$1` = Gitee issue ID (required, e.g., `IJG6FV`)
- `$2` = slug (optional; if absent, derive from issue title)

## Action

Invoke the `issuepowers:orchestration` skill in **solve mode** with these arguments:

```yaml
mode: solve
gitee_id: $1
slug: $2  # may be empty
```

## Contract

This command does **NOT return** until one of:

- ✅ `understanding.md` confirmed by user → state = `in-progress` (or `split-into-children` for parent)
- ⚠️ User unable to provide enough info → state = `understanding-needs-info`, blockers populated
- ❌ Gitee issue cannot be fetched → explicit error, no state change

After successful return, subsequent stages (implementation → merge → deploy → deliverable-check) run **autonomously** via orchestration. Human's next interaction is at validation gate.

## Anti-patterns

- ❌ Do NOT invent understanding when user is unavailable. Pause instead.
- ❌ Do NOT skip Bug-class local reproduction.
- ❌ Do NOT auto-confirm understanding without user explicit acknowledgment.
