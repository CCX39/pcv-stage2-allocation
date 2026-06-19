Languages: English | [中文](decision_log.zh-CN.md)

# Decision Log

Status: Phase 0A draft.

## Summary

| ID | Topic | Status |
|---|---|---|
| D0-1 | lookup semantics | RESOLVED_USER_CONFIRMED |
| D0-2 | infeasible budget | PENDING_USER_DECISION |
| D0-3 | lambda search rules | PENDING_USER_DECISION |
| D0-4 | provenance vocabulary | DRAFT |

```text
D0-1 lookup semantics       RESOLVED_USER_CONFIRMED
D0-2 infeasible budget      PENDING_USER_DECISION
D0-3 lambda search rules    PENDING_USER_DECISION
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
| Current candidate | Explicit `INFEASIBLE_BUDGET` is the safest first-MVP candidate, but this is not confirmed. |
| Benefits | A visible infeasible state avoids silently violating budget or candidate-set constraints. |
| Risks | Returning an error requires upper layers or experiments to handle failed allocation cases. |
| Impact on code | Later solver needs a minimum feasible budget check before multiplier search. |
| Impact on experiments | Experiment reports must distinguish infeasible cases from normal solver failures. |
| Impact on thesis/report prose | Must not claim the strategy is finalized until the user confirms it. |
| Current status | PENDING_USER_DECISION |
| Follow-up owner | Researcher/user decision required before implementation. |

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

the solver cannot satisfy all current hard constraints.

## D0-3 Lambda Search Rules

| Field | Record |
|---|---|
| Decision ID | D0-3 |
| Topic | Engineering rules for one-dimensional multiplier search |
| Background | Reference documents support Lagrangian relaxation and multiplier search, but implementation-level rules still need to be frozen. |
| Options | Fixed or adaptive upper bound; fixed tolerance; deterministic tie-breaking; maximum iteration count; retaining nearest feasible solution; score-vs-size ranking among close feasible solutions. |
| Current candidate | Adaptive doubling for upper-bound discovery, smaller data size on ties, fixed tolerance, maximum iterations, and retaining the latest feasible solution are reasonable candidates, but not confirmed. |
| Benefits | Freezing these rules before implementation improves determinism and reviewability. |
| Risks | Different tie-breaking or tolerance choices can change selected levels under near-equal scores. |
| Impact on code | Later implementation must expose or record search configuration. |
| Impact on experiments | Experiments must log search settings to keep results reproducible. |
| Impact on thesis/report prose | Search should be described as relying on monotonic non-increasing total data demand, not as proving global MCKP optimality. |
| Current status | PENDING_USER_DECISION |
| Follow-up owner | Researcher/user decision required before implementation. |

Open items:

- `lambda` initial lower bound;
- fixed or adaptive `lambda` upper bound;
- floating-point tolerance;
- deterministic tie-breaking;
- maximum search iterations;
- termination condition;
- whether to record the nearest feasible solution;
- selection rule among close-scoring feasible solutions.

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
