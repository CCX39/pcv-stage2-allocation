# 当前实现状态

本文是 `pcv-stage2-allocation` 的阶段1B接手说明，用来记录截至阶段1B的实现状态，方便新的对话或人工审查者快速继续工作。

## 项目当前目标

本仓库用于 Work1 Stage2 空间分块质量分配器。它要定义并后续实现：在给定视频组总数据预算的前提下，如何为每个参与决策的空间分块选择一个离散质量档位。

它不是距离标定项目，也不是完整的点云视频播放器。

## 当前阶段

当前已完成到：

```text
Phase 1B: fixed-lambda selection kernel completed
```

下一步建议进入：

```text
Phase 1C preparation: lambda search interface and solver assembly boundary planning
```

目前尚未实现完整 Stage2 求解器、通用 validator、实验运行器或播放器集成。

## 已完成提交记录

```text
0e03de9  docs: add stage2 MVP phase 0A contract
907feee  docs: resolve stage2 MVP budget and lambda decisions
e0844ee  schemas: add stage2 MVP JSON schema drafts
a72e618  fix: make stage2 input description optional
3833fdf  tests: add handcheck stage2 fixture set
7206f17  docs: add current implementation state
7ec5f22  test: add handcheck fixture validation script
bf1ef90  feat: add stage2 python model layer
daf90e0  fix: clarify target-aware lookup boundary
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
- `scripts/validate_handcheck_fixtures.py`
- `src/pcv_stage2/`
- `tests/test_models_handcheck.py`
- `requirements.txt`
- `docs/fixed_lambda_selection_contract.md`
- `docs/fixed_lambda_selection_contract.zh-CN.md`
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

## 校验命令

在仓库根目录运行：

```powershell
python -m pip install -r requirements.txt
python -m pytest
python scripts/validate_handcheck_fixtures.py
```

fixture 防线脚本继续保留独立校验路径，用于检查 Schema 草案和 handcheck JSON 文件；pytest 单独检查模型层、lookup cap 预处理、`B_min_feasible`、阶段1B固定 `lambda` 内核和 handcheck 预期值。两者都不是完整求解器。

## Target-aware Lookup 边界

`Stage2Input v0.1` 尚未提供 target-aware lookup 所需的上下文。预处理层会拒绝 `target_id` 非空的 lookup rule，不能把 lookup `target_id` 当成 `tile_id` 使用。

## 固定 Lambda 内核

阶段1B新增 `select_fixed_lambda(...)`。它在 lookup cap 限制后的候选集合内，为每个分块选择使 `net_utility - lambda_value * r_bytes` 最大的一个档位，并使用 D0-3 已冻结的确定性平局顺序。

输出只是 fixed-lambda candidate。`is_budget_feasible` 只描述这个候选是否满足预算，不能当作最终 `SUCCESS` 或 `INFEASIBLE_BUDGET` 状态。

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
- 通用 validator；
- `lambda` search；
- local upgrade；
- baselines；
- Longdress 输入生成；
- 批量实验；
- 图表；
- 播放器集成。
- target-aware lookup 输入语义。

## 下一步建议

下一步不建议在未审查固定 `lambda` 内核前直接写完整 solver。较稳妥的选择是：

```text
Phase 1C: lambda search interface and solver assembly boundary planning
```

这里只记录建议，不自动进入下一阶段。

## 如何接手

新的 GPT 对话或人工接手时，建议按这个顺序阅读：

1. 先读 `docs/IMPLEMENTATION_STATE_CURRENT.zh-CN.md`。
2. 再读 `docs/stage2_mvp_contract.zh-CN.md`。
3. 再读 `docs/fixed_lambda_selection_contract.zh-CN.md`。
4. 再读 `docs/schema_contract.zh-CN.md`。
5. 再看 `tests/fixtures/handcheck_3x3/hand_calculation.zh-CN.md`。
6. 安装依赖后运行 `python -m pytest` 和 `python scripts/validate_handcheck_fixtures.py`。
7. 当前不要修改 D0-1、D0-2、D0-3 的冻结语义。
8. 不要把 `handcheck_3x3` fixture 当成真实 Longdress 实验。
