Languages: English | [Chinese](lambda_bisection_contract.zh-CN.md)

# Lambda Bisection Contract

Status: Phase 1D implementation note.

This document describes the search-kernel layer added in Phase 1D. It runs bisection after adaptive lambda bracketing and records the best budget-feasible fixed-lambda candidate observed during the search. It is not the final Stage2 solver.

## Input Premise

Bisection runs only after `bracket_lambda_for_feasible_candidate(...)` has produced a valid bracket:

- `lambda_low` is a known over-budget lambda;
- `lambda_high` is a known budget-feasible lambda.

If `lambda = 0` is already budget-feasible, bisection is skipped and the zero-lambda candidate becomes the current best feasible candidate.

If bracketing fails, the search result reports `bracket_failure` and does not fabricate a feasible candidate.

## Configuration

Bracket and bisection share one explicit `LambdaSearchConfig`:

- `lambda_initial_high`: finite positive number;
- `lambda_max_bracket_steps`: non-negative integer;
- `score_epsilon`: finite non-negative number;
- `lambda_epsilon`: finite non-negative number;
- `max_iterations`: non-negative integer.

`max_iterations = 0` means the search keeps the bracket upper feasible candidate and performs no midpoint probe. The implementation rejects booleans, `NaN`, infinities, negative values, and non-integer iteration counts.

## Trace Accumulation

The search trace is cumulative:

```text
lambda = 0 probe
+ positive bracket probes
+ bisection midpoint probes
```

`step_index` is continuous from `0` across the whole trace and is not reset between bracketing and bisection.

Each trace point records:

- `lambda_value`;
- `total_bytes`;
- `total_net_utility`;
- `total_decode_ms`;
- `is_budget_feasible`;
- `selected_levels`.

All trace points come from `select_fixed_lambda(...)`.

## Bisection Rule

For each iteration:

```text
lambda_mid = (lambda_low + lambda_high) / 2
```

The midpoint candidate is evaluated with `select_fixed_lambda(...)` and appended to the trace.

If the candidate is budget-feasible, it may update the best feasible candidate and then becomes the new upper endpoint. If it exceeds budget, it becomes the new lower endpoint.

## Best Feasible Candidate

Best feasible comparison applies only to candidates that are already budget-feasible. The order follows D0-3:

1. higher `total_net_utility`;
2. if approximately equal within `score_epsilon`, higher budget utilization;
3. if still tied, lower `total_decode_ms`;
4. if still tied, deterministic lexicographic comparison of the sorted `(tile_id, selected_level_id)` sequence.

For zero budget, budget utilization is treated as tied to avoid division by zero.

## Termination Reasons

Search-level termination reasons are not final Stage2 statuses:

- `feasible_at_zero`: zero-lambda candidate fits budget and no bisection ran;
- `lambda_epsilon`: the bracket width is within `lambda_epsilon`;
- `max_iterations`: the configured midpoint-probe limit was reached;
- `bracket_failure`: no feasible upper lambda was found during bracketing;
- `floating_point_stall`: the midpoint can no longer shrink the interval.

When the search stops after a successful bracket, it may return only a candidate already verified as budget-feasible. It must not return an over-budget candidate as the best feasible result.

## Scope Boundary

Phase 1D does not implement:

- final `solve_stage2` API;
- final `SUCCESS` or `INFEASIBLE_BUDGET` result assembly;
- JSON result serialization;
- local upgrade;
- exhaustive MCKP solving;
- baseline algorithms;
- Longdress input generation;
- batch experiments;
- plotting;
- player integration;
- target-aware lookup schema extension.

The search result is a relaxed fixed-lambda search-kernel result. It must not be described as a strict global optimum of the original 0-1 MCKP.
