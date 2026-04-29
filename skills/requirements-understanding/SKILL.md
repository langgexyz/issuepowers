---
name: requirements-understanding
description: |
  Drive Socratic dialogue with the user to clarify what a Gitee issue actually requires.
  Output a confirmed understanding.md that becomes the contract for subsequent implementation.
  Detects when an issue should be split into independent sub-issues. Bug-class issues require
  local reproduction before being marked confirmed. Invoked by issuepowers:orchestration as
  part of /solve flow — not directly by users.
---

# Requirements Understanding Skill

## Goal

Turn vague issues into Agent-executable contracts. Output `understanding.md` where every "关键行为" can be mechanically translated into a `deliverable-check` test.

## Stance

**引导员，不是裁判。** Agent leads the dialog by restating + asking; user advances by nodding or correcting. Never make the user fill out a checklist.

## Inputs (passed by orchestration)

- Issue body + comments + labels (from Gitee)
- Path to write `understanding.md`
- Path to write `split-proposal.md` (if split)
- Path to `status.md` for state updates

## Returns to orchestration

One of:

| Return | Meaning |
|---|---|
| `confirmed` | Single issue, understanding.md confirmed by user |
| `split-confirmed` | Split happened; all children also have confirmed understanding |
| `needs-info` | User couldn't provide enough; blockers populated in status.md |

---

## Workflow

### Step 1 — Read issue thoroughly

Read **everything** Gitee gave: title, body, all comments, labels. Comments often contain the real context (questions answered, decisions made) that body lacks.

Don't skip. Don't summarize-then-discard.

### Step 2 — Classify type

Determine type from issue content:

| Type | Signals |
|---|---|
| **Feature** | New functionality, "添加 / 新增 / 实现 / 支持" |
| **Bug** | "错误 / 不工作 / 异常 / 修复 / fix", report of unexpected behavior |
| **Refactor** | "重构 / 优化 / 改造 / 清理", explicit "不改变行为" claim |
| **Schema 变更** | "加字段 / 删字段 / 改表 / migration" |
| **Ops / 配置** | "部署 / 配置 / 环境 / 凭证" |

Ambiguous? Ask the user directly — one short question.

Write type to status.md.

### Step 3 — Build追问脚本 (only ask what's missing)

Don't dump all questions. Only ask what the issue body + comments don't cover.

#### Feature 类追问候选

- 谁在用这个功能？什么场景下？
- 现在他们没这功能时怎么干？
- happy path 是什么？(Agent 先猜一个，让用户纠正)
- 我能想到的边界 case：[列出] —— 怎么处理？
- 跟现有 X / Y 功能怎么联动？
- 权限边界？谁能用、谁不能？
- UI/交互需求：有 mockup / 现有页面参考吗？

#### Bug 类追问候选

- 何时开始？最近改了什么？
- 偶发还是稳定？
- 哪些账号 / 角色 / 数据受影响？
- 期望行为是？
- **复现路径详细**：精确到点击哪个按钮、传什么参数、看到什么错（必需）

#### Refactor 类追问候选

- 重构什么？目标架构？
- **哪些用户可见行为绝对不能变？**（这是 deliverable-check 的锚点）
- 性能 / 体积 / 复杂度有具体目标吗？

#### Schema 变更类追问候选

- 依赖此 schema 的功能是？
- 数据迁移路径？
- 可逆吗？(决定回滚策略)
- 是否需要兼容期？

#### Ops / 配置类追问候选

通常不需要走完整 issuepowers 流程。建议跟用户确认改用 issuepowers，或人手处理。

### Step 4 — Restate (Agent 用自己的话复述)

**Critical**: Don't copy issue text verbatim. Restate in your own words. Use the `templates/understanding.md` shape:

```markdown
# Understanding: <issue-id>

## 目标
（用 Agent 自己的话复述，含推测的 why）

## 类型
[x] Feature / Bug / Refactor / Schema 变更

## 关键行为
（每条必须可测，对应一个 deliverable-check）
1. ...
2. ...

## 边界（不做什么）
- ...

## 我没把握的地方（请你定）
- [ ] ...

## 我假设但你可能要否决的
- ...

## Bug 类附加（仅 Bug 类）
- 复现路径：1. ... 2. ...
- 期望行为：
- Agent 已本地复现：[ ] 是 / [ ] 否

## Refactor 类附加（仅 Refactor 类）
- 不能变的行为：- ... - ...
```

### Step 5 — Iterate with user

Show understanding.md draft. Ask user:
> "请确认 / 修正 / 补充。我没把握的地方需要你定。"

User responds. Revise understanding.md. Repeat.

**Cap at 3-4 rounds.** If still unclear:
- Mark `state = understanding-needs-info`
- Write specific blockers to status.md
- Return `needs-info`

Don't keep grinding the same question.

### Step 6 (Bug 类专属) — Local reproduction

Bug 类必须本地按 understanding.md 的复现路径跑通：

```
Agent 在 worktree 内启动 dev 环境（或读 CLAUDE.md 找启动命令）
按 understanding.md 复现路径执行
观察是否触发预期错误
```

- ✅ Bug 复现成功 → 在 understanding.md 标 `Agent 已本地复现：[x] 是`，进入 Step 7
- ❌ Bug 复现失败 → 标 `[x] 否`，blockers = ["无法本地复现，需要补充：<具体缺啥，账号？数据？步骤？>"]，return `needs-info`

**Don't bypass.** A bug fix without reproduction is gambling.

### Step 7 — Detect split signals

Read the confirmed understanding.md. Apply split heuristics:

| 该拆 | 不该拆 |
|---|---|
| 关键行为列表 ≥ 3 条且互不依赖 | 紧耦合，半个不能交付 |
| 不同代码区（纯前端 + 纯后端） | 业务上是原子动作 |
| 不同风险等级混在一起 | 拆了协调成本 > 独立收益 |
| 估时 > 1 周 | |

If split signals dominate:
- Write `split-proposal.md` (use `templates/split-proposal.md`)
- Show to user: "我看这其实是 N 件独立的事，建议拆。或者你说不拆，整体当一个 deliverable。"
- User confirms / adjusts / declines

If user accepts split:
- Create child issue directories: `docs/superpowers/issues/<parent>-a/`, `<parent>-b/`, ...
- For each child: recursively run **this skill from Step 1**, with the child's scope as input
- All children must reach `confirmed` (or one fails → return `needs-info` with which child blocked)
- Parent's `understanding.md` is replaced by the split-proposal.md (the parent doesn't deliver anything itself)
- Set parent.children = [<child IDs>], each child.parent = <parent ID> in status.md
- Return `split-confirmed`

If user declines split:
- Continue to Step 8 with single issue

### Step 8 — Final confirmation + write artifacts

Single issue path:
- Write final `understanding.md` (already iterating)
- Show user one last time: "这是最终版理解。确认吗？"
- User: "确认" → return `confirmed`
- User: "再改 X" → back to Step 5

Split path:
- All children confirmed in Step 7
- Return `split-confirmed`

---

## Anti-patterns

- ❌ Copy-paste issue body into understanding.md (must restate in own words)
- ❌ Make user fill checklist instead of Agent restating
- ❌ Skip type classification ("just go with it")
- ❌ Skip Bug 复现 because "looks straightforward"
- ❌ Loop on the same question >2 times — escalate to `needs-info` instead
- ❌ Auto-confirm understanding without user explicit OK
- ❌ Create children scaffolding but defer their understanding (must recurse)
- ❌ Pretend to understand to be helpful (silent failure mode — fight it)

## Success criteria

`understanding.md` is a contract such that:

1. Each "关键行为" line can be mechanically translated to one e2e test (the deliverable-check)
2. A different developer reading it can implement without asking the user further
3. The "边界" section unambiguously rules out scope creep
4. For Bug class: reproduction is verified, not assumed
5. For Refactor class: "不能变的行为" lists testable invariants

If any of these fail, the contract isn't ready. Loop or escalate.
