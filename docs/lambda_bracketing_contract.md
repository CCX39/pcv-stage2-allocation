Languages: English | [Chinese](lambda_bracketing_contract.zh-CN.md)

# Lambda Bracketing Contract

Status: Phase 1C implementation note.

This document describes the adaptive lambda upper-bound bracketing kernel added in Phase 1C. The bracketing component prepares the low/high search interval and trace data consumed by the Phase 1D bisection kernel. It is not the complete Stage2 solver.

## Input Premise

Bracketing runs after input parsing, lookup cap resolution, and `B_min_feasible` calculation. If:

```text
budget_total_bytes < B_min_feasible
```

the bracketing helper raises a controlled preprocessing error. The future final `solve_stage2` layer must map that condition to `INFEASIBLE_BUDGET`; Phase 1C does not assemble a final result.

## Probe Order

The current implementation uses the shared `LambdaSearchConfig`. Bracketing consumes `lambda_initial_high`, `lambda_max_bracket_steps`, and `score_epsilon`; the bisection fields are carried by the same explicit configuration object so callers do not maintain two similar config models.

The kernel always evaluates `lambda = 0` first.

If the zero-lambda candidate is already budget-feasible, the result is marked `feasible_at_zero` and no positive lambda probe is executed.

If the zero-lambda candidate exceeds budget, probing starts at `lambda_initial_high`. Each infeasible positive probe doubles the value:

```text
lambda <- 2 * lambda
```

`lambda_max_bracket_steps` means the maximum number of positive lambda values to try. It does not count the mandatory zero-lambda probe. A value of `0` means no positive bracket probe is attempted after the zero-lambda probe.

## Result Cases

`bracket_found = true` and `feasible_at_zero = true` means the zero-lambda candidate fits budget.

`bracket_found = true` and `feasible_at_zero = false` means the trace contains an infeasible lower lambda and the first feasible positive upper lambda.

`bracket_found = false` means the configured positive probe budget was exhausted without finding a feasible candidate. This is a bracket failure result, not a final solver status, and it must not fabricate a feasible candidate.

## Trace Fields

Each trace point records:

- `step_index`;
- `lambda_value`;
- `total_bytes`;
- `total_net_utility`;
- `total_decode_ms`;
- `is_budget_feasible`;
- `selected_levels`.

All trace values come from the fixed-lambda candidate returned by `select_fixed_lambda(...)`. `total_decode_ms` is the sum of the selected levels' actual `d_ms` values.

## Scope Boundary

The bracketing component does not implement:

- bisection search;
- best feasible candidate ranking;
- final `solve_stage2` API;
- final `SUCCESS` or `INFEASIBLE_BUDGET` result assembly;
- local upgrade;
- exhaustive MCKP solving;
- baseline algorithms;
- Longdress input generation;
- batch experiments;
- plotting;
- player integration;
- target-aware lookup schema extension.

Bracket success is only a relaxed-kernel search boundary. It must not be described as a strict global optimum of the original 0-1 MCKP.
