Languages: English | [中文](manual_review_checklist.zh-CN.md)

# Manual Review Checklist

Use this checklist to review the Phase 0A and Phase 0A.1 outputs and verify that the Stage2 contract has not gone beyond the approved scope.

## 1. Project Boundary

- [ ] Can I explain the responsibility difference between Stage1 and Stage2 in my own words?
- [ ] Can I explain why this repository is not a complete player?
- [ ] Can I explain why the distance calibration project is not the Stage2 allocator?
- [ ] Can I list the functions explicitly not implemented in Phase 0A?

## 2. Mathematical Model

- [ ] Can I explain why the original Stage2 problem is an MCKP?
- [ ] Can I explain what "each tile selects exactly one level" means?
- [ ] Can I explain the total budget constraint?
- [ ] Can I explain the role of each factor in the net utility?
- [ ] Can I explain how increasing `eta` may affect allocation behavior?
- [ ] Can I explain why tiles can be selected independently after `lambda` is fixed?
- [ ] Can I explain why the algorithm must not claim strict global optimality?

## 3. Lookup Semantics

- [ ] Can I explain lookup as a candidate upper bound?
- [ ] Can I give the allowed levels when `lookup_level=3`?
- [ ] Can I explain why near-field level 5 means no clipping, not forced level 5?
- [ ] Can I explain why normalized distance is not physical meters?
- [ ] Can I explain why the current lookup cannot be generalized directly to all point-cloud content?

## 4. Infeasible Budget

- [ ] Can I compute the concept of minimum feasible budget?
- [ ] Can I explain why a budget can be infeasible?
- [ ] Can I explain why the solver must not silently exceed budget?
- [ ] Can I explain why dropping participating tiles cannot be used to fake feasibility?
- [ ] Can I explain why `INFEASIBLE_BUDGET` is a hard-constraint incompatibility rather than an algorithm failure?
- [ ] Can I list the fields expected in an `INFEASIBLE_BUDGET` output, including `budget_total`, `b_min_feasible`, and `budget_gap`?
- [ ] Is D0-2 now in `RESOLVED_USER_CONFIRMED` status?

## 5. Lambda Search Rules

- [ ] Can I explain why the future solver must check `B_min_feasible` before entering `lambda` search?
- [ ] Can I explain adaptive `lambda_high` bracketing and why it avoids relying on a manually fixed upper bound?
- [ ] Can I explain what information should be recorded for each bisection iteration?
- [ ] Can I explain how the current best feasible solution is selected?
- [ ] Can I explain the deterministic tie-breaking rule for a single tile under fixed `lambda`?
- [ ] Can I explain why search termination must not produce a budget-violating output?
- [ ] Is D0-3 now in `RESOLVED_USER_CONFIRMED` status?

## 6. Data Provenance

- [ ] Can I distinguish `measured`, `calibrated`, `derived`, `proxy`, and `synthetic`?
- [ ] Can I identify which future fields may initially use proxy values?
- [ ] Can I explain why proxy values must not be described as real decoding measurements?
- [ ] Can I explain which provenance type lookup belongs to?

## 7. Codex Output Review

- [ ] Does any document introduce an unconfirmed new algorithm assumption?
- [ ] Is D0-1 correctly recorded as resolved?
- [ ] Are D0-2 and D0-3 correctly recorded as resolved?
- [ ] Is D0-4 still kept as `DRAFT`?
- [ ] Are English and Chinese documents technically consistent?
- [ ] Is the Chinese version natural rather than mechanically translated?
- [ ] Does the Chinese version avoid unnecessary English for ordinary concepts?
- [ ] Were any algorithm source files, Schemas, or test fixtures created by mistake?
- [ ] Was `reference_docs/` modified?
- [ ] Did any work exceed Phase 0A scope?

## 8. File And Scope Check

- [ ] `.gitignore` includes `/reference_docs/`.
- [ ] `src/` contains no algorithm source file.
- [ ] `schemas/` contains no Schema file.
- [ ] `tests/fixtures/` contains no fixture data.
- [ ] The documents state that no Stage2 solver has been implemented.
- [ ] The documents state that near-field lookup level 5 does not force the final selected level to 5.
