from __future__ import annotations

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

from helpers.exhaustive_oracle import (
    DEFAULT_MAX_ENUMERATED_COMBINATIONS,
    exact_feasible_reference,
)
from helpers.generic_cases import candidate, lookup_for_tiles, stage2_case, tile
from pcv_stage2.io import load_distance_lookup, load_stage2_input
from pcv_stage2.models import LambdaSearchConfig
from pcv_stage2.preprocess import resolve_lookup_for_input
from pcv_stage2.solver import solve_stage2


FIXTURE = ROOT / "tests" / "fixtures" / "handcheck_3x3"
SCORE_EPSILON = 1e-9


def search_config(
    *,
    lambda_initial_high: float = 0.1,
    lambda_max_bracket_steps: int = 2,
    score_epsilon: float = SCORE_EPSILON,
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


def selected_candidate_map(items) -> dict[str, str]:
    return {item.tile_id: item.selected_candidate_id for item in items}


def test_exhaustive_oracle_handcheck_exact_reference_and_constraints() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    resolutions = resolve_lookup_for_input(stage2_input, lookup)

    oracle = exact_feasible_reference(
        stage2_input,
        resolutions,
        score_epsilon=SCORE_EPSILON,
    )

    assert selected_candidate_map(oracle.selected_tiles) == {
        "T1_near_important": "pdl_1_0",
        "T2_mid_visible": "pdl_0_2",
        "T3_far_capped": "pdl_0_2",
    }
    assert oracle.total_bytes == pytest.approx(200)
    assert oracle.total_net_utility == pytest.approx(39.5)
    assert oracle.combination_count == 6

    allowed_by_tile = {
        resolution.tile_id: set(resolution.allowed_candidate_ids)
        for resolution in resolutions
    }
    assert len(oracle.selected_tiles) == len(stage2_input.tiles)
    assert {item.tile_id for item in oracle.selected_tiles} == {
        tile_item.tile_id for tile_item in stage2_input.tiles
    }
    for item in oracle.selected_tiles:
        assert item.selected_candidate_id in allowed_by_tile[item.tile_id]
    assert oracle.total_bytes <= stage2_input.budget_total_bytes


def test_runtime_solver_total_net_utility_does_not_exceed_exact_reference() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    resolutions = resolve_lookup_for_input(stage2_input, lookup)

    solver_result = solve_stage2(stage2_input, lookup, search_config())
    oracle = exact_feasible_reference(
        stage2_input,
        resolutions,
        score_epsilon=SCORE_EPSILON,
    )

    assert solver_result.status == "SUCCESS"
    assert solver_result.total_bytes is not None
    assert solver_result.total_bytes <= stage2_input.budget_total_bytes
    assert solver_result.total_net_utility is not None
    assert solver_result.total_net_utility <= oracle.total_net_utility + SCORE_EPSILON


def local_repair_reaches_oracle_case():
    tiles = (
        tile(
            "A_tile",
            distance_norm=1.0,
            candidates=(
                candidate("z_seed", pdl_ratio=0.4, q_base=50.0, r_bytes=50.0),
                candidate("a_switch", pdl_ratio=0.2, q_base=65.0, r_bytes=110.0),
            ),
        ),
        tile(
            "B_tile",
            distance_norm=2.0,
            candidates=(
                candidate("z_seed", pdl_ratio=0.4, q_base=50.0, r_bytes=50.0),
                candidate("b_switch", pdl_ratio=0.2, q_base=60.0, r_bytes=110.0),
            ),
        ),
    )
    profile_id = "synthetic_local_repair_oracle_lookup"
    stage2_input = stage2_case(
        scenario_id="synthetic_local_repair_reaches_oracle",
        budget_total_bytes=160.0,
        tiles=tiles,
        lookup_profile_id=profile_id,
    )
    return (
        stage2_input,
        lookup_for_tiles(
            profile_id=profile_id,
            tiles=tiles,
            pdl_max_by_tile={"A_tile": 0.4, "B_tile": 0.4},
        ),
    )


def test_local_repair_reaches_exact_reference_with_candidate_switch() -> None:
    stage2_input, lookup = local_repair_reaches_oracle_case()
    resolutions = resolve_lookup_for_input(stage2_input, lookup)

    solver_result = solve_stage2(
        stage2_input,
        lookup,
        search_config(
            lambda_initial_high=1.0,
            lambda_max_bracket_steps=1,
            lambda_epsilon=0.0,
            max_iterations=0,
        ),
    )
    oracle = exact_feasible_reference(
        stage2_input,
        resolutions,
        score_epsilon=SCORE_EPSILON,
    )

    assert solver_result.status == "SUCCESS"
    assert solver_result.local_upgrade.enabled is True
    assert solver_result.local_upgrade.steps
    step = solver_result.local_upgrade.steps[0]
    assert step.from_candidate_id == "z_seed"
    assert step.to_candidate_id == "a_switch"
    assert solver_result.total_bytes is not None
    assert solver_result.total_bytes <= stage2_input.budget_total_bytes
    assert solver_result.total_net_utility == pytest.approx(oracle.total_net_utility)
    assert selected_candidate_map(solver_result.selected_tiles) == selected_candidate_map(
        oracle.selected_tiles
    )


def lookup_cap_boundary_case():
    tiles = (
        tile(
            "A_cross_format",
            distance_norm=1.0,
            candidates=(
                candidate("ply_pdl_0_4", pdl_ratio=0.4, q_base=1.0, r_bytes=10.0),
                candidate(
                    "drc_pdl_0_4_qp8",
                    pdl_ratio=0.4,
                    file_format="drc",
                    codec="draco",
                    codec_params={"qp": 8},
                    q_base=2.0,
                    r_bytes=20.0,
                ),
                candidate(
                    "drc_pdl_0_4_qp12",
                    pdl_ratio=0.4,
                    file_format="drc",
                    codec="draco",
                    codec_params={"qp": 12},
                    q_base=3.0,
                    r_bytes=30.0,
                ),
                candidate("ply_pdl_0_8", pdl_ratio=0.8, q_base=1000.0, r_bytes=40.0),
                candidate(
                    "drc_pdl_0_8_qp10",
                    pdl_ratio=0.8,
                    file_format="drc",
                    codec="draco",
                    codec_params={"qp": 10},
                    q_base=2000.0,
                    r_bytes=50.0,
                ),
            ),
        ),
    )
    profile_id = "synthetic_lookup_pdl_boundary"
    return (
        stage2_case(
            scenario_id="synthetic_lookup_pdl_boundary",
            budget_total_bytes=300.0,
            tiles=tiles,
            lookup_profile_id=profile_id,
        ),
        lookup_for_tiles(
            profile_id=profile_id,
            tiles=tiles,
            pdl_max_by_tile={"A_cross_format": 0.4},
        ),
    )


def test_lookup_cap_keeps_same_pdl_cross_format_and_rejects_high_pdl() -> None:
    stage2_input, lookup = lookup_cap_boundary_case()
    resolutions = resolve_lookup_for_input(stage2_input, lookup)
    resolution = resolutions[0]

    assert resolution.allowed_candidate_ids == (
        "ply_pdl_0_4",
        "drc_pdl_0_4_qp8",
        "drc_pdl_0_4_qp12",
    )
    assert resolution.rejected_candidate_ids == (
        "ply_pdl_0_8",
        "drc_pdl_0_8_qp10",
    )

    oracle = exact_feasible_reference(
        stage2_input,
        resolutions,
        score_epsilon=SCORE_EPSILON,
    )
    solver_result = solve_stage2(stage2_input, lookup, search_config())

    assert oracle.selected_tiles[0].selected_candidate_id == "drc_pdl_0_4_qp12"
    assert solver_result.status == "SUCCESS"
    assert solver_result.selected_tiles[0].selected_candidate_id == "drc_pdl_0_4_qp12"


def single_tile_tie_case(
    *,
    scenario_id: str,
    candidates,
    score_epsilon: float,
) -> str:
    tiles = (
        tile(
            "A_tile",
            distance_norm=1.0,
            candidates=tuple(candidates),
        ),
    )
    profile_id = f"{scenario_id}_lookup"
    stage2_input = stage2_case(
        scenario_id=scenario_id,
        budget_total_bytes=20.0,
        tiles=tiles,
        lookup_profile_id=profile_id,
    )
    lookup = lookup_for_tiles(
        profile_id=profile_id,
        tiles=tiles,
        pdl_max_by_tile={"A_tile": 0.5},
    )
    oracle = exact_feasible_reference(
        stage2_input,
        resolve_lookup_for_input(stage2_input, lookup),
        score_epsilon=score_epsilon,
    )
    return oracle.selected_tiles[0].selected_candidate_id


def test_exhaustive_oracle_tie_breaks_by_budget_decode_and_selection_order() -> None:
    assert single_tile_tie_case(
        scenario_id="synthetic_tie_budget_utilization",
        score_epsilon=1e-6,
        candidates=(
            candidate("less_bytes", q_base=10.0000005, r_bytes=10.0, d_ms=1.0),
            candidate("more_bytes", q_base=10.0, r_bytes=20.0, d_ms=100.0),
        ),
    ) == "more_bytes"

    assert single_tile_tie_case(
        scenario_id="synthetic_tie_decode",
        score_epsilon=1e-6,
        candidates=(
            candidate("slow", q_base=10.0, r_bytes=10.0, d_ms=5.0),
            candidate("fast", q_base=10.0, r_bytes=10.0, d_ms=3.0),
        ),
    ) == "fast"

    assert single_tile_tie_case(
        scenario_id="synthetic_tie_selection_sequence",
        score_epsilon=1e-6,
        candidates=(
            candidate("a_stable", q_base=10.0, r_bytes=10.0, d_ms=1.0),
            candidate("b_stable", q_base=10.0, r_bytes=10.0, d_ms=1.0),
        ),
    ) == "a_stable"


def large_combination_case():
    candidate_set = tuple(
        candidate(
            f"c_{index}",
            pdl_ratio=index / 10,
            q_base=float(index),
            r_bytes=float(index),
        )
        for index in range(1, 11)
    )
    tiles = tuple(
        tile(f"T{index}", distance_norm=float(index), candidates=candidate_set)
        for index in range(1, 7)
    )
    profile_id = "synthetic_large_exhaustive_oracle_rejection"
    stage2_input = stage2_case(
        scenario_id="synthetic_large_exhaustive_oracle_rejection",
        budget_total_bytes=1_000_000.0,
        tiles=tiles,
        lookup_profile_id=profile_id,
    )
    return (
        stage2_input,
        lookup_for_tiles(
            profile_id=profile_id,
            tiles=tiles,
            pdl_max_by_tile={item.tile_id: 1.0 for item in tiles},
        ),
    )


def test_exhaustive_oracle_rejects_inputs_above_combination_limit() -> None:
    stage2_input, lookup = large_combination_case()
    resolutions = resolve_lookup_for_input(stage2_input, lookup)

    with pytest.raises(ValueError, match="test-only exhaustive oracle"):
        exact_feasible_reference(
            stage2_input,
            resolutions,
            max_enumerated_combinations=DEFAULT_MAX_ENUMERATED_COMBINATIONS,
        )
