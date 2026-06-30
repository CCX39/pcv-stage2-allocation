# Stage2 MVP 契约

Stage2 MVP 的目标是在给定 `Budget_total` 下，为每个参与决策的 tile 恰好选择一个传输候选，使结果满足预算、lookup 与输入完整性硬约束。

Phase 2B.1 已完成通用传输版本候选迁移。Phase 2B.3 新增真实候选元数据只读桥接，但该桥接不属于 runtime solver 路径。

## 候选语义

运行时候选是通用传输版本候选（generic transmission candidate），可理解为：

```text
candidate = (PDL, file_format, codec/profile, codec_params, asset_ref, R, D, q, provenance)
```

`candidate_id` 只用于候选身份和最后稳定平局处理。它不表示质量、数据量、处理耗时或视觉收益大小。PDL、`qp`、codec 参数、文件格式也不表示天然优劣。

PLY 与 DRC 可以在同一 tile、同一 PDL 下共同存在。MVP 不通过格式或 codec 名称推断 `R`、`D` 或 `q`。

## Utility

当前仍固定：

```text
G(d) = 1.0
U_spatial_i,j = p_sal_i * visibility_i * screen_area_i * G(d_i) * q_base_i,j
Uhat_i,j = U_spatial_i,j - eta * d_ms_i,j
```

`q_base` 与 `d_ms` 可以是 proxy，但必须通过 provenance 标明来源。proxy 值不得写成 measured。

## Lookup

lookup 语义为 PDL metadata 上界筛选：

```text
allowed_candidate_ids_i =
  {candidate_id | candidate.pdl_ratio <= pdl_max_dist_i}
```

当前 PDL lookup 来自 PLY nested-PDL calibration。它不是 DRC-aware quality measurement，也不是最终播放器 QoE 结论。`normalized_render_distance` 是归一化渲染距离，不是物理米。

启用 PDL lookup 时，参与 lookup 的候选必须提供合法 `pdl_ratio`。缺失时返回结构化 `INVALID_INPUT`。

非空 `target_id` 的 lookup rule 必须拒绝，不实现 target-aware lookup。

## 硬约束

- 每个参与决策的 tile 恰好选择一个允许候选。
- `total_bytes <= Budget_total`。
- 只能选择 lookup 后保留的候选。
- 不允许静默超预算、漏选 tile、放宽 lookup、自动提高预算或插入空候选。

最低可行预算：

```text
B_min_feasible = sum_i min(candidate.r_bytes for candidate in allowed_candidates_i)
```

如果：

```text
Budget_total < B_min_feasible
```

返回：

```text
INFEASIBLE_BUDGET
```

并且不进入 lambda search。

## Solver MVP

当前 solver 保持低复杂度近似结构：

1. lookup 解析；
2. `B_min_feasible` 检查；
3. fixed-lambda per-tile 选择；
4. lambda 上界扩展；
5. bracket 后二分搜索；
6. 搜索内最佳预算可行 candidate 记录；
7. residual-budget local repair；
8. 结构化 result。

固定 lambda 下：

```text
argmax_j [Uhat_i,j - lambda * R_i,j]
```

平局按 penalized score、较小 `R`、较小 `D`、最后 `candidate_id` 稳定处理。

best-feasible ranking：

1. `total_net_utility` 更高；
2. 若在 `score_epsilon` 内近似相同，预算利用率更高；
3. 若仍相同，`total_decode_ms` 更低；
4. 若仍相同，按排序后的 `(tile_id, selected_candidate_id)` 序列决胜。

## Local Repair

残余预算局部修正（local repair）不是 exact solver。它只在 lambda search seed candidate 之后使用剩余预算执行贪心候选切换：

```text
Delta_R > 0
Delta_Uhat > 0
Delta_R <= residual_budget
```

repair 不依赖候选编号、PDL、`qp`、codec 或 `file_format` 的大小方向。每一步记录 from/to candidate、增量、剩余预算变化和选择原因。

## Tests-only Oracle

`tests/helpers/exhaustive_oracle.py` 是 tests-only tiny-instance exhaustive oracle。它枚举 lookup 后允许候选组合，用于小规模 exact feasible reference。

它不得进入 runtime solver，不得作为 baseline、批量实验或论文实时方法描述。

## Frame 1051 Metadata Bridge

Phase 2B.3 新增只读 bridge，用于生成 metadata-only candidate catalog。它读取 data-prep 的 profile config、source PLY manifest/tile index、DRC generation manifest 和 validation report，并校验 40/200/600/800 计数、相对路径、file stat size、source PLY linkage 与 DRC basic decode-integrity 摘要。

该 catalog 不是 MVP solver 输入。它缺少 `d_ms`、`q_base`、预算与 tile 空间因子；`d_ms_status` 与 `q_base_status` 保持 `pending`。Phase 2B.4 才会在单独 proxy scoring/profile 冻结后使用它开展 frame 1051 求解器行为验证。

## 当前未实现

MVP 当前未生成 frame 1051 正式输入，未对真实 frame 1051 调 solver，未测 target-side `D`，未构建 DRC-aware 或 format-aware `q`，未实现 target-aware lookup、Pareto pruning、baseline、batch runner、plotting、播放器接入或目标端 benchmark。
