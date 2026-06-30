# Implementation State Current

当前仓库状态：**Phase 2B.1 generic transmission candidate 迁移完成**。

## 运行时语义

Stage2 allocation 的运行时输入已经从连续 PDL 质量档位迁移为通用传输版本候选。每个 tile 包含 `candidates[]`，每个候选记录：

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

`candidate_id` 只用于身份标识和最后稳定平局处理，不承担质量、数据量、处理耗时或视觉收益顺序。`pdl_ratio` 只用于当前 PDL lookup 投影，不表示最终视觉质量全序。PLY 与 DRC 可以作为并列候选类别存在。

## Lookup

当前 lookup 仍使用 `semantics = cap`，但 cap 对象已经改为 PDL metadata 上界：

```text
allowed_candidate_ids = {candidate | candidate.pdl_ratio <= pdl_max_dist}
```

启用 PDL lookup 时，候选缺少 `pdl_ratio` 会返回结构化 `INVALID_INPUT`。非空 `target_id` 的 target-aware lookup 仍返回 `INVALID_LOOKUP`，不会被静默解释为 `tile_id`。

当前 lookup 来源仍是 PLY nested-PDL calibration，不是 DRC-aware 质量测量，也不是最终 QoE 结论。

## Solver

当前 runtime solver 是：

```text
lambda search + residual-budget local repair
```

它不是 exact MCKP、动态规划、branch-and-bound 或 baseline。固定 lambda 下按显式数值选择：

```text
argmax_j [Uhat_i,j - lambda * R_i,j]
```

平局顺序为 penalized score 更高、`R` 更小、`D` 更小、最后按 `candidate_id` 稳定决胜。

local repair 已改为候选切换。每一步只考虑：

```text
Delta_R > 0
Delta_Uhat > 0
Delta_R <= residual_budget
```

repair 不依赖候选编号、PDL、QP、codec 或 file format 的大小方向。

## 已验证资产

- handcheck 3x3 fixture 已迁移为 generic-candidate JSON，并保留 PDL-only 特例的手算结果。
- calibration-informed proxy fixture 已迁移为 generic-candidate JSON，保留 full-body strict PDL lookup 来源与 proxy tile metadata 边界。
- `tests/helpers/exhaustive_oracle.py` 继续仅在测试中使用，枚举 lookup 后允许候选组合，用于 tiny-instance exact feasible reference。
- result schema 现在输出 `selected_candidate_id`、`selected_candidate_snapshot`、`allowed_candidate_ids`、`lookup_pdl_max_dist`、lambda selected candidates 和 candidate switch repair trace。

## 未做与下一步边界

本阶段未接入真实 artifact root，未读取或生成真实 PLY/DRC assets，未生成 frame 1051 正式 Stage2Input，未测 target-side `D`，未构建 DRC-aware 或 format-aware `q`，未实现 target-aware lookup、Pareto pruning、baseline、批量实验、绘图或播放器接入。

后续 Phase 2B.2 或 frame 1051 pilot 需要处理真实 asset 映射、候选 provenance 从 proxy 到 measured/calibrated 的过渡、以及正式输入生成链路。
