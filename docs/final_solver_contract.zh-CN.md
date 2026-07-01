# 最终求解器契约

本文记录当前 typed `solve_stage2(...)` API 的运行时契约。Phase 2B.4 / 2B.5 的 frame 1051 pilots 不改变 solver 契约；它们只是把 Phase 2B.3 metadata catalog 通过显式 proxy/derived profile 映射为临时 `Stage2Input` 后调用现有 solver。

当前实现是 Stage2 allocation 的低复杂度近似路径，不是原始 0-1 MCKP 的精确求解器。

## 输入

`solve_stage2(stage2_input, lookup, config)` 接收：

- generic-candidate `Stage2Input`
- PDL cap `DistanceLookup`
- `LambdaSearchConfig`

每个 tile 必须恰好选择一个允许候选。候选由 `candidate_id` 标识，并显式记录 `R`、`D`、`q`、PDL metadata、编码描述和 provenance。

`candidate_id` 只用于身份和最后稳定平局处理，不表示自然质量顺序。PLY 与 DRC 可以作为并列候选存在，但 solver 只根据输入中的显式数值比较。

Phase 2B.3 的 candidate metadata catalog 不是 `Stage2Input`。Phase 2B.4 / 2B.5 runner 必须先经过显式 profile 映射，补入 proxy `q_base`、proxy `d_ms`、proxy 空间因子和 derived budget 后，才可调用 solver。

## Lookup 契约

当前 lookup 只实现：

```text
semantics = cap
allowed_candidate_ids = {candidate | candidate.pdl_ratio <= pdl_max_dist}
```

当前 PDL lookup 来自 PLY nested-PDL calibration，不是 DRC-aware quality measurement，也不是最终 QoE 结论。非空 `target_id` 的 target-aware lookup 是 `INVALID_LOOKUP`。

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

## Lambda Search 与 Local Repair

lambda search 保留最低可行预算检查、自适应上界扩展、bracket 后二分搜索、搜索过程中的最佳预算可行 candidate 记录和确定性 best-feasible ranking。

local repair 从 `lambda_search.best_feasible_iteration` 对应的 seed candidate 开始，只考虑：

```text
Delta_R = R_target - R_current
Delta_Uhat = Uhat_target - Uhat_current

Delta_R > 0
Delta_Uhat > 0
Delta_R <= residual_budget
```

`candidate_id` 仅作为最后稳定项，不代表升级方向。

## Phase 2B.5 处理耗时代理敏感性边界

Phase 2B.5 的 solver 行为验证使用真实候选身份、真实 metadata、真实文件本体 `r_bytes` 和 calibrated PDL lookup 支持点；同时使用 proxy `q_base`、proxy `d_ms`、proxy 空间因子、统一 calibrated context distance assignment 和 derived budget。

新增的 `d_ms` mapping 为：

- `ply_source = 80.0 ms`
- `drc_delivery = 100.0 ms`

eta scenarios 为：

- `eta0 = 0.0`
- `eta_moderate = 0.0025`
- `eta_stronger = 0.005`

这些值只用于观察当前目标函数中的 `eta * D` 项是否影响候选选择。它们不是 target-side measured benchmark，不是逐 tile 测量，不是整帧性能结论，也不是 PLY/DRC 格式优劣证据。

不同 eta 的 `total_net_utility` 不应直接横向解释为性能优劣，因为目标函数已经改变。report 中主要比较候选选择、总字节数、总 proxy `d_ms`、预算利用率和相对 eta0 的切换数量。

## 当前未实现

当前 solver 未实现 exact MCKP、动态规划、branch-and-bound、Pareto pruning、baseline、target-aware lookup、target-side `D` 测量、DRC-aware 或 format-aware `q`、batch runner、plotting、播放器接入、网络仿真或目标端 benchmark。
