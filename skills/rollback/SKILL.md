---
name: rollback
description: |
  Two-mode skill for issuepowers rollback safety net.
  Mode `generate`: invoked at self-review pass (before merge) to write rollback.md playbook.
  Mode `execute`: invoked by /rollback command to actually undo a delivered issue —
  reads rollback.md, checks dependencies, runs reverse-order rollback steps, writes report.
  Rollback never silently overrides newer dependent commits — it pauses and asks.
---

# Rollback Skill

## Modes

| Mode | When | What |
|---|---|---|
| `generate` | Self-review pass, before merge | Write `rollback.md` playbook for this issue |
| `execute` | `/rollback <id>` command | Read playbook, undo the issue |

Mode is selected by caller (orchestration skill).

---

## Mode: generate (called from merge phase, P1 wire-up)

### Goal

Capture everything needed to cleanly undo this issue **before** the issue actually merges. After merge, the relevant SHAs and migration revisions must be locked in. If we wait until rollback time to figure them out, we lose information (especially `dependent_commits_after_merge` which gets appended over time).

### Inputs

- `gitee_id` — current issue ID
- Path to `issues/<gitee_id>/rollback.md` (will be created)
- Project context: which submodules touched, which migrations included, whether feature flag exists

### Procedure

1. **Determine merge SHAs (post-squash)**
   - For each submodule (backend, web), the squash-merge commit SHA on `develop`
   - At `generate` time, this is the SHA that **will be created** when merge runs. Compute by simulating squash locally first, then capture.

2. **Capture pre-merge submodule pointer**
   - In the ai-workflow (project) repo, the submodule pointer SHA before this issue's merge updates it

3. **Capture migration revisions**
   - `before`: the alembic head before this issue's migration applies
   - `after`: the alembic head after applying this issue's migration
   - If no migration, both are null

4. **Detect feature flag (if any)**
   - Read plan.md / understanding.md / code diff for any flag introduction
   - If found, write the flag name. If not, omit.

5. **Initialize empty `dependent_commits_after_merge: []`**
   - This list grows over time. Orchestration's merge phase appends here whenever a later issue's merge touches files this issue also touched.

6. **Capture smoke test command**
   - The command to re-run deliverable-check after rollback (verify rollback succeeded)

7. **Write notes**
   - Anything that would surprise a future rollback executor: data backups taken, schema changes that destroy data, etc.

### Output

`issues/<gitee_id>/rollback.md` populated per `templates/rollback.md`. All fields filled (or explicitly null).

### Failure modes

- Cannot determine migration revision → block merge, escalate to user
- Cannot capture submodule SHA → block merge, escalate
- Generated playbook missing required field → fail loudly, do not proceed to merge

A bad rollback playbook is worse than no playbook (false safety). **Don't ship a generated playbook that wouldn't actually work.**

---

## Mode: execute (called from /rollback command)

### Goal

Cleanly undo a delivered issue: revert code, downgrade schema, restore submodule pointer, redeploy, verify.

### Inputs

- `gitee_id` — issue to roll back

### Procedure (R1 — R7 from design.md §8)

#### R1. Read rollback.md

Open `issues/<gitee_id>/rollback.md`. Validate all required fields present.

If `feature_flag` is set: this is a flag-based rollback — just toggle the flag, skip R3-R5. Then jump to R6 for verification.

#### R2. Dependency check

Check `dependent_commits_after_merge`:

- **Empty** → safe to revert; continue R3
- **Non-empty** → STOP. Show user the list and offer:
  - **(a) Cascade rollback**: roll back this issue plus all listed dependent issues, in reverse order
  - **(b) Forward fix**: don't rollback; instead create a new issue to hot-fix the problem
  - Wait for user choice. Don't proceed without it.

#### R3. Reverse migration (if any)

If `migration_revision.before != migration_revision.after`:
```
flask db downgrade <migration_revision.before>
```

If migration is destructive (data loss): cross-reference with `notes` field for backup location. Restore from backup BEFORE downgrade if backup exists. If no backup and irreversible, **STOP** and escalate — destructive rollback should never silently lose data.

#### R4. Revert backend

```
git -C <backend-submodule-path> checkout develop
git -C <backend-submodule-path> revert <merge_sha.backend> --no-edit
git -C <backend-submodule-path> push origin develop
```

#### R5. Revert web (if applicable)

Same as R4 with `merge_sha.web`. Skip if this issue had no web changes.

#### R6. Restore ai-workflow submodule pointer

```
git -C <ai-workflow-path> reset <ai_workflow_pointer_before> -- <submodule-path>
git -C <ai-workflow-path> add <submodule-path>
git -C <ai-workflow-path> commit -m "rollback: <gitee_id> — restore submodule pointer"
git -C <ai-workflow-path> push origin <main-branch>
```

This commit is what the deploy cron will pick up to redeploy the rolled-back state.

#### R7. Wait for redeploy + verify

- Wait for cron deploy to pick up the new pointer (~1-2 min)
- Run `smoke_test_cmd` from rollback.md
- Verify: tests that previously checked the issue's deliverable now should fail (because the deliverable no longer exists), OR if rollback restores prior behavior, verify prior behavior is back

If verification fails, write that to rollback-report.md and **escalate to user** — partial rollback is worse than complete rollback or none.

### Output

`issues/<gitee_id>/rollback-report.md`:

```markdown
# Rollback Report: <gitee_id>

**Started**: <timestamp>
**Completed**: <timestamp>
**Triggered by**: <user | auto-from-deliverable-check-fail>

## Steps executed
- [x] Migration downgrade (revision X → Y)
- [x] Backend revert (sha: <revert-commit-sha>)
- [x] Web revert (sha: <revert-commit-sha>)
- [x] ai-workflow pointer restore
- [x] Redeploy verified
- [x] Smoke test post-rollback: PASS / FAIL

## Result

state: rolled-back
```

Update `status.md` state to `rolled-back`.

Update `STATUS.md` to move this issue from In-Flight to Rolled-Back section.

### Failure modes

- `dependent_commits_after_merge` non-empty and user picks neither option → don't proceed; mark `rollback-blocked` state in status.md
- Migration downgrade fails → STOP; investigate manually before any other step
- Revert produces conflicts → STOP; resolve conflicts then re-run
- Smoke verification fails after rollback → STOP; alert user; do NOT mark state as rolled-back

---

## Anti-patterns

- ❌ Generate playbook with missing fields (false safety)
- ❌ Skip dependency check (would silently break dependent issues)
- ❌ Run destructive migration downgrade without checking backup
- ❌ Mark state `rolled-back` before smoke verification passes
- ❌ Auto-trigger cascade rollback without user confirmation
- ❌ Proceed past R3-R7 if any prior step failed
