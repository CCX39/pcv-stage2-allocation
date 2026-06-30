# 决策记录

本文记录当前仓库已经冻结的工程决策。Phase 2B.2 只整理文档语言和 Markdown 组织，不改变这些技术决策。

## D0-1 / D2B.1：lookup 是基于 candidate.pdl_ratio 的 PDL 上界筛选

| 项 | 内容 |
|---|---|
| 决策 | lookup `semantics = cap` 表示 `candidate.pdl_ratio <= pdl_max_dist` 的候选保留规则。 |
| 背景 | 旧运行时曾把 lookup 解释为连续 PDL 档位前缀。Phase 2B.1 已迁移为 generic transmission candidate，候选不再天然全序。 |
| 影响 | 预处理只按显式 `pdl_ratio` 筛选，不按 `candidate_id`、数组位置、QP、codec 或 file format 筛选。 |
| 边界 | 当前 PDL lookup 来自 PLY nested-PDL calibration，不是 DRC-aware quality measurement，也不是最终 QoE 结论。 |

相同 PDL 下的 PLY、DRC 或不同 codec 参数候选应同时保留。高于 `pdl_max_dist` 的候选被剔除并记录在 lookup resolution 中。

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

搜索内 best-feasible ranking：

1. `total_net_utility` 更高；
2. 若在 `score_epsilon` 内近似相同，预算利用率更高；
3. 若仍相同，`total_decode_ms` 更低；
4. 若仍相同，按排序后的 `(tile_id, selected_candidate_id)` 序列决胜。

`candidate_id` 不承担质量顺序，只是最后稳定项。

## D1F / D2B.1：local repair 是候选切换

local repair 从 lambda search 的最佳预算可行 seed candidate 开始，使用剩余预算做轻量候选切换。它只考虑：

```text
Delta_R > 0
Delta_Uhat > 0
Delta_R <= residual_budget
```

repair 不依赖候选编号、PDL、QP、codec 或 file format 的大小方向。trace 记录 `from_candidate_id`、`to_candidate_id`、增量、剩余预算变化与选择原因。

## D1G：小规模 exhaustive oracle 仅用于测试

`tests/helpers/exhaustive_oracle.py` 只用于 tiny-instance 测试。它枚举 lookup 后允许候选组合，返回 exact feasible reference，用于验证 runtime solver 不违反硬约束且不超过小规模精确可行参考。

它不是 runtime solver，不是 baseline，不用于大规模输入、批量实验或论文实时方法描述。

## D2A / D2B.1：calibration-informed proxy fixture 的边界

calibration-informed proxy fixture 使用 Longdress full-body strict PDL lookup support points，但 tile identity、空间因子、`R`、`D`、`q`、预算和 `asset_ref` 均为 proxy。

该 fixture 只验证输入映射、lookup cap、预算状态和可审查输出。它不能用于声明 Longdress tile-level 传输收益、真实解码开销、真实播放器 QoE 或算法性能提升。

## D2B.2：项目说明文档只保留中文

Phase 2B.2 将仓库说明文档统一收敛为中文 Markdown。对应英文镜像被删除；保留的中文文档继续使用 `.zh-CN.md` 文件名。

该阶段不修改代码、Schema、fixture、测试、脚本或算法语义。

## 后续阶段编号

- Phase 2B.3：真实候选元数据只读桥接，尚未开始。
- Phase 2B.4：frame 1051 求解器行为验证，尚未开始。

本轮不接入真实 artifact root，不读取或生成真实 PLY/DRC assets，不生成 frame 1051 正式 Stage2Input，不测 target-side `D`，不构建 DRC-aware 或 format-aware `q`，不实现 target-aware lookup、Pareto pruning、baseline、batch runner、plotting 或播放器接入。
