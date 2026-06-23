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

from helpers.exhaustive_oracle import exact_feasible_reference
from pcv_stage2.io import load_distance_lookup, load_json, load_stage2_input
from pcv_stage2.models import LambdaSearchConfig
from pcv_stage2.preprocess import resolve_lookup_for_input
from pcv_stage2.solver import solve_stage2


FIXTURE = ROOT / "tests" / "fixtures" / "calibration_informed_proxy"
INPUT_SCHEMA = ROOT / "schemas" / "stage2_input.schema.json"
LOOKUP_SCHEMA = ROOT / "schemas" / "distance_lookup.schema.json"
RESULT_SCHEMA = ROOT / "schemas" / "stage2_result.schema.json"
SCORE_EPSILON = 1e-9


def search_config() -> LambdaSearchConfig:
    return LambdaSearchConfig(
        lambda_initial_high=0.1,
        lambda_max_bracket_steps=10,
        score_epsilon=SCORE_EPSILON,
        lambda_epsilon=1e-6,
        max_iterations=20,
    )


def assert_schema_valid(payload: dict, schema_path: Path) -> None:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)


def selected_levels(result) -> tuple[tuple[str, int], ...]:
    return tuple(
        (tile.tile_id, tile.selected_level_id) for tile in result.selected_tiles
    )


def solver_signature(result) -> tuple[object, ...]:
    return (
        result.status,
        selected_levels(result),
        result.total_bytes,
        result.total_net_utility,
        result.local_upgrade.to_dict(),
    )


def test_calibration_informed_proxy_fixture_json_schema_and_loader() -> None:
    feasible_payload = load_json(FIXTURE / "input_feasible.json")
    infeasible_payload = load_json(FIXTURE / "input_infeasible.json")
    lookup_payload = load_json(FIXTURE / "distance_lookup_fullbody_strict.json")

    assert_schema_valid(feasible_payload, INPUT_SCHEMA)
    assert_schema_valid(infeasible_payload, INPUT_SCHEMA)
    assert_schema_valid(lookup_payload, LOOKUP_SCHEMA)

    feasible = load_stage2_input(FIXTURE / "input_feasible.json")
    infeasible = load_stage2_input(FIXTURE / "input_infeasible.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup_fullbody_strict.json")

    assert feasible.scenario_id == "calibration_informed_proxy_feasible"
    assert infeasible.scenario_id == "calibration_informed_proxy_infeasible"
    assert lookup.semantics == "cap"
    assert all(rule.target_id is None for rule in lookup.rules)
    assert lookup.source["threshold_profile"] == "strict_p10_ssim_ge_0.98"
    assert lookup.source["source_runs"] == ["20260602_161531_longdress_full10"]


def test_calibration_informed_proxy_fixture_has_no_measured_tile_provenance() -> None:
    for filename in ("input_feasible.json", "input_infeasible.json"):
        payload = load_json(FIXTURE / filename)
        assert "measured" not in json.dumps(payload)
        for tile in payload["tiles"]:
            assert tile["provenance"]["distance_norm"] == "calibrated"
            for field_name in ("p_sal", "visibility", "screen_area", "view_context"):
                assert tile["provenance"][field_name] == "proxy"
            for level in tile["levels"]:
                assert level["provenance"]["pdl_ratio"] == "calibrated"
                assert level["provenance"]["q_base"] == "proxy"
                assert level["provenance"]["r_bytes"] == "proxy"
                assert level["provenance"]["d_ms"] == "proxy"


def test_calibration_informed_proxy_lookup_cap_resolves_allowed_levels() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_feasible.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup_fullbody_strict.json")

    resolutions = resolve_lookup_for_input(stage2_input, lookup)

    assert {
        resolution.tile_id: resolution.allowed_levels for resolution in resolutions
    } == {
        "T_near_core": (1, 2, 3, 4, 5),
        "T_mid_visible": (1, 2, 3),
        "T_far_peripheral": (1, 2),
    }


def test_calibration_informed_proxy_feasible_solver_path_and_determinism() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_feasible.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup_fullbody_strict.json")

    first = solve_stage2(stage2_input, lookup, search_config())
    second = solve_stage2(stage2_input, lookup, search_config())
    payload = first.to_dict()

    assert first.status == "SUCCESS"
    assert len(first.selected_tiles) == len(stage2_input.tiles)
    assert {tile.tile_id for tile in first.selected_tiles} == {
        tile.tile_id for tile in stage2_input.tiles
    }
    assert first.total_bytes is not None
    assert first.total_bytes <= 600.0

    for item in first.selected_tiles:
        assert item.selected_level_id in item.allowed_levels

    json.dumps(payload)
    assert_schema_valid(payload, RESULT_SCHEMA)
    assert solver_signature(first) == solver_signature(second)


def test_calibration_informed_proxy_solver_does_not_exceed_tests_only_oracle() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_feasible.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup_fullbody_strict.json")
    resolutions = resolve_lookup_for_input(stage2_input, lookup)

    solver_result = solve_stage2(stage2_input, lookup, search_config())
    oracle = exact_feasible_reference(
        stage2_input,
        resolutions,
        score_epsilon=SCORE_EPSILON,
    )

    assert solver_result.status == "SUCCESS"
    assert solver_result.total_net_utility is not None
    assert solver_result.total_net_utility <= oracle.total_net_utility + SCORE_EPSILON


def test_calibration_informed_proxy_infeasible_solver_path_and_schema() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_infeasible.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup_fullbody_strict.json")

    result = solve_stage2(stage2_input, lookup, search_config())
    payload = result.to_dict()

    assert result.status == "INFEASIBLE_BUDGET"
    assert result.b_min_feasible == pytest.approx(220.0)
    assert result.budget_total_bytes == pytest.approx(219.0)
    assert result.budget_gap == pytest.approx(1.0)
    assert result.selected_tiles == ()
    assert payload["selected_tiles"] == []
    assert payload["lambda_search"]["enabled"] is False
    assert payload["local_upgrade"]["enabled"] is False

    json.dumps(payload)
    assert_schema_valid(payload, RESULT_SCHEMA)
