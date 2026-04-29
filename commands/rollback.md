---
description: 回滚一个已交付的 Gitee issue
argument-hint: <gitee-id>
---

# /rollback

User invoked: `/rollback $1`

- `$1` = Gitee issue ID to roll back (required)

## Action

Invoke the `issuepowers:rollback` skill in **execute mode** with:

```yaml
mode: execute
gitee_id: $1
```

The skill will:
1. Read `issues/$1/rollback.md` playbook
2. Check `dependent_commits_after_merge` — pause and ask user if non-empty
3. Reverse-order rollback: migration downgrade → revert backend → revert web → restore submodule pointer
4. Wait for redeploy and verify
5. Write `issues/$1/rollback-report.md`
6. Update `status.md` state = `rolled-back`

## Contract

- If `dependent_commits_after_merge` is non-empty, command STOPS and asks user:
  - cascade rollback (roll back $1 plus all dependent issues)
  - forward fix (open new issue, don't rollback)
- If any rollback step fails, command STOPS — do NOT mark state as rolled-back partially
- Destructive migrations require backup verification before downgrade; if no backup and irreversible, ESCALATE

## When this command CANNOT run

- Issue has no `rollback.md` (was never merged, or playbook generation was skipped)
- Issue is not in a state that can be rolled back (already in `done`, `rolled-back`, or pre-merge state)
- Required playbook fields are missing or invalid

In any of these cases, exit with explicit error explaining which condition failed.

## Anti-patterns

- ❌ Don't auto-cascade rollback dependents without user confirmation
- ❌ Don't skip dependency check ("it's probably fine")
- ❌ Don't proceed past a failed rollback step
- ❌ Don't mark `rolled-back` before smoke verification passes
