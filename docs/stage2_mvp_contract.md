Languages: English | [中文](stage2_mvp_contract.zh-CN.md)

# Stage2 MVP Contract

Status: Phase 0A draft. This document defines the planned Stage2 MVP contract. It does not implement any computation.

## 1. Purpose

The purpose of this project is not to build a complete streaming system immediately. The first implementation target is a Stage2 spatial quality allocator that can later be:

- runnable;
- reproducible;
- batch-testable;
- explainable;
- gradually portable to the Web side.

Phase 0A only records the contract needed before implementation.

## 2. MVP Scope

The first MVP is planned to support:

- reading tile and quality-level data for one GoF or one decision instant;
- receiving `Budget_total`;
- representing multiple discrete quality levels for each tile;
- parsing distance lookup results as an upper bound on allowed quality levels;
- computing spatial- and compute-aware net utility;
- running a later Lagrangian multiplier search;
- recovering a budget-feasible integer solution;
- using residual budget for local incremental upgrades;
- outputting structured results and trace information.

These are planned MVP capabilities. None of them is implemented in Phase 0A.

## 3. Explicit Non-Goals

The first MVP does not include:

- complete online Stage1 Meta-BOLA implementation;
- real HTTP download;
- complete player integration;
- occlusion detection;
- Work2 adaptive point-size rendering;
- spatial smoothing joint optimization;
- LPIPS;
- large-scale user studies;
- large-scale exact MCKP solving;
- end-to-end network QoE validation.

## 4. Input Concepts

Future inputs need to express the following concepts. Phase 0A defines only the concepts and does not create a JSON Schema.

### Scene-Level Fields

- scene identifier;
- GoF or decision-instant identifier;
- `Budget_total`;
- `eta`;
- lookup profile;
- data source and version.

### Tile-Level Fields

- `tile_id`;
- `P_sal_i`, the saliency weight;
- `V_i`, viewport visibility;
- `A_i`, projected screen area ratio;
- `d_i`, normalized rendering distance;
- scene context such as full-body or near-field;
- field provenance.

### Quality-Level Fields

- `level_id`;
- explicit quality ordering;
- `R_i,j`, data size;
- `D_i,j`, expected decoding latency;
- `q_i,j`, base quality gain;
- point-density ratio or another quality identifier;
- field provenance.

## 5. Output Concepts

Future outputs need to express at least:

- status code;
- final quality level selected for each tile;
- data size of each selected level;
- net utility of each selected level;
- total data size;
- total net utility;
- total spatial visual utility;
- total expected decoding latency;
- budget utilization;
- minimum feasible budget;
- lookup parsing results;
- multiplier search trace;
- search iteration count;
- algorithm runtime;
- input and algorithm configuration snapshot;
- provenance summary;
- warnings and exception information.

Phase 0A only defines these output concepts. It does not implement output code.

## 6. Mathematical Model And Symbols

The planned Stage2 problem is a Multiple-Choice Knapsack Problem (MCKP) with one total budget constraint. The original problem uses binary variables and is not a convex optimization problem. Only after continuous relaxation can it be discussed as a linear program.

Objective:

```text
maximize:
sum_i sum_j Uhat_i,j * x_i,j
```

Budget constraint:

```text
sum_i sum_j R_i,j * x_i,j <= Budget_total
```

Multiple-choice constraint:

```text
sum_j x_i,j = 1
```

Integer constraint:

```text
x_i,j in {0, 1}
```

Net utility:

```text
Uhat_i,j =
(P_sal_i * V_i * A_i * G(d_i)) * q_i,j
- eta * D_i,j
```

Distance-aware candidate set:

```text
M_i(d_i) = {1, ..., j_max_dist(d_i)}
```

Fixed-`lambda` choice rule:

```text
argmax_j [
    Uhat_i,j - lambda * R_i,j
]
```

`G(d_i)` is a distance-sensitivity modulation term. Current reference documents support "lookup first, `G(d_i)` as auxiliary interpretation"; they do not establish a unique analytical form of `G(d_i)`.

Lookup semantics are a confirmed cap:

```text
lookup_level = j_max_dist
allowed_levels = {1, 2, ..., j_max_dist}
```

For near-field lookup level 5, the cap keeps all levels `{1, 2, 3, 4, 5}` available. It does not force the final selected level to be 5.

The future solver is positioned as a low-complexity approximate integer solution framework. It must not claim strict global optimality for the original MCKP.

## 7. Quality-Level Ordering

- Larger `level_id` means higher quality.
- Under normal point-density-level interpretation, larger PDL means higher quality.
- A lookup level is the highest allowed candidate level under the current cap semantics.
- Inputs should not rely only on array position to imply quality order.
- Later inputs must explicitly record level identifiers.
- In real encoded data, `R_i,j` or `D_i,j` may be affected by encoding details and may not be strictly monotonic.
- If a later algorithm depends on monotonicity, that condition must be verified first or explicitly stated in the contract.

## 8. Planned Solver Flow

The later implementation is expected to follow this flow:

```text
input validation
-> lookup matching
-> build allowed candidate set for each tile
-> compute net utility for each tile and level
-> check minimum feasible budget
-> independent choice under fixed lambda
-> one-dimensional multiplier search
-> record a budget-feasible integer solution
-> local upgrade with residual budget
-> constraint recheck
-> output result
```

None of these modules is implemented in Phase 0A.

## 9. Required Invariants

1. Every participating tile selects exactly one quality level.
2. Final total data size must not exceed `Budget_total`.
3. A tile can only select a level from its allowed candidate set.
4. Lookup must be applied as a candidate upper bound.
5. Identical input and identical configuration must produce deterministic results.
6. Output must record input sources and algorithm configuration.
7. Proxy-data experiments and real-data experiments must be clearly separated.
8. Normalized distance must not be written as physical meters.
9. The original problem is integer MCKP, not convex optimization.
10. Algorithm output is an approximate integer solution and must not be described as strict global optimum.
11. Infeasible budget cannot be silently ignored.
12. Feasibility must not be fabricated by dropping participating tiles.
13. Lookup constraints must not be relaxed without being recorded.
14. Final experimental conclusions must be traceable to concrete inputs, configuration, and outputs.

## 10. Decision Gates

```text
D0-1 lookup semantics       RESOLVED_USER_CONFIRMED
D0-2 infeasible budget      PENDING_USER_DECISION
D0-3 lambda search rules    PENDING_USER_DECISION
D0-4 provenance vocabulary  DRAFT
```

### D0-2 Minimum Feasible Budget

For allowed sets `allowed_levels_i`, the minimum feasible data size is:

```text
B_min_feasible =
sum over i [
    min R_i,j
    for j in allowed_levels_i
]
```

If `Budget_total < B_min_feasible`, the current candidate solutions include returning `INFEASIBLE_BUDGET`, asking Stage1 for more budget, relaxing selected hard constraints, allowing some invisible tiles not to download, or adding a base empty/skip level. The final behavior is not confirmed.

For a first MVP, an explicit infeasible status is usually the safest candidate because it does not silently violate the budget or candidate-set constraints. This is a candidate recommendation, not a confirmed decision.

### D0-3 Multiplier Search Rules

Future implementation must still freeze the `lambda` lower bound, upper-bound strategy, floating tolerance, deterministic tie-breaking, maximum iteration count, termination rules, whether the nearest feasible solution is retained, and how close-scoring feasible solutions are ranked. Phase 0A records these questions only.

## 11. Expected Status Codes

These are conceptual status codes only. They are not implemented.

```text
SUCCESS
```

The solver completed and produced a budget-feasible integer solution.

```text
INFEASIBLE_BUDGET
```

`Budget_total` is below the minimum feasible data size. The final handling strategy remains pending.

```text
INVALID_INPUT
```

Input fields are missing, out of range, duplicated, or have invalid types.

```text
INVALID_LOOKUP
```

Lookup data is missing, distance range cannot be matched, a lookup level exceeds available levels, or semantics are inconsistent.

```text
NO_ALLOWED_LEVEL
```

A tile has no allowed quality level after lookup and other constraints.

```text
NUMERICAL_ERROR
```

Non-finite values, floating-point exceptions, or unstable search termination are encountered.

```text
INTERNAL_CONSTRAINT_VIOLATION
```

The produced result violates the per-tile multiple-choice constraint, budget constraint, or candidate-set constraint.

## 12. Provenance Requirements

Each key data field should record a source type:

- `measured`: directly measured from real files, decoders, browsers, or experiment pipelines.
- `calibrated`: obtained from offline calibration experiments, such as distance lookup.
- `derived`: computed from real geometry, camera state, or other known data, such as distance, viewport intersection, or projected area.
- `proxy`: an engineering proxy with physical or implementation rationale, but not yet directly measured.
- `synthetic`: constructed for unit tests or controlled algorithm checks.

Proxy values must state their formula or construction basis. Synthetic values must not be mixed with real experiment claims. Lookup records should preserve source run ID, thresholds, dataset, and rendering pipeline.

## 13. Phase 0A Completion Criteria

Phase 0A completion means only:

- project skeleton is created;
- English and Chinese README files are created;
- English and Chinese algorithm contract drafts are created;
- English and Chinese decision logs are created;
- English and Chinese manual review checklists are created;
- D0-1 is recorded with the confirmed user semantics;
- D0-2 and D0-3 remain pending;
- no solver, Schema, or fixture is implemented.

## 14. Not Implemented Modules

The following modules are not implemented:

- input Schema;
- lookup Schema;
- input validator;
- net utility calculator;
- fixed-`lambda` selector;
- multiplier search;
- infeasible budget handling;
- feasible solution recovery;
- residual budget upgrade;
- baseline algorithm;
- batch runner;
- figures and experiment statistics;
- Longdress tile input generation;
- Python reference implementation;
- TypeScript port;
- player interface;
- formal experiment.
