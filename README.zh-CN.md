# pcv-stage2-allocation

本仓库实现 Work1 Stage2 allocation 的低复杂度运行时路径。当前阶段为 **Phase 2B.2：中文文档收口与英文 Markdown 文档清理**。

Phase 2B.1 已完成从连续 PDL 质量档位到通用传输版本候选（generic transmission candidate）的运行时迁移。本轮 Phase 2B.2 只整理说明文档的语言和组织方式，不改变求解器行为、Schema、测试或数据资产。

## 当前运行时语义

Stage2 不再把候选解释为连续质量档位。每个 tile 包含一组通用传输版本候选，候选可以表达：

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

`candidate_id` 只表示 tile 内候选身份，用于引用和最后稳定平局处理；它不表示质量、数据量、处理耗时或视觉收益顺序。`pdl_ratio` 只用于当前 PDL lookup 投影，不代表最终视觉质量的全序。

PLY 与 DRC 可以在同一 tile、同一 PDL 下作为并列候选存在。`R`、`D`、`q` 的比较必须依赖显式数值，不依赖候选数组顺序、`candidate_id`、QP、codec 或 file format。

数据来源标记（provenance）的受控词汇为：

```text
measured
calibrated
derived
proxy
synthetic
```

## Lookup

当前 lookup 仍使用 `semantics = cap`，但 cap 对象是候选的 PDL metadata：

```text
allowed_candidate_ids = {candidate | candidate.pdl_ratio <= pdl_max_dist}
```

启用 PDL lookup 时，参与 lookup 的候选必须显式提供合法 `pdl_ratio`。当前 PDL lookup 来自 PLY nested-PDL calibration，不是 DRC-aware quality measurement，也不是最终 QoE 结论。`normalized_render_distance` 是归一化渲染距离，不是物理米。

非空 `target_id` 的 target-aware lookup 仍会被拒绝。

## 当前 solver

当前 runtime solver 是低复杂度近似路径：

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

残余预算局部修正（local repair）已从旧的“档位升级”改为候选切换（candidate switch）。它只考虑：

```text
Delta_R > 0
Delta_Uhat > 0
Delta_R <= residual_budget
```

local repair 不依赖 `candidate_id`、PDL、QP、codec 或 file format 的大小方向，并且不会选择 lookup 已剔除的候选。

## 测试资产

- `tests/fixtures/handcheck_3x3/`：合成 3 tile generic-candidate 手算 fixture，保留旧 PDL-only 特例下的数学回归语义。
- `tests/fixtures/calibration_informed_proxy/`：calibration-informed proxy fixture。lookup 来自 Longdress full-body strict PDL support points，其余 tile metadata、`R`、`D`、`q`、预算与空间因子均为 proxy。
- `tests/helpers/exhaustive_oracle.py`：仅供测试使用的小规模 exhaustive oracle，用于 tiny instance exact feasible reference；不是 runtime solver，不是 baseline，不用于大规模实验。

## 阶段边界

- Phase 2B.1：已完成通用候选语义迁移。
- Phase 2B.2：当前阶段，只做中文文档收口与英文 Markdown 清理。
- Phase 2B.3：真实候选元数据只读桥接，尚未开始。
- Phase 2B.4：frame 1051 求解器行为验证，尚未开始。

本仓库当前未接入真实 artifact root，未读取或生成真实 PLY/DRC assets，未构建 frame 1051 正式输入，未测 target-side `D`，未构建 DRC-aware 或 format-aware `q`，未实现 target-aware lookup、Pareto pruning、baseline、batch runner、plotting 或播放器接入。
