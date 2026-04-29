# Rollback Playbook: <ISSUE-ID>

# 由 Agent 在 self-review 通过后、merge 前生成。
# /rollback 命令读取此文件执行。
# 字段约束严格，缺一不可（除标注「如有」的）。

issue: <ISSUE-ID>

merge_strategy: merge-no-ff   # 决定 rollback 用 git revert -m 1 (mainline parent)
                              # design.md §2 原则 6: 一律 --no-ff, 不允许 squash

merge_sha:
  backend: <merge-commit-sha>
  web: <merge-commit-sha>

ai_workflow_pointer_before: <sha>

migration_revision:
  before: <alembic-revision>
  after: <alembic-revision>

feature_flag: <flag-name>  # 如有，则回滚 = 翻 flag，不走 git revert

dependent_commits_after_merge: []
# orchestration 持续维护：每次有新 issue merge 且改动了与本 issue 相同的文件，
# 就 append 新 issue 的 merge_sha 到这里。
# /rollback 时如果非空 → 停下问人：连带回滚 or 前向修复

smoke_test_cmd: |
  # 一行命令重新跑 deliverable-check，回滚后用来验证回滚成功
  # 例：cd worktrees/<ISSUE> && pnpm test:e2e --grep <slug>

notes: |
  # Agent 写下任何回滚时需要注意的事
  # 例如：「此 issue 改了 sample 表，回滚 migration 会丢 N 条新数据，已 pg_dump 到 backups/<date>.sql」
