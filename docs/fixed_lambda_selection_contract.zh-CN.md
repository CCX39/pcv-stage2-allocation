语言：[English](fixed_lambda_selection_contract.md) | 中文

# 固定 Lambda 选档契约

状态：阶段1B实现说明。

本文说明阶段1B新增的固定 `lambda` 选档内核。它是后续乘子搜索要复用的局部能力，不是完整 Stage2 求解器。

## 选档规则

每个分块先按已经确认的 lookup cap 语义解析候选集合：

```text
allowed_levels_i = {level_id | level_id <= min(lookup_level_i, max_existing_level_i)}
```

固定 `lambda` 内核只在 `allowed_levels_i` 内选一个档位：

```text
argmax_j [
    net_utility_i,j - lambda_value * r_bytes_i,j
]
```

输出中的 `total_net_utility` 是原始净效用之和；`total_penalized_score` 才是扣除 `lambda` 数据量惩罚后的得分之和。

## 平局处理

单个分块的平局顺序来自 `docs/decision_log.zh-CN.md` 和 `docs/stage2_mvp_contract.zh-CN.md` 中已经冻结的 D0-3 规则：

1. 惩罚后得分更高；
2. 若得分在容差内近似相同，选择 `r_bytes` 更小的档位；
3. 若仍相同，选择 `d_ms` 更小的档位；
4. 若仍相同，选择 `level_id` 更小的档位。

实现中保留 `score_epsilon`，用于判断得分是否近似相同。

## Candidate 不是最终结果

固定 `lambda` 输出只是候选选档。它的 `is_budget_feasible` 只表示当前候选是否满足 `budget_total_bytes`。

预算可行不等于正式 `SUCCESS`；超预算也不等于正式 `INFEASIBLE_BUDGET`。最终状态组装、预算不可行处理、`lambda` 上界扩展、二分搜索、最佳可行解记录和剩余预算局部升级，仍属于后续完整求解器的职责。

## 预算行为

固定 `lambda` candidate 可以超预算，因为它对每个分块独立最大化松弛后的局部得分。恢复预算可行性是后续乘子搜索和最终约束复核要做的事。

## 范围边界

阶段1B没有实现：

- `lambda` 上界扩展；
- 二分搜索；
- 最佳可行解记录；
- 剩余预算局部升级；
- 最终 `solve_stage2` API；
- 原始 MCKP 的穷举精确求解；
- baseline 算法；
- Longdress 输入生成；
- 批量实验；
- 绘图；
- 播放器集成。

固定 `lambda` 内核也不是原始 MCKP 的精确全局求解器。它只是计划中的拉格朗日松弛流程里的一个局部构件。
