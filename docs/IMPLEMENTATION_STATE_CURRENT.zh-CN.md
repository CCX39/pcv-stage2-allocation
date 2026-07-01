# 当前实现状态

当前仓库阶段：**Phase 2B.5：frame 1051 处理耗时代理敏感性验证**。

Phase 2B.1 已完成 Stage2 allocation 的 generic-candidate 迁移。Phase 2B.3 已新增只读 metadata bridge。Phase 2B.4 已基于真实 frame 1051 candidate metadata catalog 构造临时、可追溯、严格标注为 proxy/derived 的 `Stage2Input`，验证现有 solver 在真实候选目录上的行为。Phase 2B.5 在不改变 core solver、Schema、metadata bridge 或真实资产的前提下，新增 proxy `d_ms` mapping 与 eta scenarios，验证 `eta * D` 项是否能产生可追溯的候选切换。

## 运行时状态

运行时输入使用通用传输版本候选。每个 tile 包含 `candidates[]`，候选记录 `candidate_id`、`pdl_ratio`、`file_format`、`codec`、`codec_params`、`asset_ref`、`r_bytes`、`d_ms`、`q_base` 和 `provenance`。

`candidate_id` 只用于身份标识和最后稳定平局处理，不承担质量、数据量、处理耗时或视觉收益顺序。`pdl_ratio` 只用于当前 PDL lookup 投影。

## Solver 状态

当前 runtime solver 是：

```text
lambda search + residual-budget local repair
```

它不是 exact MCKP、动态规划、branch-and-bound、Pareto pruning 或 baseline。固定 lambda 下按显式数值选择：

```text
argmax_j [Uhat_i,j - lambda * R_i,j]
```

local repair 已改为候选切换，只考虑：

```text
Delta_R > 0
Delta_Uhat > 0
Delta_R <= residual_budget
```

## Phase 2B.3 / 2B.4 已完成内容

- `src/pcv_stage2/frame1051_metadata_bridge.py`：只读构建 frame 1051 candidate metadata catalog。
- `scripts/build_frame1051_candidate_catalog.py`：显式接收本机 data-prep root，可将真实 catalog 写入 ignored `outputs/`。
- `configs/frame1051_fullbody_proxy_behavior_v1.json`：Phase 2B.4 行为验证 profile。
- `src/pcv_stage2/frame1051_behavior_pilot.py` 与 `scripts/run_frame1051_behavior_pilot.py`：把 metadata catalog 显式映射为临时 generic-candidate `Stage2Input`，派生预算并运行现有 solver。

Phase 2B.4 使用真实 `tile_id`、`candidate_id`、PLY/DRC metadata、`pdl_ratio`、`asset_ref` 和 measured 文件本体 `r_bytes`；使用 calibrated PLY lookup 支持点；使用 proxy `q_base`、proxy `d_ms=0.0`、proxy 空间因子、统一 context distance assignment 和 derived `Budget_total`。

## Phase 2B.5 已新增内容

- `configs/frame1051_fullbody_proxy_dms_sensitivity_v1.json`：处理耗时代理敏感性 profile。
- runner 支持 profile 中的 `d_ms_by_candidate_kind` 与 `eta_scenarios`。
- report 新增 eta scenario、d_ms mapping、`total_selected_d_ms` 和相对 eta0 的 selected candidate change count。
- `tests/test_frame1051_dms_sensitivity_pilot.py`：覆盖 d_ms mapping、fail-closed、eta0 回归、正 eta 受控切换、pending 边界、稳定性和 non-claims。

Phase 2B.5 固定：

- `ply_source`: `d_ms = 80.0 ms`
- `drc_delivery`: `d_ms = 100.0 ms`
- `eta0 = 0.0`
- `eta_moderate = 0.0025`
- `eta_stronger = 0.005`

这些值是人为设定的候选级 proxy，不是 target-side measured benchmark，不是逐 tile 测量，也不是完整帧加载耗时。所有 DRC `qp` 共用同一 proxy `d_ms`，不根据 `qp`、`candidate_id`、文件大小或数组顺序继续细分。

## 边界

真实事实只包括候选身份、metadata、`pdl_ratio`、`asset_ref` 和 measured file body `r_bytes`。`r_bytes` 可作为 `R_i,j` 的文件本体字节记账值参与预算和 `lambda * R_i,j`，但不是端到端网络总开销。

`q_base = pdl_ratio` 仍是 proxy scoring rule，不是 DRC-aware 或 format-aware 质量测量。不同 eta 的 `total_net_utility` 不应直接横向解释为性能优劣，因为目标函数已经改变。

## 下一步边界

后续仍需研究者冻结或准备：

- target-side `d_ms` 独立 benchmark；
- format-aware / DRC-aware `q_base`；
- 真实 saliency、visibility、screen_area、distance assignment 或 viewport pipeline；
- Stage1 `Budget_total` 在线接口；
- 是否以及如何做 Pareto pruning、baseline、batch runner、plotting 或播放器接入。

当前仍未实现 target-aware lookup、Pareto pruning、baseline、batch runner、plotting、播放器接入、网络仿真、目标端 benchmark、DRC-aware 质量测量或正式性能实验。
