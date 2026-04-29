---
name: orchestration
description: |
  Top-level orchestrator for issuepowers. Drives a Gitee issue through its lifecycle
  (understanding → implementation → merge → deploy → deliverable-check → validation).
  Triggered by /solve, /rollback, and SessionStart. Maintains issue status.md and global STATUS.md.
  P0 implements `solve` mode through confirmed understanding; subsequent modes are P1+.
---

# Orchestration Skill

Top-level driver for issuepowers. Routes by mode.

## Modes

| Mode | Trigger | Stage |
|---|---|---|
| `solve` | `/solve <id>` command | P0 ✅ — covers up to confirmed understanding |
| `implement` | After `solve` returns in-progress | P1 ✅ — drives superpowers 闭环 + cross-issue conflict + rollback rehearsal |
| `merge` | After self-review pass | P1 ✅ — `.merge-lock` + squash + tag + submodule pointer |
| `deploy-check` | After merge + cron deploy | P1 ✅ — calls `issuepowers:deliverable-check`, handles signals |
| `fix-forward` | User reports minor UAT failure | P1 ✅ — append uat-feedback to understanding, restart from plan |
| `rollback` | `/rollback <id>` command | P1 ✅ — wraps `issuepowers:rollback` execute mode |
| `resume` | SessionStart hook | P2 ⏳ — reads STATUS.md, reports in-flight |

---

## State Machine

External states:

- `understanding-in-progress` — in /solve dialog
- `understanding-needs-info` — paused, blocked
- `in-progress` — Agent autonomous (P1); also re-entered on fix-forward
- `pending-validation` — awaiting human validation (P1)
- `done`
- `rolled-back`
- `split-into-children` — parent

Transitions at `pending-validation`:

- ✅ pass → `done`
- ⚠️ fail-minor → `in-progress` (fix-forward, increment counter)
- ❌ fail-major → `rolled-back` (via `/rollback`)

Constraints:

- fix-forward counter ≥ 3 → force rollback path
- `deliverable-check` fail during `in-progress` → auto rollback, no fix-forward

---

## Mode: solve (P0)

### Inputs
- `gitee_id` — required, Gitee issue ID (e.g., `IJG6FV`)
- `slug` — optional; derive from title if absent

### Step 1 — Pull issue from Gitee

Use deferred tool `mcp__gitee-ent__get_enterprise_issue_detail`. Need to load via ToolSearch first if not in current scope.

Required fields to extract: title, body, labels, comments (read all comments — context often there, not in body).

**On fetch failure**: report to user with exact error; do not proceed.

### Step 2 — Resolve slug

If `slug` provided, use it. Otherwise:
- Take title
- Lowercase
- ASCII-only (drop CJK / emoji)
- Replace whitespace + punctuation with `-`
- Truncate to 40 chars
- Strip trailing `-`

If after slugification the slug is empty (e.g., title was all CJK), ask the user to provide one.

### Step 3 — Create issue directory

Create `docs/superpowers/issues/<gitee_id>/`.

Inside, create `status.md`:

```yaml
issue: <gitee_id>
slug: <slug>
state: understanding-in-progress
type: unknown            # filled by requirements-understanding
risk: unknown            # filled at plan stage (P1)
created: <ISO timestamp>
worktree: worktrees/<gitee_id>/
branches:
  backend: feature/<gitee_id>-<slug>
  web: feature/<gitee_id>-<slug>
parent: null             # set if this is a child of a split
children: []             # set if this issue is split
blockers: []
```

### Step 4 — Setup worktrees + feature branches

In the **consuming project** (the project using issuepowers, not the issuepowers repo itself):

For each submodule that this issue likely touches (backend, web — read from project's CLAUDE.md if uncertain):

```bash
git -C <submodule-path> fetch origin develop
git -C <submodule-path> worktree add ../worktrees/<gitee_id>/<submodule-name> -b feature/<gitee_id>-<slug> origin/develop
```

If `feature/<gitee_id>-<slug>` already exists upstream, check out instead of `-b`.

### Step 5 — Update STATUS.md

Append a row to `docs/superpowers/STATUS.md` under "In-Flight Issues":

```markdown
| <gitee_id> | <slug> | understanding-in-progress | <type> | <risk> | Agent (in /solve) |
```

If STATUS.md doesn't exist, create from template (header + In-Flight + Recently Done sections).

### Step 6 — Invoke requirements-understanding

Call skill `issuepowers:requirements-understanding`, passing:
- issue body + comments (from Step 1)
- path to `understanding.md` to write
- path to `split-proposal.md` (in case split is needed)

Wait for skill to return one of:
- `confirmed` — single issue, understanding.md done
- `split-confirmed` — split happened, all children also confirmed
- `needs-info` — user can't answer enough; blockers populated

### Step 7 — Land state

| Skill returned | status.md update |
|---|---|
| `confirmed` | state = `in-progress` |
| `split-confirmed` | parent state = `split-into-children`; for each child issue, state = `in-progress` |
| `needs-info` | state = `understanding-needs-info`, blockers from skill |

Update STATUS.md row accordingly.

### Step 8 — Report to user

Be brief but specific:

```
✅ Understanding confirmed for <id>.
   State: in-progress
   Path:  docs/superpowers/issues/<id>/understanding.md
   
   Next: Agent will proceed autonomously through implementation, merge, and deploy.
   You'll be notified at the validation gate.
```

For `needs-info`:
```
⚠️ Cannot reach confirmed understanding for <id>.
   State: understanding-needs-info
   Blockers:
     - <blocker 1>
     - <blocker 2>
   
   Resolve blockers and re-run /solve <id>.
```

### Step 9 (P1 — currently stub)

Hand off to `mode: implement`. **For P0**, return control to user — do not auto-trigger implementation.

---

## Mode: merge (P1)

### Goal

Atomically merge a self-review-passed feature branch to develop **with rollback playbook in place
before merge**. Serial via `.merge-lock` to keep develop linear and revertable.

### Pre-conditions (caller must ensure)

- All `plan.md` checkboxes done
- Type / lint / unit tests green
- Acceptance tests written: `tests/acceptance/<gitee_id>/` exists, one test per `## 关键行为`
- Cross-issue conflict check: passed (no overlap with other in-flight issues' files)
- Rollback rehearsal: passed (scratch squash + revert + smoke succeeded)

If any pre-condition unmet, **do NOT enter merge mode** — escalate.

### Inputs

```yaml
gitee_id: <id>
slug: <slug>
branches:
  backend: feature/<id>-<slug>
  web: feature/<id>-<slug>      # may be absent if web not touched
project_root: <path>
submodule_paths:
  backend: <path>
  web: <path>
```

### Step 1 — Acquire .merge-lock

At `<project_root>`:

```bash
if ! ( set -o noclobber; echo "$$" > .merge-lock ) 2>/dev/null; then
  existing_pid=$(cat .merge-lock)
  if kill -0 "$existing_pid" 2>/dev/null; then
    echo "Another merge in progress (PID $existing_pid)"
    exit 1
  fi
  rm .merge-lock && echo "$$" > .merge-lock   # stale lock, recover
fi
trap 'rm -f .merge-lock' EXIT
```

If acquire fails (live competing merge), surface to user — do NOT auto-wait silently. The user decides whether to queue or pause.

### Step 2 — Pre-merge tags

For each submodule:

```bash
git -C <submodule_path> fetch origin develop
TS=$(date +%s)
git -C <submodule_path> tag pre-merge/<gitee_id>-$TS origin/develop
git -C <submodule_path> push origin pre-merge/<gitee_id>-$TS
```

These tags lock down "where develop was just before this merge" — anchors for rollback verification.

### Step 3 — Generate rollback.md (must succeed)

Call `issuepowers:rollback` skill in `generate` mode. Pass:
- `gitee_id`
- Computed merge SHAs (dry-run squash to capture)
- Pre-merge tag names from Step 2
- Migration revisions (before / after)
- Feature flag (if any)

If generation fails (missing fields, can't compute SHAs): **abort merge, release lock**. Do NOT proceed.

A bad/incomplete rollback.md is worse than no merge — false safety beats no safety.

### Step 4 — Squash merge each submodule

For each submodule:

```bash
cd <submodule_path>
git checkout develop
git pull origin develop                        # ensure up-to-date
git merge --squash feature/<gitee_id>-<slug>
```

Compose commit message:

```
feat(<gitee_id>): <slug, human-readable summary>

<bullet list from understanding.md 关键行为>

Rollback playbook: docs/superpowers/issues/<gitee_id>/rollback.md
```

Commit:

```bash
git commit -F .git/COMMIT_EDITMSG_<gitee_id>
```

If squash conflicts: **abort, release lock, escalate** (cross-issue conflict check should have caught this; if slipped through, that's a bug in the check).

### Step 5 — Push to develop

```bash
git push origin develop
```

If rejected (concurrent push):
- `git pull --rebase`
- `git push origin develop` (one retry)
- Still fails → abort, release lock, escalate

### Step 6 — Post-merge tags

```bash
git tag deployed/<gitee_id>-$TS develop
git push origin deployed/<gitee_id>-$TS
```

This sha must match the `merge_sha` field captured in rollback.md from Step 3.

### Step 7 — Update ai-workflow submodule pointers

At project root:

```bash
cd <project_root>
git submodule update --remote backend
git submodule update --remote web                # if applicable
git add backend web
git commit -m "chore(<gitee_id>): submodule pointer update"
git push origin main
```

This is the commit the deploy cron picks up to redeploy.

### Step 8 — Update dependent_commits_after_merge for older in-flight issues

**Critical for rollback dependency check.** Without this, rolling back this issue later won't know which subsequent issues built on top of it.

```python
this_issue_files = git_diff_names(pre_merge_tag, deployed_tag)
for other_issue in in_flight_issues_other_than_self:
    other_files = read_other_branch_diff(other_issue)
    if intersect(this_issue_files, other_files):
        append_to(other_issue.rollback_md.dependent_commits_after_merge, deployed_tag.sha)
```

If `git diff` for an older issue fails (branch deleted, etc.), log warning but don't block — that issue's rollback dependency check will be incomplete and need manual review.

### Step 9 — Update state

- `status.md`: state stays `in-progress` (merge ≠ end of in-progress; deploy-check follows)
- Append history entry: `merged: <ISO timestamp>, sha: <merge-sha>`
- Update `STATUS.md` row's "Waiting on" → `Agent (deploy + check)`

### Step 10 — Release lock + hand off

```bash
rm .merge-lock        # also covered by trap
```

Hand off to `deploy-check` mode (orchestration enters the next mode automatically).

### Failure handling matrix

| Step | Failure | Action |
|---|---|---|
| 1 | Lock held by alive PID | Surface to user, no auto-wait |
| 1 | Stale lock | Clean + retry once |
| 3 | rollback.md gen fail | Abort, release lock |
| 4 | Squash conflict | Abort, release lock, escalate (process-violation flag) |
| 5 | Push rejected | Rebase + retry once; persist fail → escalate |
| 6 | Tag push fail | Retry once, then escalate |
| 7 | Submodule pointer commit/push fail | Roll back step 4-6 (revert squash on develop), release lock, escalate |
| 8 | Cannot read other in-flight issues | Continue, log warning (incomplete rollback graph) |

### Anti-patterns

- ❌ Hold `.merge-lock` for > 60s (refactor or split if longer)
- ❌ Force push under any circumstance
- ❌ Skip Step 3 (rollback.md generation) — false safety
- ❌ Skip Step 8 (dependent commits update) — silently breaks rollback for siblings
- ❌ Continue past any failed step — must abort
- ❌ Merge commit instead of squash (revert wouldn't be clean)

---

## Mode: rollback (P1)

Thin orchestration wrapper around `issuepowers:rollback` skill.

### Procedure

1. Validate state allows rollback:
   - state ∈ { `in-progress`, `pending-validation`, `deployed-pending-uat` }
   - Otherwise: refuse (e.g., already `rolled-back`, `done`, or pre-merge state — different rules apply)
2. Call `issuepowers:rollback` skill in `execute` mode with `gitee_id`
3. Skill handles: dependency check, migration downgrade, reverts, pointer restore, redeploy verify, report
4. On skill completion: state = `rolled-back`, update STATUS.md (move to "Recently Rolled-Back" section)

### Failure

- Skill returns `dependency-blocked`: state = `rollback-blocked`, surface options (cascade vs hot-fix) to user
- Skill returns `partial-failure`: state = `rollback-incomplete`, escalate hard — manual repair needed
- Skill returns `verification-failed`: same as partial — don't claim rolled-back without smoke confirming

---

## Mode: implement (P1)

Drives autonomous portion from `in-progress` to ready-for-merge.

### Pre-conditions

- state = `in-progress`
- `understanding.md` confirmed
- worktree + feature branches set up by solve mode

### Inputs

```yaml
gitee_id: <id>
understanding_path: docs/superpowers/issues/<id>/understanding.md
worktree_path: worktrees/<id>/
branches:
  backend: feature/<id>-<slug>
  web: feature/<id>-<slug>
project_root: <path>
```

### Phase A — Optional brainstorming

Skip for most issues — understanding.md is usually sufficient.

Invoke `superpowers:brainstorming` only when:

- Issue is large / architectural in scope
- understanding.md mentions "需要进一步设计"
- User explicitly requests deeper exploration

Output: `docs/superpowers/specs/<date>-<gitee_id>-<slug>-design.md`

### Phase B — Plan (mandatory)

Invoke `superpowers:writing-plans` skill, passing understanding.md (and spec.md if Phase A ran) as context.

Output: `docs/superpowers/plans/<date>-<gitee_id>-<slug>-plan.md`

**Critical augmentation**: ensure the plan includes this task block early:

```markdown
### Task: 写 acceptance tests

For each `## 关键行为` line in understanding.md:
  - Create `tests/acceptance/<gitee_id>/<n>-<short-slug>.<ext>` (extension by project: .spec.ts, .py, etc.)
  - Test asserts the behavior holds against deployed env (not local mocks)

For Bug 类:
  - Test asserting原复现路径 produces the corrected behavior
  - Test asserting bug-trigger condition does NOT produce buggy outcome

For Refactor 类:
  - For each「不能变的行为」, write a regression test
```

If `superpowers:writing-plans` doesn't auto-include this, manually add. Without these tests, deliverable-check will block at `incomplete-coverage`.

### Phase C — Execute plan

Invoke `superpowers:subagent-driven-development`. Use `superpowers:test-driven-development` for unit-level discipline.

Don't proceed past plan execution until all checkboxes are done.

### Phase D — Self-review (must ALL pass before merge)

#### D1. Code review

- `superpowers:requesting-code-review` (Agent prepares request: diff + intent)
- `superpowers:receiving-code-review` (reviewer subagent gives structured feedback)
- Iterate until reviewer approves

#### D2. Cross-issue conflict check (issuepowers-specific)

For each in-flight issue (state ∈ {`in-progress`, `pending-validation`}) **other than this**:

```bash
this_files=$(git -C <submodule> diff --name-only develop...feature/<gitee_id>-<slug> | sort)

for other in $other_inflight_issues; do
  other_files=$(git -C <submodule> diff --name-only develop...feature/$other_id-$other_slug | sort)
  intersect=$(comm -12 <(echo "$this_files") <(echo "$other_files"))
  if [ -n "$intersect" ]; then
    echo "CONFLICT: $other_id touches the same files: $intersect"
    BLOCK=1
  fi
done
```

If conflict found:

- **BLOCK** — do not proceed to merge mode
- Surface to user: "X and Y both touch <file list>. Coordinate which goes first."
- Wait for resolution: either the other issue completes (state → done/rolled-back), or user decides serialization order

#### D3. Rollback rehearsal (issuepowers-specific)

In a scratch worktree:

```bash
git worktree add /tmp/rehearsal-<gitee_id> develop
cd /tmp/rehearsal-<gitee_id>
git merge --squash feature/<gitee_id>-<slug>
git commit -m "rehearsal squash"
SQUASH_SHA=$(git rev-parse HEAD)
git revert $SQUASH_SHA --no-edit
<project test command>      # smoke / acceptance tests on reverted state
cd <project_root>
git worktree remove /tmp/rehearsal-<gitee_id> --force
```

If smoke tests fail post-revert: **rollback path is broken**. Common causes:
- Migration without downgrade
- Delete-then-recreate that loses data
- Schema change that's destructive on revert

**BLOCK merge until rollback story is fixed.** False rollback safety > no safety.

#### D4. Migration up/down check

If this issue includes a migration:

```bash
cd <backend>
flask db downgrade <rev-before-this-issue>   # must succeed cleanly
flask db upgrade head                         # must succeed
flask db downgrade <rev-before-this-issue>   # second cycle: still works?
flask db upgrade head                         # back to head
```

Both directions must run cleanly. If downgrade fails or loses data unsafely: BLOCK, fix migration.

#### D5. Final green checks

- Type checks pass (`pnpm ts:check`, `mypy`, etc.)
- Lint clean (`pnpm lint`, `flake8`, etc.)
- Unit tests pass (`pnpm test`, `pytest`, etc.)
- Acceptance test count ≥ count of `## 关键行为` lines in understanding.md
- Diff size sanity: warn at > 1000 lines, **block at > 5000 lines** (scope ballooned, should have been split)

### On all D phases pass

Hand off to `merge` mode.

### Failure handling

| D phase | Fail | Action |
|---|---|---|
| D1 | Review feedback unaddressed | Iterate fix until reviewer approves |
| D2 | Cross-issue conflict | Block, escalate to user for coordination |
| D3 | Rollback rehearsal fails | Block, fix rollback story (often: add downgrade, or feature-flag the change) |
| D4 | Migration not bidirectional | Block, add downgrade logic |
| D5 | Greens not all green | Iterate fix |

State stays `in-progress` throughout failure handling. Never advance to merge with unresolved D-phase issues.

### Anti-patterns

- ❌ Skip Phase B's acceptance test augmentation (will fail at deliverable-check Step 2)
- ❌ Skip any D phase — they're the safety net before `.merge-lock` is touched
- ❌ "Approximately passed" D phases — must be hard pass
- ❌ Run merge mode without all D phases verified

---

## Mode: deploy-check (P1)

Triggered automatically by `merge` mode after Step 7 (submodule pointer push).

### Pre-conditions

- merge mode completed successfully
- Project's `main` branch has a new submodule pointer commit
- Deploy cron expected to pick it up

### Step 1 — Wait for deploy

Poll deploy completion. Mechanism depends on project (read project's CLAUDE.md):

- **Stamp file**: deploy script writes `deploy/last-deployed-sha` after success → poll until matches
- **Endpoint**: `GET /version` or `/deploy-info` → check `commit_sha` field
- **Log tail**: SSH to deploy host, tail deploy log for completion marker

Default: 30s polling, **10 min total timeout**. If timeout: escalate (cron broken or stuck), do NOT proceed.

### Step 2 — Stabilization wait

After deploy reports success, wait 30-60s. Apps may need:
- Cache warm-up
- Migration to apply (if not part of deploy)
- Worker pool restart
- CDN propagation

### Step 3 — Call deliverable-check

Invoke `issuepowers:deliverable-check` skill:

```yaml
gitee_id: <id>
understanding_path: docs/superpowers/issues/<id>/understanding.md
report_path: docs/superpowers/issues/<id>/deliverable-report.md
deploy_env: dev | staging   # from project config
```

### Step 4 — Handle signal

| Signal | Action |
|---|---|
| `pass` | state = `pending-validation`; append `validated_at: <ts>` to status.md; STATUS.md "Waiting on" → "User UAT"; notify user |
| `fail` | **auto-trigger `rollback` mode** (no user gate — Agent 自我打脸) |
| `incomplete-coverage` | Escalate; retain `in-progress` state; surface which behaviors lack tests |
| `error` | Escalate (test infra broken); retain state |
| `over-budget` | Escalate (tests too heavy); retain state |

For `pass`, notification format:

```
✅ <gitee_id> <slug> deployed and verified.
   <X/Y> acceptance tests pass (<duration>).

   State: pending-validation
   Report: docs/superpowers/issues/<id>/deliverable-report.md

   Action needed: please UAT and respond.
   - Pass: confirm verbally → state = done
   - Minor failure: create issues/<id>/uat-feedback.md, fix-forward will resume
   - Major failure: /rollback <id>
```

### Anti-patterns

- ❌ Mark pending-validation without re-running tests against deployed env
- ❌ "We tested locally so it's fine" shortcut
- ❌ Continue past deploy timeout (escalate, not silent)
- ❌ Auto-mark pass on `incomplete-coverage`

---

## Mode: fix-forward (P1)

Triggered by user creating `issues/<id>/uat-feedback.md` with type=minor.

### Pre-conditions

- state = `pending-validation`
- `uat-feedback.md` exists and `failure_type` is marked `minor`
- User has decided fix-forward over rollback

### Step 1 — Validate inputs

If `uat-feedback.md` missing or empty: ask user to provide specific feedback. Don't proceed without concrete signal.

If marked `major`: refuse fix-forward, instruct user to use `/rollback <id>`.

### Step 2 — Validate counter

Read `status.md.fix-forward-count` (default 0).

If count ≥ 3:
- **Refuse** fix-forward
- Tell user: "已 fix-forward 3 次仍未通过 UAT。说明 understanding 本身有偏差或实施路径有结构问题。建议 /rollback <id>，必要时重新 /solve（修订 understanding）。"
- Do NOT increment, do NOT change state. User must explicitly /rollback.

### Step 3 — Append uat-feedback to understanding.md

**Append** (don't replace) a new section:

```markdown
## UAT Feedback Iteration <N> — incremental requirement refinement

<content from uat-feedback.md, organized as 关键行为 additions / clarifications>

(添加于 <ISO timestamp>，由 fix-forward 流程引入)
```

Treats UAT feedback as discovered requirements that augment the contract, not contradict it. The original 关键行为 section remains the contract anchor.

### Step 4 — Increment counter + history

```yaml
status.md:
  fix-forward-count: <prev + 1>
  history:
    - { event: fix-forward-started, iteration: <N>, at: <ts>, source: uat-feedback.md }
```

### Step 5 — State transition

state = `in-progress`. Update STATUS.md row "Waiting on" → "Agent (fix-forward iteration N)".

### Step 6 — Restart from implement mode Phase B

Do NOT redo understanding — it's the (now augmented) contract anchor.

Restart at implement mode Phase B (writing-plans):
- Pass updated understanding.md to `superpowers:writing-plans`
- New plan should explicitly address the UAT feedback items
- Old acceptance tests remain; new ones may be added if new 关键行为 emerged from feedback

Continue through Phase C → D → merge → deploy-check as normal.

### Anti-patterns

- ❌ Replace understanding.md (loses contract history)
- ❌ Skip counter check (allows infinite fix-forward churn)
- ❌ Re-run requirements-understanding (the issue is implementation drift, not misunderstanding)
- ❌ Auto-decide fix-forward vs rollback (user must explicitly choose by what they create)
- ❌ Continue with vague uat-feedback.md (concrete failure description required)

---

## Mode: resume (P2 ⏳)

Triggered by SessionStart hook.

### When P2 ships, this mode will:

1. Read `STATUS.md`
2. For each in-flight issue, summarize current state
3. Surface "Waiting on you" rows prominently (the user's TODO list at session start)
4. Do NOT auto-resume `understanding-needs-info` issues (they need user input)

---

## Anti-patterns

- ❌ Skip requirements-understanding (always run, even if issue looks "obvious")
- ❌ Invent understanding when user is unavailable — pause instead
- ❌ Mix multiple issues' state in one status.md
- ❌ Allow two issues into merge phase simultaneously (must use `.merge-lock`)
- ❌ Auto-resume `understanding-needs-info` without checking blockers
