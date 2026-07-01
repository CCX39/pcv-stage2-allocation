# 决策记录

本文记录当前仓库已经冻结的工程决策。

## D0-1 / D2B.1：lookup 是基于 candidate.pdl_ratio 的 PDL 上界筛选

| 项 | 内容 |
|---|---|
| 决策 | lookup `semantics = cap` 表示 `candidate.pdl_ratio <= pdl_max_dist` 的候选保留规则。 |
| 背景 | 旧运行时曾把 lookup 解释为连续 PDL 档位前缀。Phase 2B.1 已迁移为 generic transmission candidate，候选不再天然全序。 |
| 影响 | 预处理只按显式 `pdl_ratio` 筛选，不按 `candidate_id`、数组位置、`qp`、codec 或 `file_format` 筛选。 |
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

repair 不依赖候选编号、PDL、`qp`、codec 或 `file_format` 的大小方向。trace 记录 `from_candidate_id`、`to_candidate_id`、增量、剩余预算变化与选择原因。

## D1G：小规模 exhaustive oracle 仅用于测试

`tests/helpers/exhaustive_oracle.py` 只用于 tiny-instance 测试。它枚举 lookup 后允许候选组合，返回 exact feasible reference，用于验证 runtime solver 不违反硬约束且不超过小规模精确可行参考。

它不是 runtime solver，不是 baseline，不用于大规模输入、批量实验或论文实时方法描述。

## D2A / D2B.1：calibration-informed proxy fixture 的边界

calibration-informed proxy fixture 使用 Longdress full-body strict PDL lookup support points，但 tile identity、空间因子、`R`、`D`、`q`、预算和 `asset_ref` 均为 proxy。

该 fixture 只验证输入映射、lookup cap、预算状态和可审查输出。它不能用于声明 Longdress tile-level 传输收益、真实解码开销、真实播放器 QoE 或算法性能提升。

## D2B.2：项目说明文档只保留中文

Phase 2B.2 将仓库说明文档统一收敛为中文 Markdown。对应英文镜像被删除；保留的中文文档继续使用 `.zh-CN.md` 文件名。

该阶段不修改代码、Schema、fixture、测试、脚本或算法语义。

## D2B.3：frame 1051 metadata bridge 是只读目录桥接

Phase 2B.3 新增 read-only metadata bridge。它显式接收本机 `pcv-stage2-data-prep` root，只读取轻量 JSON manifest/report，并通过 stat size 校验 manifest 引用文件。

bridge fail-closed：Longdress / frame 1051 / G128 / 5 PDL / 3 qp / Draco / point-cloud / `cl=10`、40 non-empty tile、200 PLY、600 DRC、800 total candidate、相对路径、文件存在性、manifest size、source PLY linkage 或 validation 摘要任一不一致都会失败。

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

真实事实只包括候选身份、metadata、`pdl_ratio`、`asset_ref` 和 measured file body `r_bytes`。`r_bytes` 可作为 `R_i,j` 的文件本体字节记账值参与预算和 `lambda * R_i,j`，但不是端到端网络总开销。

该 pilot 的选择分布只是在上述 proxy profile 下的行为输出，不能解释为 PLY 或 DRC 的实际质量、处理开销、网络性能或 QoE 更优。

## 后续仍未完成

后续仍需研究者确认或准备 target-side `d_ms`、format-aware / DRC-aware `q_base`、真实空间因子、真实 distance assignment、Stage1 `Budget_total` 接口，以及是否进入 Pareto pruning、baseline、batch runner、plotting 或播放器接入。

本仓库仍未实现 target-aware lookup、Pareto pruning、baseline、batch runner、plotting、播放器接入或目标端 benchmark。
