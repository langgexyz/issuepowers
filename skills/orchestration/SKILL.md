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
| `merge` | After self-review pass | P1 ✅ — `.merge-lock` + `merge --no-ff` + tag + submodule pointer |
| `deploy-check` | After merge + cron deploy | P1 ✅ — calls `issuepowers:deliverable-check`, handles signals |
| `fix-forward` | User reports minor validation failure | P1 ✅ — append user-validation-feedback to understanding, restart from plan |
| `rollback` | `/rollback <id>` command | P1 ✅ — wraps `issuepowers:rollback` execute mode |
| `resume` | SessionStart hook | P1 ✅ — reads STATUS.md, surfaces "waiting on user" rows |

---

## STATUS.md Protocol

所有 mode 共享的协调文件。

### 路径

`<project_root>/docs/superpowers/STATUS.md`

### 格式

```markdown
# In-Flight Issues  (last updated: <ISO timestamp>)

| Issue | Slug | State | Type | Risk | Waiting on |
|---|---|---|---|---|---|
| IJG6FV | scan-confirm | pending-validation | feature | low | User validation |
| IJ9X12 | experiment-v2 | in-progress | refactor | high | Agent (D2 cross-issue check) |
| IJFBUP | timeliness-warning | understanding-needs-info | feature | medium | User (answer blockers) |

# Recently Done

- IJFBUG actual-reviewer (done, deployed 2026-04-28, UAT pass)
- IJF7K2 batch-import (rolled-back 2026-04-26, UAT 发现严重数据问题)
```

### 更新规约

- **谁写**：每个发生状态转换的 mode 都要更新本文件。Mode 即写入者，不允许集中后处理（避免漏更新）
- **写什么**：
  - state 变化 → 更新该行的 State 列
  - "Waiting on" 列粒度要够细：
    - `Agent (in /solve)` — understanding 对话中
    - `User (answer blockers)` — needs-info
    - `Agent (Phase B writing-plans)` — plan 阶段
    - `Agent (Phase D2 cross-issue check)` — self-review 中具体哪一项
    - `Agent (deploy + check)` — 等 cron + deliverable-check
    - `User validation` — pending UAT
    - `User (rollback decision: cascade vs hot-fix)` — rollback 阻塞
  - 终态（done / rolled-back）→ 把行从 In-Flight 段搬到 Recently Done 段
- **何时写**：状态转换原子动作里同步写，不要等「稍后批量更新」
- **不写**：
  - 中间过程的细分进度（不用每分钟更新）
  - 用户的私人备注（status.md 内部用，不暴露看板）

### 并发

多 Agent 进程不会同时写本文件 —— 各 mode 在各自 worktree 跑，但 `STATUS.md` 在项目根。当多 issue 同时推进，理论上写竞争存在，但实践极少（mode 内瞬时写一次就完）。

如果未来变成瓶颈：append-only 行格式 + 离线整合。当前不优化。

### 用户交互

`resume` mode 是用户对 STATUS.md 的主要消费入口。用户也可以直接打开文件看（普通 markdown 表格人类可读）。

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
- All commits on feature branch follow `<type>(<gitee_id>): <subject>` convention (design.md §2 原则 6)
- Cross-issue conflict check: passed (no overlap with other in-flight issues' files)
- Rollback rehearsal: passed (scratch worktree: `git merge --no-ff` + `git revert -m 1` + smoke succeeded)

If any pre-condition unmet, **do NOT enter merge mode** — escalate.

### Where operations happen

**所有对 develop 的操作都在主 worktree 的 submodule 内进行**。Per-issue worktree (`worktrees/<gitee_id>/`) 永远不 checkout develop —— 它只在 `feature/<gitee_id>-<slug>` 分支上工作。这把「实施期工作区」和「合并到 develop」物理隔离，防止误推。

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

### Step 2 — Pre-merge tags（主 worktree submodule）

For each submodule, in **主 worktree's submodule path**:

```bash
cd <main_worktree>/<submodule_name>
git fetch origin
TS=$(date +%s)
git tag pre-merge/<gitee_id>-$TS origin/develop
git push origin pre-merge/<gitee_id>-$TS
```

Tag 锁定「merge 之前 origin/develop 在哪儿」—— rollback 验证锚点。

### Step 3 — Merge --no-ff（拿真实 MERGE_SHA）

For each submodule, **仍在主 worktree submodule 内**:

```bash
cd <main_worktree>/<submodule_name>
git checkout develop
git pull origin develop                        # sync local develop with origin

# 写 merge commit message
cat > /tmp/merge-msg-<gitee_id> <<EOF
merge(<gitee_id>): <slug, human-readable summary>

- <bullet list from understanding.md 关键行为>

Rollback playbook: docs/superpowers/issues/<gitee_id>/rollback.md
EOF

# 关键: --no-ff 强制创建 merge commit, feature 的 N 个 commit 全部保留可见
git merge --no-ff feature/<gitee_id>-<slug> -F /tmp/merge-msg-<gitee_id>

MERGE_SHA[<submodule>]=$(git rev-parse HEAD)
```

约束：
- **必须** `--no-ff`（design.md §2 原则 6），不允许 squash 或 fast-forward
- **必须** 用 `(<gitee_id>)` scope 的 message（自动 grep 可定位）

如果 merge 冲突：cross-issue conflict check 应该已经抓住，到这一步算 process violation —— **abort，release lock，escalate**。

### Step 4 — Generate rollback.md（用真实 MERGE_SHA）

merge 已经创造了真 SHA，**现在**调 `issuepowers:rollback` 的 `generate` mode：

```yaml
gitee_id: <gitee_id>
merge_strategy: merge-no-ff   # 决定 rollback 用 git revert -m 1
merge_sha:
  backend: <real-merge-sha>
  web: <real-merge-sha>
ai_workflow_pointer_before: <主仓 main 当前 SHA>
pre_merge_tags:
  backend: pre-merge/<gitee_id>-$TS
  web: pre-merge/<gitee_id>-$TS
migration_revision:
  before: <alembic-rev-before>
  after: <alembic-rev-after>
feature_flag: <name 或 null>
```

如果生成失败（字段缺、模板异常）：**abort**。撤销刚才的本地 merge：

```bash
# 不能 reset --hard (违反 §2 原则 7)
# 用 revert 创造反向 commit, 历史完整
git revert -m 1 HEAD --no-edit
```

撤销后 release lock，escalate。本地 develop 会有 merge + revert 的对子（不 push 出去就不影响别人），下次 merge 重试时 `git pull --rebase` 会处理掉这对（origin 上没这两个 commit）。

### Step 5 — Push develop

```bash
cd <main_worktree>/<submodule_name>
git push origin develop
```

失败处理：

| 失败原因 | 处理 |
|---|---|
| 远端有新 commit (rejected non-fast-forward) | `git pull --rebase origin develop` 后重试 1 次 |
| 重试仍失败 | `git revert -m 1 HEAD --no-edit` (撤回 merge 创建反向 commit), `git push origin develop` (推 revert), abort, escalate |
| 网络 / 认证错误 | escalate, 不自动重试 (可能凭据过期) |

**不允许** `git reset` / `git push --force` 任何形式。

### Step 6 — Post-merge tags

```bash
cd <main_worktree>/<submodule_name>
git tag deployed/<gitee_id>-$TS develop
git push origin deployed/<gitee_id>-$TS
```

deployed tag 的 SHA = rollback.md 里 `merge_sha[<submodule>]` 字段，必须一致。

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
| 3 | merge 冲突 | Process violation (cross-issue check 应该抓), abort, escalate |
| 4 | rollback.md gen fail | `git revert -m 1 HEAD --no-edit` (本地撤回 merge), abort, release lock |
| 5 | Push rejected (non-ff) | `git pull --rebase` + 重试 1 次; 仍失败则 `git revert -m 1` + push revert, escalate |
| 5 | 网络/认证错 | Escalate (不自动重试) |
| 6 | Tag push fail | 重试 1 次, 仍失败 escalate |
| 7 | Submodule pointer commit/push fail | 用 `git revert -m 1` 撤回各 submodule develop 上的 merge, release lock, escalate |
| 8 | 读其他 in-flight issues 失败 | Continue, 标 warning (rollback graph 不完整, 后续 manual review) |

### Anti-patterns

- ❌ Hold `.merge-lock` for > 60s (refactor or split if longer)
- ❌ `git push --force[-with-lease]` under ANY circumstance
- ❌ `git reset --hard <任何 ref>` —— design.md §2 原则 7 已禁
- ❌ Skip Step 4 (rollback.md generation) — false safety
- ❌ Skip Step 8 (dependent commits update) — silently breaks rollback for siblings
- ❌ Continue past any failed step — must abort
- ❌ `git merge --squash` —— design.md §2 原则 6 禁，必须 --no-ff 留全 commit 历史
- ❌ Per-issue worktree 内 checkout develop —— 主 worktree 才操作 develop
- ❌ Merge message 缺 `(<gitee_id>)` scope —— 违反 §2 原则 6

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
- **Commit message convention** (design.md §2 原则 6): `git log develop..feature/<gitee_id>-<slug> --pretty=%s` 输出每行必须匹配 `^[a-z]+\(<gitee_id>\): ` —— 任意一行不符合就 BLOCK，让 Agent 改 message（`git rebase -i` 或在 plan 阶段加 commit-msg hook）

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
| `pass` | state = `pending-validation`; append `validated_at: <ts>` to status.md; STATUS.md "Waiting on" → "User validation"; notify user |
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

   Action needed: please validate and respond.
   - Pass: confirm verbally → state = done
   - Minor failure: create issues/<id>/user-validation-feedback.md, fix-forward will resume
   - Major failure: /rollback <id>
```

### Anti-patterns

- ❌ Mark pending-validation without re-running tests against deployed env
- ❌ "We tested locally so it's fine" shortcut
- ❌ Continue past deploy timeout (escalate, not silent)
- ❌ Auto-mark pass on `incomplete-coverage`

---

## Mode: fix-forward (P1)

Triggered by user creating `issues/<id>/user-validation-feedback.md` with type=minor.

### Pre-conditions

- state = `pending-validation`
- `user-validation-feedback.md` exists and `failure_type` is marked `minor`
- User has decided fix-forward over rollback

### Step 1 — Validate inputs

If `user-validation-feedback.md` missing or empty: ask user to provide specific feedback. Don't proceed without concrete signal.

If marked `major`: refuse fix-forward, instruct user to use `/rollback <id>`.

### Step 2 — Validate counter

Read `status.md.fix-forward-count` (default 0).

If count ≥ 3:
- **Refuse** fix-forward
- Tell user: "已 fix-forward 3 次仍未通过用户验证。说明 understanding 本身有偏差或实施路径有结构问题。建议 /rollback <id>，必要时重新 /solve（修订 understanding）。"
- Do NOT increment, do NOT change state. User must explicitly /rollback.

### Step 3 — Append user-validation-feedback to understanding.md

**Append** (don't replace) a new section:

```markdown
## 用户验证反馈第 <N> 轮 — 需求增量修订

<内容来自 user-validation-feedback.md, 整理为关键行为的补充或澄清>

(添加于 <ISO timestamp>，由 fix-forward 流程引入)
```

Treats user validation feedback as discovered requirements that augment the contract, not contradict it. The original 关键行为 section remains the contract anchor.

### Step 4 — Increment counter + history

```yaml
status.md:
  fix-forward-count: <prev + 1>
  history:
    - { event: fix-forward-started, iteration: <N>, at: <ts>, source: user-validation-feedback.md }
```

### Step 5 — State transition

state = `in-progress`. Update STATUS.md row "Waiting on" → "Agent (fix-forward iteration N)".

### Step 6 — Restart from implement mode Phase B

Do NOT redo understanding — it's the (now augmented) contract anchor.

Restart at implement mode Phase B (writing-plans):
- Pass updated understanding.md to `superpowers:writing-plans`
- New plan should explicitly address the user validation feedback items
- Old acceptance tests remain; new ones may be added if new 关键行为 emerged from feedback

Continue through Phase C → D → merge → deploy-check as normal.

### Anti-patterns

- ❌ Replace understanding.md (loses contract history)
- ❌ Skip counter check (allows infinite fix-forward churn)
- ❌ Re-run requirements-understanding (the issue is implementation drift, not misunderstanding)
- ❌ Auto-decide fix-forward vs rollback (user must explicitly choose by what they create)
- ❌ Continue with vague user-validation-feedback.md (concrete failure description required)

---

## Mode: resume (P1)

Triggered automatically by SessionStart hook when a Claude Code session starts in an issuepowers-enabled project.

**Goal**: 把所有 in-flight issue 现状摆出来，让用户一眼看到「哪些等我处理」。绝不自动推进 issue。

### Pre-conditions

- SessionStart hook fired
- Working directory is an issuepowers-enabled project (has `docs/superpowers/STATUS.md` or `docs/superpowers/issues/`)

### Step 1 — Read STATUS.md

Path: `docs/superpowers/STATUS.md`.

If file doesn't exist:
- Project is fresh / no issuepowers usage yet
- Output: `📭 No in-flight issuepowers issues. Use /solve <gitee-id> to start.`
- Exit (don't create empty STATUS.md proactively)

### Step 2 — Parse In-Flight Issues

Read the `# In-Flight Issues` table. For each row, extract: issue id / slug / state / type / risk / waiting on.

### Step 3 — Classify by who's blocked

Two buckets:

**等用户**（必须用户介入才能推进）：
- `understanding-needs-info` — Agent 需要用户补信息（blockers 在 status.md）
- `pending-validation` — Agent 已交付，等用户验证
- `rollback-blocked` — 回滚有依赖，等用户选 cascade vs hot-fix

**Agent 在跑**（不需要用户介入，仅信息性）：
- `in-progress` — Agent 自动跑实施 / 自审 / 部署 / check
- `understanding-in-progress` — `/solve` 对话中（如果出现说明会话被中断，可能要用户重启）

**已终止**（不展示在 in-flight，仅出现在 Recently Done）：
- `done` / `rolled-back` / `split-into-children`（父）

### Step 4 — Output 格式

```
📋 in-flight: <N> issues

⏳ 等你处理 (<M>):
  • IJG6FV scan-confirm — pending-validation
    → 看 issues/IJG6FV/deliverable-report.md → 确认通过 / 写 user-validation-feedback / /rollback
  • IJ9X12 experiment-v2 — understanding-needs-info
    → blockers: <列出 blockers from status.md>

🤖 Agent 在跑 (<K>):
  • IJFBUP timeliness-warning — in-progress (Phase D2 跨 issue 冲突检查)
  • IJ7HX2 scan-batch — in-progress (Phase C 实施中, task 4/9)
```

排序：等用户的优先（按风险高→低 + 进入该状态时间长→短），Agent 在跑的次之。

如果两个 bucket 都为空（仅 done / rolled-back 历史）：
```
📋 No in-flight issues. <N> recently done. Use /solve <id> to start a new one.
```

### Step 5 — 不做的事

绝对不做：
- ❌ 自动调用 /solve、/rollback 或任何 mode 推进 issue
- ❌ 修改 STATUS.md
- ❌ 进入 worktree（resume 是只读视图）
- ❌ 给用户施加压力（"该处理 IJG6FV 了"之类）—— 只陈述事实

### Performance

应该 < 1s。STATUS.md 很大（多 in-flight issue）也要快出，不要阻塞会话启动。

---

## Anti-patterns

- ❌ Skip requirements-understanding (always run, even if issue looks "obvious")
- ❌ Invent understanding when user is unavailable — pause instead
- ❌ Mix multiple issues' state in one status.md
- ❌ Allow two issues into merge phase simultaneously (must use `.merge-lock`)
- ❌ Auto-resume `understanding-needs-info` without checking blockers
