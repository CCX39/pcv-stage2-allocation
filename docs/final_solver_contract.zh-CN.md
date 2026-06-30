# 最终求解器契约

本文记录当前 typed `solve_stage2(...)` API 的运行时契约。Phase 2B.1 已完成通用传输版本候选迁移；Phase 2B.3 新增的 frame 1051 metadata bridge 不改变 solver 契约，也不会被 `solve_stage2(...)` 调用。

当前实现是 Stage2 allocation 的低复杂度近似路径，不是原始 0-1 MCKP 的精确求解器。

## 输入

`solve_stage2(stage2_input, lookup, config)` 接收：

- generic-candidate `Stage2Input`
- PDL cap `DistanceLookup`
- `LambdaSearchConfig`

每个 tile 必须恰好选择一个允许候选。候选由 `candidate_id` 标识，并显式记录 `R`、`D`、`q`、PDL metadata、编码描述和 provenance。

`candidate_id` 只用于身份和最后稳定平局处理，不表示自然质量顺序。PLY 与 DRC 可以作为并列候选存在，但 solver 只根据输入中的显式数值比较。

Phase 2B.3 的 candidate metadata catalog 不是 `Stage2Input`。catalog 缺少 `d_ms`、`q_base`、预算和 tile 空间因子，不能直接求解。

## Lookup 契约

当前 lookup 只实现：

```text
semantics = cap
allowed_candidate_ids = {candidate | candidate.pdl_ratio <= pdl_max_dist}
```

启用 PDL lookup 时，候选缺少 `pdl_ratio` 是 `INVALID_INPUT`。非空 `target_id` 的 target-aware lookup 是 `INVALID_LOOKUP`，不得把 `target_id` 当作 `tile_id`。

当前 PDL lookup 来自 PLY nested-PDL calibration，不是 DRC-aware quality measurement，也不是最终 QoE 结论。

## 状态码

- `SUCCESS`：lambda search 找到预算可行 seed candidate，local repair 完成后结果仍满足预算与 lookup 硬约束。
- `INFEASIBLE_BUDGET`：`budget_total_bytes < B_min_feasible`，不进入 lambda search。
- `INVALID_INPUT`：输入候选字段缺失、数值非法，或启用 PDL lookup 时缺少 `pdl_ratio`。
- `INVALID_LOOKUP`：lookup profile 不匹配、距离规则无法唯一匹配、存在 target-aware lookup，或 lookup 语义不受支持。
- `NO_ALLOWED_CANDIDATE`：某个 tile 经过 PDL cap 后没有允许候选。
- `NUMERICAL_ERROR`：理论上预算可行，但当前 lambda search 配置未恢复预算可行候选。
- `INTERNAL_CONSTRAINT_VIOLATION`：组装结果违反内部不变量。

## Fixed Lambda 选择

固定 lambda 下，每个 tile 独立选择：

```text
argmax_j [Uhat_i,j - lambda * R_i,j]
```

平局顺序：

1. penalized score 更高；
2. 若在 `score_epsilon` 内近似相同，`R` 更小；
3. 若仍相同，`D` 更小；
4. 最后按 `candidate_id` 稳定决胜。

这里不会使用数组位置、候选编号大小、`qp`、`codec` 或 `file_format` 表达优劣。

## Lambda Search

lambda search 保留：

- 最低可行预算检查；
- 自适应上界扩展；
- bracket 后二分搜索；
- 搜索过程中的最佳预算可行 candidate 记录；
- 确定性 best-feasible ranking。

best-feasible ranking 为总净效用更高、预算利用率更高、总解码耗时更低、排序后的 `(tile_id, selected_candidate_id)` 序列更小。

## Local Repair

local repair 从 `lambda_search.best_feasible_iteration` 对应的 seed candidate 开始。它不会改写 lambda trace。

每一步枚举同一 tile 的其他允许候选，只考虑：

```text
Delta_R = R_target - R_current
Delta_Uhat = Uhat_target - Uhat_current

Delta_R > 0
Delta_Uhat > 0
Delta_R <= residual_budget
```

排序使用单位预算增益，再用显式增量和 tile/candidate 身份稳定决胜。`candidate_id` 仅作为最后稳定项，不代表升级方向。

`local_upgrade.steps[]` 记录 candidate switch trace：`from_candidate_id`、`to_candidate_id`、`delta_r_bytes`、`delta_net_utility`、剩余预算变化、累计结果和选择原因。

## Result

结果保留：

- `status`
- `total_bytes`
- `total_net_utility`
- `B_min_feasible`
- `budget_utilization`
- `lambda_search`
- `local_upgrade`
- `warnings` / `errors`
- `config_snapshot`
- `runtime_ms`

候选相关输出包括：

- `selected_candidate_id`
- `selected_candidate_snapshot`
- `allowed_candidate_ids`
- `rejected_candidate_ids`
- `lookup_pdl_max_dist`
- lambda trace 的 selected candidates
- candidate switch repair trace

`selected_candidate_snapshot` 必须保留候选解释信息，包括 PDL、format、codec、asset ref、`R`、`D`、`q` 和 provenance。

## 当前未实现

当前 solver 未实现 exact MCKP、动态规划、branch-and-bound、Pareto pruning、baseline、target-aware lookup、真实 frame 1051 正式输入、target-side `D` 测量、DRC-aware 或 format-aware `q`、batch runner、plotting、播放器接入或目标端 benchmark。

Phase 2B.3 已能生成 metadata-only catalog，但不会读取候选二进制内容，不运行 Draco，不复制真实 assets，不把 catalog 传入 solver。Phase 2B.4 才会在明确 proxy scoring/profile 冻结后开展 frame 1051 求解器行为验证。
