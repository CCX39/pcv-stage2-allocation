# pcv-stage2-allocation

本仓库实现 Work1 Stage2 allocation 的低复杂度运行时路径。当前状态为**阶段2B.1：generic transmission candidate 迁移完成**。

Stage2 不再把运行时候选解释为连续 PDL 质量档位。每个 tile 现在包含一组通用传输版本候选（generic transmission candidate），候选可以表达 `pdl_ratio`、`file_format`、`codec`、`codec_params`、`asset_ref`、`r_bytes`、`d_ms`、`q_base` 和 `provenance`。

## 当前语义

- `candidate_id` 只表示 tile 内候选身份，用于引用和最后稳定平局处理；它不表示质量、数据量、解码耗时或视觉收益顺序。
- `pdl_ratio` 只用于当前 PDL lookup 投影；它不代表最终视觉质量的全序。
- PLY 与 DRC 可以在同一 tile、同一 PDL 下作为并列候选存在。
- `r_bytes`、`d_ms`、`q_base` 的比较只依赖显式数值，不依赖候选数组顺序、`candidate_id`、QP、codec 或 file format。
- provenance 受控词汇为 `measured`、`calibrated`、`derived`、`proxy`、`synthetic`。

当前启用的 lookup 仍是来自 PLY nested-PDL calibration 的 PDL metadata 上界筛选：

```text
allowed_candidate_ids = {candidate | candidate.pdl_ratio <= pdl_max_dist}
```

启用 PDL lookup 时，参与 lookup 的候选必须显式提供合法 `pdl_ratio`。当前 lookup 不是 DRC-aware 质量测量，也不是最终 QoE 结论。

## Solver

当前 runtime solver 仍是低复杂度近似路径：

```text
lookup 解析
-> B_min_feasible 检查
-> fixed-lambda per-tile argmax
-> lambda 上界扩展与二分搜索
-> 最佳预算可行 seed candidate
-> residual-budget local repair
-> 结构化 result
```

固定 lambda 下每个 tile 独立选择：

```text
argmax_j [Uhat_i,j - lambda * R_i,j]
```

同分时依次比较 penalized score、较小 `R`、较小 `D`，最后才按 `candidate_id` 稳定决胜。

local repair 已从旧的“档位升级”改为候选切换。它只考虑满足以下条件的切换：

```text
Delta_R > 0
Delta_Uhat > 0
Delta_R <= residual_budget
```

repair 不依赖 `candidate_id`、PDL、QP、codec 或 file format 的大小方向，并且不会选择 lookup 已剔除的候选。

## 测试资产

- `tests/fixtures/handcheck_3x3/`：合成 3 tile generic-candidate 手算 fixture，保留旧 PDL-only 特例下的数学回归语义。
- `tests/fixtures/calibration_informed_proxy/`：calibration-informed proxy fixture。lookup 来自 Longdress full-body strict PDL support points，其余 tile metadata、`R`、`D`、`q`、预算与空间因子均为 proxy。
- `tests/helpers/exhaustive_oracle.py`：仅供测试使用的小规模 exhaustive oracle，用于 tiny instance exact feasible reference；不是 runtime solver，不是 baseline，不用于大规模实验。

## 明确未做

本阶段未接入真实 artifact root，未读取或生成真实 PLY/DRC assets，未构建 frame 1051 正式输入，未测 target-side `D`，未构建 DRC-aware 或 format-aware `q`，未实现 target-aware lookup、Pareto pruning、baseline、批量实验、绘图或播放器接入。
