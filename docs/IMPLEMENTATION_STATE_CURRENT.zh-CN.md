# 当前实现状态

当前仓库阶段：**Phase 2B.4：frame 1051 求解器行为验证**。

Phase 2B.1 已完成 Stage2 allocation 的 generic-candidate 迁移。Phase 2B.3 已新增只读 metadata bridge。Phase 2B.4 在不改变 core solver、Schema 或真实资产的前提下，基于真实 frame 1051 candidate metadata catalog 构造临时、可追溯、严格标注为 proxy/derived 的 `Stage2Input`，用于验证现有 solver 在真实候选目录上的行为。

## 运行时状态

运行时输入已经从连续 PDL 质量档位改为通用传输版本候选。每个 tile 包含 `candidates[]`，候选记录 `candidate_id`、`pdl_ratio`、`file_format`、`codec`、`codec_params`、`asset_ref`、`r_bytes`、`d_ms`、`q_base` 和 `provenance`。

`candidate_id` 只用于身份标识和最后稳定平局处理，不承担质量、数据量、处理耗时或视觉收益顺序。`pdl_ratio` 只用于当前 PDL lookup 投影。

## Lookup 状态

当前 lookup 使用 PDL metadata 上界筛选：

```text
allowed_candidate_ids = {candidate | candidate.pdl_ratio <= pdl_max_dist}
```

启用 PDL lookup 时，候选缺少 `pdl_ratio` 会返回结构化 `INVALID_INPUT`。非空 `target_id` 的 target-aware lookup 仍返回 `INVALID_LOOKUP`，不会被解释为 `tile_id`。

当前 lookup 来源仍是 PLY nested-PDL calibration，不是 DRC-aware quality measurement，也不是最终 QoE 结论。`normalized_render_distance` 不是物理米。

## Solver 状态

当前 runtime solver 是：

```text
lambda search + residual-budget local repair
```

它不是 exact MCKP、动态规划、branch-and-bound、Pareto pruning 或 baseline。

固定 lambda 下按显式数值选择：

```text
argmax_j [Uhat_i,j - lambda * R_i,j]
```

平局顺序为 penalized score 更高、`R` 更小、`D` 更小、最后按 `candidate_id` 稳定决胜。

local repair 已改为候选切换，只考虑：

```text
Delta_R > 0
Delta_Uhat > 0
Delta_R <= residual_budget
```

## Phase 2B.3 已完成内容

- `src/pcv_stage2/frame1051_metadata_bridge.py`：只读构建 frame 1051 candidate metadata catalog。
- `scripts/build_frame1051_candidate_catalog.py`：显式接收本机 data-prep root，可将真实 catalog 写入 ignored `outputs/`。
- bridge 只读取 JSON manifest/report，并用 `Path.stat()` 校验 manifest 引用文件存在且 size 一致；不读取 PLY/DRC 二进制内容，不运行 Draco，不重算大文件 SHA-256。

catalog 包含 8i Longdress frame 1051、G128、40 个 non-empty tile、200 个 source PLY 候选和 600 个 DRC delivery 候选。`r_bytes` 是候选文件本体字节数，provenance 为 `measured`，不是端到端网络总开销。catalog 中 `d_ms_status = pending`、`q_base_status = pending`，不是 `Stage2Input`，不能直接求解。

## Phase 2B.4 已新增内容

- `configs/frame1051_fullbody_proxy_behavior_v1.json`：行为验证 profile，记录 full-body context、proxy scoring、预算推导、solver config 与 non-claims。
- `src/pcv_stage2/frame1051_behavior_pilot.py`：把 metadata catalog 显式映射为临时 generic-candidate `Stage2Input`，派生预算并运行现有 solver。
- `scripts/run_frame1051_behavior_pilot.py`：显式接收本机 data-prep root，把真实 run output 写入 ignored `outputs/frame1051_behavior_pilot/`。
- `tests/test_frame1051_behavior_pilot.py`：synthetic tests，覆盖 lookup cap、allowed candidate count、proxy provenance、catalog pending 边界、预算公式、solver invariants、重复运行稳定性、catalog 候选顺序稳定性和 non-claims。

## Behavior Pilot 配置边界

本轮使用真实 metadata：

- `tile_id`
- `candidate_id`
- PLY / DRC metadata
- `r_bytes`，即 measured 文件本体字节数
- `pdl_ratio`
- `asset_ref` 与 integrity linkage

本轮使用 calibrated context：

- Longdress full-body strict PLY lookup 支持点；
- `distance_norm = 1.0` 对应 `pdl_max_dist = 1.0`；
- `distance_norm = 3.0` 对应 `pdl_max_dist = 0.6`。

本轮使用 proxy / derived：

- `q_base = pdl_ratio`，provenance 为 `proxy`；
- `d_ms = 0.0`，provenance 为 `proxy`；
- `p_sal = visibility = screen_area = 1.0`，provenance 为 `proxy`；
- `Budget_total` 由 lookup-allowed 候选的 `R` 派生，provenance 为 `derived`。

`eta = 0`，因此 `d_ms` 不参与本轮净效用；这不是目标端处理耗时为零的测量结论。本轮不比较 PLY 与 DRC 的端侧处理开销。

## 已验证资产

- handcheck 3x3 fixture 已迁移为 generic-candidate JSON。
- calibration-informed proxy fixture 已迁移为 generic-candidate JSON。
- tests-only exhaustive oracle 继续只在测试中使用。
- frame 1051 metadata bridge 可只读检查 data-prep 的真实 PLY/DRC metadata。
- frame 1051 behavior pilot 可在 6 个场景中运行现有 solver，并检查预算、allowed candidate、catalog linkage、provenance 和 result JSON invariants。

## 下一步边界

后续仍需研究者冻结或准备：

- target-side `d_ms` 测量或明确 proxy profile；
- format-aware / DRC-aware `q_base`；
- 真实 saliency、visibility、screen_area、distance assignment 或 viewport pipeline；
- Stage1 `Budget_total` 在线接口；
- 是否以及如何做 Pareto pruning、baseline、batch runner、plotting 或播放器接入。

当前仍未实现 target-aware lookup、Pareto pruning、baseline、batch runner、plotting、播放器接入、目标端 benchmark、DRC-aware 质量测量或正式性能实验。
