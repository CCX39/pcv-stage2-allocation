# 当前实现状态

本文是 `pcv-stage2-allocation` 的阶段1F接手说明，用来记录截至阶段1F的实现状态，方便新的对话或人工审查者快速继续工作。

## 项目当前目标

本仓库用于 Work1 Stage2 空间分块质量分配器。它要定义并后续实现：在给定视频组总数据预算的前提下，如何为每个参与决策的空间分块选择一个离散质量档位。

它不是距离标定项目，也不是完整的点云视频播放器。

## 当前阶段

当前已完成到：

```text
Phase 1F: residual-budget local upgrade integration completed
```

下一步建议进入：

```text
Phase 1G preparation: result inspection workflow or solver output documentation
```

目前尚未实现精确 MCKP 求解、通用 validator、实验运行器或播放器集成。

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
e3022ed  feat: add fixed lambda selection kernel
c0a0075  feat: add lambda bracketing trace kernel
fb88ce4  feat: add lambda bisection search kernel
0b3bf42  feat: add structured stage2 solver result
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
- `tests/test_lambda_bracketing.py`
- `tests/test_lambda_bisection.py`
- `tests/test_solver_result.py`
- `requirements.txt`
- `src/pcv_stage2/solver.py`
- `docs/fixed_lambda_selection_contract.md`
- `docs/fixed_lambda_selection_contract.zh-CN.md`
- `docs/lambda_bracketing_contract.md`
- `docs/lambda_bracketing_contract.zh-CN.md`
- `docs/lambda_bisection_contract.md`
- `docs/lambda_bisection_contract.zh-CN.md`
- `docs/final_solver_contract.md`
- `docs/final_solver_contract.zh-CN.md`
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

fixture 防线脚本继续保留独立校验路径，用于检查 Schema 草案和 handcheck JSON 文件；pytest 单独检查模型层、lookup cap 预处理、`B_min_feasible`、阶段1B固定 `lambda` 内核、阶段1C括区间 trace 内核、阶段1D二分搜索内核、阶段1E结构化 solver result、阶段1F剩余预算 local upgrade 和 handcheck 预期值。

## Target-aware Lookup 边界

`Stage2Input v0.1` 尚未提供 target-aware lookup 所需的上下文。预处理层会拒绝 `target_id` 非空的 lookup rule，不能把 lookup `target_id` 当成 `tile_id` 使用。

## 固定 Lambda 内核

阶段1B新增 `select_fixed_lambda(...)`。它在 lookup cap 限制后的候选集合内，为每个分块选择使 `net_utility - lambda_value * r_bytes` 最大的一个档位，并使用 D0-3 已冻结的确定性平局顺序。

输出只是 fixed-lambda candidate。`is_budget_feasible` 只描述这个候选是否满足预算，不能当作最终 `SUCCESS` 或 `INFEASIBLE_BUDGET` 状态。

## Lambda 括区间内核

阶段1C新增 `bracket_lambda_for_feasible_candidate(...)`。它先评估 `lambda = 0`，再从 `lambda_initial_high` 开始加倍正 `lambda`，直到找到第一个预算可行 fixed-lambda candidate，或用完 `lambda_max_bracket_steps`。

输出只是 bracket result 和 trace，不是最终 Stage2 result。trace 记录每次 probe 的 `lambda`、总数据量、原始净效用、总解码耗时、预算可行性和选档结果。如果 `budget_total_bytes < B_min_feasible`，helper 会抛出预处理错误，正式 `INFEASIBLE_BUDGET` 组装留给未来 solver 层。

## Lambda 二分搜索内核

阶段1D新增 `search_lambda_feasible_candidates(...)`。它复用 bracket helper，在一个已知超预算的 lower lambda 和一个已知预算可行的 upper lambda 之间做二分搜索。trace 会连续累积零 `lambda`、bracket 和 midpoint probe，`step_index` 从 0 开始连续递增。

输出只是搜索内核结果，不是最终 Stage2 result。它记录 `termination_reason`、当前 lambda 边界、完整 trace，以及搜索中观察到的最佳预算可行 fixed-lambda candidate。最佳可行 candidate 比较遵循 D0-3：总净效用更高优先；若在 `score_epsilon` 内近似相同，则预算利用率更高优先；再相同时总解码耗时更低优先；最后按排序后的 `(tile_id, selected_level_id)` 序列确定性决胜。

## 结构化 Solver API

阶段1E新增 `solve_stage2(stage2_input, lookup, config)`。它先解析 lookup cap 候选、计算 `B_min_feasible`；如果预算低于最低可行值，则不进入 lambda search，直接返回结构化 `INFEASIBLE_BUDGET`；否则运行阶段1D lambda search。

输出是 `Stage2SolveResult`。`Stage2SolveResult.to_dict()` 会生成 JSON-compatible dict，并可通过 `schemas/stage2_result.schema.json` 校验。结果记录 selected tiles、lookup resolution、lambda trace、config snapshot、runtime、warnings 和 errors。

这仍是 Stage2 分配问题的低复杂度近似路径，不能描述为原始 0-1 MCKP 的精确全局求解器。

## 剩余预算 Local Upgrade

阶段1F新增成功 lambda search 之后的 local-upgrade 后处理。seed 始终来自 lambda search 的 `best_feasible_candidate`，并由 `lambda_search.best_feasible_iteration` 标识。

每次升级都必须限制在 `allowed_levels` 内，要求增量数据量为正、增量净效用为正，并且不超过当前剩余预算。贪心顺序为单位预算收益最高；若收益完全相同，则按 `(tile_id, target_level_id)` 升序决胜。升级审计记录在 `local_upgrade.steps[]` 中；lambda trace 仍只表示 lambda search 过程。

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

- 通用 validator；
- 精确或穷举 MCKP 求解器；
- baselines；
- Longdress 输入生成；
- 批量实验；
- 图表；
- 播放器集成。
- target-aware lookup 输入语义。

## 下一步建议

下一步不建议在未审查 local-upgrade 审计输出前直接进入实验。较稳妥的选择是：

```text
Phase 1G: result inspection workflow or solver output documentation
```

这里只记录建议，不自动进入下一阶段。

## 如何接手

新的 GPT 对话或人工接手时，建议按这个顺序阅读：

1. 先读 `docs/IMPLEMENTATION_STATE_CURRENT.zh-CN.md`。
2. 再读 `docs/stage2_mvp_contract.zh-CN.md`。
3. 再读 `docs/fixed_lambda_selection_contract.zh-CN.md`。
4. 再读 `docs/lambda_bracketing_contract.zh-CN.md`。
5. 再读 `docs/lambda_bisection_contract.zh-CN.md`。
6. 再读 `docs/final_solver_contract.zh-CN.md`。
7. 再读 `docs/schema_contract.zh-CN.md`。
8. 再看 `tests/fixtures/handcheck_3x3/hand_calculation.zh-CN.md`。
9. 安装依赖后运行 `python -m pytest` 和 `python scripts/validate_handcheck_fixtures.py`。
10. 当前不要修改 D0-1、D0-2、D0-3 的冻结语义。
11. 不要把 `handcheck_3x3` fixture 当成真实 Longdress 实验。
