# Deliverable Report: <ISSUE-ID>

**Deploy**: <timestamp>
**Commits**:
- backend: <sha>
- web: <sha>

## understanding.md 兑现情况

每条「关键行为」对应一条 e2e 测试，结果如下：

| # | 关键行为 | 结果 | 耗时 |
|---|---|---|---|
| 1 | ... | ✅ PASS / ❌ FAIL | <s> |
| 2 | ... | ... | ... |
| 3 | ... | ... | ... |

## Bug 类附加（仅 Bug 类）

- 原复现路径：✅ 不再触发 / ❌ 仍可复现
- 期望行为：✅ 出现 / ❌ 未出现

## 总结

- N/M 关键行为通过
- 全通过 → **等人验收**（state=pending-validation）
- 任一失败 → **已自动触发 /rollback**

## 详情

（失败时贴最小可读的失败证据 — 错误消息、截图、日志关键行。
不倒一堆原始日志。）
