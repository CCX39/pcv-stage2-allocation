# 当前实现状态

本文是 `pcv-stage2-allocation` 的阶段0C.1接手说明，用来记录截至阶段0C的实现状态，方便新的对话或人工审查者快速继续工作。

## 项目当前目标

本仓库用于 Work1 Stage2 空间分块质量分配器。它要定义并后续实现：在给定视频组总数据预算的前提下，如何为每个参与决策的空间分块选择一个离散质量档位。

它不是距离标定项目，也不是完整的点云视频播放器。

## 当前阶段

当前已完成到：

```text
Phase 0C: handcheck fixture set completed
```

下一步建议进入：

```text
Phase 0D or Phase 1 preparation: validator / core solver preparation
```

目前尚未实现 validator、求解器、实验运行器或播放器集成。

## 已完成提交记录

```text
0e03de9  docs: add stage2 MVP phase 0A contract
907feee  docs: resolve stage2 MVP budget and lambda decisions
e0844ee  schemas: add stage2 MVP JSON schema drafts
a72e618  fix: make stage2 input description optional
3833fdf  tests: add handcheck stage2 fixture set
```

## 决策状态

```text
D0-1 lookup semantics       RESOLVED_USER_CONFIRMED
D0-2 infeasible budget      RESOLVED_USER_CONFIRMED
D0-3 lambda search rules    RESOLVED_USER_CONFIRMED
D0-4 provenance vocabulary  DRAFT
```

- D0-1：lookup 是候选质量上界，`allowed_levels = {1, ..., lookup_level}`。
- D0-2：如果 `Budget_total < B_min_feasible`，未来求解器应返回 `INFEASIBLE_BUDGET`。
- D0-3：未来求解器应使用自适应 `lambda` 上界、确定性平局处理，并记录当前最佳可行解。
- D0-4：数据来源词汇仍是草案，不能写成最终冻结。

## 当前已有资产

- `schemas/stage2_input.schema.json`
- `schemas/distance_lookup.schema.json`
- `schemas/stage2_result.schema.json`
- `tests/fixtures/handcheck_3x3/`
- `docs/stage2_mvp_contract.zh-CN.md`
- `docs/schema_contract.zh-CN.md`
- `docs/decision_log.zh-CN.md`

`handcheck_3x3` 包含：

- success 输入；
- infeasible 输入；
- lookup fixture；
- expected success result；
- expected infeasible result；
- 中英文手算说明。

## 手算 Fixture 核心结果

success：

```text
selected levels = T1_near_important:L3, T2_mid_visible:L1, T3_far_capped:L1
total_bytes = 200
total_net_utility = 39.5
budget_total_bytes = 210
```

infeasible：

```text
budget_total_bytes = 100
B_min_feasible = 120
budget_gap = 20
status = INFEASIBLE_BUDGET
```

## 当前尚未实现

- Python 或 TypeScript 求解器；
- validator；
- JSON Schema 自动校验脚本；
- `lambda` search；
- local upgrade；
- baselines；
- Longdress 输入生成；
- 批量实验；
- 图表；
- 播放器集成。

## 下一步建议

下一步不建议直接写完整 solver。更稳妥的选择是先做其中一项：

```text
Phase 0D: minimal schema/fixture validation script
```

或：

```text
Phase 1A: Python project skeleton + dataclass/model definitions
```

这里只记录建议，不自动进入下一阶段。

## 如何接手

新的 GPT 对话或人工接手时，建议按这个顺序阅读：

1. 先读 `docs/IMPLEMENTATION_STATE_CURRENT.zh-CN.md`。
2. 再读 `docs/stage2_mvp_contract.zh-CN.md`。
3. 再读 `docs/schema_contract.zh-CN.md`。
4. 再看 `tests/fixtures/handcheck_3x3/hand_calculation.zh-CN.md`。
5. 当前不要修改 D0-1、D0-2、D0-3 的冻结语义。
6. 不要把 `handcheck_3x3` fixture 当成真实 Longdress 实验。
