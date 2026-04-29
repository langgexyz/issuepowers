# issuepowers — Design Spec v1

> Date: 2026-04-29
> Status: Initial draft. This spec is itself the first issue solved by issuepowers (bootstrapping).

---

## 一、定位

issuepowers 是基于 **Gitee issue** 的工作流框架，运行在 [superpowers](https://github.com/obra/superpowers) 之上。

| 维度 | superpowers | issuepowers |
|---|---|---|
| 视角 | 一条 feature 分支 | 一个 Gitee issue |
| 主体 | 单 Agent + 单 worktree | 多 Agent + 多 worktree + 串行合并 |
| 人 Gate | 多处人审（design / plan / finish） | **仅两处**：理解确认 + 交付验收 |
| 边界 | 到 PR / merge 为止 | 延伸到 **部署 + 验证 + 回滚** |
| 知识沉淀 | 无 | MEMORY.md 沉淀判断规则 |

issuepowers **不重写** superpowers 的 skill，只 require 后增强。

---

## 二、核心设计原则

1. **理解准就放权**：进入实施前 understanding.md 100% 确认；之后 Agent 全自动到部署 + 验证。
2. **回滚就绪**：rollback playbook 在 merge 前已生成；UAT 失败可一键回滚。
3. **并行物理隔离 + 串行合并**：worktree 物理并行开发，`.merge-lock` 保证合并串行 → 回滚永远干净。

---

## 三、工作流

```
人 ─ /solve IJG6FV ──→ 【Gate 1】confirm understanding.md
                            ↓
                Agent 全自动（superpowers 闭环）
                brainstorm → spec → plan → 实施 → merge → 部署 → deliverable-check
                            ↓
                通知人验收
                            ↓
人 ─ 【Gate 2】验收 ──→ ✅ pass         → done
                       ├─ ⚠️ fail-minor → in-progress（fix-forward, 重跑闭环）
                       └─ ❌ fail-major → /rollback → rolled-back
```

人介入只在两端，中间 Agent 不打扰。

---

## 四、状态机

```
主线：
  in-progress → pending-validation
                    ├─ pass         → done
                    ├─ fail-minor   → in-progress（fix-forward, 计数 +1）
                    └─ fail-major   → rolled-back

约束：
  - fix-forward 计数 ≥ 3 → 强制走 rollback 分支
  - deliverable-check 失败（实施期间）→ 不给 fix-forward，自动 rollback（理由见 §7）

特殊：
  split-into-children       拆分后的父 issue
  understanding-needs-info  /solve 暂停，等人补信息
```

外部可见状态 3+2 个，远比传统多 gate 的工作流清爽。

---

## 五、命令

### /solve <gitee-id>

**契约**：不返回，直到 understanding 100% 确认（或显式失败）。

**拆分情况**：拆分后 `/solve` 在同一次调用内对每个子 issue 递归跑 understanding，全部子确认才往下走。不让人后续再逐个触发。

```
/solve IJG6FV
    ↓
拉 Gitee issue 原文
    ↓
建 worktree + 前后端 feature 分支 + issues/IJG6FV/ 目录 + status.md
    ↓
启动 requirements-understanding 对话：
    ├─ Agent 复述 + 追问
    └─ 人 confirm / 修正
    ↓
分流：
    ├─ 拆分 → split-proposal.md → 人 confirm → 创建 N 个子 issue
    │           → 同一次 /solve 调用内对每个子递归跑 understanding
    │           → 全部子 confirmed → 父 state=split-into-children + 所有子 in-progress
    └─ 不拆 → understanding.md confirmed → state=in-progress
    ↓
返回
    ↓
Agent 自动进入 superpowers 闭环
```

### /rollback <gitee-id>

**契约**：读 rollback.md → 依赖检查 → 反序执行 → 写 rollback-report.md。

详见第十节。

---

## 六、Requirements Understanding

Agent 的姿态是**引导员**，不是裁判。主动追问 + 用自己的话复述，把模糊需求变成可测试的承诺。

输出 `understanding.md`，含：
- **目标**：Agent 用自己的话复述要解决什么
- **关键行为**：每条对应一个 deliverable-check 测试
- **边界**：明确不做什么
- **没把握的地方**：请人定
- **假设**：请人否决

人 confirm → state = `in-progress`。

### 类型决定追问脚本

| 类型 | Agent 主要追问 |
|---|---|
| Feature | 谁在用？happy path？边界 case？跟现有功能联动？权限？ |
| Bug | 何时开始？偶发还是稳定？影响范围？期望行为？复现路径？ |
| Refactor | 重构什么？哪些用户可见行为**不能变**？目标架构？ |
| Schema 变更 | 依赖此 schema 的功能行为如何？数据迁移路径？ |

### Bug 类专属：复现验证

Bug 类的 understanding 多一道硬条件 —— **Agent 必须在本地按 understanding.md 的复现路径跑通一次**：

- 跑通 → 根因有抓手，进入 `in-progress`
- 跑不通 → 标 `understanding-needs-info`，blockers 写「无法复现，需要补充步骤/账号/数据」，反弹给提单人

不让 Agent 在「猜代码改哪里」的状态下进入实施。那种修法本质是赌，回滚都救不回信任。

### 拆分能力

Agent 在 understanding 阶段识别可拆信号：

| 拆 | 不拆 |
|---|---|
| 多个独立用户故事 | 紧耦合，半个不能交付 |
| 不同风险等级 | 拆了协调成本 > 收益 |
| 不同代码区且互不依赖 | 业务上是一个原子动作 |
| 实施估时过大 | |

输出 `split-proposal.md` → 人 confirm → 创建子 issue（如 IJG6FV-a/b/c）→ 父 state = `split-into-children`。

每个子 issue 独立 understanding / 实施 / deliverable-check / 回滚。

---

## 七、Deliverable Check

部署后**唯一**动作：**验证 understanding.md 里的关键行为兑现了吗？**

不做的：
- ❌ 服务存活（部署流程负责）
- ❌ Schema 一致性（migration 流程负责）
- ❌ Config 加载（启动失败就起不来）
- ❌ 完整回归（CI 夜间负责）
- ❌ 性能/安全（独立流程）

只做的：
- ✅ understanding.md 每条「关键行为」机械翻译成 e2e 测试
- ✅ Bug 类：原复现路径再跑，验证不再触发 + 期望行为正常
- ✅ Refactor 类：「不能变的行为」回归验证

输出 `deliverable-report.md`，5 分钟内出结果。

失败 → 自动 /rollback（无需等人）。

### 为什么 deliverable-check 失败不给 fix-forward

deliverable-check 测的是 Agent 自己在 understanding.md 里写下的承诺。这一关失败 = **Agent 自我打脸**，信任已断。

直接 rollback 让 Agent 从头跑闭环（understanding 也可能要修），比让 Agent 在「知道自己刚搞砸」的状态下打补丁更稳。

UAT（人验证）失败则不同 —— 那是「需求 vs 实现」对不上，可能小事可能大事，由人决定 fix-forward 还是 rollback（见 §4 状态机）。

---

## 八、Rollback 设计

### 前置规约（merge 前必满足）

1. 1 issue = 1 squash commit（不是 merge commit / fast-forward）
2. Migration 必有 downgrade
3. 删字段/表分两步：deprecated → 下个 issue 真删
4. 不可逆数据变更 → 强制 pg_dump 备份；understanding.md 必须明确标注此变更，人 confirm 时即知情同意（不另设 gate）
5. 同文件同段冲突的 issue 串行做（cross-issue conflict check 拦截）
6. 高风险逻辑可走 feature flag（回滚=翻 flag，不动 git）

### rollback.md（merge 前 Agent 生成）

```yaml
issue: <ID>
merge_sha:
  backend: <sha>
  web: <sha>
ai_workflow_pointer_before: <sha>
migration_revision:
  before: <rev>
  after: <rev>
feature_flag: <name>             # 如有
dependent_commits_after_merge: []  # orchestration 持续维护
smoke_test_cmd: <reproducible cmd>
```

### /rollback 执行

```
[R1] 读 rollback.md
[R2] 依赖检查
     ├─ dependent_commits_after_merge 为空 → 干净 revert
     └─ 非空 → 停下问人：
              a) 连带回滚后续 issue
              b) 前向修复（hotfix）
[R3] 反序执行
     ├─ flask db downgrade <before>
     ├─ git revert <merge-sha> on backend, push
     ├─ git revert <merge-sha> on web, push
     └─ ai-workflow submodule 指针回退
[R4] 等 cron 重新部署
[R5] 跑 smoke 验证回滚成功
[R6] 写 rollback-report.md
[R7] status.md → rolled-back
```

---

## 九、并行隔离

| 资源 | 隔离手段 |
|---|---|
| 代码 | 每 issue 独立 git worktree + 前后端各自 feature 分支 |
| Agent 上下文 | 每 issue 独立会话 |
| 状态 | `issues/<ISSUE>/` 目录 |
| 合并到 develop | `.merge-lock` 文件锁，**串行** |
| ai-workflow submodule 指针 | 同上锁 |
| 部署 | 服务器 cron 串行 |

并行的真瓶颈：**同文件冲突** 和 **DB schema 冲突**。
- 同文件冲突：`cross-issue-conflict` 在 self-review 阶段检测（读所有 in-flight status.md + git diff）
- Schema 冲突：plan 阶段就识别（在 understanding.md 标 schema 改动）

---

## 十、MEMORY.md 沉淀什么

不写代码细节（spec / plan / issues/<ID>/ 都已经在记录），只写**判断规则** —— 让 Agent 不重复踩之前踩过的坑。

### 内容类型

- **判断条件清单**：何时选「破坏性修改」vs「V2 并跑」、何时必须本机复刻测试、何时画 prototype
- **自审清单**：spec / plan 阶段 Agent 自查时的项目（边界 / null / 权限 / 回滚 / 性能）
- **风险分级标准**：实施风险高/中/低的判定条件（spec/plan 阶段 Agent 按此自评）
- **常见错误模式**：被纠正过的设计/实施倾向（例如「不要凭空替提单人猜需求」）

### 每条结构

每条 memory 三部分：

- **规则**：一句话陈述
- **Why**：来自哪次踩坑或哪条原则
- **How to apply**：什么时候用这条规则

### 用法

- Agent 在 spec / plan 阶段自审前先读 MEMORY.md
- 风险分级时 Agent 按 MEMORY.md 标准自评，写进 plan
- 用户纠正 Agent 的判断后，把可复用的纠正写进 MEMORY.md
- MEMORY.md 跟着**项目**走（在使用 issuepowers 的项目仓库内），不在 issuepowers plugin 里

---

## 十一、Skill / Command / Hook / Template 清单

```yaml
provides:
  commands:
    - /solve <gitee-id>
    - /rollback <gitee-id>

  skills:
    - issuepowers:orchestration              # 主入口，串各阶段，含冲突检测
    - issuepowers:requirements-understanding # 仅被 /solve 调用，含拆分
    - issuepowers:deliverable-check          # 部署后 e2e 跑承诺
    - issuepowers:rollback                   # 生成 + 执行回滚

  hooks:
    - SessionStart                           # 续 STATUS.md 上下文

  templates:
    - understanding.md
    - split-proposal.md
    - uat-feedback.md
    - deliverable-report.md
    - rollback.md
```

---

## 十二、目录结构（在使用 issuepowers 的项目里）

```
<project>/
├─ docs/superpowers/issues/<ISSUE>/
│   ├─ status.md             ← 状态机锚点
│   ├─ understanding.md      ← 必有
│   ├─ split-proposal.md     ← 仅拆分时
│   ├─ uat-feedback.md       ← 仅 UAT 失败走 fix-forward 时
│   ├─ deliverable-report.md ← 部署后
│   ├─ rollback.md           ← merge 前生成
│   └─ rollback-report.md    ← 仅回滚时
├─ docs/superpowers/STATUS.md ← 多 issue 看板
├─ docs/superpowers/MEMORY.md ← 判断规则沉淀
├─ worktrees/<ISSUE>/
└─ .merge-lock                ← 物理锁
```

---

## 十三、与 superpowers 的边界

> **注**：阶段 0 和 0.5 发生在 `/solve` 命令内部，不对应外部可见状态；阶段 1 之后由 orchestration 自动驱动，对人不可见。

| 阶段 | superpowers 提供 | issuepowers 增强 |
|---|---|---|
| 0 选 issue | — | 从 Gitee 拉 + 建目录 |
| 0.5 需求理解 | — | **新写 requirements-understanding skill** |
| 1 Brainstorm | `brainstorming` | issue 关联 |
| 2 起草 spec | `brainstorming` 设计段 | — |
| 3 起草 plan | `writing-plans` | — |
| 4 建 worktree | `using-git-worktrees` | 命名规范 |
| 5 实施 | `executing-plans` + `subagent-driven-development` + `test-driven-development` | submodule 协调 |
| 6 自测 | `verification-before-completion` | migration up/down |
| 7 Self-review | `requesting-code-review` + `receiving-code-review` | **跨 issue 冲突 + 回滚演练 + rollback.md 生成** |
| 8 Merge | `finishing-a-development-branch` | **`.merge-lock` + squash + tag + 指针更新** |
| 9 部署 | — | cron 自动 |
| 10 deliverable-check | — | **新写 deliverable-check skill** |
| 11 验收 | — | 人 |
| 12 回滚（如需） | — | **新写 rollback skill + /rollback 命令** |

红字（粗体）= issuepowers 真正新写。其余复用 superpowers。

---

## 十四、落地路线图

### P0 — 单 issue 跑通完整闭环（~2.5 天）

- [x] 项目骨架 + plugin manifest + 4 skill 目录占位
- [ ] `/solve` 命令 + requirements-understanding skill + understanding.md / split-proposal.md 模板
- [ ] rollback skill + rollback.md 模板 + merge 前生成钩子

### P1 — 多 issue 并行 + 部署后验证（~3 天）

- [ ] `.merge-lock` + squash / tag / 指针更新协议
- [ ] deliverable-check skill + deliverable-report.md 模板
- [ ] Migration up/down 双向校验脚本
- [ ] cross-issue 冲突检测（折进 orchestration）
- [ ] `/rollback` 命令完整实现

### P2 — 自动化 + 体验（~1.5 天）

- [ ] STATUS.md 自动维护 + SessionStart hook
- [ ] MEMORY.md 起草（风险判断 + 自审清单）
- [ ] 拿一个低风险 issue 做试金石

---

## 十五、待决问题

1. **superpowers 安装方式**：marketplace plugin 还是项目内置？影响 skill `REQUIRE` 的写法。
2. **Gitee issue 状态回写**：走到关键阶段时是否自动在 Gitee 上 comment？
3. **`/rollback` 触发权限**：deliverable-check 失败时 Agent 自动触发，还是必须人触发？

---

## 十六、试金石

拿一个简单的低风险 issue（如 `IJG6FV scan-confirm`）做首个全自动闭环：

1. `/solve IJG6FV` → understanding 确认 → state = `in-progress`
2. Agent 自动跑完 spec / plan / 实施 / merge / 部署 / deliverable-check → state = `pending-validation`
3. 故意在验收阶段标失败 → `/rollback IJG6FV` → state = `rolled-back`
4. 验证：develop 分支干净、submodule 指针回退、migration 已 down、deliverable-check 不再产出 fail

跑通 = issuepowers 真正立起来。
