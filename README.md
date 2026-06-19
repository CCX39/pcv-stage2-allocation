Languages: English | [中文](README.zh-CN.md)

# pcv-stage2-allocation

`pcv-stage2-allocation` is the Stage2 workspace for Work1 of the research topic "Lightweight viewport-aware point-cloud volumetric video transmission and rendering co-optimization." Its purpose is to define, review, and later implement the spatial tile quality allocation mechanism under a total GoF data budget.

This repository is currently at **Phase 0B: Stage2 MVP JSON Schema drafts**. Phase 0A created the project skeleton and algorithm contract draft; Phase 0A.1 froze the MVP default behavior for infeasible budgets and `lambda` search rules; Phase 0B adds draft schemas for Stage2 input, distance lookup, and future result output. These phases create documentation and traceable engineering boundaries only. They do not implement the Stage2 solver.

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

These schemas define data formats only. They do not implement validation code, a solver, fixtures, or experiments.

## Current Structure

```text
pcv-stage2-allocation/
├─ README.md
├─ README.zh-CN.md
├─ .gitignore
├─ docs/
│  ├─ stage2_mvp_contract.md
│  ├─ stage2_mvp_contract.zh-CN.md
│  ├─ decision_log.md
│  ├─ decision_log.zh-CN.md
│  ├─ manual_review_checklist.md
│  ├─ manual_review_checklist.zh-CN.md
│  ├─ schema_contract.md
│  └─ schema_contract.zh-CN.md
├─ schemas/
│  ├─ stage2_input.schema.json
│  ├─ distance_lookup.schema.json
│  ├─ stage2_result.schema.json
│  └─ .gitkeep
├─ data/
│  └─ lookups/
│     └─ .gitkeep
├─ tests/
│  └─ fixtures/
│     └─ .gitkeep
├─ src/
│  └─ .gitkeep
├─ outputs/
│  └─ .gitkeep
└─ reference_docs/
   └─ local read-only reference documents
```

`reference_docs/` is local context and is ignored by Git.

## Available Documents

- [Stage2 MVP Contract](docs/stage2_mvp_contract.md): planned algorithm contract, model boundaries, inputs, outputs, invariants, and resolved MVP decision defaults.
- [Schema Contract](docs/schema_contract.md): explains the Stage2 input, distance lookup, and result Schema drafts.
- [Decision Log](docs/decision_log.md): decision gates for lookup semantics, infeasible budget behavior, multiplier search rules, and provenance vocabulary.
- [Manual Review Checklist](docs/manual_review_checklist.md): questions for researcher-side review of the generated Stage2 contract.
- [中文 Stage2 MVP 契约](docs/stage2_mvp_contract.zh-CN.md)
- [中文 Schema 契约](docs/schema_contract.zh-CN.md)
- [中文决策记录](docs/decision_log.zh-CN.md)
- [中文人工验收清单](docs/manual_review_checklist.zh-CN.md)

## Not Implemented Yet

This repository currently has no:

- Stage2 solver;
- implemented JSON validator;
- test fixture;
- formal experiment result;
- Web player integration;
- online Stage1 interface.

It should not be described as a completed or validated Stage2 allocator.

## Next Plan

After Phase 0B is reviewed, later phases may add validator tooling, prepare controlled fixtures, implement the solver, add end-to-end checks, and run formal experiments. Those steps are intentionally outside the current scope.
