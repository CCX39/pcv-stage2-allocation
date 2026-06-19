语言：[English](decision_log.md) | 中文

# 决策记录

状态：阶段0A.1草案。

## 总表

| 编号 | 主题 | 状态 |
|---|---|---|
| D0-1 | lookup 语义 | RESOLVED_USER_CONFIRMED |
| D0-2 | 预算不可行行为 | RESOLVED_USER_CONFIRMED |
| D0-3 | lambda 搜索规则 | RESOLVED_USER_CONFIRMED |
| D0-4 | 数据来源词汇 | DRAFT |

```text
D0-1 lookup semantics       RESOLVED_USER_CONFIRMED
D0-2 infeasible budget      RESOLVED_USER_CONFIRMED
D0-3 lambda search rules    RESOLVED_USER_CONFIRMED
D0-4 provenance vocabulary  DRAFT
```

## D0-1 lookup 语义

| 字段 | 记录 |
|---|---|
| 决策编号 | D0-1 |
| 主题 | 距离到质量 lookup 的运行时语义 |
| 背景 | full-body 与 near-field 标定为 Stage2 候选集合构造提供视距到质量档位依据。实现求解器前必须固定 lookup 的运行时含义。 |
| 可选方案 | `cap`、`floor`、`fixed`、纯 `recommended` |
| 已确认方案 | 采用 `cap` 语义，已由研究者确认 |
| 优点 | 可在中远距离移除不必要高档位，同时保持 MCKP 结构不变。 |
| 风险 | 如果后续文字写成“near-field 必须选择 level 5”，就会违背已确认语义。 |
| 对代码的影响 | 候选集合构造必须使用 `allowed_levels = {1, ..., lookup_level}`。 |
| 对实验的影响 | lookup 结果作为标定得到的候选上界，而不是直接作为最终选择。 |
| 对论文或汇报表述的影响 | 必须说明 lookup 给出当前距离条件下最高有必要保留的候选质量档位。 |
| 当前状态 | RESOLVED_USER_CONFIRMED |
| 后续确认责任人 | 研究者在后续文档和实现中持续核对该语义。 |

已确认细节：

- 该决策已由研究者确认。
- 当前 MVP 采用 `cap` 语义。
- lookup 表示当前距离条件下最高有必要保留的候选质量档位。
- 候选集合为 `{1, ..., lookup_level}`。
- full-body 中远距离可能裁剪高质量档位。
- near-field level 5 表示不进行候选上界裁剪。
- near-field 不等于强制最终选择最高档。
- `floor`、`fixed` 和纯软推荐未被当前 MVP 采用。

## D0-2 预算不可行行为

| 字段 | 记录 |
|---|---|
| 决策编号 | D0-2 |
| 主题 | `Budget_total` 低于最低可行数据量时的行为 |
| 背景 | 每个参与决策的分块必须恰好选择一个允许档位。如果总预算低于所有分块最低允许数据量之和，当前硬约束无法同时满足。 |
| 可选方案 | 返回 `INFEASIBLE_BUDGET`；请求 Stage1 提高预算；放宽某些硬约束；允许部分不可见分块不下载；引入显式空档位或跳过档位。 |
| 已确认方案 | 当 `Budget_total < B_min_feasible` 时显式返回 `INFEASIBLE_BUDGET`。 |
| 优点 | 显式不可行状态可以避免静默违反预算或候选集合约束。 |
| 风险 | 上层流程或实验脚本需要处理显式不可行状态。 |
| 对代码的影响 | 后续求解器必须在乘子搜索前检查 `B_min_feasible`，并返回结构化不可行输出。 |
| 对实验的影响 | 实验报告需要区分输入预算与硬约束不兼容，以及算法本身失败。 |
| 对论文或汇报表述的影响 | 应描述为硬约束不兼容，而不是求解器崩溃。 |
| 当前状态 | RESOLVED_USER_CONFIRMED |
| 后续确认责任人 | 研究者在后续实现和报告中核对该默认策略。 |

最低可行预算概念：

```text
B_min_feasible =
sum over i [
    min R_i,j
    for j in allowed_levels_i
]
```

如果：

```text
Budget_total < B_min_feasible
```

则求解器必须返回如下结构化信息：

```text
status = INFEASIBLE_BUDGET
budget_total = ...
b_min_feasible = ...
budget_gap = b_min_feasible - budget_total
```

已确认约束：

- 每个参与决策的分块仍必须恰好选择一个质量档位；
- 不允许静默超预算；
- 不允许通过漏选参与决策的分块伪造预算可行；
- 不允许自动放宽 lookup 候选集合；
- 不允许自动请求 Stage1 修改 `Budget_total`；
- MVP 不引入空档位或跳过档位。

## D0-3 lambda 搜索规则

| 字段 | 记录 |
|---|---|
| 决策编号 | D0-3 |
| 主题 | 一维乘子搜索的工程规则 |
| 背景 | 参考文档支持拉格朗日松弛与乘子搜索。阶段0A.1冻结括区间、可行解记录、平局处理和停止行为等 MVP 默认规则。 |
| 可选方案 | 固定或自适应上界；固定容差；确定性平局处理；最大迭代次数；保留最近可行解；在得分接近的可行解之间按得分或数据量排序。 |
| 已确认方案 | 自适应上界括区间、二分搜索、最佳可行解记录、确定性平局处理，以及在 `B_min_feasible <= Budget_total` 但仍无法恢复可行解时返回明确异常状态。 |
| 优点 | 冻结这些规则有助于确定性、可审查性和可复现性。 |
| 风险 | 不同平局处理或容差可能在得分接近时改变最终档位选择。 |
| 对代码的影响 | 后续实现必须暴露并记录搜索配置和搜索轨迹。 |
| 对实验的影响 | 实验必须记录搜索设置以保证可复现。 |
| 对论文或汇报表述的影响 | 搜索依据应写为总数据需求随 `lambda` 单调不增，而不是证明原始 MCKP 全局最优。 |
| 当前状态 | RESOLVED_USER_CONFIRMED |
| 后续确认责任人 | 研究者在后续实现和报告中核对该默认策略。 |

已确认规则：

- 搜索前先完成输入校验、lookup 解析、`allowed_levels` 构造和 `B_min_feasible` 检查。
- 如果预算不可行，直接返回 `INFEASIBLE_BUDGET`，不进入乘子搜索。
- 使用 `lambda_low = 0` 和自适应正数 `lambda_high`。
- 持续加倍 `lambda_high`，直到出现预算可行解或达到 `lambda_max_bracket_steps`。
- 记录 `lambda_initial_high`、`lambda_max_bracket_steps`、`score_epsilon`、`lambda_epsilon` 和 `max_iterations` 等配置。
- 二分搜索中记录 `lambda`、`total_bytes`、`total_net_utility`、`is_budget_feasible` 和 `selected_levels`。
- 每次出现预算可行解时，更新当前最佳可行解。

最佳可行解排序：

1. 总净效用更高；
2. 若近似相同，预算利用率更高；
3. 若仍相同，总预计解码耗时更低；
4. 若仍相同，按 `tile_id` 和 `level_id` 的确定性顺序比较。

固定 `lambda` 下单个分块选档的平局规则：

1. 拉格朗日得分更高；
2. 若得分在容差内近似相同，选择数据量更小的档位；
3. 若仍相同，选择解码耗时更小的档位；
4. 若仍相同，选择 `level_id` 更小的档位。

停止规则：

- `max_iterations` 是主要停止条件。
- 可以使用 `lambda_epsilon` 和 `no_change_rounds` 作为辅助停止条件。
- 不得因为搜索未完全收敛而输出违反预算的结果。
- 若在 `B_min_feasible <= Budget_total` 的情况下仍无法获得可行解，应返回 `NUMERICAL_ERROR` 或 `INTERNAL_CONSTRAINT_VIOLATION`，并记录搜索轨迹。

剩余预算局部升级仍作为后续实现计划保留。升级必须限制在 `allowed_levels` 内，满足 `delta_R > 0` 和 `delta_U > 0`，并保持预算和 lookup 约束。

## D0-4 数据来源词汇

| 字段 | 记录 |
|---|---|
| 决策编号 | D0-4 |
| 主题 | 数据来源与可信度词汇 |
| 背景 | 未来 Stage2 输入会混合真实测量、离线标定、几何推导、代理值和合成值。文档必须防止把代理值或合成值写成真实测量结果。 |
| 可选方案 | 先定义一组小型受控词汇，后续 Schema 和字段设计时再细化。 |
| 当前候选 | `measured`、`calibrated`、`derived`、`proxy`、`synthetic` |
| 优点 | 提升可追溯性，避免夸大实验依据。 |
| 风险 | 字段级数据来源设计尚未完成，因此词汇必须保持草案状态。 |
| 对代码的影响 | 后续 Schema 和输出应包含数据来源字段。 |
| 对实验的影响 | 报告必须区分真实测量、代理数据和合成数据。 |
| 对论文或汇报表述的影响 | 结论需要说明数据来自标定、直接测量、推导、代理假设还是合成测试。 |
| 当前状态 | DRAFT |
| 后续确认责任人 | 研究者/用户在设计 Schema 和 fixture 时继续细化。 |

词汇草案：

- `measured`：通过真实文件、解码器、浏览器或实验管线直接测量的数据。
- `calibrated`：由离线标定得到的数据，例如距离 lookup。
- `derived`：由已知几何、相机状态或其他真实数据计算得到的数据。
- `proxy`：有物理或工程解释、但尚未直接测量的代理值。
- `synthetic`：为单元测试或受控算法实验构造的数据。
