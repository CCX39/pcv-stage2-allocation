语言：[English](hand_calculation.md) | 中文

# 3x3 Stage2 手算 Fixture

本 fixture 是一个很小的合成手算样例，用于后续验证 Stage2 的 lookup `cap` 语义、每个分块恰好选择一个档位、`B_min_feasible`、`INFEASIBLE_BUDGET`、净效用计算和预算可行性。

它不是真实 Longdress 实验数据，也不表示 Stage2 求解器已经实现。

## 基本假设

为避免在阶段0C提前固定 `G(d_i)` 的解析形式，本手算统一采用：

```text
G(d_i) = 1.0
eta = 0.1
```

因此：

```text
spatial_utility_i,j = p_sal_i * visibility_i * screen_area_i * q_base_i,j
net_utility_i,j = spatial_utility_i,j - eta * d_ms_i,j
```

所有数值都是合成手算值。

## Lookup Cap 解析

lookup 使用 D0-1 已确认的 `cap` 语义：

```text
allowed_levels = {1, ..., lookup_level}
```

| 分块 | distance_norm | lookup_level | allowed_levels | 说明 |
|---|---:|---:|---|---|
| T1_near_important | 1.0 | 3 | {1,2,3} | 三个档位都允许 |
| T2_mid_visible | 3.0 | 2 | {1,2} | level 3 在输入中存在，但被 lookup 裁剪 |
| T3_far_capped | 6.0 | 1 | {1} | level 2 和 level 3 在输入中存在，但被 lookup 裁剪 |

## 各档位效用

### T1_near_important

| level_id | q_base | r_bytes | d_ms | spatial_utility | net_utility |
|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 50 | 1 | 10 | 9.9 |
| 2 | 2 | 90 | 2 | 20 | 19.8 |
| 3 | 3 | 130 | 3 | 30 | 29.7 |

### T2_mid_visible

| level_id | q_base | r_bytes | d_ms | spatial_utility | net_utility |
|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 40 | 1 | 6 | 5.9 |
| 2 | 2 | 80 | 2 | 12 | 11.8 |
| 3 | 3 | 120 | 3 | 18 | 17.7 |

T2 的 level 3 经过 lookup cap 后不允许选择。

### T3_far_capped

| level_id | q_base | r_bytes | d_ms | spatial_utility | net_utility |
|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 30 | 1 | 4 | 3.9 |
| 2 | 2 | 70 | 2 | 8 | 7.8 |
| 3 | 3 | 110 | 3 | 12 | 11.7 |

T3 的 level 2 和 level 3 经过 lookup cap 后不允许选择。

## 最低可行预算

经过 lookup cap 后：

```text
B_min_feasible = 50 + 40 + 30 = 120
```

这里取的是每个参与决策分块在允许候选集合中的最低数据量档位。

## Success Case

`input_success.json` 使用：

```text
budget_total_bytes = 210
```

允许组合比较：

| 组合 | total_bytes | total_net_utility | 在 210 预算下是否可行 | 说明 |
|---|---:|---:|---|---|
| T1L3 + T2L2 + T3L1 | 240 | 45.4 | 否 | 超预算 |
| T1L3 + T2L1 + T3L1 | 200 | 39.5 | 是 | 选中 |
| T1L2 + T2L2 + T3L1 | 200 | 35.5 | 是 | 效用低于选中组合 |
| T1L2 + T2L1 + T3L1 | 160 | 29.6 | 是 | 效用更低 |
| T1L1 + T2L2 + T3L1 | 160 | 25.6 | 是 | 效用更低 |
| T1L1 + T2L1 + T3L1 | 120 | 19.7 | 是 | 最低可行组合 |

允许组合中效用最高的是 T1L3 + T2L2 + T3L1，但它需要 240 bytes，超过预算。预算内最优手算组合为：

```text
T1_near_important -> level 3
T2_mid_visible    -> level 1
T3_far_capped     -> level 1
```

汇总结果：

```text
total_bytes = 130 + 40 + 30 = 200
total_spatial_utility = 30 + 6 + 4 = 40
total_decode_ms = 3 + 1 + 1 = 5
total_net_utility = 29.7 + 5.9 + 3.9 = 39.5
budget_utilization = 200 / 210 = 0.9523809524
```

`expected_success_result.json` 记录这个手算结果。`lambda_search.enabled` 为 `false`，因为该文件是手算参考结果，不是求解器搜索轨迹。

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

不能通过漏选分块、选择 lookup 不允许的档位、静默超预算、自动提高预算或加入空档位来伪造可行结果。

`expected_infeasible_result.json` 记录 `selected_tiles = []`，保留三个分块的 lookup 解析结果，并在 `errors` 中记录 `INFEASIBLE_BUDGET`。

## 边界说明

本 fixture 只是人工手算参考，不实现求解器，不测试真实渲染器，也不代表正式实验结果。
