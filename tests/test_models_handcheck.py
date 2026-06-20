from __future__ import annotations

import json
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
    compute_b_min_feasible,
    compute_net_utility,
    resolve_allowed_levels,
    resolve_lookup_for_input,
)


FIXTURE = ROOT / "tests" / "fixtures" / "handcheck_3x3"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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
