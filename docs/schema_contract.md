Languages: English | [中文](schema_contract.zh-CN.md)

# Stage2 MVP Schema Contract

Status: Phase 0C draft. This document explains the JSON Schema drafts added for the Stage2 MVP and how the synthetic handcheck fixture uses them. The schemas describe data format only. They do not implement validation code, a solver, or experiments.

## 1. Purpose

Phase 0B introduces three JSON Schema Draft 2020-12 files so that later phases can describe Stage2 inputs, distance lookup profiles, and future solver outputs consistently:

- `schemas/stage2_input.schema.json`
- `schemas/distance_lookup.schema.json`
- `schemas/stage2_result.schema.json`

The schemas are intended to support review, later validation, handcheck fixtures, and reproducible experiments. They are not a claim that Stage2 allocation can already run.

## 2. Schema Responsibilities

`stage2_input.schema.json` describes one Stage2 decision scenario. It records the total budget, solver coefficient `eta`, lookup profile reference, participating tiles, quality levels, and field provenance.

`distance_lookup.schema.json` describes an offline distance-to-quality lookup profile. It records quality levels, calibration source metadata, and lookup rules that map normalized render distances to the highest allowed quality candidate.

`stage2_result.schema.json` describes the output shape expected from a future solver. It includes status, selected quality levels, budget accounting, lookup resolution, multiplier-search trace, configuration snapshot, warnings, and errors.

## 3. Input Schema

The input schema requires:

- `schema_version`
- `scenario_id`
- `budget_total_bytes`
- `eta`
- `lookup_profile_id`
- `tiles`
- `provenance_summary`

Optional `description` can be used for human-readable context.

Each tile records:

- `tile_id`
- `p_sal`
- `visibility`
- `screen_area`
- `distance_norm`
- `view_context`
- `levels`
- `provenance`

Each quality level records:

- `level_id`
- `quality_label`
- `pdl_ratio`
- `q_base`
- `r_bytes`
- `d_ms`
- `provenance`

The schema checks basic ranges such as non-negative budget and latency, `0 <= visibility <= 1`, `0 <= screen_area <= 1`, `distance_norm >= 0`, and `0 < pdl_ratio <= 1`.

The schema does not require `R_i,j` or `D_i,j` to be strictly monotonic with `level_id`. Real encoded data can violate strict monotonicity, so a later validator may report monotonicity warnings without making that a JSON Schema rule.

## 4. Lookup Schema

The lookup schema fixes:

```json
"semantics": "cap"
```

and:

```json
"distance_unit": "normalized_render_distance"
```

`quality_levels[]` records the available level identifiers, PDL ratios, and labels.

`source` records calibration context:

- `dataset`
- `renderer`
- `metric`
- `threshold_profile`
- `source_runs`
- `notes`

`rules[]` records lookup rules. A rule includes `rule_id`, `view_context`, optional `target_id`, `distance_match`, `lookup_level`, and `threshold_profile`.

`distance_match` supports either `exact_distance` or a `distance_min` / `distance_max` interval. Phase 0B only defines the structure. It does not implement the matching algorithm.

## 5. Result Schema

The result schema records future solver output. Its `status` enum includes:

```text
SUCCESS
INFEASIBLE_BUDGET
INVALID_INPUT
INVALID_LOOKUP
NO_ALLOWED_LEVEL
NUMERICAL_ERROR
INTERNAL_CONSTRAINT_VIOLATION
```

`selected_tiles[]` records each tile's selected level, selected data size, decoding latency, net utility, spatial utility, and allowed levels.

`lookup_resolution[]` records the lookup profile, matched rule, lookup level, and final allowed levels for each tile.

`lambda_search` records the future multiplier-search configuration and trace:

- `enabled`
- `lambda_initial_high`
- `lambda_max_bracket_steps`
- `score_epsilon`
- `lambda_epsilon`
- `max_iterations`
- `iterations`
- `best_feasible_iteration`

Each iteration can record `lambda`, `total_bytes`, `total_net_utility`, `total_decode_ms`, `is_budget_feasible`, `selected_levels`, and its iteration index. `selected_levels` records the discrete tile-level choices for each bracket or bisection probe so the search trace can be reproduced.

## 6. Provenance Vocabulary

The schemas use the current D0-4 draft vocabulary:

```text
measured
calibrated
derived
proxy
synthetic
```

D0-4 remains `DRAFT`. The vocabulary is sufficient for the Phase 0B schema draft and Phase 0C handcheck fixture, but it is not a final field-level provenance design.

## 7. Lookup Cap Semantics

Lookup semantics remain the D0-1 confirmed `cap` rule:

```text
allowed_levels = {1, ..., lookup_level}
```

If `lookup_level = 3`, the allowed levels are `{1, 2, 3}`.

Near-field `lookup_level = 5` means no high-quality candidate is clipped when five levels exist. It does not force the final selection to be level 5.

## 8. Normalized Distance Boundary

`distance_norm` and lookup distances use normalized render distance. They must not be described as physical meters. The current lookup evidence depends on the Longdress data, the recorded source runs, and the Web/Three.js rendering pipeline.

## 9. Infeasible Budget Output

D0-2 is resolved as an explicit infeasible-budget response. If:

```text
Budget_total < B_min_feasible
```

future output should use:

```text
status = INFEASIBLE_BUDGET
budget_total_bytes = ...
b_min_feasible = ...
budget_gap = b_min_feasible - budget_total_bytes
```

This means the input budget and hard constraints are incompatible. It is not a solver crash.

## 10. Lambda Search Recording

D0-3 requires future implementations to record multiplier-search configuration and trace. The result schema therefore includes `lambda_initial_high`, `lambda_max_bracket_steps`, `score_epsilon`, `lambda_epsilon`, `max_iterations`, `iterations`, and `best_feasible_iteration`.

If no feasible solution is recovered despite `B_min_feasible <= Budget_total`, the result should use a clear abnormal status and preserve the trace for debugging.

## 11. Handcheck Fixture Use

Phase 0C adds `tests/fixtures/handcheck_3x3/`, a synthetic 3-tile by 3-level handcheck fixture set. It uses the Stage2 input schema, distance lookup schema, and result schema to record:

- a feasible success input;
- an infeasible-budget input;
- a synthetic lookup profile using `cap` semantics;
- expected success and infeasible results;
- bilingual hand-calculation notes.

The fixture is intended to check schema shape, lookup cap behavior, `B_min_feasible`, `INFEASIBLE_BUDGET`, and simple utility arithmetic. It is not real Longdress data, not a formal experiment result, and not generated by a solver.

## 12. Not Implemented Through Phase 0C

Phase 0C does not implement:

- a JSON validator wrapper;
- a Stage2 solver;
- lookup matching code;
- formal experiments;
- Web player integration.

## 13. Later Use

Later phases can use these schemas to validate hand-written inputs, lookup profiles, fixture files, and solver outputs. As implementation begins, the schemas may be refined based on real sample data, but any semantic change to D0-1, D0-2, or D0-3 must be recorded in the decision log.
