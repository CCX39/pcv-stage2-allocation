# Current Implementation State

This document is the Phase 1A handoff note for `pcv-stage2-allocation`. It records the implementation state through Phase 1A so a new conversation or human reviewer can resume without reconstructing the whole history.

## Project Goal

This repository is for the Work1 Stage2 spatial tile quality allocator. Its role is to define and later implement how a total GoF data budget is allocated across spatial tiles by selecting one discrete quality level per participating tile.

It is not the distance calibration project, and it is not a complete point-cloud video player.

## Current Phase

Current completed phase:

```text
Phase 1A: Python project skeleton + dataclass/model definitions completed
```

Suggested next preparation phase:

```text
Phase 1B preparation: solver interface and core algorithm planning
```

No Stage2 solver, general-purpose validator, experiment runner, or player integration has been implemented yet.

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
- `requirements.txt`
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

The fixture guardrail script keeps an independent validation path for draft schemas and handcheck JSON files. The pytest suite separately checks the Phase 1A model layer, lookup cap preprocessing, `B_min_feasible`, and handcheck expected values. Neither command runs a solver.

## Target-Aware Lookup Boundary

`Stage2Input v0.1` does not provide the context required for target-aware lookup. Lookup rules with non-null `target_id` are rejected during preprocessing. `target_id` must not be treated as `tile_id`.

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

- Python or TypeScript solver;
- general-purpose validator;
- `lambda` search;
- local upgrade;
- baselines;
- Longdress input generation;
- batch experiments;
- charts and figures;
- player integration.
- target-aware lookup input semantics.

## Suggested Next Step

Do not jump directly into a full solver without reviewing the model layer first. A reasonable next step is:

```text
Phase 1B: solver interface and core algorithm planning
```

This document only records suggestions. It does not start either phase.

## How To Resume

For a new GPT conversation or human handoff:

1. Read `docs/IMPLEMENTATION_STATE_CURRENT.zh-CN.md` first.
2. Then read `docs/stage2_mvp_contract.zh-CN.md`.
3. Then read `docs/schema_contract.zh-CN.md`.
4. Then inspect `tests/fixtures/handcheck_3x3/hand_calculation.zh-CN.md`.
5. Run `python -m pytest` and `python scripts/validate_handcheck_fixtures.py` after installing requirements.
6. Do not change the frozen semantics of D0-1, D0-2, or D0-3.
7. Do not treat the `handcheck_3x3` fixture as a real Longdress experiment.
