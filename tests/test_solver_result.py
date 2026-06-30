from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = ROOT / "tests"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from helpers.generic_cases import candidate, lookup_for_tiles, stage2_case, tile
from pcv_stage2 import solver as solver_module
from pcv_stage2.io import load_distance_lookup, load_stage2_input
from pcv_stage2.models import (
    DistanceLookup,
    FixedLambdaSelection,
    FixedLambdaTileSelection,
    LambdaSearchConfig,
    LambdaSearchResult,
    LambdaSelectedCandidate,
    LambdaTracePoint,
    LookupDistanceMatch,
    LookupRule,
)
from pcv_stage2.solver import InternalSolverInvariantError, solve_stage2


FIXTURE = ROOT / "tests" / "fixtures" / "handcheck_3x3"
RESULT_SCHEMA = ROOT / "schemas" / "stage2_result.schema.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def search_config(
    *,
    lambda_initial_high: float = 0.1,
    lambda_max_bracket_steps: int = 2,
    score_epsilon: float = 1e-9,
    lambda_epsilon: float = 0.0125,
    max_iterations: int = 10,
) -> LambdaSearchConfig:
    return LambdaSearchConfig(
        lambda_initial_high=lambda_initial_high,
        lambda_max_bracket_steps=lambda_max_bracket_steps,
        score_epsilon=score_epsilon,
        lambda_epsilon=lambda_epsilon,
        max_iterations=max_iterations,
    )


def assert_schema_valid(payload: dict) -> None:
    json.dumps(payload)
    schema = load_json(RESULT_SCHEMA)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)


def selected_candidate_map(payload: dict) -> dict[str, str]:
    return {
        item["tile_id"]: item["selected_candidate_id"]
        for item in payload["selected_tiles"]
    }


def synthetic_switch_case():
    tiles = (
        tile(
            "A_tile",
            distance_norm=1.0,
            candidates=(
                candidate("z_seed", pdl_ratio=0.4, q_base=50.0, r_bytes=50.0),
                candidate(
                    "a_switch",
                    pdl_ratio=0.2,
                    q_base=60.0,
                    r_bytes=110.0,
                    d_ms=2.0,
                ),
            ),
        ),
        tile(
            "B_tile",
            distance_norm=2.0,
            candidates=(
                candidate("z_seed", pdl_ratio=0.4, q_base=50.0, r_bytes=50.0),
                candidate(
                    "b_switch",
                    pdl_ratio=0.2,
                    q_base=60.0,
                    r_bytes=110.0,
                    d_ms=2.0,
                ),
            ),
        ),
    )
    stage2_input = stage2_case(
        scenario_id="synthetic_local_switch_tie",
        budget_total_bytes=160.0,
        eta=0.0,
        lookup_profile_id="synthetic_switch_lookup",
        tiles=tiles,
    )
    lookup = lookup_for_tiles(
        profile_id="synthetic_switch_lookup",
        tiles=tiles,
        pdl_max_by_tile={"A_tile": 0.4, "B_tile": 0.4},
    )
    return stage2_input, lookup


def test_solver_success_matches_handcheck_and_schema() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")

    result = solve_stage2(stage2_input, lookup, search_config())
    payload = result.to_dict()

    assert payload["status"] == "SUCCESS"
    assert selected_candidate_map(payload) == {
        "T1_near_important": "pdl_1_0",
        "T2_mid_visible": "pdl_0_2",
        "T3_far_capped": "pdl_0_2",
    }
    assert payload["total_bytes"] == pytest.approx(200)
    assert payload["total_net_utility"] == pytest.approx(39.5)
    assert payload["total_spatial_utility"] == pytest.approx(40)
    assert payload["total_decode_ms"] == pytest.approx(5)
    assert payload["budget_total_bytes"] == pytest.approx(210)
    assert payload["budget_utilization"] == pytest.approx(200 / 210)
    assert payload["runtime_ms"] >= 0
    assert payload["lambda_search"]["enabled"] is True
    assert payload["lambda_search"]["best_feasible_iteration"] is not None
    assert payload["local_upgrade"]["enabled"] is True
    assert payload["local_upgrade"]["steps"] == []
    assert payload["local_upgrade"]["termination_reason"] == "NO_FEASIBLE_POSITIVE_SWITCH"
    assert payload["local_upgrade"]["initial_total_bytes"] == pytest.approx(200)
    assert payload["local_upgrade"]["initial_total_net_utility"] == pytest.approx(39.5)

    for item in payload["selected_tiles"]:
        assert item["selected_candidate_id"] in item["allowed_candidate_ids"]
        snapshot = item["selected_candidate_snapshot"]
        assert snapshot["candidate_id"] == item["selected_candidate_id"]
        assert snapshot["provenance"]["r_bytes"] == "synthetic"
    assert selected_candidate_map(payload)["T3_far_capped"] == "pdl_0_2"

    assert_schema_valid(payload)


def test_solver_local_repair_applies_candidate_switch_and_preserves_trace() -> None:
    stage2_input, lookup = synthetic_switch_case()

    result = solve_stage2(stage2_input, lookup, search_config())
    payload = result.to_dict()

    assert payload["status"] == "SUCCESS"
    assert payload["local_upgrade"]["enabled"] is True
    assert payload["local_upgrade"]["initial_total_bytes"] == pytest.approx(100)
    assert payload["local_upgrade"]["initial_total_net_utility"] == pytest.approx(100)
    assert payload["local_upgrade"]["initial_total_decode_ms"] == pytest.approx(2)
    assert payload["local_upgrade"]["seed_best_feasible_trace_index"] == payload[
        "lambda_search"
    ]["best_feasible_iteration"]
    assert len(payload["local_upgrade"]["steps"]) == 1

    step = payload["local_upgrade"]["steps"][0]
    assert step["step_index"] == 0
    assert step["tile_id"] == "A_tile"
    assert step["from_candidate_id"] == "z_seed"
    assert step["to_candidate_id"] == "a_switch"
    assert step["delta_r_bytes"] == pytest.approx(60)
    assert step["delta_net_utility"] == pytest.approx(10)
    assert step["gain_per_byte"] == pytest.approx(10 / 60)
    assert step["residual_budget_before"] == pytest.approx(60)
    assert step["residual_budget_after"] == pytest.approx(0)
    assert step["total_bytes_after"] == pytest.approx(160)
    assert step["total_net_utility_after"] == pytest.approx(110)
    assert step["total_decode_ms_after"] == pytest.approx(3)

    assert selected_candidate_map(payload) == {
        "A_tile": "a_switch",
        "B_tile": "z_seed",
    }
    assert payload["total_bytes"] == pytest.approx(160)
    assert payload["total_bytes"] <= payload["budget_total_bytes"]
    assert payload["total_net_utility"] == pytest.approx(110)
    assert payload["total_net_utility"] > payload["local_upgrade"]["initial_total_net_utility"]
    assert payload["total_decode_ms"] == pytest.approx(3)

    seed_index = payload["lambda_search"]["best_feasible_iteration"]
    seed_trace = payload["lambda_search"]["iterations"][seed_index]
    assert {
        item["tile_id"]: item["selected_candidate_id"]
        for item in seed_trace["selected_candidates"]
    } == {
        "A_tile": "z_seed",
        "B_tile": "z_seed",
    }
    assert selected_candidate_map(payload) != {
        item["tile_id"]: item["selected_candidate_id"]
        for item in seed_trace["selected_candidates"]
    }

    assert_schema_valid(payload)


def test_solver_infeasible_budget_returns_structured_result_and_schema() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_infeasible.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")

    result = solve_stage2(stage2_input, lookup, search_config())
    payload = result.to_dict()

    assert payload["status"] == "INFEASIBLE_BUDGET"
    assert payload["b_min_feasible"] == pytest.approx(120)
    assert payload["budget_gap"] == pytest.approx(20)
    assert payload["selected_tiles"] == []
    assert payload["total_bytes"] is None
    assert payload["total_net_utility"] is None
    assert payload["total_spatial_utility"] is None
    assert payload["total_decode_ms"] is None
    assert payload["budget_utilization"] is None
    assert payload["lambda_search"]["enabled"] is False
    assert payload["lambda_search"]["iterations"] == []
    assert payload["lambda_search"]["best_feasible_iteration"] is None
    assert payload["local_upgrade"]["enabled"] is False
    assert payload["local_upgrade"]["steps"] == []
    assert payload["local_upgrade"]["termination_reason"] == "NOT_RUN"

    assert_schema_valid(payload)


def test_solver_bracket_failure_returns_numerical_error_with_trace() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    config = search_config(lambda_max_bracket_steps=1)

    result = solve_stage2(stage2_input, lookup, config)
    payload = result.to_dict()

    assert payload["status"] == "NUMERICAL_ERROR"
    assert payload["status"] != "INFEASIBLE_BUDGET"
    assert payload["selected_tiles"] == []
    assert payload["b_min_feasible"] == pytest.approx(120)
    assert payload["budget_gap"] == pytest.approx(0)
    assert payload["lambda_search"]["enabled"] is True
    assert payload["lambda_search"]["best_feasible_iteration"] is None
    assert payload["local_upgrade"]["enabled"] is False
    assert payload["local_upgrade"]["termination_reason"] == "NOT_RUN"
    assert [item["lambda"] for item in payload["lambda_search"]["iterations"]] == [
        pytest.approx(0.0),
        pytest.approx(0.1),
    ]
    assert payload["errors"][0]["code"] == "LAMBDA_SEARCH_NO_FEASIBLE_CANDIDATE"
    assert "did not recover a budget-feasible candidate" in payload["errors"][0]["message"]

    assert_schema_valid(payload)


def test_solver_returns_structured_internal_violation_when_local_repair_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")

    def raise_invariant(*_args: object, **_kwargs: object) -> None:
        raise InternalSolverInvariantError("synthetic test failure")

    monkeypatch.setattr(solver_module, "_apply_local_upgrade", raise_invariant)

    result = solve_stage2(stage2_input, lookup, search_config())
    payload = result.to_dict()

    assert payload["status"] == "INTERNAL_CONSTRAINT_VIOLATION"
    assert payload["selected_tiles"] == []
    assert payload["lambda_search"]["enabled"] is True
    assert payload["lambda_search"]["iterations"]
    assert payload["lambda_search"]["best_feasible_iteration"] is not None
    assert payload["local_upgrade"]["enabled"] is False
    assert payload["local_upgrade"]["steps"] == []
    assert payload["local_upgrade"]["termination_reason"] == "NOT_RUN"
    assert payload["errors"][0]["code"] == "RESULT_INVARIANT_VIOLATION"
    assert "synthetic test failure" in payload["errors"][0]["message"]

    assert_schema_valid(payload)


def test_solver_target_aware_lookup_returns_invalid_lookup() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    base_lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    tile_item = stage2_input.tile_by_id("T1_near_important")

    lookup = DistanceLookup(
        schema_version=base_lookup.schema_version,
        lookup_profile_id=base_lookup.lookup_profile_id,
        semantics="cap",
        distance_unit=base_lookup.distance_unit,
        pdl_support=base_lookup.pdl_support,
        source=base_lookup.source,
        rules=(
            LookupRule(
                rule_id="target_aware_rule",
                view_context=tile_item.view_context,
                target_id="T1_near_important",
                distance_match=LookupDistanceMatch(exact_distance=tile_item.distance_norm),
                pdl_max_dist=1.0,
                threshold_profile="handcheck_pdl_cap_profile",
            ),
            LookupRule(
                rule_id="null_target_fallback_rule",
                view_context=tile_item.view_context,
                target_id=None,
                distance_match=LookupDistanceMatch(exact_distance=tile_item.distance_norm),
                pdl_max_dist=1.0,
                threshold_profile="handcheck_pdl_cap_profile",
            ),
        ),
    )

    result = solve_stage2(stage2_input, lookup, search_config())
    payload = result.to_dict()

    assert payload["status"] == "INVALID_LOOKUP"
    assert payload["selected_tiles"] == []
    assert payload["lambda_search"]["enabled"] is False
    assert payload["lambda_search"]["iterations"] == []
    assert payload["local_upgrade"]["enabled"] is False
    assert payload["errors"][0]["code"] == "INVALID_LOOKUP"
    assert "target_id must not be treated as tile_id" in payload["errors"][0]["message"]

    assert_schema_valid(payload)


def test_solver_no_allowed_candidate_returns_structured_error() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    base_lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    tile_item = stage2_input.tile_by_id("T1_near_important")
    lookup = DistanceLookup(
        schema_version=base_lookup.schema_version,
        lookup_profile_id=base_lookup.lookup_profile_id,
        semantics="cap",
        distance_unit=base_lookup.distance_unit,
        pdl_support=base_lookup.pdl_support,
        source=base_lookup.source,
        rules=(
            LookupRule(
                rule_id="synthetic_no_allowed_candidate",
                view_context=tile_item.view_context,
                target_id=None,
                distance_match=LookupDistanceMatch(exact_distance=tile_item.distance_norm),
                pdl_max_dist=0.1,
                threshold_profile="synthetic_test_only",
            ),
        ),
    )

    result = solve_stage2(stage2_input, lookup, search_config())
    payload = result.to_dict()

    assert payload["status"] == "NO_ALLOWED_CANDIDATE"
    assert payload["selected_tiles"] == []
    assert payload["lambda_search"]["enabled"] is False
    assert payload["local_upgrade"]["enabled"] is False
    assert payload["errors"][0]["code"] == "NO_ALLOWED_CANDIDATE"

    assert_schema_valid(payload)


def test_lambda_search_result_rejects_best_candidate_trace_mismatch() -> None:
    candidate_result = FixedLambdaSelection(
        lambda_value=0.2,
        tile_selections=(
            FixedLambdaTileSelection(
                lambda_value=0.2,
                tile_id="A",
                allowed_candidate_ids=("candidate_a",),
                selected_candidate_id="candidate_a",
                selected_r_bytes=10,
                selected_d_ms=1,
                selected_net_utility=5,
                selected_penalized_score=3,
            ),
        ),
        total_bytes=10,
        total_net_utility=5,
        total_penalized_score=3,
        budget_total_bytes=20,
        is_budget_feasible=True,
    )
    trace = (
        LambdaTracePoint(
            step_index=0,
            lambda_value=0.1,
            total_bytes=10,
            total_net_utility=5,
            total_decode_ms=1,
            is_budget_feasible=True,
            selected_candidates=(
                LambdaSelectedCandidate(
                    tile_id="A",
                    selected_candidate_id="candidate_a",
                ),
            ),
        ),
    )

    with pytest.raises(ValueError, match="must match the referenced trace point"):
        LambdaSearchResult(
            bracket_found=True,
            feasible_at_zero=False,
            bisection_performed=False,
            termination_reason="max_iterations",
            lower_infeasible_lambda=0.0,
            upper_feasible_lambda=0.2,
            best_feasible_candidate=candidate_result,
            best_feasible_trace_index=0,
            trace=trace,
        )
