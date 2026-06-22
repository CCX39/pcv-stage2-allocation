from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pcv_stage2.io import load_distance_lookup, load_stage2_input
from pcv_stage2.models import (
    DistanceLookup,
    FixedLambdaSelection,
    FixedLambdaTileSelection,
    LambdaSearchConfig,
    LambdaSearchResult,
    LambdaSelectedLevel,
    LambdaTracePoint,
    LookupDistanceMatch,
    LookupRule,
)
from pcv_stage2.solver import solve_stage2


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
    schema = load_json(RESULT_SCHEMA)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)


def selected_level_map(payload: dict) -> dict[str, int]:
    return {
        item["tile_id"]: item["selected_level_id"]
        for item in payload["selected_tiles"]
    }


def test_solver_success_matches_handcheck_and_schema() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    expected_manual = load_json(FIXTURE / "expected_success_result.json")

    result = solve_stage2(stage2_input, lookup, search_config())
    payload = result.to_dict()

    assert payload["status"] == "SUCCESS"
    assert selected_level_map(payload) == {
        "T1_near_important": 3,
        "T2_mid_visible": 1,
        "T3_far_capped": 1,
    }
    assert selected_level_map(payload) == selected_level_map(expected_manual)
    assert payload["total_bytes"] == pytest.approx(200)
    assert payload["total_net_utility"] == pytest.approx(39.5)
    assert payload["total_spatial_utility"] == pytest.approx(40)
    assert payload["total_decode_ms"] == pytest.approx(5)
    assert payload["budget_total_bytes"] == pytest.approx(210)
    assert payload["budget_utilization"] == pytest.approx(200 / 210)
    assert payload["runtime_ms"] >= 0
    assert payload["lambda_search"]["enabled"] is True
    assert payload["lambda_search"]["best_feasible_iteration"] is not None

    allowed_by_tile = {
        item["tile_id"]: set(item["allowed_levels"])
        for item in payload["selected_tiles"]
    }
    for tile_id, selected_level_id in selected_level_map(payload).items():
        assert selected_level_id in allowed_by_tile[tile_id]

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
    assert [item["lambda"] for item in payload["lambda_search"]["iterations"]] == [
        pytest.approx(0.0),
        pytest.approx(0.1),
    ]
    assert payload["errors"][0]["code"] == "LAMBDA_SEARCH_NO_FEASIBLE_CANDIDATE"
    assert "did not recover a budget-feasible candidate" in payload["errors"][0]["message"]

    assert_schema_valid(payload)


def test_solver_target_aware_lookup_returns_invalid_lookup() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    base_lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    tile = stage2_input.tile_by_id("T1_near_important")

    lookup = DistanceLookup(
        schema_version=base_lookup.schema_version,
        lookup_profile_id=base_lookup.lookup_profile_id,
        semantics="cap",
        distance_unit=base_lookup.distance_unit,
        quality_levels=base_lookup.quality_levels,
        source=base_lookup.source,
        rules=(
            LookupRule(
                rule_id="target_aware_rule",
                view_context=tile.view_context,
                target_id="T1_near_important",
                distance_match=LookupDistanceMatch(exact_distance=tile.distance_norm),
                lookup_level=3,
                threshold_profile="handcheck_cap_profile",
            ),
            LookupRule(
                rule_id="null_target_fallback_rule",
                view_context=tile.view_context,
                target_id=None,
                distance_match=LookupDistanceMatch(exact_distance=tile.distance_norm),
                lookup_level=3,
                threshold_profile="handcheck_cap_profile",
            ),
        ),
    )

    result = solve_stage2(stage2_input, lookup, search_config())
    payload = result.to_dict()

    assert payload["status"] == "INVALID_LOOKUP"
    assert payload["selected_tiles"] == []
    assert payload["lambda_search"]["enabled"] is False
    assert payload["lambda_search"]["iterations"] == []
    assert payload["errors"][0]["code"] == "INVALID_LOOKUP"
    assert "target_id must not be treated as tile_id" in payload["errors"][0]["message"]

    assert_schema_valid(payload)


def test_solver_no_allowed_level_returns_structured_error() -> None:
    # Synthetic unit-test-only lookup data, not real Longdress experiment output.
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    base_lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    tile = stage2_input.tile_by_id("T1_near_important")
    dirty_rule = object.__new__(LookupRule)
    object.__setattr__(dirty_rule, "rule_id", "synthetic_no_allowed_level")
    object.__setattr__(dirty_rule, "view_context", tile.view_context)
    object.__setattr__(dirty_rule, "target_id", None)
    object.__setattr__(
        dirty_rule,
        "distance_match",
        LookupDistanceMatch(exact_distance=tile.distance_norm),
    )
    object.__setattr__(dirty_rule, "lookup_level", 0)
    object.__setattr__(dirty_rule, "threshold_profile", "synthetic_test_only")
    object.__setattr__(dirty_rule, "notes", "test-only malformed cap")
    lookup = DistanceLookup(
        schema_version=base_lookup.schema_version,
        lookup_profile_id=base_lookup.lookup_profile_id,
        semantics="cap",
        distance_unit=base_lookup.distance_unit,
        quality_levels=base_lookup.quality_levels,
        source=base_lookup.source,
        rules=(dirty_rule,),
    )

    result = solve_stage2(stage2_input, lookup, search_config())
    payload = result.to_dict()

    assert payload["status"] == "NO_ALLOWED_LEVEL"
    assert payload["selected_tiles"] == []
    assert payload["lambda_search"]["enabled"] is False
    assert payload["errors"][0]["code"] == "NO_ALLOWED_LEVEL"

    assert_schema_valid(payload)


def test_lambda_search_result_rejects_best_candidate_trace_mismatch() -> None:
    candidate = FixedLambdaSelection(
        lambda_value=0.2,
        tile_selections=(
            FixedLambdaTileSelection(
                lambda_value=0.2,
                tile_id="A",
                allowed_level_ids=(1,),
                selected_level_id=1,
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
            selected_levels=(LambdaSelectedLevel(tile_id="A", selected_level_id=1),),
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
            best_feasible_candidate=candidate,
            best_feasible_trace_index=0,
            trace=trace,
        )
