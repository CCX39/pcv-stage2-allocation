# 当前实现状态

当前仓库阶段：**Phase 2B.2：中文文档收口与英文 Markdown 文档清理**。

本阶段只整理仓库说明文档的语言、标题、内部链接和中英文镜像文件组织方式，不修改求解器行为、Schema、Python 代码、测试、fixture、脚本或任何真实资产。

## 已完成的 Phase 2B.1

Phase 2B.1 已完成 Stage2 allocation 的 generic-candidate 迁移。运行时输入已经从连续 PDL 质量档位改为通用传输版本候选。

每个 tile 包含 `candidates[]`，候选记录：

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

## 已验证资产

- handcheck 3x3 fixture 已迁移为 generic-candidate JSON，并保留 PDL-only 特例的手算结果。
- calibration-informed proxy fixture 已迁移为 generic-candidate JSON，保留 full-body strict PDL lookup 来源与 proxy tile metadata 边界。
- tests-only exhaustive oracle 继续只在测试中使用，用于 tiny-instance exact feasible reference。
- result schema 输出 `selected_candidate_id`、`selected_candidate_snapshot`、`allowed_candidate_ids`、`lookup_pdl_max_dist`、lambda selected candidates 和 candidate switch repair trace。

## 当前文档整理结果

Phase 2B.2 将项目说明统一收敛为中文 Markdown。英文镜像说明文档被删除；保留的中文文档保持 `.zh-CN.md` 文件名，不改为中文文件名，也不新建英文镜像。

## 下一步边界

- Phase 2B.3：真实候选元数据只读桥接，尚未开始。
- Phase 2B.4：frame 1051 求解器行为验证，尚未开始。

当前仍未接入真实 artifact root，未读取或生成真实 PLY/DRC assets，未生成 frame 1051 正式 Stage2Input，未测 target-side `D`，未构建 DRC-aware 或 format-aware `q`，未实现 target-aware lookup、Pareto pruning、baseline、batch runner、plotting 或播放器接入。
