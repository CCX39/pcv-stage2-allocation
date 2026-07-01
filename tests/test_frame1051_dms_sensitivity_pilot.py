from __future__ import annotations

import copy
import json
import math
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = ROOT / "tests"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from pcv_stage2.frame1051_behavior_pilot import (  # noqa: E402
    BehaviorPilotError,
    load_behavior_pilot_profile,
    run_behavior_pilot,
)

from test_frame1051_behavior_pilot import normalize_run, synthetic_catalog  # noqa: E402


BEHAVIOR_PROFILE_PATH = ROOT / "configs" / "frame1051_fullbody_proxy_behavior_v1.json"
SENSITIVITY_PROFILE_PATH = (
    ROOT / "configs" / "frame1051_fullbody_proxy_dms_sensitivity_v1.json"
)


def test_dms_mapping_applies_to_ply_and_drc_candidates() -> None:
    profile = load_behavior_pilot_profile(SENSITIVITY_PROFILE_PATH)
    run = run_behavior_pilot(synthetic_catalog(), profile)

    assert run["report"]["scenario_count"] == 18
    assert run["report"]["proxy_assumptions"]["d_ms_mapping"] == {
        "drc_delivery": 100.0,
        "ply_source": 80.0,
    }

    first_input = run["scenario_artifacts"][0]["input_payload"]
    candidates = {
        candidate["candidate_id"]: candidate for candidate in first_input["tiles"][0]["candidates"]
    }
    assert candidates["ply__pdl_0p2"]["d_ms"] == 80.0
    assert candidates["drc__pdl_0p2__qp_8__cl_10"]["d_ms"] == 100.0
    assert candidates["drc__pdl_0p2__qp_10__cl_10"]["d_ms"] == 100.0
    assert candidates["drc__pdl_0p2__qp_12__cl_10"]["d_ms"] == 100.0
    assert candidates["ply__pdl_0p2"]["provenance"]["d_ms"] == "proxy"
    assert candidates["drc__pdl_0p2__qp_8__cl_10"]["provenance"]["d_ms"] == "proxy"


@pytest.mark.parametrize(
    "mutator,match",
    [
        (
            lambda profile: profile["candidate_proxy_fields"]["d_ms_by_candidate_kind"].pop("ply_source"),
            "missing",
        ),
        (
            lambda profile: profile["candidate_proxy_fields"]["d_ms_by_candidate_kind"].update({"ply_source": -1}),
            "finite and non-negative",
        ),
        (
            lambda profile: profile["candidate_proxy_fields"]["d_ms_by_candidate_kind"].update({"ply_source": math.inf}),
            "finite and non-negative",
        ),
        (
            lambda profile: profile["candidate_proxy_fields"]["eta_scenarios"][1].update({"eta": -0.1}),
            "finite and non-negative",
        ),
        (
            lambda profile: profile["candidate_proxy_fields"]["eta_scenarios"][1].update({"eta": math.nan}),
            "finite and non-negative",
        ),
    ],
)
def test_invalid_dms_mapping_or_eta_fails_closed(mutator, match: str) -> None:
    profile = load_behavior_pilot_profile(SENSITIVITY_PROFILE_PATH)
    mutator(profile)

    with pytest.raises(BehaviorPilotError, match=match):
        run_behavior_pilot(synthetic_catalog(), profile)


def test_unknown_candidate_kind_fails_closed() -> None:
    profile = load_behavior_pilot_profile(SENSITIVITY_PROFILE_PATH)
    catalog = synthetic_catalog()
    catalog["tiles"][0]["candidates"][0]["candidate_kind"] = "mystery_codec"

    with pytest.raises(BehaviorPilotError, match="candidate_kind"):
        run_behavior_pilot(catalog, profile)


def test_catalog_pending_boundary_still_applies() -> None:
    profile = load_behavior_pilot_profile(SENSITIVITY_PROFILE_PATH)
    catalog = synthetic_catalog()
    catalog["tiles"][0]["candidates"][0]["d_ms_status"] = "ready"

    with pytest.raises(BehaviorPilotError, match="d_ms_status"):
        run_behavior_pilot(catalog, profile)


def test_eta0_matches_phase2b4_behavior_decisions() -> None:
    baseline_profile = load_behavior_pilot_profile(BEHAVIOR_PROFILE_PATH)
    sensitivity_profile = load_behavior_pilot_profile(SENSITIVITY_PROFILE_PATH)
    catalog = synthetic_catalog()

    baseline = run_behavior_pilot(catalog, baseline_profile)
    sensitivity = run_behavior_pilot(catalog, sensitivity_profile)

    baseline_by_key = {
        scenario_key(scenario): scenario for scenario in baseline["report"]["scenarios"]
    }
    eta0_by_key = {
        scenario_key(scenario): scenario
        for scenario in sensitivity["report"]["scenarios"]
        if scenario["eta"]["eta_id"] == "eta0"
    }

    assert set(baseline_by_key) == set(eta0_by_key)
    for key, baseline_scenario in baseline_by_key.items():
        eta0_scenario = eta0_by_key[key]
        assert eta0_scenario["selected_candidate_ids"] == baseline_scenario["selected_candidate_ids"]
        assert eta0_scenario["total_bytes"] == baseline_scenario["total_bytes"]
        assert eta0_scenario["budget_utilization"] == baseline_scenario["budget_utilization"]
        assert eta0_scenario["lookup_context"]["allowed_candidate_counts_by_tile"] == baseline_scenario["lookup_context"]["allowed_candidate_counts_by_tile"]


def test_positive_eta_prefers_lower_dms_under_controlled_same_r_and_q() -> None:
    profile = load_behavior_pilot_profile(SENSITIVITY_PROFILE_PATH)
    catalog = synthetic_catalog()
    tile = catalog["tiles"][0]
    for candidate in tile["candidates"]:
        if candidate["candidate_id"] in {
            "ply__pdl_0p2",
            "drc__pdl_0p2__qp_8__cl_10",
        }:
            candidate["r_bytes"] = 1000
            candidate["manifest_integrity"]["file_size_bytes"] = 1000
            candidate["manifest_integrity"]["stat_size_bytes"] = 1000
    run = run_behavior_pilot(catalog, profile)
    min_scenarios = {
        scenario["eta"]["eta_id"]: scenario
        for scenario in run["report"]["scenarios"]
        if scenario["lookup_context"]["context_id"] == "fullbody_d1"
        and scenario["budget"]["budget_id"] == "min_feasible"
    }

    for eta_id in ("eta_moderate", "eta_stronger"):
        assert (
            min_scenarios[eta_id]["selected_candidate_ids"][tile["tile_id"]]
            == "ply__pdl_0p2"
        )
    assert (
        min_scenarios["eta0"]["selected_candidate_ids"][tile["tile_id"]]
        == "ply__pdl_0p2"
    )
    assert min_scenarios["eta0"]["selected_candidate_change_count_vs_eta0"] == 0


def test_repeated_run_and_reordered_catalog_are_stable() -> None:
    profile = load_behavior_pilot_profile(SENSITIVITY_PROFILE_PATH)

    first = normalize_run(run_behavior_pilot(synthetic_catalog(), profile))
    second = normalize_run(run_behavior_pilot(synthetic_catalog(), profile))
    reordered = normalize_run(run_behavior_pilot(synthetic_catalog(reverse=True), profile))

    assert first == second
    assert first["scenario_artifacts"] == reordered["scenario_artifacts"]
    assert first["report"]["scenarios"] == reordered["report"]["scenarios"]


def test_report_keeps_dms_proxy_non_claims_and_change_counts() -> None:
    profile = load_behavior_pilot_profile(SENSITIVITY_PROFILE_PATH)
    report = run_behavior_pilot(synthetic_catalog(), profile)["report"]

    assert report["all_invariants_passed"] is True
    assert report["proxy_assumptions"]["d_ms_mapping"] == {
        "drc_delivery": 100.0,
        "ply_source": 80.0,
    }
    assert [item["eta_id"] for item in report["proxy_assumptions"]["eta_scenarios"]] == [
        "eta0",
        "eta_moderate",
        "eta_stronger",
    ]
    assert all(
        scenario["selected_candidate_change_count_vs_eta0"] is not None
        for scenario in report["scenarios"]
    )
    non_claims = " ".join(report["non_claims"])
    assert "不是 target-side measured benchmark" in non_claims
    assert "不是实际逐 tile 测量" in non_claims
    assert "实际质量、处理开销、网络性能或 QoE 更优" in non_claims
    assert '"d_ms": "measured"' not in json.dumps(report, ensure_ascii=False)


def scenario_key(scenario: dict[str, Any]) -> tuple[str, str]:
    return (
        scenario["lookup_context"]["context_id"],
        scenario["budget"]["budget_id"],
    )
