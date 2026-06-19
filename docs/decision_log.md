Languages: English | [中文](decision_log.zh-CN.md)

# Decision Log

Status: Phase 0A.1 draft.

## Summary

| ID | Topic | Status |
|---|---|---|
| D0-1 | lookup semantics | RESOLVED_USER_CONFIRMED |
| D0-2 | infeasible budget | RESOLVED_USER_CONFIRMED |
| D0-3 | lambda search rules | RESOLVED_USER_CONFIRMED |
| D0-4 | provenance vocabulary | DRAFT |

```text
D0-1 lookup semantics       RESOLVED_USER_CONFIRMED
D0-2 infeasible budget      RESOLVED_USER_CONFIRMED
D0-3 lambda search rules    RESOLVED_USER_CONFIRMED
D0-4 provenance vocabulary  DRAFT
```

## D0-1 Lookup Semantics

| Field | Record |
|---|---|
| Decision ID | D0-1 |
| Topic | Runtime semantics of distance-to-quality lookup |
| Background | Full-body and near-field calibration provide distance-to-quality levels for Stage2 candidate construction. The runtime meaning must be fixed before a solver is implemented. |
| Options | `cap`, `floor`, `fixed`, pure `recommended` |
| Confirmed option | `cap` semantics, confirmed by the researcher |
| Benefits | Removes unnecessary high-quality candidates at middle and far distances while preserving the MCKP structure. |
| Risks | If future prose says "near-field must choose level 5," it would contradict the confirmed semantics. |
| Impact on code | Candidate set construction must use `allowed_levels = {1, ..., lookup_level}`. |
| Impact on experiments | Lookup results are used as calibrated candidate upper bounds, not as direct final selections. |
| Impact on thesis/report prose | Must state that lookup gives the highest necessary candidate quality level. |
| Current status | RESOLVED_USER_CONFIRMED |
| Follow-up owner | Researcher verifies future documents and implementation against this semantics. |

Confirmed details:

- The researcher has confirmed the decision.
- The current MVP adopts `cap` semantics.
- Lookup means the highest quality level that is necessary to keep as a candidate under the current distance condition.
- The allowed candidate set is `{1, ..., lookup_level}`.
- Full-body middle and far distances may clip high quality levels.
- Near-field level 5 means no upper-bound clipping.
- Near-field does not mean forced highest final quality.
- `floor`, `fixed`, and pure soft recommendation are not adopted by the current MVP.

## D0-2 Infeasible Budget

| Field | Record |
|---|---|
| Decision ID | D0-2 |
| Topic | Behavior when `Budget_total` is below the minimum feasible data size |
| Background | Each participating tile must choose exactly one allowed quality level. If the total budget is below the sum of per-tile minimum allowed data sizes, the constraints cannot all be satisfied. |
| Options | Return `INFEASIBLE_BUDGET`; ask Stage1 to increase budget; relax selected hard constraints; allow some invisible tiles not to download; introduce an explicit empty or skip level. |
| Confirmed option | Return explicit `INFEASIBLE_BUDGET` when `Budget_total < B_min_feasible`. |
| Benefits | A visible infeasible state avoids silently violating budget or candidate-set constraints. |
| Risks | Upper layers or experiment scripts must handle the explicit infeasible state. |
| Impact on code | Later solver must check `B_min_feasible` before multiplier search and return structured infeasible output. |
| Impact on experiments | Experiment reports must distinguish incompatible input budgets from algorithm failures. |
| Impact on thesis/report prose | This should be described as a hard-constraint incompatibility, not a solver crash. |
| Current status | RESOLVED_USER_CONFIRMED |
| Follow-up owner | Researcher verifies future implementation and reports against this default. |

Minimum feasible budget concept:

```text
B_min_feasible =
sum over i [
    min R_i,j
    for j in allowed_levels_i
]
```

If:

```text
Budget_total < B_min_feasible
```

the solver must return structured output such as:

```text
status = INFEASIBLE_BUDGET
budget_total = ...
b_min_feasible = ...
budget_gap = b_min_feasible - budget_total
```

Confirmed constraints:

- every participating tile still selects exactly one quality level;
- the solver must not silently exceed budget;
- the solver must not fabricate feasibility by dropping participating tiles;
- the solver must not automatically relax lookup candidate sets;
- the solver must not automatically ask Stage1 to change `Budget_total`;
- the MVP does not introduce an empty level or skip level.

## D0-3 Lambda Search Rules

| Field | Record |
|---|---|
| Decision ID | D0-3 |
| Topic | Engineering rules for one-dimensional multiplier search |
| Background | Reference documents support Lagrangian relaxation and multiplier search. Phase 0A.1 freezes MVP defaults for bracketing, feasible-solution recording, tie-breaking, and stopping behavior. |
| Options | Fixed or adaptive upper bound; fixed tolerance; deterministic tie-breaking; maximum iteration count; retaining feasible solutions; ranking among close feasible solutions. |
| Confirmed option | Adaptive upper-bound bracketing, bisection, best feasible solution tracking, deterministic tie-breaking, and explicit abnormal status if feasibility cannot be recovered despite `B_min_feasible <= Budget_total`. |
| Benefits | Frozen rules improve determinism, reviewability, and reproducibility. |
| Risks | Different tie-breaking or tolerance choices can change selected levels under near-equal scores. |
| Impact on code | Later implementation must expose and record search configuration and search traces. |
| Impact on experiments | Experiments must log search settings to keep results reproducible. |
| Impact on thesis/report prose | Search should be described as relying on monotonic non-increasing total data demand, not as proving global MCKP optimality. |
| Current status | RESOLVED_USER_CONFIRMED |
| Follow-up owner | Researcher verifies future implementation and reports against this default. |

Confirmed rules:

- Before search, complete input validation, lookup parsing, `allowed_levels` construction, and `B_min_feasible` check.
- If budget is infeasible, return `INFEASIBLE_BUDGET` and do not enter multiplier search.
- Use `lambda_low = 0` and an adaptive positive `lambda_high`.
- Double `lambda_high` until a budget-feasible solution appears or `lambda_max_bracket_steps` is reached.
- Record configuration such as `lambda_initial_high`, `lambda_max_bracket_steps`, `score_epsilon`, `lambda_epsilon`, and `max_iterations`.
- During bisection, record `lambda`, `total_bytes`, `total_net_utility`, `is_budget_feasible`, and `selected_levels`.
- Update the current best feasible solution whenever a feasible solution appears.

Best feasible solution ranking:

1. higher total net utility;
2. if nearly equal, higher budget utilization;
3. if still tied, lower total expected decoding latency;
4. if still tied, deterministic comparison by `tile_id` and `level_id`.

Single-tile tie-breaking under fixed `lambda`:

1. higher Lagrangian score;
2. if scores are within tolerance, smaller data size;
3. if still tied, smaller decoding latency;
4. if still tied, smaller `level_id`.

Stopping rules:

- `max_iterations` is the primary stop condition.
- `lambda_epsilon` and `no_change_rounds` may be used as auxiliary stop conditions.
- The solver must not output a budget-violating result because search did not fully converge.
- If no feasible solution is found despite `B_min_feasible <= Budget_total`, return `NUMERICAL_ERROR` or `INTERNAL_CONSTRAINT_VIOLATION` and record the search trace.

Residual-budget local upgrades remain planned for implementation. They must stay inside `allowed_levels`, require `delta_R > 0` and `delta_U > 0`, and preserve the budget and lookup constraints.

## D0-4 Provenance Vocabulary

| Field | Record |
|---|---|
| Decision ID | D0-4 |
| Topic | Data source and trust vocabulary |
| Background | Future Stage2 inputs will mix measured, calibrated, derived, proxy, and synthetic values. The documents must prevent proxy or synthetic values from being reported as real measurements. |
| Options | Define a small controlled vocabulary now; expand per-field provenance later. |
| Current candidate | `measured`, `calibrated`, `derived`, `proxy`, `synthetic` |
| Benefits | Improves traceability and prevents over-claiming experimental evidence. |
| Risks | Field-level provenance design is not complete, so the vocabulary must remain draft. |
| Impact on code | Later schemas and outputs should include provenance fields. |
| Impact on experiments | Reports must separate real measurements from proxy and synthetic data. |
| Impact on thesis/report prose | Claims must identify whether data came from calibration, direct measurement, derivation, proxy assumptions, or synthetic tests. |
| Current status | DRAFT |
| Follow-up owner | Researcher/user to refine when schemas and fixtures are designed. |

Draft vocabulary:

- `measured`: directly measured through real files, decoders, browsers, or experiment pipelines.
- `calibrated`: obtained from offline calibration, such as the distance lookup.
- `derived`: computed from known geometry, camera state, or other real data.
- `proxy`: physically or engineering-motivated value that has not yet been directly measured.
- `synthetic`: constructed for unit tests or controlled algorithm experiments.
