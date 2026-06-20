Languages: English | [Chinese](fixed_lambda_selection_contract.zh-CN.md)

# Fixed-Lambda Selection Contract

Status: Phase 1B implementation note.

This document describes the local fixed-lambda selection kernel added in Phase 1B. It is a reusable kernel for later multiplier search. It is not the complete Stage2 solver.

## Selection Rule

For each tile, lookup is resolved first using the confirmed cap semantics:

```text
allowed_levels_i = {level_id | level_id <= min(lookup_level_i, max_existing_level_i)}
```

The fixed-lambda kernel then selects one level from `allowed_levels_i`:

```text
argmax_j [
    net_utility_i,j - lambda_value * r_bytes_i,j
]
```

The summed `total_net_utility` is the original net utility sum. The summed `total_penalized_score` is the lambda-penalized score sum.

## Tie-Breaking

The tile-level tie-break order follows the frozen D0-3 rule in `docs/decision_log.md` and `docs/stage2_mvp_contract.md`:

1. Higher penalized score.
2. If scores are approximately equal, smaller `r_bytes`.
3. If still tied, smaller `d_ms`.
4. If still tied, smaller `level_id`.

The implementation exposes `score_epsilon` for approximate score equality.

## Candidate, Not Final Result

A fixed-lambda output is a candidate selection only. Its `is_budget_feasible` flag only says whether that candidate fits `budget_total_bytes`.

It must not be interpreted as a final `SUCCESS` result when feasible, and it must not be interpreted as `INFEASIBLE_BUDGET` when over budget. Final status assembly, infeasible-budget handling, lambda upper-bound expansion, binary search, best feasible candidate tracking, and local upgrade remain future solver responsibilities.

## Budget Behavior

A fixed-lambda candidate can exceed budget because it optimizes the relaxed per-tile score independently. Budget restoration is the role of the later lambda search and final solver checks.

## Scope Boundary

Phase 1B does not implement:

- lambda upper-bound expansion;
- binary search;
- best feasible record tracking;
- local upgrade;
- final `solve_stage2` API;
- exhaustive MCKP solving;
- baseline algorithms;
- Longdress input generation;
- batch experiments;
- plotting;
- player integration.

The fixed-lambda kernel is also not an exact global solver for the original MCKP. It is one local building block for the planned Lagrangian-relaxation workflow.
