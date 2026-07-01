from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pcv_stage2.frame1051_behavior_pilot import (
    BehaviorPilotError,
    build_behavior_lookup,
    build_stage2_input_payload,
    derive_budget_points,
    load_behavior_pilot_profile,
    run_behavior_pilot,
)
from pcv_stage2.io import stage2_input_from_dict
from pcv_stage2.preprocess import resolve_lookup_for_input


PDLS = (0.2, 0.4, 0.6, 0.8, 1.0)
QPS = (8, 10, 12)
PROFILE_PATH = ROOT / "configs" / "frame1051_fullbody_proxy_behavior_v1.json"


def test_lookup_caps_keep_expected_candidate_counts_for_d1_and_d3() -> None:
    profile = load_behavior_pilot_profile(PROFILE_PATH)
    catalog = synthetic_catalog()

    d1 = profile["observation_contexts"][0]
    d3 = profile["observation_contexts"][1]
    d1_budget = derive_budget_points(catalog, profile, d1)
    d3_budget = derive_budget_points(catalog, profile, d3)

    assert d1_budget["pdl_max_dist"] == 1.0
    assert set(d1_budget["allowed_candidate_counts_by_tile"].values()) == {20}
    assert d1_budget["total_allowed_candidate_count"] == 800

    assert d3_budget["pdl_max_dist"] == 0.6
    assert set(d3_budget["allowed_candidate_counts_by_tile"].values()) == {12}
    assert d3_budget["total_allowed_candidate_count"] == 480


def test_stage2_input_proxy_provenance_and_same_pdl_candidates_are_preserved() -> None:
    profile = load_behavior_pilot_profile(PROFILE_PATH)
    catalog = synthetic_catalog()
    observation = profile["observation_contexts"][1]
    budget_point = derive_budget_points(catalog, profile, observation)["budget_points"][1]

    payload = build_stage2_input_payload(catalog, profile, observation, budget_point)
    stage2_input = stage2_input_from_dict(payload)
    lookup = build_behavior_lookup(profile)
    resolutions = resolve_lookup_for_input(stage2_input, lookup)

    assert payload["eta"] == 0.0
    assert payload["provenance_summary"]["r_bytes"] == "measured"
    assert payload["provenance_summary"]["q_base"] == "proxy"
    assert payload["provenance_summary"]["d_ms"] == "proxy"
    assert payload["provenance_summary"]["budget_total_bytes"] == "derived"

    first_tile = payload["tiles"][0]
    assert first_tile["p_sal"] == 1.0
    assert first_tile["visibility"] == 1.0
    assert first_tile["screen_area"] == 1.0
    assert first_tile["distance_norm"] == 3.0
    assert first_tile["provenance"]["distance_norm"] == "calibrated"
    for candidate in first_tile["candidates"]:
        assert candidate["q_base"] == candidate["pdl_ratio"]
        assert candidate["d_ms"] == 0.0
        assert candidate["provenance"]["r_bytes"] == "measured"
        assert candidate["provenance"]["q_base"] == "proxy"
        assert candidate["provenance"]["d_ms"] == "proxy"

    allowed_first_tile = set(resolutions[0].allowed_candidate_ids)
    assert {
        "ply__pdl_0p4",
        "drc__pdl_0p4__qp_8__cl_10",
        "drc__pdl_0p4__qp_10__cl_10",
        "drc__pdl_0p4__qp_12__cl_10",
    } <= allowed_first_tile
    assert "ply__pdl_0p8" not in allowed_first_tile


@pytest.mark.parametrize(
    "mutator,match",
    [
        (lambda catalog: catalog.update({"solver_ready": True}), "solver_ready"),
        (
            lambda catalog: catalog["tiles"][0]["candidates"][0].update(
                {"d_ms_status": "ready"}
            ),
            "d_ms_status",
        ),
        (
            lambda catalog: catalog["tiles"][0]["candidates"][0].update(
                {"q_base_status": "ready"}
            ),
            "q_base_status",
        ),
    ],
)
def test_catalog_boundary_must_remain_pending_and_not_solver_ready(
    mutator,
    match: str,
) -> None:
    profile = load_behavior_pilot_profile(PROFILE_PATH)
    catalog = synthetic_catalog()
    mutator(catalog)

    with pytest.raises(BehaviorPilotError, match=match):
        run_behavior_pilot(catalog, profile)


def test_budget_derivation_uses_min_midpoint_and_reference_max_formula() -> None:
    profile = load_behavior_pilot_profile(PROFILE_PATH)
    catalog = synthetic_catalog()
    observation = profile["observation_contexts"][0]

    budget_context = derive_budget_points(catalog, profile, observation)

    expected_min = sum(
        min(candidate["r_bytes"] for candidate in tile["candidates"])
        for tile in catalog["tiles"]
    )
    expected_max = sum(
        max(candidate["r_bytes"] for candidate in tile["candidates"])
        for tile in catalog["tiles"]
    )
    expected_mid = (expected_min + expected_max) // 2

    assert budget_context["B_min"] == expected_min
    assert budget_context["B_reference_max"] == expected_max
    assert [item["budget_id"] for item in budget_context["budget_points"]] == [
        "min_feasible",
        "midpoint",
        "reference_max",
    ]
    assert [item["budget_total_bytes"] for item in budget_context["budget_points"]] == [
        expected_min,
        expected_mid,
        expected_max,
    ]


def test_all_solver_results_satisfy_budget_allowed_candidate_and_catalog_invariants() -> None:
    profile = load_behavior_pilot_profile(PROFILE_PATH)
    catalog = synthetic_catalog()

    run = run_behavior_pilot(catalog, profile)
    report = run["report"]

    assert report["scenario_count"] == 6
    assert report["all_invariants_passed"] is True
    for scenario in report["scenarios"]:
        assert scenario["status"] == "SUCCESS"
        assert scenario["total_bytes"] <= scenario["budget"]["budget_total_bytes"]
        assert scenario["invariants"]["checks"]["one_selection_per_tile"] is True
        assert scenario["invariants"]["checks"]["selected_candidates_allowed"] is True
        assert scenario["invariants"]["checks"]["selected_candidates_in_catalog"] is True
        assert scenario["invariants"]["checks"]["selected_r_bytes_match_catalog"] is True


def test_repeated_run_has_stable_inputs_report_order_and_normalized_results() -> None:
    profile = load_behavior_pilot_profile(PROFILE_PATH)
    catalog = synthetic_catalog()

    first = normalize_run(run_behavior_pilot(catalog, profile))
    second = normalize_run(run_behavior_pilot(catalog, profile))

    assert first == second
    assert [scenario["scenario_id"] for scenario in first["report"]["scenarios"]] == [
        "frame1051_fullbody_proxy_behavior_v1__fullbody_d1__min_feasible",
        "frame1051_fullbody_proxy_behavior_v1__fullbody_d1__midpoint",
        "frame1051_fullbody_proxy_behavior_v1__fullbody_d1__reference_max",
        "frame1051_fullbody_proxy_behavior_v1__fullbody_d3__min_feasible",
        "frame1051_fullbody_proxy_behavior_v1__fullbody_d3__midpoint",
        "frame1051_fullbody_proxy_behavior_v1__fullbody_d3__reference_max",
    ]


def test_reordered_catalog_candidates_do_not_change_non_tie_decisions() -> None:
    profile = load_behavior_pilot_profile(PROFILE_PATH)
    ordered = run_behavior_pilot(synthetic_catalog(), profile)
    reordered = run_behavior_pilot(synthetic_catalog(reverse=True), profile)

    ordered_normalized = normalize_run(ordered)
    reordered_normalized = normalize_run(reordered)

    assert ordered_normalized["scenario_artifacts"] == reordered_normalized["scenario_artifacts"]
    assert ordered_normalized["report"]["scenarios"] == reordered_normalized["report"]["scenarios"]


def test_report_non_claims_and_provenance_do_not_mark_proxy_as_measured() -> None:
    profile = load_behavior_pilot_profile(PROFILE_PATH)
    report = run_behavior_pilot(synthetic_catalog(), profile)["report"]

    assert report["proxy_assumptions"]["candidate_proxy_fields"]["q_base_provenance"] == "proxy"
    assert report["proxy_assumptions"]["candidate_proxy_fields"]["d_ms_provenance"] == "proxy"
    assert report["proxy_assumptions"]["budget_total_bytes_provenance"] == "derived"
    non_claims = " ".join(report["non_claims"])
    assert "不是 DRC-aware" in non_claims
    assert "不是端到端网络总开销" in non_claims
    assert "质量、处理开销、网络性能或 QoE 更优" in non_claims
    assert '"q_base": "measured"' not in json.dumps(report, ensure_ascii=False)
    assert '"d_ms": "measured"' not in json.dumps(report, ensure_ascii=False)


def synthetic_catalog(*, reverse: bool = False) -> dict[str, Any]:
    tiles = []
    for tile_index in range(40):
        tile_id = f"gx_{tile_index}_gy_4_gz_0"
        candidates = []
        for pdl_index, pdl in enumerate(PDLS):
            candidates.append(
                catalog_candidate(
                    tile_id=tile_id,
                    candidate_id=f"ply__pdl_{pdl_token(pdl)}",
                    candidate_kind="ply_source",
                    pdl_ratio=pdl,
                    file_format="ply",
                    codec="binary_little_endian_ply",
                    codec_params={"source_pdl": pdl},
                    r_bytes=10000 + tile_index * 100 + pdl_index * 1000,
                )
            )
            for qp in QPS:
                candidates.append(
                    catalog_candidate(
                        tile_id=tile_id,
                        candidate_id=f"drc__pdl_{pdl_token(pdl)}__qp_{qp}__cl_10",
                        candidate_kind="drc_delivery",
                        pdl_ratio=pdl,
                        file_format="drc",
                        codec="draco",
                        codec_params={
                            "source_pdl": pdl,
                            "qp": qp,
                            "compression_level": 10,
                            "point_cloud_mode": True,
                        },
                        r_bytes=1000 + tile_index * 20 + pdl_index * 400 + qp * 10,
                    )
                )
        if reverse:
            candidates.reverse()
        tiles.append(
            {
                "tile_id": tile_id,
                "point_count": 1000 + tile_index,
                "provenance": {"tile_geometry": "synthetic"},
                "candidates": candidates,
            }
        )
    if reverse:
        tiles.reverse()
    return {
        "catalog_type": "frame1051_candidate_metadata_catalog",
        "catalog_version": "0.1.0",
        "solver_ready": False,
        "dataset_id": "8i_longdress",
        "frame_id": 1051,
        "grid_profile_id": "longdress_raw_g128_fullseq_pilot_v1",
        "read_inputs": [
            {
                "path": "synthetic/source.json",
                "sha256": "synthetic",
                "size_bytes": 1,
            }
        ],
        "summary": {
            "non_empty_tile_count": 40,
            "ply_candidate_count": 200,
            "drc_candidate_count": 600,
            "total_candidate_count": 800,
            "pdl_values": list(PDLS),
            "qp_values": list(QPS),
            "codec_id": "draco",
            "point_cloud_flag": "-point_cloud",
            "compression_level": 10,
        },
        "non_claims": ["synthetic catalog for tests only"],
        "tiles": tiles,
    }


def catalog_candidate(
    *,
    tile_id: str,
    candidate_id: str,
    candidate_kind: str,
    pdl_ratio: float,
    file_format: str,
    codec: str,
    codec_params: dict[str, Any],
    r_bytes: int,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "candidate_kind": candidate_kind,
        "pdl_ratio": pdl_ratio,
        "file_format": file_format,
        "codec": codec,
        "codec_params": codec_params,
        "artifact_root": f"artifacts/{candidate_kind}",
        "asset_ref": f"tiles/{tile_id}/{candidate_id}.{file_format}",
        "r_bytes": r_bytes,
        "r_bytes_provenance": "measured",
        "manifest_integrity": {
            "relative_path": f"tiles/{tile_id}/{candidate_id}.{file_format}",
            "file_size_bytes": r_bytes,
            "file_exists": True,
            "stat_size_bytes": r_bytes,
            "size_matches_manifest": True,
        },
        "availability": {
            "status": "available",
            "file_exists": True,
            "size_matches_manifest": True,
        },
        "d_ms_status": "pending",
        "q_base_status": "pending",
        "provenance": {
            "pdl_ratio": "derived",
            "asset_ref": "derived",
            "r_bytes": "measured",
        },
    }


def pdl_token(pdl: float) -> str:
    return f"{pdl:.1f}".replace(".", "p")


def normalize_run(run: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(run)
    normalized.pop("catalog", None)
    for artifact in normalized["scenario_artifacts"]:
        artifact["result_payload"]["runtime_ms"] = "<runtime>"
    return normalized
