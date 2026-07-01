# 决策记录

本文记录当前仓库已经冻结的工程决策。

## D0-1 / D2B.1：lookup 是基于 candidate.pdl_ratio 的 PDL 上界筛选

| 项 | 内容 |
|---|---|
| 决策 | lookup `semantics = cap` 表示 `candidate.pdl_ratio <= pdl_max_dist` 的候选保留规则。 |
| 背景 | 旧运行时曾把 lookup 解释为连续 PDL 档位前缀。Phase 2B.1 已迁移为 generic transmission candidate，候选不再天然全序。 |
| 影响 | 预处理只按显式 `pdl_ratio` 筛选，不按 `candidate_id`、数组位置、`qp`、codec 或 `file_format` 筛选。 |
| 边界 | 当前 PDL lookup 来自 PLY nested-PDL calibration，不是 DRC-aware quality measurement，也不是最终 QoE 结论。 |

## D0-2：预算不可行必须显式返回

如果：

```text
Budget_total < B_min_feasible
```

则返回：

```text
INFEASIBLE_BUDGET
```

其中：

```text
B_min_feasible = sum_i min(candidate.r_bytes for candidate in allowed_candidates_i)
```

不允许静默超预算、漏选 tile、放宽 lookup、自动提高预算或插入空候选。

## D0-3 / D2B.1：fixed lambda 与 best-feasible 平局规则

固定 lambda 下每个 tile 独立选择：

```text
argmax_j [Uhat_i,j - lambda * R_i,j]
```

fixed-lambda 内部平局：

1. penalized score 更高；
2. `R` 更小；
3. `D` 更小；
4. 最后按 `candidate_id` 稳定决胜。

`candidate_id` 不承担质量顺序，只是最后稳定项。

## D1F / D2B.1：local repair 是候选切换

local repair 从 lambda search 的最佳预算可行 seed candidate 开始，使用剩余预算做轻量候选切换。它只考虑：

```text
Delta_R > 0
Delta_Uhat > 0
Delta_R <= residual_budget
```

repair 不依赖候选编号、PDL、`qp`、codec 或 `file_format` 的大小方向。

## D2B.3：frame 1051 metadata bridge 是只读目录桥接

Phase 2B.3 新增 read-only metadata bridge。它显式接收本机 `pcv-stage2-data-prep` root，只读取轻量 JSON manifest/report，并通过 stat size 校验 manifest 引用文件。

catalog 中 `r_bytes` 是候选文件本体字节数，来自 manifest 与 stat size 的一致性检查，provenance 为 `measured`。它不是端到端网络总开销。`d_ms` 与 `q_base` 保持 `pending`，不得由文件大小、点数、PDL、`qp`、codec 或常数推导。

catalog 不是 `Stage2Input`，不能直接传入 solver。本阶段不读取 PLY/DRC 二进制内容，不运行 Draco，不重算大文件 SHA-256，不复制真实 assets。

## D2B.4：frame 1051 behavior pilot 只验证 solver 行为

Phase 2B.4 新增 `frame1051_fullbody_proxy_behavior_v1` profile 和 runner。runner 先调用 Phase 2B.3 bridge，再把 catalog 显式映射为临时 Stage2 input，运行现有 `solve_stage2(...)`。

本阶段冻结：

- `fullbody_d1`：`distance_norm = 1.0`，`pdl_max_dist = 1.0`；
- `fullbody_d3`：`distance_norm = 3.0`，`pdl_max_dist = 0.6`；
- `q_base = pdl_ratio`，provenance 为 `proxy`；
- `d_ms = 0.0`，`eta = 0`，provenance 为 `proxy`；
- `p_sal = visibility = screen_area = 1.0`，provenance 为 `proxy`；
- `Budget_total` 使用 `min_feasible`、`midpoint`、`reference_max` 三个 derived 预算点。

## D2B.5：d_ms sensitivity pilot 只验证处理代价项行为

Phase 2B.5 新增 `frame1051_fullbody_proxy_dms_sensitivity_v1` profile。它保持 Phase 2B.4 的真实 catalog、lookup、q_base proxy、空间因子和预算推导不变，只新增 proxy `d_ms` mapping 与 eta scenarios。

冻结设定：

- `ply_source = 80.0 ms`
- `drc_delivery = 100.0 ms`
- `eta0 = 0.0`
- `eta_moderate = 0.0025`
- `eta_stronger = 0.005`

这组 `d_ms` 与 eta 只是行为验证代理，不是 target-side measured benchmark，不是逐 tile 测量，不是完整帧加载耗时，也不是 PLY/DRC 格式优劣证据。所有 DRC `qp` 共用同一 `100.0 ms` proxy；不得从 `qp`、`candidate_id`、codec 字符串、文件大小或数组顺序推导质量或处理耗时顺序。

report 应主要比较候选选择、总字节数、总 proxy `d_ms`、预算利用率和相对 eta0 的切换数量。不同 eta 的 `total_net_utility` 不应直接横向解释为性能优劣，因为目标函数已经改变。

## 后续仍未完成

后续仍需研究者确认或准备 target-side `d_ms` 独立 benchmark、format-aware / DRC-aware `q_base`、真实空间因子、真实 distance assignment、Stage1 `Budget_total` 接口，以及是否进入 Pareto pruning、baseline、batch runner、plotting 或播放器接入。

本仓库仍未实现 target-aware lookup、Pareto pruning、baseline、batch runner、plotting、播放器接入、网络仿真或目标端 benchmark。
