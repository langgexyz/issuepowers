# issuepowers

Issue-driven workflow framework for Claude Code, built on top of [superpowers](https://github.com/obra/superpowers).

## What it does

Two commands, two human gates, full Agent autonomy in between.

```
人 ─ /solve <gitee-id> ─→ [Gate 1] confirm understanding
                              ↓
                    Agent 全自动（superpowers 实施）
                              ↓
人 ─ [Gate 2] 验收 ─→ done  或  /rollback <gitee-id>
```

- `/solve <gitee-id>` — drive an issue from understanding to delivery, autonomously
- `/rollback <gitee-id>` — roll back a delivered issue when validation fails

## Why

superpowers 解决「Agent 怎么把一件事做好」。
issuepowers 解决「N 个 Agent 怎么把 N 个 issue 同时做好且能回滚」。

## Status

v0.1 — early design. See [docs/design.md](docs/design.md) for the full spec.

## Dependencies

- [superpowers](https://github.com/obra/superpowers) — required, provides the underlying skills (brainstorming, writing-plans, executing-plans, TDD, code-review, git-worktrees, finishing-a-development-branch, etc.)

## License

TBD
