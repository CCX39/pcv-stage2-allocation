语言：[English](lambda_bisection_contract.md) | 中文

# Lambda 二分搜索契约

状态：阶段1D实现说明。

本文说明阶段1D新增的搜索内核层。它在自适应 `lambda` 括区间之后执行二分搜索，并记录搜索过程中观察到的最佳预算可行 fixed-lambda candidate。它不是最终 Stage2 求解器。

## 输入前提

二分搜索只在 `bracket_lambda_for_feasible_candidate(...)` 已经得到有效 bracket 后执行：

- `lambda_low` 是已知超预算端；
- `lambda_high` 是已知预算可行端。

如果 `lambda = 0` 已经预算可行，则跳过二分搜索，并把零 `lambda` candidate 作为当前最佳可行 candidate。

如果 bracket 失败，则 search result 报告 `bracket_failure`，不得伪造预算可行 candidate。

## 配置模型

bracket 和 bisection 共用一个显式的 `LambdaSearchConfig`：

- `lambda_initial_high`：有限正数；
- `lambda_max_bracket_steps`：非负整数；
- `score_epsilon`：有限非负数；
- `lambda_epsilon`：有限非负数；
- `max_iterations`：非负整数。

`max_iterations = 0` 表示保留 bracket 得到的 upper feasible candidate，不执行 midpoint probe。实现会拒绝 bool、`NaN`、无穷大、负数和非整数 iteration count。

## Trace 累积

搜索 trace 是连续累积的：

```text
lambda = 0 probe
+ 正 lambda bracket probes
+ bisection midpoint probes
```

`step_index` 在完整 trace 中从 `0` 开始连续递增，不会在 bracketing 和 bisection 之间重置。

每个 trace point 记录：

- `lambda_value`；
- `total_bytes`；
- `total_net_utility`；
- `total_decode_ms`；
- `is_budget_feasible`；
- `selected_levels`。

所有 trace point 都来自 `select_fixed_lambda(...)`。

## 二分规则

每轮迭代计算：

```text
lambda_mid = (lambda_low + lambda_high) / 2
```

midpoint candidate 由 `select_fixed_lambda(...)` 评估，并追加到 trace。

如果 candidate 预算可行，它可以更新当前最佳可行 candidate，并成为新的 upper 端点；如果它超预算，则成为新的 lower 端点。

## 最佳可行 Candidate

best feasible 比较只用于已经预算可行的 candidate。顺序遵循 D0-3：

1. `total_net_utility` 更高；
2. 若在 `score_epsilon` 内近似相同，预算利用率更高；
3. 若仍相同，`total_decode_ms` 更低；
4. 若仍相同，按排序后的 `(tile_id, selected_level_id)` 序列做确定性字典序比较。

当预算为 0 时，为避免除零，预算利用率这一层视为平局。

## 终止原因

search-level 的 `termination_reason` 不是最终 Stage2 状态：

- `feasible_at_zero`：零 `lambda` candidate 已满足预算，未执行二分；
- `lambda_epsilon`：bracket 宽度已不大于 `lambda_epsilon`；
- `max_iterations`：达到配置允许的 midpoint probe 次数；
- `bracket_failure`：bracketing 阶段没有找到预算可行 upper lambda；
- `floating_point_stall`：midpoint 已无法继续缩小区间。

成功 bracket 之后，即使搜索未完全收敛，也只能返回已经复核过的预算可行 candidate，不能把超预算 candidate 作为 best feasible result 返回。

## 范围边界

阶段1D没有实现：

- 最终 `solve_stage2` API；
- 最终 `SUCCESS` 或 `INFEASIBLE_BUDGET` result 组装；
- JSON result 序列化；
- local upgrade；
- 原始 MCKP 的穷举精确求解；
- baseline 算法；
- Longdress 输入生成；
- 批量实验；
- 绘图；
- 播放器集成；
- target-aware lookup schema 扩展。

search result 是 fixed-lambda 松弛搜索内核结果，不能描述为原始 0-1 MCKP 的严格全局最优解。
