# UAT Feedback: <ISSUE-ID>

> 由用户在 UAT 失败时提交（或 Agent 根据用户描述代填后用户确认）。
> Agent 把这视为 understanding.md 的**增量修订**（追加，不是替换）。

## 失败类型

- [ ] **minor** —— 小问题，触发 fix-forward（重跑闭环）
- [ ] **major** —— 严重问题，要求 /rollback

## 问题描述

（具体哪里跟期望不符。直接陈述事实，不要解释 / 推测原因。）

## 期望行为

（应该是什么样的。能贴 mockup / 截图最好。）

## 复现步骤（仅 minor 类需要）

1. ...
2. ...
3. ...

## 附加信息

- 截图 / 录屏：
- 错误日志：
- 受影响的账号 / 数据：
- 环境（dev / staging / prod）：

---

## 处理路径

| 类型 | 路径 |
|---|---|
| **minor** | Agent 把本文件视为 understanding 增量 → state 回到 `in-progress` → fix-forward-count += 1 → 重跑 plan → 实施 → merge → 部署 → deliverable-check → 再次 UAT |
| **major** | 用户运行 `/rollback <issue-id>` → state = `rolled-back` |

**强制约束**：fix-forward-count ≥ 3 时强制走 rollback 分支。三次还修不好说明 understanding 本身有偏差，应该回滚重新走 /solve。
