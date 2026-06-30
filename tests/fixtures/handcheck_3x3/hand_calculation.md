Languages: English | [中文](hand_calculation.zh-CN.md)

# Handcheck 3x3 Stage2 Fixture

This fixture is a tiny synthetic reference case for Stage2 validation after the generic-candidate migration. It uses 3 tiles and 3 transmission candidates per tile to check PDL lookup `cap` semantics, exactly-one-candidate selection, `B_min_feasible`, `INFEASIBLE_BUDGET`, net utility calculation, and budget feasibility.

It is not real Longdress experiment data.

## Assumptions

```text
G(d_i) = 1.0
eta = 0.1
```

```text
spatial_utility_i,j = p_sal_i * visibility_i * screen_area_i * q_base_i,j
net_utility_i,j = spatial_utility_i,j - eta * d_ms_i,j
```

All fixture values are synthetic. `candidate_id` is an identity key only.

## Lookup Cap Resolution

The lookup profile uses PDL metadata cap semantics:

```text
allowed_candidate_ids = {candidate | candidate.pdl_ratio <= pdl_max_dist}
```

| Tile | distance_norm | pdl_max_dist | allowed candidates | Notes |
|---|---:|---:|---|---|
| T1_near_important | 1.0 | 1.0 | pdl_0_2, pdl_0_6, pdl_1_0 | all candidates allowed |
| T2_mid_visible | 3.0 | 0.6 | pdl_0_2, pdl_0_6 | pdl_1_0 is clipped |
| T3_far_capped | 6.0 | 0.2 | pdl_0_2 | pdl_0_6 and pdl_1_0 are clipped |

## Per-Candidate Utility

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

## Minimum Feasible Budget

```text
B_min_feasible = 50 + 40 + 30 = 120
```

## Success Case

`input_success.json` uses:

```text
budget_total_bytes = 210
```

The best feasible allowed combination is:

```text
T1_near_important -> pdl_1_0
T2_mid_visible    -> pdl_0_2
T3_far_capped     -> pdl_0_2
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

This must not be repaired by dropping a tile, choosing a lookup-disallowed candidate, silently exceeding budget, automatically raising the budget, or adding an empty candidate.
