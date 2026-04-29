---
description: 会话启动时报告 in-flight issuepowers issue 现状
---

# SessionStart Hook

Claude Code 会话启动时自动触发。

## Action

Invoke the `issuepowers:orchestration` skill in **resume mode**.

## Contract

- 只读视图：读 `docs/superpowers/STATUS.md`，summarize in-flight issues
- 不自动推进任何 issue（不调 /solve、/rollback、任何 mode）
- 不修改 STATUS.md
- < 1s 出结果，不阻塞会话启动

## 输出

按 orchestration resume mode 的格式：等用户处理的 issues 优先展示，Agent 在跑的次之，没有就提示「No in-flight issues, use /solve to start」。

## When this hook NOT triggered

- 工作目录不是 issuepowers-enabled 项目（无 `docs/superpowers/STATUS.md` 也无 `docs/superpowers/issues/`）→ 静默不动
- STATUS.md 损坏 / 格式不识别 → 输出错误提示，不阻塞会话

## Anti-patterns

- ❌ 创建空 STATUS.md（用户没提单就别提示）
- ❌ 给用户施加压力（"你该处理 X 了"）
- ❌ 写日志 / 修改任何文件
