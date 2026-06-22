Languages: English | [Chinese](final_solver_contract.zh-CN.md)

# Final Solver Contract

Status: Phase 1E implementation note.

This document describes the typed `solve_stage2(...)` API added in Phase 1E. It assembles lookup cap resolution, `B_min_feasible`, lambda search, best-feasible candidate selection, and structured result serialization. It is still a low-complexity integer approximation framework, not an exact 0-1 MCKP solver.

## Inputs And Output

`solve_stage2(stage2_input, lookup, config)` accepts typed model objects:

- `Stage2Input`;
- `DistanceLookup`;
- `LambdaSearchConfig`.

It returns a `Stage2SolveResult`. `Stage2SolveResult.to_dict()` produces a JSON-compatible dictionary matching `schemas/stage2_result.schema.json`.

The API does not load JSON files, validate arbitrary dictionaries, write result files, or provide a CLI.

## Status Mapping

`INFEASIBLE_BUDGET` means lookup cap resolution succeeded, `B_min_feasible` was computed, and `budget_total_bytes < B_min_feasible`. The solver does not enter lambda search in this case.

`SUCCESS` means lambda search recovered a budget-feasible fixed-lambda candidate and final result assembly rechecked all selected tiles against lookup cap and budget constraints.

`NUMERICAL_ERROR` means `B_min_feasible <= budget_total_bytes`, but the current lambda search configuration did not recover a budget-feasible candidate. The result keeps the lambda trace for diagnosis.

`INVALID_LOOKUP` covers lookup profile mismatch, unsupported lookup semantics, missing or ambiguous matching rules, and unsupported target-aware lookup rules. Non-null lookup `target_id` values must not be treated as tile ids.

`NO_ALLOWED_LEVEL` covers the case where lookup cap resolution leaves a tile with no usable quality level.

`INVALID_INPUT` remains reserved for schema or typed-input validation boundaries. The Phase 1E API receives already constructed typed models and does not add a dict/JSON input interface.

`INTERNAL_CONSTRAINT_VIOLATION` is reserved for result assembly invariants that the solver can clearly detect.

## Success Rechecks

For `SUCCESS`, the assembled result verifies:

- each participating tile has exactly one selected level;
- the selected level is inside that tile's allowed lookup-cap levels;
- total bytes do not exceed `budget_total_bytes`;
- total bytes, net utility, spatial utility, and decode time agree with selected tiles.

Current MVP spatial utility uses the existing model-layer default `g_distance = 1.0`. Phase 1E does not fit or introduce a new distance function.

## Lambda Trace In Result

For lambda search paths, `lambda_search.iterations[]` is populated from the full search trace:

```text
lambda = 0 probe
+ positive bracket probes
+ bisection midpoint probes
```

Each iteration records lambda, total bytes, total net utility, total decode time, budget feasibility, and selected levels. `best_feasible_iteration` points to the full trace step index.

## Scope Boundary

Phase 1E does not implement:

- local upgrade;
- exact or exhaustive MCKP solving;
- baseline algorithms;
- Longdress input generation;
- batch experiments;
- plotting;
- player integration;
- target-aware lookup schema extension;
- Stage1 online integration;
- JSON file output CLI.

The result is a structured Stage2 solver output for the current low-complexity approximation path. It must not be described as a strict global optimum of the original 0-1 MCKP.
