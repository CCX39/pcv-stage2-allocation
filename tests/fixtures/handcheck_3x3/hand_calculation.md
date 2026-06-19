Languages: English | [中文](hand_calculation.zh-CN.md)

# Handcheck 3x3 Stage2 Fixture

This fixture is a tiny synthetic reference case for later Stage2 validation. It uses 3 tiles and 3 quality levels per tile to check lookup `cap` semantics, exactly-one-level selection, `B_min_feasible`, `INFEASIBLE_BUDGET`, net utility calculation, and budget feasibility.

It is not real Longdress experiment data and does not mean that the Stage2 solver has been implemented.

## Assumptions

To avoid freezing a distance-sensitivity function in Phase 0C, this handcheck uses:

```text
G(d_i) = 1.0
eta = 0.1
```

Therefore:

```text
spatial_utility_i,j = p_sal_i * visibility_i * screen_area_i * q_base_i,j
net_utility_i,j = spatial_utility_i,j - eta * d_ms_i,j
```

All fixture values are synthetic.

## Lookup Cap Resolution

The lookup profile uses confirmed D0-1 `cap` semantics:

```text
allowed_levels = {1, ..., lookup_level}
```

| Tile | distance_norm | lookup_level | allowed_levels | Notes |
|---|---:|---:|---|---|
| T1_near_important | 1.0 | 3 | {1,2,3} | all levels allowed |
| T2_mid_visible | 3.0 | 2 | {1,2} | level 3 exists in input but is clipped |
| T3_far_capped | 6.0 | 1 | {1} | levels 2 and 3 exist in input but are clipped |

## Per-Level Utility

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

T2 level 3 is not allowed after lookup cap.

### T3_far_capped

| level_id | q_base | r_bytes | d_ms | spatial_utility | net_utility |
|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 30 | 1 | 4 | 3.9 |
| 2 | 2 | 70 | 2 | 8 | 7.8 |
| 3 | 3 | 110 | 3 | 12 | 11.7 |

T3 levels 2 and 3 are not allowed after lookup cap.

## Minimum Feasible Budget

After lookup cap:

```text
B_min_feasible = 50 + 40 + 30 = 120
```

This comes from selecting the minimum data-size allowed level for each participating tile.

## Success Case

`input_success.json` uses:

```text
budget_total_bytes = 210
```

Allowed combination comparison:

| Combination | total_bytes | total_net_utility | Feasible under 210? | Notes |
|---|---:|---:|---|---|
| T1L3 + T2L2 + T3L1 | 240 | 45.4 | no | exceeds budget |
| T1L3 + T2L1 + T3L1 | 200 | 39.5 | yes | selected |
| T1L2 + T2L2 + T3L1 | 200 | 35.5 | yes | lower utility than selected |
| T1L2 + T2L1 + T3L1 | 160 | 29.6 | yes | lower utility |
| T1L1 + T2L2 + T3L1 | 160 | 25.6 | yes | lower utility |
| T1L1 + T2L1 + T3L1 | 120 | 19.7 | yes | minimum feasible combination |

The highest-utility allowed combination, T1L3 + T2L2 + T3L1, uses 240 bytes and is infeasible. The best feasible allowed combination is:

```text
T1_near_important -> level 3
T2_mid_visible    -> level 1
T3_far_capped     -> level 1
```

Totals:

```text
total_bytes = 130 + 40 + 30 = 200
total_spatial_utility = 30 + 6 + 4 = 40
total_decode_ms = 3 + 1 + 1 = 5
total_net_utility = 29.7 + 5.9 + 3.9 = 39.5
budget_utilization = 200 / 210 = 0.9523809524
```

`expected_success_result.json` records this manual result. `lambda_search.enabled` is `false` because this file is a reference result, not a solver trace.

## Infeasible Case

`input_infeasible.json` uses:

```text
budget_total_bytes = 100
```

Since:

```text
B_min_feasible = 120
budget_gap = 120 - 100 = 20
```

the expected status is:

```text
INFEASIBLE_BUDGET
```

This must not be repaired by dropping a tile, choosing a lookup-disallowed level, silently exceeding budget, automatically raising the budget, or adding an empty level.

`expected_infeasible_result.json` records `selected_tiles = []`, keeps lookup resolution for the three tiles, and includes an `INFEASIBLE_BUDGET` error entry.

## Boundary

This fixture is a manual handcheck reference. It does not implement the solver, does not test a real renderer, and does not represent a formal experiment result.
