语言：[English](hand_calculation.md) | 中文

# 3x3 Stage2 手算 Fixture

本 fixture 是一个很小的合成手算样例，用于在 generic-candidate 迁移后验证 Stage2 的 PDL lookup `cap` 语义、每个 tile 恰好选择一个候选、`B_min_feasible`、`INFEASIBLE_BUDGET`、净效用计算和预算可行性。

它不是真实 Longdress 实验数据。

## 基本假设

```text
G(d_i) = 1.0
eta = 0.1
```

```text
spatial_utility_i,j = p_sal_i * visibility_i * screen_area_i * q_base_i,j
net_utility_i,j = spatial_utility_i,j - eta * d_ms_i,j
```

所有数值都是合成手算值。`candidate_id` 只表示候选身份，不表示质量顺序。

## Lookup Cap 解析

lookup 使用 PDL metadata 上界筛选：

```text
allowed_candidate_ids = {candidate | candidate.pdl_ratio <= pdl_max_dist}
```

| 分块 | distance_norm | pdl_max_dist | 允许候选 | 说明 |
|---|---:|---:|---|---|
| T1_near_important | 1.0 | 1.0 | pdl_0_2, pdl_0_6, pdl_1_0 | 全部候选允许 |
| T2_mid_visible | 3.0 | 0.6 | pdl_0_2, pdl_0_6 | pdl_1_0 被剔除 |
| T3_far_capped | 6.0 | 0.2 | pdl_0_2 | pdl_0_6 和 pdl_1_0 被剔除 |

## 各候选效用

### T1_near_important

| candidate_id | pdl_ratio | q_base | r_bytes | d_ms | spatial_utility | net_utility |
|---|---:|---:|---:|---:|---:|---:|
| pdl_0_2 | 0.2 | 1 | 50 | 1 | 10 | 9.9 |
| pdl_0_6 | 0.6 | 2 | 90 | 2 | 20 | 19.8 |
| pdl_1_0 | 1.0 | 3 | 130 | 3 | 30 | 29.7 |

### T2_mid_visible

| candidate_id | pdl_ratio | q_base | r_bytes | d_ms | spatial_utility | net_utility |
|---|---:|---:|---:|---:|---:|---:|
| pdl_0_2 | 0.2 | 1 | 40 | 1 | 6 | 5.9 |
| pdl_0_6 | 0.6 | 2 | 80 | 2 | 12 | 11.8 |
| pdl_1_0 | 1.0 | 3 | 120 | 3 | 18 | 17.7 |

### T3_far_capped

| candidate_id | pdl_ratio | q_base | r_bytes | d_ms | spatial_utility | net_utility |
|---|---:|---:|---:|---:|---:|---:|
| pdl_0_2 | 0.2 | 1 | 30 | 1 | 4 | 3.9 |
| pdl_0_6 | 0.6 | 2 | 70 | 2 | 8 | 7.8 |
| pdl_1_0 | 1.0 | 3 | 110 | 3 | 12 | 11.7 |

## 最低可行预算

```text
B_min_feasible = 50 + 40 + 30 = 120
```

## Success Case

`input_success.json` 使用：

```text
budget_total_bytes = 210
```

预算内最优手算组合为：

```text
T1_near_important -> pdl_1_0
T2_mid_visible    -> pdl_0_2
T3_far_capped     -> pdl_0_2
```

汇总结果：

```text
total_bytes = 130 + 40 + 30 = 200
total_spatial_utility = 30 + 6 + 4 = 40
total_decode_ms = 3 + 1 + 1 = 5
total_net_utility = 29.7 + 5.9 + 3.9 = 39.5
budget_utilization = 200 / 210 = 0.9523809524
```

`expected_success_result.json` 记录这个手算结果。`lambda_search.enabled` 为 `false`，因为该文件是手算参考，不是 solver 搜索轨迹。

## Infeasible Case

`input_infeasible.json` 使用：

```text
budget_total_bytes = 100
```

因为：

```text
B_min_feasible = 120
budget_gap = 120 - 100 = 20
```

预期状态为：

```text
INFEASIBLE_BUDGET
```

不能通过漏选 tile、选择 lookup 不允许的候选、静默超预算、自动提高预算或加入空候选来伪造可行结果。
