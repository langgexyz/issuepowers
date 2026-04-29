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

## Install (development mode)

issuepowers 还未发布到 marketplace。本地开发模式安装：

```bash
# 启动 Claude Code 时加 --plugin-dir 指向本仓库
claude --plugin-dir /Users/zero/Documents/projects/tcuni/issuepowers/

# 多 plugin 并存（含 superpowers 依赖）:
claude --plugin-dir /path/to/superpowers \
       --plugin-dir /Users/zero/Documents/projects/tcuni/issuepowers/

# 在会话内验证:
/help                              # 应该能看到 /solve 和 /rollback
/issuepowers:orchestration         # 主 skill 触发

# 编辑 skill 文件后热加载:
/reload-plugins
```

## Dependencies

- [superpowers](https://github.com/obra/superpowers) — required, provides the underlying skills (brainstorming, writing-plans, executing-plans, TDD, code-review, git-worktrees, finishing-a-development-branch, etc.)

## License

TBD
