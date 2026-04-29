---
name: deliverable-check
description: |
  Post-deploy verification that the delivered code matches what understanding.md promised.
  Reads "关键行为" from understanding.md, runs corresponding pre-written acceptance tests
  in the deployed environment (dev / staging), writes deliverable-report.md.
  On any failure, signals orchestration to auto-rollback. Does NOT test service health,
  schema integrity, or config — those are deploy-pipeline concerns, not deliverable concerns.
---

# Deliverable Check Skill

## Goal

Answer one question, post-deploy:

> **Did Agent deliver what understanding.md promised?**

Not "is the service alive". Not "is the schema right". Not "did we break unrelated functionality". Only — **does the promised behavior actually work in the deployed environment?**

## Pre-conditions

This skill **requires** that implementation phase has already written acceptance tests for each `## 关键行为` line in understanding.md, organized as `tests/acceptance/<gitee_id>/`.

If those tests don't exist when this skill runs, that's a **process violation** — escalate, don't try to generate them on the fly.

(Test generation on the fly = un-tested code shipped to validation; defeats the entire model.)

## When invoked

Called by orchestration's `deploy-check` mode, **after**:

1. Submodule changes merged to `develop`
2. Deploy cron picked up the merge and redeployed
3. Brief stabilization wait (~30-60s post-redeploy)

## Inputs

```yaml
gitee_id: <issue id>
understanding_path: docs/superpowers/issues/<id>/understanding.md
report_path: docs/superpowers/issues/<id>/deliverable-report.md
deploy_env: dev | staging   # which env to verify against
```

## Procedure

### Step 1 — Parse understanding.md

Extract from understanding.md:

- `## 关键行为` numbered list — primary verification source
- `## Bug 类附加` if present — 复现路径 + 期望行为
- `## Refactor 类附加` if present — 不能变的行为 list

If any required section is missing or empty, **fatal**: understanding wasn't really confirmed. Escalate, do not proceed.

### Step 2 — Locate acceptance tests

For each关键行为 (and bug repro / refactor invariant), find the corresponding pre-written test in `tests/acceptance/<gitee_id>/`.

If a test is missing:
- Stop immediately
- Escalate to user with which behavior is uncovered
- Mark deliverable-report state as `incomplete-coverage`
- Do NOT try to generate, do NOT mark pass

### Step 3 — Run tests against deployed environment

Use the project's test command (consult project's CLAUDE.md or `package.json` / `Makefile`):

```bash
<project test command> --grep <gitee_id> --env=<deploy_env>
```

Capture per-test:
- Result: PASS / FAIL / SKIPPED / ERROR
- Duration
- Failure message (if FAIL — minimal, not full log)

**Hard runtime budget: 5 minutes total.** If exceeded, the test suite is too heavy for deliverable-check (drift into regression). Stop, escalate.

### Step 4 — Write deliverable-report.md

Use `templates/deliverable-report.md` shape. Fill:

- Deploy timestamp + commits
- Each关键行为 row with result + duration
- Bug 类 sanity (if applicable): 复现路径 result + 期望行为 result
- Refactor 类 (if applicable): each invariant result
- Summary line (N/M passed)
- For failures: minimal failure description (not log dumps)

### Step 5 — Signal orchestration

| Outcome | Signal | Orchestration action |
|---|---|---|
| All关键行为 pass | `pass` | state = `pending-validation`, notify user |
| Any test fail | `fail` | auto-trigger `/rollback` |
| Test missing for any行为 | `incomplete-coverage` | escalate to user, freeze state |
| Test infra broken | `error` | escalate, retain current state |
| Runtime > 5min | `over-budget` | escalate, the test set is too heavy |

## Failure handling philosophy

- **Any fail = fail** (no partial pass)
- **Auto-rollback on fail** is the right default — Agent over-promised, shouldn't get a chance to fudge it manually
- **Process violations escalate**, don't get auto-fixed (covering them up rots the model)

## Anti-patterns

- ❌ Generate tests on the fly (must be written during implementation, period)
- ❌ Test things outside understanding.md (drift into general regression)
- ❌ Soft-pass partial failure ("3/4 close enough")
- ❌ Skip re-running after redeploy ("the local tests passed")
- ❌ Test service health / config / schema (those are deploy pipeline concerns)
- ❌ Allow runtime > 5 min (then it's not a smoke check anymore)
- ❌ Dump raw logs into deliverable-report.md (minimal failure descriptions)

## Why "no health checks"

Repeating because this distinction is easily lost:

- **Service health** = "did deploy succeed" — deploy script's responsibility (`curl /health`)
- **Schema integrity** = "is the DB schema what code expects" — migration script's responsibility (`alembic check`)
- **Config loading** = "does the app start with right env" — startup logic's responsibility (app crashes → never gets here)
- **Deliverable check** = "does promised behavior work" — **this skill's responsibility**

Mixing them dilutes deliverable-check into a generic smoke suite, making failures harder to interpret. Keep the layers clean.

## Edge cases

### Empty关键行为 list

If understanding.md has no关键行为 (e.g., pure config change that shouldn't have been a issuepowers issue):
- Block. Pure config issues should bypass issuepowers — escalate to user.

### Bug 类 with no expected positive behavior

Some bugs are "stop doing X" (e.g., stop sending duplicate emails). Test must verify X stopped, not just "no error" — write the test to assert absence.

### Refactor 类 with non-functional invariants

E.g., "performance must not regress > 10%". This is hard to test deterministically. Either:
- Convert to a concrete behavioral assertion (e.g., "p99 latency < 200ms on standard fixture")
- Or drop from acceptance tests, accept it's only checked at UAT

### Flaky tests

If a test in acceptance suite is known flaky:
- Fix it (preferred)
- Or remove it from acceptance suite (then the关键行为 it covered is uncovered → process violation)
- Don't add retries — flaky acceptance tests are a smell that the tests aren't really testing the behavior

## Implementation note (for orchestration callers)

When implementing orchestration's `implement` mode (P1+), make sure the plan stage explicitly schedules a task: "For each `## 关键行为` in understanding.md, write a corresponding acceptance test in `tests/acceptance/<gitee_id>/`". Without this, deliverable-check will block at Step 2 every time.
