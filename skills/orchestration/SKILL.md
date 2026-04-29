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
| `implement` | After `solve` returns in-progress | P1 ⏳ — drives superpowers 闭环 |
| `merge` | After self-review pass | P1 ⏳ — `.merge-lock` + squash + tag |
| `deploy-check` | After merge + cron deploy | P1 ⏳ — calls `issuepowers:deliverable-check` |
| `fix-forward` | User reports minor UAT failure | P1 ⏳ — write `uat-feedback.md`, increment count, restart from plan |
| `rollback` | `/rollback <id>` command | P1 ⏳ — calls `issuepowers:rollback` |
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

## Modes: implement / merge / deploy-check / rollback / resume

⏳ **Not implemented in P0.** See design.md §14 for roadmap.

When P1 ships, this skill will:
- Drive superpowers 闭环 (`brainstorming` → `writing-plans` → `executing-plans` / `subagent-driven-development` → `requesting-code-review` / `receiving-code-review`)
- Insert issuepowers-specific steps: cross-issue conflict check, generate rollback.md, acquire `.merge-lock`, squash + tag, update submodule pointers
- After deploy: call `issuepowers:deliverable-check`
- Maintain STATUS.md throughout

---

## Anti-patterns

- ❌ Skip requirements-understanding (always run, even if issue looks "obvious")
- ❌ Invent understanding when user is unavailable — pause instead
- ❌ Mix multiple issues' state in one status.md
- ❌ Allow two issues into merge phase simultaneously (must use `.merge-lock`)
- ❌ Auto-resume `understanding-needs-info` without checking blockers
