from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = ROOT / "tests"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from helpers.generic_cases import candidate, lookup_for_tiles, stage2_case, tile
from pcv_stage2.io import load_distance_lookup, load_stage2_input
from pcv_stage2.models import DistanceLookup, LookupDistanceMatch, LookupRule
from pcv_stage2.preprocess import (
    PreprocessError,
    compute_b_min_feasible,
    compute_net_utility,
    match_lookup_rule,
    resolve_allowed_candidates,
    resolve_lookup_for_input,
    select_fixed_lambda,
)


FIXTURE = ROOT / "tests" / "fixtures" / "handcheck_3x3"


def fixed_lambda_selection_map(result):
    return {selection.tile_id: selection for selection in result.tile_selections}


def test_success_handcheck_lookup_and_expected_selection() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")

    resolutions = {
        resolution.tile_id: list(resolution.allowed_candidate_ids)
        for resolution in resolve_lookup_for_input(stage2_input, lookup)
    }
    assert resolutions == {
        "T1_near_important": ["pdl_0_2", "pdl_0_6", "pdl_1_0"],
        "T2_mid_visible": ["pdl_0_2", "pdl_0_6"],
        "T3_far_capped": ["pdl_0_2"],
    }
    assert compute_b_min_feasible(stage2_input, lookup) == pytest.approx(120)

    selected_candidates = {
        "T1_near_important": "pdl_1_0",
        "T2_mid_visible": "pdl_0_2",
        "T3_far_capped": "pdl_0_2",
    }

    total_bytes = 0.0
    total_net_utility = 0.0
    for tile_id, candidate_id in selected_candidates.items():
        tile_item = stage2_input.tile_by_id(tile_id)
        option = tile_item.candidate_by_id(candidate_id)
        total_bytes += option.r_bytes
        total_net_utility += compute_net_utility(
            tile_item,
            option,
            stage2_input.eta,
        )

    assert total_bytes == pytest.approx(200)
    assert total_net_utility == pytest.approx(39.5)


def test_fixed_lambda_zero_selects_max_net_utility_per_allowed_tile() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")

    result = select_fixed_lambda(stage2_input, lookup, lambda_value=0.0)
    selected = fixed_lambda_selection_map(result)

    assert {tile_id: item.selected_candidate_id for tile_id, item in selected.items()} == {
        "T1_near_important": "pdl_1_0",
        "T2_mid_visible": "pdl_0_6",
        "T3_far_capped": "pdl_0_2",
    }
    assert list(selected["T3_far_capped"].allowed_candidate_ids) == ["pdl_0_2"]
    assert result.total_bytes == pytest.approx(240)
    assert result.total_net_utility == pytest.approx(45.4)
    assert result.total_penalized_score == pytest.approx(45.4)
    assert result.budget_total_bytes == pytest.approx(210)
    assert result.is_budget_feasible is False


def test_fixed_lambda_nonzero_penalty_changes_handcheck_selection() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")

    result = select_fixed_lambda(stage2_input, lookup, lambda_value=0.2)
    selected = fixed_lambda_selection_map(result)

    assert {tile_id: item.selected_candidate_id for tile_id, item in selected.items()} == {
        "T1_near_important": "pdl_1_0",
        "T2_mid_visible": "pdl_0_2",
        "T3_far_capped": "pdl_0_2",
    }
    assert result.total_bytes == pytest.approx(200)
    assert result.total_net_utility == pytest.approx(39.5)
    assert result.total_penalized_score == pytest.approx(-0.5)
    assert result.is_budget_feasible is True


def test_fixed_lambda_tie_break_prefers_smaller_bytes_before_candidate_identity() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")

    result = select_fixed_lambda(stage2_input, lookup, lambda_value=0.2475)
    selected = fixed_lambda_selection_map(result)

    assert selected["T1_near_important"].selected_candidate_id == "pdl_0_2"
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

    b_min_feasible = compute_b_min_feasible(stage2_input, lookup)
    budget_gap = b_min_feasible - stage2_input.budget_total_bytes

    assert stage2_input.budget_total_bytes == pytest.approx(100)
    assert b_min_feasible == pytest.approx(120)
    assert budget_gap == pytest.approx(20)


def test_pdl_cap_above_existing_candidates_keeps_all_existing_candidates() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    base_lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    tile_item = stage2_input.tile_by_id("T1_near_important")

    near_field_lookup = DistanceLookup(
        schema_version=base_lookup.schema_version,
        lookup_profile_id=base_lookup.lookup_profile_id,
        semantics="cap",
        distance_unit=base_lookup.distance_unit,
        pdl_support=base_lookup.pdl_support,
        source=base_lookup.source,
        rules=(
            LookupRule(
                rule_id="synthetic_near_field_pdl1_0",
                view_context=tile_item.view_context,
                target_id=None,
                distance_match=LookupDistanceMatch(exact_distance=tile_item.distance_norm),
                pdl_max_dist=1.0,
                threshold_profile="handcheck_pdl_cap_profile",
            ),
        ),
    )

    resolution = resolve_allowed_candidates(tile_item, near_field_lookup)
    assert resolution.pdl_max_dist == pytest.approx(1.0)
    assert list(resolution.allowed_candidate_ids) == ["pdl_0_2", "pdl_0_6", "pdl_1_0"]


def test_candidate_array_order_does_not_change_non_tie_decision() -> None:
    forward_candidates = (
        candidate("z_large_but_bad", pdl_ratio=0.4, q_base=1.0, r_bytes=200.0),
        candidate("a_small_best", pdl_ratio=0.4, q_base=10.0, r_bytes=20.0),
        candidate("m_middle", pdl_ratio=0.4, q_base=5.0, r_bytes=100.0),
    )
    reverse_candidates = tuple(reversed(forward_candidates))
    profile_id = "candidate_order_non_tie"
    inputs = []
    for scenario_id, items in (
        ("candidate_order_forward", forward_candidates),
        ("candidate_order_reverse", reverse_candidates),
    ):
        tiles = (
            tile(
                "A_tile",
                distance_norm=1.0,
                candidates=items,
            ),
        )
        inputs.append(
            (
                stage2_case(
                    scenario_id=scenario_id,
                    budget_total_bytes=500.0,
                    tiles=tiles,
                    lookup_profile_id=profile_id,
                ),
                lookup_for_tiles(
                    profile_id=profile_id,
                    tiles=tiles,
                    pdl_max_by_tile={"A_tile": 0.4},
                ),
            )
        )

    selections = [
        select_fixed_lambda(stage2_input, lookup, lambda_value=0.0).tile_selections[
            0
        ].selected_candidate_id
        for stage2_input, lookup in inputs
    ]
    assert selections == ["a_small_best", "a_small_best"]


@pytest.mark.parametrize("target_id", ["T1_near_important", "upper_body"])
def test_target_aware_lookup_rule_is_rejected(target_id: str) -> None:
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
                target_id=target_id,
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

    with pytest.raises(PreprocessError, match="Stage2Input v0.2.*target_id.*tile_id"):
        match_lookup_rule(tile_item, lookup)

    with pytest.raises(PreprocessError, match="Stage2Input v0.2.*target_id.*tile_id"):
        select_fixed_lambda(stage2_input, lookup, lambda_value=0.0)
