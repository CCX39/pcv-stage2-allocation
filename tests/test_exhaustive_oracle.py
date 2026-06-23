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
from pcv_stage2.io import load_distance_lookup, load_stage2_input
from pcv_stage2.models import (
    DistanceLookup,
    LambdaSearchConfig,
    LookupDistanceMatch,
    LookupQualityLevel,
    LookupRule,
    QualityLevel,
    Stage2Input,
    Tile,
)
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


def level(
    level_id: int,
    *,
    q_base: float,
    r_bytes: float,
    d_ms: float = 1.0,
) -> QualityLevel:
    return QualityLevel(
        level_id=level_id,
        quality_label=f"L{level_id}",
        pdl_ratio=float(level_id),
        q_base=q_base,
        r_bytes=r_bytes,
        d_ms=d_ms,
    )


def tile(
    tile_id: str,
    *,
    distance_norm: float,
    levels: tuple[QualityLevel, ...],
    view_context: str = "synthetic_context",
) -> Tile:
    return Tile(
        tile_id=tile_id,
        p_sal=1.0,
        visibility=1.0,
        screen_area=1.0,
        distance_norm=distance_norm,
        view_context=view_context,
        levels=levels,
    )


def lookup_for_tiles(
    *,
    profile_id: str,
    tiles: tuple[Tile, ...],
    caps: dict[str, int],
    max_level_id: int,
) -> DistanceLookup:
    return DistanceLookup(
        schema_version="0.1.0",
        lookup_profile_id=profile_id,
        semantics="cap",
        distance_unit="normalized_render_distance",
        quality_levels=tuple(
            LookupQualityLevel(
                level_id=level_id,
                pdl_ratio=float(level_id),
                quality_label=f"L{level_id}",
            )
            for level_id in range(1, max_level_id + 1)
        ),
        source={
            "dataset": "synthetic",
            "renderer": "synthetic",
            "metric": "synthetic",
            "threshold_profile": "synthetic",
            "source_runs": [],
        },
        rules=tuple(
            LookupRule(
                rule_id=f"rule_{item.tile_id}",
                view_context=item.view_context,
                target_id=None,
                distance_match=LookupDistanceMatch(
                    exact_distance=item.distance_norm,
                ),
                lookup_level=caps[item.tile_id],
                threshold_profile="synthetic",
            )
            for item in tiles
        ),
    )


def stage2_case(
    *,
    scenario_id: str,
    budget_total_bytes: float,
    tiles: tuple[Tile, ...],
    lookup_profile_id: str,
    eta: float = 0.0,
) -> Stage2Input:
    return Stage2Input(
        schema_version="0.1.0",
        scenario_id=scenario_id,
        budget_total_bytes=budget_total_bytes,
        eta=eta,
        lookup_profile_id=lookup_profile_id,
        tiles=tiles,
        provenance_summary={
            "default_type": "synthetic",
            "source_ids": ["test_exhaustive_oracle"],
        },
        description="Synthetic test-only exhaustive oracle case.",
    )


def selected_level_map(items) -> dict[str, int]:
    return {item.tile_id: item.selected_level_id for item in items}


def test_exhaustive_oracle_handcheck_exact_reference_and_constraints() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    resolutions = resolve_lookup_for_input(stage2_input, lookup)

    oracle = exact_feasible_reference(
        stage2_input,
        resolutions,
        score_epsilon=SCORE_EPSILON,
    )

    assert selected_level_map(oracle.selected_tiles) == {
        "T1_near_important": 3,
        "T2_mid_visible": 1,
        "T3_far_capped": 1,
    }
    assert oracle.total_bytes == pytest.approx(200)
    assert oracle.total_net_utility == pytest.approx(39.5)
    assert oracle.combination_count == 6

    allowed_by_tile = {
        resolution.tile_id: set(resolution.allowed_levels) for resolution in resolutions
    }
    assert len(oracle.selected_tiles) == len(stage2_input.tiles)
    assert {item.tile_id for item in oracle.selected_tiles} == {
        tile.tile_id for tile in stage2_input.tiles
    }
    for item in oracle.selected_tiles:
        assert item.selected_level_id in allowed_by_tile[item.tile_id]
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


def local_upgrade_reaches_oracle_case() -> tuple[Stage2Input, DistanceLookup]:
    tiles = (
        tile(
            "A_tile",
            distance_norm=1.0,
            levels=(
                level(1, q_base=50.0, r_bytes=50.0),
                level(2, q_base=65.0, r_bytes=110.0),
            ),
        ),
        tile(
            "B_tile",
            distance_norm=2.0,
            levels=(
                level(1, q_base=50.0, r_bytes=50.0),
                level(2, q_base=60.0, r_bytes=110.0),
            ),
        ),
    )
    profile_id = "synthetic_local_upgrade_oracle_lookup"
    stage2_input = stage2_case(
        scenario_id="synthetic_local_upgrade_reaches_oracle",
        budget_total_bytes=160.0,
        tiles=tiles,
        lookup_profile_id=profile_id,
    )
    return (
        stage2_input,
        lookup_for_tiles(
            profile_id=profile_id,
            tiles=tiles,
            caps={"A_tile": 2, "B_tile": 2},
            max_level_id=2,
        ),
    )


def test_local_upgrade_reaches_exact_reference_on_tiny_instance() -> None:
    stage2_input, lookup = local_upgrade_reaches_oracle_case()
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
    assert solver_result.total_bytes is not None
    assert solver_result.total_bytes <= stage2_input.budget_total_bytes
    assert solver_result.total_net_utility == pytest.approx(oracle.total_net_utility)
    assert selected_level_map(solver_result.selected_tiles) == selected_level_map(
        oracle.selected_tiles
    )


def lookup_cap_boundary_case() -> tuple[Stage2Input, DistanceLookup]:
    tiles = (
        tile(
            "A_cap1_high_level_forbidden",
            distance_norm=1.0,
            levels=(
                level(1, q_base=1.0, r_bytes=10.0),
                level(2, q_base=1000.0, r_bytes=20.0),
            ),
        ),
        tile(
            "B_cap2_allowed_upgrade",
            distance_norm=2.0,
            levels=(
                level(1, q_base=1.0, r_bytes=10.0),
                level(2, q_base=2.0, r_bytes=20.0),
            ),
        ),
    )
    profile_id = "synthetic_lookup_cap_boundary"
    stage2_input = stage2_case(
        scenario_id="synthetic_lookup_cap_boundary",
        budget_total_bytes=300.0,
        tiles=tiles,
        lookup_profile_id=profile_id,
    )
    return (
        stage2_input,
        lookup_for_tiles(
            profile_id=profile_id,
            tiles=tiles,
            caps={
                "A_cap1_high_level_forbidden": 1,
                "B_cap2_allowed_upgrade": 2,
            },
            max_level_id=2,
        ),
    )


def test_lookup_cap_is_hard_boundary_for_oracle_and_runtime_solver() -> None:
    stage2_input, lookup = lookup_cap_boundary_case()
    resolutions = resolve_lookup_for_input(stage2_input, lookup)

    oracle = exact_feasible_reference(
        stage2_input,
        resolutions,
        score_epsilon=SCORE_EPSILON,
    )
    solver_result = solve_stage2(stage2_input, lookup, search_config())

    allowed_by_tile = {
        resolution.tile_id: tuple(resolution.allowed_levels) for resolution in resolutions
    }
    assert allowed_by_tile["A_cap1_high_level_forbidden"] == (1,)
    assert oracle.combination_count == 2
    assert selected_level_map(oracle.selected_tiles) == {
        "A_cap1_high_level_forbidden": 1,
        "B_cap2_allowed_upgrade": 2,
    }
    assert solver_result.status == "SUCCESS"
    assert selected_level_map(solver_result.selected_tiles) == {
        "A_cap1_high_level_forbidden": 1,
        "B_cap2_allowed_upgrade": 2,
    }


def single_tile_tie_case(
    *,
    scenario_id: str,
    levels: tuple[QualityLevel, ...],
    score_epsilon: float,
) -> int:
    tiles = (
        tile(
            "A_tile",
            distance_norm=1.0,
            levels=levels,
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
        caps={"A_tile": 2},
        max_level_id=2,
    )
    oracle = exact_feasible_reference(
        stage2_input,
        resolve_lookup_for_input(stage2_input, lookup),
        score_epsilon=score_epsilon,
    )
    return oracle.selected_tiles[0].selected_level_id


def test_exhaustive_oracle_tie_breaks_by_budget_decode_and_selection_order() -> None:
    assert single_tile_tie_case(
        scenario_id="synthetic_tie_budget_utilization",
        score_epsilon=1e-6,
        levels=(
            level(1, q_base=10.0000005, r_bytes=10.0, d_ms=1.0),
            level(2, q_base=10.0, r_bytes=20.0, d_ms=100.0),
        ),
    ) == 2

    assert single_tile_tie_case(
        scenario_id="synthetic_tie_decode",
        score_epsilon=1e-6,
        levels=(
            level(1, q_base=10.0, r_bytes=10.0, d_ms=5.0),
            level(2, q_base=10.0, r_bytes=10.0, d_ms=3.0),
        ),
    ) == 2

    assert single_tile_tie_case(
        scenario_id="synthetic_tie_selection_sequence",
        score_epsilon=1e-6,
        levels=(
            level(1, q_base=10.0, r_bytes=10.0, d_ms=1.0),
            level(2, q_base=10.0, r_bytes=10.0, d_ms=1.0),
        ),
    ) == 1


def large_combination_case() -> tuple[Stage2Input, DistanceLookup]:
    levels = tuple(
        level(level_id, q_base=float(level_id), r_bytes=float(level_id))
        for level_id in range(1, 11)
    )
    tiles = tuple(
        tile(f"T{index}", distance_norm=float(index), levels=levels)
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
            caps={item.tile_id: 10 for item in tiles},
            max_level_id=10,
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
