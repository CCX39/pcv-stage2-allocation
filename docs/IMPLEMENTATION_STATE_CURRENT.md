# Current Implementation State

This document is the Phase 1F handoff note for `pcv-stage2-allocation`. It records the implementation state through Phase 1F so a new conversation or human reviewer can resume without reconstructing the whole history.

## Project Goal

This repository is for the Work1 Stage2 spatial tile quality allocator. Its role is to define and later implement how a total GoF data budget is allocated across spatial tiles by selecting one discrete quality level per participating tile.

It is not the distance calibration project, and it is not a complete point-cloud video player.

## Current Phase

Current completed phase:

```text
Phase 1F: residual-budget local upgrade integration completed
```

Suggested next preparation phase:

```text
Phase 1G preparation: result inspection workflow or solver output documentation
```

No exact MCKP solver, general-purpose validator, experiment runner, or player integration has been implemented yet.

## Key Commit History

```text
0e03de9  docs: add stage2 MVP phase 0A contract
907feee  docs: resolve stage2 MVP budget and lambda decisions
e0844ee  schemas: add stage2 MVP JSON schema drafts
a72e618  fix: make stage2 input description optional
3833fdf  tests: add handcheck stage2 fixture set
7206f17  docs: add current implementation state
7ec5f22  test: add handcheck fixture validation script
bf1ef90  feat: add stage2 python model layer
daf90e0  fix: clarify target-aware lookup boundary
e3022ed  feat: add fixed lambda selection kernel
c0a0075  feat: add lambda bracketing trace kernel
fb88ce4  feat: add lambda bisection search kernel
0b3bf42  feat: add structured stage2 solver result
b500cf2  feat: add residual-budget local upgrade
```

## Decision State

```text
D0-1 lookup semantics       RESOLVED_USER_CONFIRMED
D0-2 infeasible budget      RESOLVED_USER_CONFIRMED
D0-3 lambda search rules    RESOLVED_USER_CONFIRMED
D0-4 provenance vocabulary  DRAFT
```

- D0-1: lookup is a candidate quality upper bound, with `allowed_levels = {1, ..., lookup_level}`.
- D0-2: if `Budget_total < B_min_feasible`, the future solver must return `INFEASIBLE_BUDGET`.
- D0-3: the future solver should use an adaptive `lambda` upper bound, deterministic tie-breaking, and best feasible solution recording.
- D0-4: the provenance vocabulary is still a draft and must not be treated as final.

## Existing Assets

- `schemas/stage2_input.schema.json`
- `schemas/distance_lookup.schema.json`
- `schemas/stage2_result.schema.json`
- `tests/fixtures/handcheck_3x3/`
- `scripts/validate_handcheck_fixtures.py`
- `src/pcv_stage2/`
- `tests/test_models_handcheck.py`
- `tests/test_lambda_bracketing.py`
- `tests/test_lambda_bisection.py`
- `tests/test_solver_result.py`
- `requirements.txt`
- `src/pcv_stage2/solver.py`
- `docs/fixed_lambda_selection_contract.md`
- `docs/fixed_lambda_selection_contract.zh-CN.md`
- `docs/lambda_bracketing_contract.md`
- `docs/lambda_bracketing_contract.zh-CN.md`
- `docs/lambda_bisection_contract.md`
- `docs/lambda_bisection_contract.zh-CN.md`
- `docs/final_solver_contract.md`
- `docs/final_solver_contract.zh-CN.md`
- `docs/stage2_mvp_contract.zh-CN.md`
- `docs/schema_contract.zh-CN.md`
- `docs/decision_log.zh-CN.md`

The `handcheck_3x3` fixture contains:

- success input;
- infeasible input;
- lookup fixture;
- expected success result;
- expected infeasible result;
- bilingual hand-calculation notes.

## Validation Command

Run from the repository root:

```powershell
python -m pip install -r requirements.txt
python -m pytest
python scripts/validate_handcheck_fixtures.py
```

The fixture guardrail script keeps an independent validation path for draft schemas and handcheck JSON files. The pytest suite separately checks the model layer, lookup cap preprocessing, `B_min_feasible`, the Phase 1B fixed-lambda kernel, the Phase 1C bracketing trace kernel, the Phase 1D bisection search kernel, the Phase 1E structured solver result, the Phase 1F residual-budget local upgrade, and handcheck expected values.

## Target-Aware Lookup Boundary

`Stage2Input v0.1` does not provide the context required for target-aware lookup. Lookup rules with non-null `target_id` are rejected during preprocessing. `target_id` must not be treated as `tile_id`.

## Fixed-Lambda Kernel

Phase 1B adds `select_fixed_lambda(...)`. It selects one allowed level per tile by maximizing `net_utility - lambda_value * r_bytes`, using lookup cap candidates and the D0-3 deterministic tie-break order.

The output is a fixed-lambda candidate. Its `is_budget_feasible` field only describes that candidate and is not a final `SUCCESS` or `INFEASIBLE_BUDGET` status.

## Lambda Bracketing Kernel

Phase 1C adds `bracket_lambda_for_feasible_candidate(...)`. It probes `lambda = 0` first, then doubles positive lambda values from `lambda_initial_high` until the first budget-feasible fixed-lambda candidate is found or `lambda_max_bracket_steps` is exhausted.

The output is a bracket result and trace, not a final Stage2 result. It records per-probe lambda, total bytes, original net utility, total decode time, budget feasibility, and selected levels. If `budget_total_bytes < B_min_feasible`, the helper raises a preprocessing error and leaves final `INFEASIBLE_BUDGET` assembly to the future solver layer.

## Lambda Bisection Search Kernel

Phase 1D adds `search_lambda_feasible_candidates(...)`. It reuses the bracketing helper, then bisects between a known over-budget lower lambda and a known budget-feasible upper lambda. The trace is cumulative across zero-lambda, bracket, and midpoint probes, with consecutive `step_index` values.

The output is a search-kernel result, not a final Stage2 result. It records `termination_reason`, the current lambda bounds, the complete trace, and the best budget-feasible fixed-lambda candidate observed so far. Best-feasible comparison follows D0-3: higher total net utility, then higher budget utilization within `score_epsilon`, then lower total decode time, then a deterministic sorted `(tile_id, selected_level_id)` sequence.

## Structured Solver API

Phase 1E adds `solve_stage2(stage2_input, lookup, config)`. It resolves lookup cap candidates, computes `B_min_feasible`, returns structured `INFEASIBLE_BUDGET` without lambda search when the budget floor is impossible, and otherwise runs the Phase 1D lambda search.

The output is a `Stage2SolveResult`. `Stage2SolveResult.to_dict()` produces a JSON-compatible dictionary that validates against `schemas/stage2_result.schema.json`. It records selected tiles, lookup resolution, lambda trace, config snapshot, runtime, warnings, and errors.

This is still a low-complexity approximation path for the Stage2 allocation problem. It must not be described as an exact 0-1 MCKP global solver.

## Residual-Budget Local Upgrade

Phase 1F adds a local-upgrade postprocess after successful lambda search. The seed is always the lambda search `best_feasible_candidate`, identified by `lambda_search.best_feasible_iteration`.

Each upgrade stays inside `allowed_levels`, requires positive added bytes and positive net utility, and must fit in the current residual budget. The greedy order is highest gain per byte, with exact ties resolved by ascending `(tile_id, target_level_id)`. The upgrade audit is recorded in `local_upgrade.steps[]`; lambda trace remains only the lambda search trace.

## Handcheck Fixture Core Results

Success case:

```text
selected levels = T1_near_important:L3, T2_mid_visible:L1, T3_far_capped:L1
total_bytes = 200
total_net_utility = 39.5
budget_total_bytes = 210
```

Infeasible case:

```text
budget_total_bytes = 100
B_min_feasible = 120
budget_gap = 20
status = INFEASIBLE_BUDGET
```

## Not Implemented Yet

- general-purpose validator;
- exact or exhaustive MCKP solver;
- baselines;
- Longdress input generation;
- batch experiments;
- charts and figures;
- player integration.
- target-aware lookup input semantics.

## Suggested Next Step

Do not jump directly into experiments without reviewing the local-upgrade audit first. A reasonable next step is:

```text
Phase 1G: result inspection workflow or solver output documentation
```

This document only records suggestions. It does not start either phase.

## How To Resume

For a new GPT conversation or human handoff:

1. Read `docs/IMPLEMENTATION_STATE_CURRENT.zh-CN.md` first.
2. Then read `docs/stage2_mvp_contract.zh-CN.md`.
3. Then read `docs/fixed_lambda_selection_contract.zh-CN.md`.
4. Then read `docs/lambda_bracketing_contract.zh-CN.md`.
5. Then read `docs/lambda_bisection_contract.zh-CN.md`.
6. Then read `docs/final_solver_contract.zh-CN.md`.
7. Then read `docs/schema_contract.zh-CN.md`.
8. Then inspect `tests/fixtures/handcheck_3x3/hand_calculation.zh-CN.md`.
9. Run `python -m pytest` and `python scripts/validate_handcheck_fixtures.py` after installing requirements.
10. Do not change the frozen semantics of D0-1, D0-2, or D0-3.
11. Do not treat the `handcheck_3x3` fixture as a real Longdress experiment.
