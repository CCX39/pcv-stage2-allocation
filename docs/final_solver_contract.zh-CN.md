语言：[English](final_solver_contract.md) | 中文

# 最终 Solver API 契约

状态：阶段1F实现说明。

本文说明截至阶段1F的 typed `solve_stage2(...)` API。它把 lookup cap 解析、`B_min_feasible`、lambda search、最佳可行 candidate、剩余预算 local upgrade 和结构化 result 组装起来。当前实现仍是低复杂度整数近似框架，不是原始 0-1 MCKP 的精确求解器。

## 输入与输出

`solve_stage2(stage2_input, lookup, config)` 接收 typed 模型对象：

- `Stage2Input`；
- `DistanceLookup`；
- `LambdaSearchConfig`。

它返回 `Stage2SolveResult`。`Stage2SolveResult.to_dict()` 会生成 JSON-compatible dict，并满足 `schemas/stage2_result.schema.json`。

该 API 不负责加载 JSON 文件，不校验任意 dict，不写 result 文件，也不提供 CLI。

## 状态映射

`INFEASIBLE_BUDGET` 表示 lookup cap 解析成功、`B_min_feasible` 已计算，且 `budget_total_bytes < B_min_feasible`。这种情况下 solver 不进入 lambda search。

`SUCCESS` 表示 lambda search 恢复了预算可行的 fixed-lambda seed candidate，随后执行剩余预算 local upgrade，并且最终 result 组装重新复核了 lookup cap 和预算约束。

`NUMERICAL_ERROR` 表示 `B_min_feasible <= budget_total_bytes`，但当前 lambda search 配置没有恢复预算可行 candidate。结果会保留 lambda trace，方便排查。

`INVALID_LOOKUP` 覆盖 lookup profile 不匹配、lookup 语义不支持、匹配规则缺失或歧义、以及当前不支持的 target-aware lookup rule。lookup 中非空的 `target_id` 不能当成 `tile_id` 使用。

`NO_ALLOWED_LEVEL` 表示某个分块经过 lookup cap 后没有任何可用质量档位。

`INVALID_INPUT` 暂时作为 Schema 或 typed 输入校验边界的预留状态。阶段1F API 接收已经构造好的 typed model，不新增 dict/JSON 输入接口。

`INTERNAL_CONSTRAINT_VIOLATION` 只用于 solver 能明确发现的 result 组装不变量破坏。

## SUCCESS 复核

对于 `SUCCESS`，组装结果时会复核：

- 每个参与分块恰好有一个选档；
- 选中档位属于该分块 lookup cap 后的允许候选集合；
- 总数据量不超过 `budget_total_bytes`；
- 总数据量、净效用、空间效用和解码耗时与 selected tiles 一致。

当前 MVP 的空间效用沿用模型层默认 `g_distance = 1.0`。阶段1F不拟合、也不引入新的距离函数。

## Lambda Trace 写入结果

进入 lambda search 的路径会把完整搜索轨迹写入 `lambda_search.iterations[]`：

```text
lambda = 0 probe
+ 正 lambda bracket probes
+ bisection midpoint probes
```

每次 iteration 记录 lambda、总数据量、总净效用、总解码耗时、预算可行性和 selected levels。`best_feasible_iteration` 指向完整 trace 中的 step index。

## 剩余预算 Local Upgrade

对于 `SUCCESS`，local upgrade 从 `lambda_search.best_feasible_iteration` 对应的 candidate 开始，也就是 lambda search 找到的最佳可行 seed candidate。它不会使用最后一个 trace point，除非最后一个 trace point 本身就是最佳可行 candidate。

local upgrade 只考虑满足以下条件的目标档位：

- `target_level_id` 高于当前档位；
- 仍位于该 tile 的 `allowed_levels` 内；
- 增量数据量为正；
- 增量净效用为正；
- 不超过当前剩余预算。

每一步选择 `delta_net_utility / delta_r_bytes` 最大的候选。若单位收益完全相同，则按 `(tile_id, target_level_id)` 升序决胜。每次应用升级后，重新计算剩余预算和下一轮候选集合。

`local_upgrade.steps[]` 记录该后处理的审计轨迹。这些 step 不会写入 `lambda_search.iterations[]`，也不会改写 lambda trace。最终 `selected_tiles` 和汇总指标反映 local upgrade 后的结果。

## 范围边界

阶段1F没有实现：

- 原始 MCKP 的精确或穷举求解；
- baseline 算法；
- Longdress 输入生成；
- 批量实验；
- 绘图；
- 播放器集成；
- target-aware lookup schema 扩展；
- Stage1 在线集成；
- JSON 文件输出 CLI。

当前结果是本阶段低复杂度近似路径下的结构化 Stage2 solver 输出，不能描述为原始 0-1 MCKP 的严格全局最优解。
