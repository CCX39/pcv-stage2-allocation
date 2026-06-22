Languages: English | [中文](README.zh-CN.md)

# pcv-stage2-allocation

`pcv-stage2-allocation` is the Stage2 workspace for Work1 of the research topic "Lightweight viewport-aware point-cloud volumetric video transmission and rendering co-optimization." Its purpose is to define, review, and later implement the spatial tile quality allocation mechanism under a total GoF data budget.

This repository is currently at **Phase 1D: bisection search and best-feasible candidate kernel**. Phase 0A created the project skeleton and algorithm contract draft; Phase 0A.1 froze the MVP default behavior for infeasible budgets and `lambda` search rules; Phase 0B added draft schemas for Stage2 input, distance lookup, and future result output; Phase 0C added a small 3-tile by 3-level handcheck fixture; Phase 0D added a minimal schema and handcheck validation script; Phase 1A adds reusable Python dataclasses, JSON loading, preprocessing helpers, and handcheck tests; Phase 1B adds a fixed-lambda per-tile selection candidate kernel; Phase 1C adds adaptive lambda upper-bound bracketing and trace models; Phase 1D adds bisection over a bracket and best-feasible candidate tracking. These phases create documentation, validation scaffolding, and model-layer/search-kernel boundaries only. They do not implement the complete Stage2 solver.

## Work1 Structure

Work1 uses a two-stage decision structure:

- Stage1 estimates the total GoF data budget `Budget_total` from network state, buffer state, and viewport/content scale.
- Stage2 allocates that budget across spatial tiles by selecting one discrete quality level per participating tile.

This repository is responsible only for Stage2 spatial quality allocation. Stage1 can provide `Budget_total` in the future, but the first Stage2 version may also receive it from configuration or offline experiments.

## Relation To Distance Calibration

The independent `PCV-Distance-Quality-Calibration` project provides offline distance-to-quality lookup evidence for Longdress under the current Web/Three.js rendering pipeline. That project is not the Stage2 allocator.

In this repository, lookup assets are treated as calibrated external inputs. The current confirmed runtime semantics are:

```text
lookup_level = highest necessary candidate quality level
allowed_levels = {1, 2, ..., lookup_level}
```

Near-field lookup level 5 means the upper-bound cap does not remove high-quality candidates. It does not force the final allocator to choose level 5.

## Phase 0A.1 Decision Defaults

Phase 0A.1 resolves two MVP defaults:

- If `Budget_total < B_min_feasible`, the future solver must return `INFEASIBLE_BUDGET` explicitly. It must not silently exceed budget, drop participating tiles, relax lookup constraints, request Stage1 changes automatically, or introduce an empty/skip level in the MVP.
- The future `lambda` search uses an adaptive upper bound, records feasible candidates during bisection, applies deterministic tie-breaking, and must never output a budget-violating result when search does not fully converge.

## Phase 0B Schema Drafts

Phase 0B adds JSON Schema Draft 2020-12 files:

- `schemas/stage2_input.schema.json`
- `schemas/distance_lookup.schema.json`
- `schemas/stage2_result.schema.json`

These schemas define data formats only. They do not implement validation code, a solver, or experiments.

## Phase 0C Handcheck Fixture

Phase 0C adds a synthetic `tests/fixtures/handcheck_3x3/` fixture set. It contains success and infeasible input examples, a synthetic lookup profile, expected result files, and bilingual hand-calculation notes.

The fixture is for manual checking and later solver validation. It is not real Longdress experiment data and is not a formal experiment result.

## Phase 0D Validation Script

Phase 0D adds a minimal script that validates the handcheck fixture JSON files against the draft schemas and checks the hand-calculated lookup cap behavior, `B_min_feasible`, success result, and infeasible result.

Run from the repository root:

```powershell
python -m pip install -r requirements.txt
python scripts/validate_handcheck_fixtures.py
```

This script is a fixture guardrail, not a Stage2 solver.

## Phase 1A Python Model Layer

Phase 1A adds a minimal `pcv_stage2` Python package for Stage2 input models, distance lookup models, JSON loading, lookup cap preprocessing, utility calculation, and `B_min_feasible` calculation.

Run from the repository root:

```powershell
python -m pytest
python scripts/validate_handcheck_fixtures.py
```

The Phase 1A model layer was preparation for later search kernels. It did not implement local upgrade, baselines, or MCKP solving.

Target-aware lookup is not supported by the current `Stage2Input v0.1` model. Non-null lookup `target_id` values must not be treated as `tile_id` values.

The fixture guardrail script keeps an independent validation path. Model-layer behavior is covered separately by `pytest`.

## Phase 1B Fixed-Lambda Selection Kernel

Phase 1B adds `select_fixed_lambda(...)`, a local per-tile selection kernel that chooses one allowed level per tile by maximizing:

```text
net_utility_i,j - lambda_value * r_bytes_i,j
```

The result is a fixed-lambda candidate, not a final Stage2 result. It records total bytes, original net utility, penalized score, and whether that candidate fits the input budget. Feasible candidates must not be treated as final `SUCCESS`, and over-budget candidates must not be treated as final `INFEASIBLE_BUDGET`.

The Phase 1B fixed-lambda component itself does not perform lambda upper-bound expansion, binary search, best feasible tracking, local upgrade, baselines, or final solver assembly.

## Phase 1C Lambda Bracketing Trace Kernel

Phase 1C adds `bracket_lambda_for_feasible_candidate(...)`, which first probes `lambda = 0` and then doubles positive lambda values until it finds the first budget-feasible fixed-lambda candidate or exhausts `lambda_max_bracket_steps`.

The bracket output is trace data, not a final Stage2 result. It records each probe's lambda, total bytes, original net utility, total decode time, budget feasibility, and selected levels. The bracketing component itself does not perform binary search, best feasible candidate ranking, local upgrade, final `solve_stage2`, or final `SUCCESS` / `INFEASIBLE_BUDGET` assembly.

## Phase 1D Lambda Bisection Search Kernel

Phase 1D adds `search_lambda_feasible_candidates(...)`, which reuses the bracketing helper and then bisects between a known over-budget lower lambda and a known budget-feasible upper lambda. The full trace accumulates the zero-lambda probe, positive bracket probes, and bisection midpoint probes without resetting `step_index`.

The search result records a best feasible fixed-lambda candidate using the D0-3 order: higher total net utility first, then higher budget utilization within `score_epsilon`, then lower total decode time, then a deterministic sorted `(tile_id, selected_level_id)` sequence. This is still a search-kernel result, not a final Stage2 result or a proof of exact 0-1 MCKP optimality.

## Current Structure

```text
pcv-stage2-allocation/
├─ README.md
├─ README.zh-CN.md
├─ .gitignore
├─ requirements.txt
├─ docs/
│  ├─ stage2_mvp_contract.md
│  ├─ stage2_mvp_contract.zh-CN.md
│  ├─ decision_log.md
│  ├─ decision_log.zh-CN.md
│  ├─ manual_review_checklist.md
│  ├─ manual_review_checklist.zh-CN.md
│  ├─ schema_contract.md
│  ├─ schema_contract.zh-CN.md
│  ├─ fixed_lambda_selection_contract.md
│  ├─ fixed_lambda_selection_contract.zh-CN.md
│  ├─ lambda_bracketing_contract.md
│  ├─ lambda_bracketing_contract.zh-CN.md
│  ├─ lambda_bisection_contract.md
│  └─ lambda_bisection_contract.zh-CN.md
├─ schemas/
│  ├─ stage2_input.schema.json
│  ├─ distance_lookup.schema.json
│  ├─ stage2_result.schema.json
│  └─ .gitkeep
├─ data/
│  └─ lookups/
│     └─ .gitkeep
├─ tests/
│  ├─ test_models_handcheck.py
│  ├─ test_lambda_bracketing.py
│  ├─ test_lambda_bisection.py
│  └─ fixtures/
│     ├─ handcheck_3x3/
│     │  ├─ input_success.json
│     │  ├─ input_infeasible.json
│     │  ├─ distance_lookup.json
│     │  ├─ expected_success_result.json
│     │  ├─ expected_infeasible_result.json
│     │  ├─ hand_calculation.md
│     │  └─ hand_calculation.zh-CN.md
│     └─ .gitkeep
├─ src/
│  ├─ pcv_stage2/
│  │  ├─ __init__.py
│  │  ├─ models.py
│  │  ├─ preprocess.py
│  │  └─ io.py
│  └─ .gitkeep
├─ scripts/
│  └─ validate_handcheck_fixtures.py
├─ outputs/
│  └─ .gitkeep
└─ reference_docs/
   └─ local read-only reference documents
```

`reference_docs/` is local context and is ignored by Git.

## Available Documents

- [Current Implementation State](docs/IMPLEMENTATION_STATE_CURRENT.md): quick handoff summary for the current phase, decisions, assets, and next-step suggestions.
- [Fixed-Lambda Selection Contract](docs/fixed_lambda_selection_contract.md): local fixed-lambda candidate rule, tie-breaking, and solver boundary.
- [Lambda Bracketing Contract](docs/lambda_bracketing_contract.md): adaptive upper-bound bracketing, trace fields, and solver boundary.
- [Lambda Bisection Contract](docs/lambda_bisection_contract.md): bisection trace accumulation, best-feasible candidate ranking, and solver boundary.
- [Stage2 MVP Contract](docs/stage2_mvp_contract.md): planned algorithm contract, model boundaries, inputs, outputs, invariants, and resolved MVP decision defaults.
- [Schema Contract](docs/schema_contract.md): explains the Stage2 input, distance lookup, and result Schema drafts.
- [Decision Log](docs/decision_log.md): decision gates for lookup semantics, infeasible budget behavior, multiplier search rules, and provenance vocabulary.
- [Manual Review Checklist](docs/manual_review_checklist.md): questions for researcher-side review of the generated Stage2 contract.
- [Handcheck Fixture Notes](tests/fixtures/handcheck_3x3/hand_calculation.md): manual calculation for the synthetic 3x3 fixture.
- [Chinese Current Implementation State](docs/IMPLEMENTATION_STATE_CURRENT.zh-CN.md)
- [Chinese Fixed-Lambda Selection Contract](docs/fixed_lambda_selection_contract.zh-CN.md)
- [Chinese Lambda Bracketing Contract](docs/lambda_bracketing_contract.zh-CN.md)
- [Chinese Lambda Bisection Contract](docs/lambda_bisection_contract.zh-CN.md)
- [中文 Stage2 MVP 契约](docs/stage2_mvp_contract.zh-CN.md)
- [中文 Schema 契约](docs/schema_contract.zh-CN.md)
- [中文决策记录](docs/decision_log.zh-CN.md)
- [中文人工验收清单](docs/manual_review_checklist.zh-CN.md)

## Not Implemented Yet

This repository currently has no:

- Stage2 solver;
- final `solve_stage2` API;
- final `SUCCESS` / `INFEASIBLE_BUDGET` result assembly;
- JSON result serializer;
- local upgrade;
- general-purpose JSON validator;
- fixture generator;
- formal experiment result;
- Web player integration;
- online Stage1 interface.

It should not be described as a completed or validated Stage2 allocator.

## Next Plan

After Phase 1D is reviewed, the next suggested step is to plan the final `solve_stage2` API and result assembly boundary. Local upgrade, exact MCKP solving, baselines, experiments, and player integration remain outside the current scope.
