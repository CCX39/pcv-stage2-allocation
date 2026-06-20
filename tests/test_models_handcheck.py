from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pcv_stage2.io import load_distance_lookup, load_stage2_input
from pcv_stage2.models import DistanceLookup, LookupDistanceMatch, LookupRule
from pcv_stage2.preprocess import (
    PreprocessError,
    compute_b_min_feasible,
    compute_net_utility,
    match_lookup_rule,
    resolve_allowed_levels,
    resolve_lookup_for_input,
    select_fixed_lambda,
)


FIXTURE = ROOT / "tests" / "fixtures" / "handcheck_3x3"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fixed_lambda_selection_map(result):
    return {selection.tile_id: selection for selection in result.tile_selections}


def test_success_handcheck_lookup_and_expected_selection() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    expected_result = load_json(FIXTURE / "expected_success_result.json")

    resolutions = {
        resolution.tile_id: list(resolution.allowed_levels)
        for resolution in resolve_lookup_for_input(stage2_input, lookup)
    }
    assert resolutions == {
        "T1_near_important": [1, 2, 3],
        "T2_mid_visible": [1, 2],
        "T3_far_capped": [1],
    }
    assert compute_b_min_feasible(stage2_input, lookup) == pytest.approx(120)

    selected_levels = {
        item["tile_id"]: item["selected_level_id"]
        for item in expected_result["selected_tiles"]
    }
    assert selected_levels == {
        "T1_near_important": 3,
        "T2_mid_visible": 1,
        "T3_far_capped": 1,
    }

    total_bytes = 0.0
    total_net_utility = 0.0
    for tile_id, level_id in selected_levels.items():
        tile = stage2_input.tile_by_id(tile_id)
        level = tile.level_by_id(level_id)
        total_bytes += level.r_bytes
        total_net_utility += compute_net_utility(tile, level, stage2_input.eta)

    assert total_bytes == pytest.approx(200)
    assert total_net_utility == pytest.approx(39.5)
    assert expected_result["total_bytes"] == pytest.approx(total_bytes)
    assert expected_result["total_net_utility"] == pytest.approx(total_net_utility)
    assert expected_result["status"] == "SUCCESS"
    assert expected_result["budget_total_bytes"] == pytest.approx(210)


def test_fixed_lambda_zero_selects_max_net_utility_per_allowed_tile() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")

    result = select_fixed_lambda(stage2_input, lookup, lambda_value=0.0)
    selected = fixed_lambda_selection_map(result)

    assert {tile_id: item.selected_level_id for tile_id, item in selected.items()} == {
        "T1_near_important": 3,
        "T2_mid_visible": 2,
        "T3_far_capped": 1,
    }
    assert list(selected["T3_far_capped"].allowed_level_ids) == [1]
    assert result.total_bytes == pytest.approx(240)
    assert result.total_net_utility == pytest.approx(45.4)
    assert result.total_penalized_score == pytest.approx(45.4)
    assert result.budget_total_bytes == pytest.approx(210)
    assert result.is_budget_feasible is False


def test_fixed_lambda_nonzero_penalty_changes_handcheck_selection() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")

    # For T2, score(L2) - score(L1) = 5.9 - 40 * lambda.
    # lambda = 0.2 is above the 0.1475 crossover, so T2 changes from L2 to L1.
    result = select_fixed_lambda(stage2_input, lookup, lambda_value=0.2)
    selected = fixed_lambda_selection_map(result)

    assert {tile_id: item.selected_level_id for tile_id, item in selected.items()} == {
        "T1_near_important": 3,
        "T2_mid_visible": 1,
        "T3_far_capped": 1,
    }
    assert result.total_bytes == pytest.approx(200)
    assert result.total_net_utility == pytest.approx(39.5)
    assert result.total_penalized_score == pytest.approx(-0.5)
    assert result.is_budget_feasible is True


def test_fixed_lambda_tie_break_prefers_smaller_bytes() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")

    # T1 L1/L2/L3 all have the same penalized score at lambda = 9.9 / 40.
    result = select_fixed_lambda(stage2_input, lookup, lambda_value=0.2475)
    selected = fixed_lambda_selection_map(result)

    assert selected["T1_near_important"].selected_level_id == 1
    assert selected["T1_near_important"].selected_penalized_score == pytest.approx(
        -2.475
    )


def test_fixed_lambda_repeated_calls_are_deterministic() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")

    first = select_fixed_lambda(stage2_input, lookup, lambda_value=0.2)
    second = select_fixed_lambda(stage2_input, lookup, lambda_value=0.2)

    assert first == second


@pytest.mark.parametrize("lambda_value", [-0.1, math.nan, math.inf, -math.inf])
def test_fixed_lambda_rejects_invalid_lambda_values(lambda_value: float) -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")

    with pytest.raises(PreprocessError, match="lambda_value must be finite"):
        select_fixed_lambda(stage2_input, lookup, lambda_value=lambda_value)


def test_infeasible_handcheck_budget_gap() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_infeasible.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    expected_result = load_json(FIXTURE / "expected_infeasible_result.json")

    b_min_feasible = compute_b_min_feasible(stage2_input, lookup)
    budget_gap = b_min_feasible - stage2_input.budget_total_bytes

    assert stage2_input.budget_total_bytes == pytest.approx(100)
    assert b_min_feasible == pytest.approx(120)
    assert budget_gap == pytest.approx(20)
    assert expected_result["b_min_feasible"] == pytest.approx(b_min_feasible)
    assert expected_result["budget_gap"] == pytest.approx(budget_gap)
    assert expected_result["status"] == "INFEASIBLE_BUDGET"
    assert expected_result["selected_tiles"] == []


def test_lookup_level_above_existing_max_keeps_all_existing_levels() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    base_lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    tile = stage2_input.tile_by_id("T1_near_important")

    near_field_lookup = DistanceLookup(
        schema_version=base_lookup.schema_version,
        lookup_profile_id=base_lookup.lookup_profile_id,
        semantics="cap",
        distance_unit=base_lookup.distance_unit,
        quality_levels=base_lookup.quality_levels,
        source=base_lookup.source,
        rules=(
            LookupRule(
                rule_id="synthetic_near_field_cap5",
                view_context=tile.view_context,
                target_id=None,
                distance_match=LookupDistanceMatch(exact_distance=tile.distance_norm),
                lookup_level=5,
                threshold_profile="handcheck_cap_profile",
            ),
        ),
    )

    resolution = resolve_allowed_levels(tile, near_field_lookup)
    assert resolution.lookup_level == 5
    assert list(resolution.allowed_levels) == [1, 2, 3]


@pytest.mark.parametrize("target_id", ["T1_near_important", "upper_body"])
def test_target_aware_lookup_rule_is_rejected(target_id: str) -> None:
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
                target_id=target_id,
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

    with pytest.raises(PreprocessError, match="Stage2Input v0.1.*target_id.*tile_id"):
        match_lookup_rule(tile, lookup)

    with pytest.raises(PreprocessError, match="Stage2Input v0.1.*target_id.*tile_id"):
        select_fixed_lambda(stage2_input, lookup, lambda_value=0.0)
