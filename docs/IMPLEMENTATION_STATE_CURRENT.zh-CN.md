# 当前实现状态

当前仓库阶段：**Phase 2B.3：frame 1051 真实候选元数据只读桥接**。

Phase 2B.1 已完成 Stage2 allocation 的 generic-candidate 迁移。Phase 2B.2 已将项目说明文档收口为中文 Markdown。本轮 Phase 2B.3 新增 allocation 侧的只读 metadata bridge，用于消费 `pcv-stage2-data-prep` 中 frame 1051 的轻量 JSON manifest/report，生成可审查的 candidate metadata catalog。

本轮没有修改 `solve_stage2(...)` 的算法行为、Schema、fixture 语义或真实数据资产。

## 运行时状态

运行时输入已经从连续 PDL 质量档位改为通用传输版本候选。每个 tile 包含 `candidates[]`，候选记录：

- `candidate_id`
- `pdl_ratio`
- `file_format`
- `codec`
- `codec_params`
- `asset_ref`
- `r_bytes`
- `d_ms`
- `q_base`
- `provenance`

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

## Phase 2B.3 已新增内容

- 新增 `src/pcv_stage2/frame1051_metadata_bridge.py`，只读构建 frame 1051 candidate metadata catalog。
- 新增 `scripts/build_frame1051_candidate_catalog.py`，显式接收本机 data-prep root，可将真实 catalog 写入 ignored `outputs/`。
- 新增 synthetic bridge 测试，覆盖正常 catalog 构造、同 PDL 下 PLY/DRC 并列、路径越界、source/DRC tile 集合不一致、source linkage 缺失、组合不完整、manifest size mismatch、profile mismatch、validation 未通过、pending 字段和排序稳定性。

## Metadata Bridge 边界

桥接读取的权威层级为：

1. data-prep profile config；
2. source PLY artifact manifest 与 tile index；
3. DRC generation manifest；
4. DRC validation report。

桥接只读取 JSON manifest/report，并用 `Path.stat()` 校验 manifest 引用文件存在且 size 一致。它不读取 PLY/DRC 二进制内容，不运行 Draco，不重算大文件 SHA-256，不复制真实 assets、manifest 或绝对路径。

catalog 包含 8i Longdress frame 1051、G128、40 个 non-empty tile、200 个 source PLY 候选和 600 个 DRC delivery 候选。`r_bytes` 是候选文件本体字节数，provenance 为 `measured`，可作为后续 `R_i,j` 的候选事实来源；它不是端到端网络总开销。

catalog 中 `d_ms_status = pending`、`q_base_status = pending`。本轮未填 `d_ms` 或 `q_base` 数值，未把文件大小、点数、PDL、`qp`、`codec` 或常数当作代理评分。

catalog 不是正式 `Stage2Input`，不能直接传入 `solve_stage2(...)`。Phase 2B.4 才会在研究者冻结明确 proxy scoring/profile 后，将 catalog 与评分配置组合为行为验证输入。

## 已验证资产

- handcheck 3x3 fixture 已迁移为 generic-candidate JSON，并保留 PDL-only 特例的手算结果。
- calibration-informed proxy fixture 已迁移为 generic-candidate JSON，保留 full-body strict PDL lookup 来源与 proxy tile metadata 边界。
- tests-only exhaustive oracle 继续只在测试中使用，用于 tiny-instance exact feasible reference。
- frame 1051 metadata bridge 可只读检查 data-prep 的真实 PLY/DRC metadata，并生成 ignored catalog。

## 下一步边界

- Phase 2B.4：frame 1051 求解器行为验证，尚未开始。
- Phase 2B.4 之前仍需冻结明确的 proxy scoring/profile：如何给 catalog 中候选补入 proxy `d_ms`、proxy `q_base`、预算与 tile 空间因子。

当前仍未生成 frame 1051 正式 `Stage2Input`，未对真实 frame 1051 调用 solver，未测 target-side `D`，未构建 DRC-aware 或 format-aware `q`，未实现 target-aware lookup、Pareto pruning、baseline、batch runner、plotting、播放器接入或目标端 benchmark。
