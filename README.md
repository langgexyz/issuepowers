# issuepowers

> 基于 Gitee issue 的**开发工程化** issue 解决工作流框架，运行在 [superpowers](https://github.com/obra/superpowers) 之上。
> **两个用户 gate（理解 + 验证），中间 Agent 全自动**跑完实施 → 部署 → 交付物验证。

```
用户 ─ /solve <gitee-id> ──→ 【Gate 1】confirm 理解
                                   ↓
                  Agent 全自动 (spec → plan → 实施 → merge → 部署 → 验证)
                                   ↓
用户 ─ 【Gate 2】验证 ──→ ✅ done / ⚠️ fix-forward / ❌ rollback
```

## 解决什么问题

如果你的开发流程是「Gitee 提单 → 工程师手工推进每一步 → 部署 → 验证」，且 N 个 issue 同时在飞容易乱、出错不能可靠回滚，issuepowers 把中间环节全部交给 Agent 自动跑，**用户只做两件事**：

1. **理解 confirm** —— Agent 把需求复述给你，你点头或纠错
2. **验收** —— Agent 跑完 acceptance test 通过后通知你，你确认 / fix-forward / rollback

## 安装

### 推荐：通过 marketplace 安装（标准做法）

在 Claude Code 会话内：

```
/plugin marketplace add langgexyz/issuepowers
/plugin install issuepowers@issuepowers-marketplace
```

这跟装 superpowers 的方式同源，零额外配置，团队成员各自跑一遍同样命令即可。

后续升级：

```
/plugin marketplace update issuepowers-marketplace
```

### 替代：源码安装

```bash
git clone https://github.com/langgexyz/issuepowers.git
claude --plugin-dir ./issuepowers
```

### 依赖

issuepowers 依赖 [superpowers](https://github.com/obra/superpowers)，需先装：

```
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```

## 快速开始

```bash
# 1. 在你的开发项目目录里启动 Claude Code
cd /path/to/your-dev-project
claude

# 2. Claude Code 会话内验证
/help                              # 应看到 /solve 和 /rollback

# 3. 解决一个 issue
/solve IJG6FV scan-confirm
```

## 命令

| 命令 | 说明 |
|---|---|
| `/solve <gitee-id> [slug]` | 解决一个 Gitee issue（含理解、实施、merge、部署、交付物验证） |
| `/rollback <gitee-id>` | 回滚一个已交付的 issue（git revert + migration downgrade + 部署） |

## skill 清单

| skill | 职责 |
|---|---|
| `issuepowers:orchestration` | 主入口，7 modes 串生命周期（solve / implement / merge / deploy-check / fix-forward / rollback / resume） |
| `issuepowers:requirements-understanding` | 引导式需求理解对话 + 拆分识别 + Bug 类必须本地复现 |
| `issuepowers:deliverable-check` | 部署后承诺验证（only 测 understanding 关键行为兑现，5 分钟硬预算） |
| `issuepowers:rollback` | generate（merge 前生成 playbook）+ execute（`/rollback` 执行）双模式 |

## 核心概念

| 概念 | 说明 |
|---|---|
| **understanding.md** | Agent 用自己的话复述 issue，列「关键行为」「边界」「不确定项」。用户 confirm 后才进实施。 |
| **split-proposal.md** | issue 太大或多件事时，Agent 提议拆成 N 个独立子 issue 各自走流程，父子关系记在 status.md |
| **deliverable-check** | 部署后机械地把 understanding 的「关键行为」翻译成 e2e test 跑一遍，全过 → 等用户 UAT；任意失败 → 自动 rollback |
| **rollback playbook** | merge **前**就生成 `rollback.md`（含真实 merge SHA、migration revision、依赖追踪），UAT 失败时一键执行 |
| **fix-forward** | UAT 小问题不需回滚，写 `user-validation-feedback.md` → 重跑实施流程 → 再验证（≥3 次自动转 rollback） |
| **`.merge-lock`** | 跨 issue 串行合并，保证 develop 永远线性可干净 revert |

## 工作流（7 modes）

```
state machine:
  understanding-in-progress  ← /solve 进行中（瞬态）
        ↓
  in-progress  ← Agent 自动实施 + merge + 部署
        ↓
  pending-validation  ← 等用户验证
        ├─ ✅ pass → done
        ├─ ⚠️ fail-minor → in-progress (fix-forward)
        └─ ❌ fail-major → rolled-back (via /rollback)

特殊状态:
  understanding-needs-info  ← /solve 暂停, 等用户补信息
  split-into-children       ← 拆分后的父 issue
```

## 5 条核心设计原则

1. **理解准就放权** —— 进入实施前 understanding 100% 确认，之后 Agent 全自动
2. **回滚就绪** —— `merge --no-ff` + `git revert -m 1`，rollback playbook 在 merge 后立即生成
3. **并行物理隔离 + 串行合并** —— 每 issue 独立 worktree + feature 分支；`.merge-lock` 保证合并串行
4. **围绕用户的语言** —— 用户面向产物用普通话，避免行业黑话（UAT / smoke test 等）
5. **角色术语固定** —— 用户 / 开发者 / Agent 含义固定，禁用「人」

加上两条工程实操规约：

6. **Commit 强约束** —— 每个 commit 必须 `<type>(<issue-id>): <subject>`，merge 一律 `--no-ff`
7. **Git 安全规约** —— automation 永不 `git reset --hard` / `push --force` / `clean -fd`，撤回用 `git revert`

## 范围

| ✅ 在范围内（开发工程化） | ❌ 在范围外 |
|---|---|
| 代码改动（前端/后端/共享库/脚本） | 纯文档撰写 |
| 构建 / 编译 / 打包 | 沟通协调 |
| 测试（单元/集成/e2e/acceptance） | 业务调研 / 客户走访 |
| DB schema 变更 + migration | 设计资源（mockup / brand） |
| CI / CD / 部署 | 数据分析 / 报表 |
| 运维配置 / IaC | 业务流程改造 |
| 代码 review / 合规 | |

边界：「**最终产出是 git 可追踪的工程产物**」。跨界 issue（既要写代码也要发邮件）issuepowers 只接代码部分，邮件部分用户自己跟 lark-mail 之类的 skill 协作。

## 状态

**v0.1 — 早期开发**

当前实现以 [process-manage-ai-workflow](https://gitee.com/) 项目栈作参考实例硬编码（`flask db downgrade` / `pnpm test:e2e` / cron deploy 等）。**只服务该项目**。

**v1 规划**：引入 `.issuepowers/config.yaml`（项目仓库自带，跟代码同版本），任意符合 schema 的开发工程化项目都可接入。详见 [docs/design.md §17](docs/design.md)。

## 设计文档

完整设计见 [`docs/design.md`](docs/design.md)（17 节）：

- §1 定位与范围
- §2 5 条核心设计原则
- §3 工作流图
- §4 状态机
- §5 命令契约（`/solve`、`/rollback`）
- §6 Requirements Understanding（含拆分能力）
- §7 Deliverable Check
- §8 Rollback 设计（含 playbook 模板与 R1-R7 流程）
- §9 并行隔离
- §10 MEMORY.md 沉淀什么
- §11 Skill / Command / Hook / Template 清单
- §12 目录结构（在使用 issuepowers 的项目里）
- §13 与 superpowers 的边界
- §14 落地路线图（P0 ~ P3）
- §15 待决问题
- §16 试金石
- §17 项目 config schema 与 v0/v1 升级路径

## 项目结构

```
issuepowers/
├─ .claude-plugin/plugin.json       ← Claude Code plugin manifest
├─ docs/design.md                   ← 完整设计 spec
├─ commands/{solve, rollback}.md    ← 2 个 slash 命令
├─ skills/<name>/SKILL.md           ← 4 个 skill
├─ hooks/SessionStart.md            ← 1 个 hook
├─ templates/                       ← 5 个产物模板
│   ├─ understanding.md
│   ├─ split-proposal.md
│   ├─ user-validation-feedback.md
│   ├─ deliverable-report.md
│   └─ rollback.md
└─ scripts/check-consistency.py     ← 维护用一致性检查
```

## 开发与维护

```bash
# 框架内部一致性检查（每次改 design / skill / 命令时跑）
python3 scripts/check-consistency.py

# 编辑 skill 后热加载（mid-session）
# 在 Claude Code 会话内:
/reload-plugins
```

## 贡献

issuepowers v0.1 仍在快速迭代，API 可能 breaking change。

如果想试用、报 issue、讨论设计，欢迎 [开 issue](https://github.com/langgexyz/issuepowers/issues) 或 PR。

## License

TBD（暂未确定，倾向 MIT 或 Apache 2.0）
