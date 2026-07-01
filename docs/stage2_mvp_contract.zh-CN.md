# Stage2 MVP 契约

Stage2 MVP 的目标是在给定 `Budget_total` 下，为每个参与决策的 tile 恰好选择一个传输候选，使结果满足预算、lookup 与输入完整性硬约束。

Phase 2B.1 已完成通用传输版本候选迁移。Phase 2B.4 新增的 frame 1051 behavior pilot 是 MVP solver 的行为验证，不改变 runtime solver 路径。

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

Phase 2B.4 behavior pilot 固定 `q_base = pdl_ratio`、`d_ms = 0.0`、`eta = 0`。该设置只用于验证 solver 行为，不是质量或端侧耗时测量。

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

## Frame 1051 Behavior Pilot

Phase 2B.4 profile 固定两个 full-body context：

- `fullbody_d1`：`distance_norm = 1.0`，`pdl_max_dist = 1.0`；
- `fullbody_d3`：`distance_norm = 3.0`，`pdl_max_dist = 0.6`。

每个 context 派生三个预算点：

- `min_feasible`；
- `midpoint`；
- `reference_max`。

因此正常情况下运行 6 个 scenario。若某些预算点数值偶然重复，runner 会去重并在 report 中记录。

真实字段边界：

- 使用真实 `tile_id`、`candidate_id`、PLY/DRC metadata、`pdl_ratio`、`asset_ref` 和 measured file body `r_bytes`；
- 使用 calibrated PLY full-body strict lookup 支持点；
- 使用 proxy `q_base`、proxy `d_ms`、proxy 空间因子、统一 context distance assignment 和 derived `Budget_total`。

该 pilot 只验证 solver 的输入映射、lookup、预算、trace、provenance 和不变量，不声明视觉质量、端侧性能、QoE、网络吞吐或格式优劣。

## Tests-only Oracle

`tests/helpers/exhaustive_oracle.py` 是 tests-only tiny-instance exhaustive oracle。它枚举 lookup 后允许候选组合，用于小规模 exact feasible reference。

它不得进入 runtime solver，不得作为 baseline、批量实验或论文实时方法描述。

## 当前未实现

MVP 当前未测 target-side `D`，未构建 DRC-aware 或 format-aware `q`，未接入真实 saliency/visibility/projection pipeline，未接入 Stage1 `Budget_total` 在线接口，未实现 target-aware lookup、Pareto pruning、baseline、batch runner、plotting、播放器接入或目标端 benchmark。
