语言：[English](lambda_bracketing_contract.md) | 中文

# Lambda 括区间契约

状态：阶段1C实现说明。

本文说明阶段1C新增的自适应 `lambda` 上界括区间内核。bracketing 组件为阶段1D二分搜索内核准备 low/high 搜索区间和 trace 数据，不是完整 Stage2 求解器。

## 输入前提

括区间流程发生在输入解析、lookup cap 解析和 `B_min_feasible` 计算之后。如果：

```text
budget_total_bytes < B_min_feasible
```

bracketing helper 会抛出受控的预处理错误。未来最终 `solve_stage2` 层必须把这个条件映射为 `INFEASIBLE_BUDGET`；阶段1C不组装正式结果。

## Probe 顺序

当前实现使用统一的 `LambdaSearchConfig`。bracketing 会使用其中的 `lambda_initial_high`、`lambda_max_bracket_steps` 和 `score_epsilon`；二分相关字段也放在同一个显式配置对象中，避免调用方维护两套含义相近的配置模型。

内核总是先评估 `lambda = 0`。

如果零 `lambda` candidate 已经满足预算，则结果标记为 `feasible_at_zero`，不再执行正 `lambda` probe。

如果零 `lambda` candidate 超预算，则从 `lambda_initial_high` 开始尝试。每次正 `lambda` probe 仍超预算时，将当前值加倍：

```text
lambda <- 2 * lambda
```

`lambda_max_bracket_steps` 表示最多尝试多少个正 `lambda` 值，不包含必做的零 `lambda` probe。取值为 `0` 表示零 `lambda` probe 之后不再尝试正 `lambda` bracket probe。

## 结果类型

`bracket_found = true` 且 `feasible_at_zero = true` 表示零 `lambda` candidate 已满足预算。

`bracket_found = true` 且 `feasible_at_zero = false` 表示 trace 中包含一个超预算的 lower lambda 和首次预算可行的正 upper lambda。

`bracket_found = false` 表示配置允许的正 `lambda` probe 次数用完后仍未找到预算可行 candidate。这是 bracket failure result，不是最终 solver 状态，也不得伪造可行 candidate。

## Trace 字段

每个 trace point 记录：

- `step_index`；
- `lambda_value`；
- `total_bytes`；
- `total_net_utility`；
- `total_decode_ms`；
- `is_budget_feasible`；
- `selected_levels`。

所有 trace 值都来自 `select_fixed_lambda(...)` 返回的 fixed-lambda candidate。`total_decode_ms` 是实际被选档位的 `d_ms` 之和。

## 范围边界

bracketing 组件本身不实现：

- 二分搜索；
- 最佳可行 candidate 排序；
- 最终 `solve_stage2` API；
- 最终 `SUCCESS` 或 `INFEASIBLE_BUDGET` result 组装；
- local upgrade；
- 原始 MCKP 的穷举精确求解；
- baseline 算法；
- Longdress 输入生成；
- 批量实验；
- 绘图；
- 播放器集成；
- target-aware lookup schema 扩展。

bracket success 只是松弛内核的搜索边界，不能描述为原始 0-1 MCKP 的严格全局最优。
