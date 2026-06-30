from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pcv_stage2.frame1051_metadata_bridge import (
    DRC_ARTIFACT_ROOT,
    DRC_GENERATION_MANIFEST,
    DRC_PROFILE_CONFIG,
    DRC_VALIDATION_REPORT,
    EXPECTED_COMPRESSION_LEVEL,
    EXPECTED_DATASET_ID,
    EXPECTED_DRC_CANDIDATE_COUNT,
    EXPECTED_DRC_PROFILE_ID,
    EXPECTED_FRAME_ID,
    EXPECTED_GRID_PROFILE_ID,
    EXPECTED_NON_EMPTY_TILE_COUNT,
    EXPECTED_PDLS,
    EXPECTED_PLY_CANDIDATE_COUNT,
    EXPECTED_QPS,
    EXPECTED_SOURCE_PROFILE_ID,
    EXPECTED_TOTAL_CANDIDATE_COUNT,
    MetadataBridgeError,
    SOURCE_ARTIFACT_ROOT,
    SOURCE_GENERATION_MANIFEST,
    SOURCE_PROFILE_CONFIG,
    SOURCE_TILE_INDEX,
    SOURCE_VALIDATION_REPORT,
    build_frame1051_candidate_catalog,
)


Payloads = dict[str, dict[str, Any]]
PayloadMutator = Callable[[Payloads], None]
AfterWriteMutator = Callable[[Path, Payloads], None]


def test_build_catalog_keeps_ply_and_drc_candidates_parallel_and_pending(
    tmp_path: Path,
) -> None:
    data_prep_root = make_synthetic_data_prep_root(tmp_path)

    catalog = build_frame1051_candidate_catalog(data_prep_root)

    assert catalog["catalog_type"] == "frame1051_candidate_metadata_catalog"
    assert catalog["solver_ready"] is False
    assert catalog["summary"] == {
        "non_empty_tile_count": EXPECTED_NON_EMPTY_TILE_COUNT,
        "ply_candidate_count": EXPECTED_PLY_CANDIDATE_COUNT,
        "drc_candidate_count": EXPECTED_DRC_CANDIDATE_COUNT,
        "total_candidate_count": EXPECTED_TOTAL_CANDIDATE_COUNT,
        "pdl_values": list(EXPECTED_PDLS),
        "qp_values": list(EXPECTED_QPS),
        "codec_id": "draco",
        "point_cloud_flag": "-point_cloud",
        "compression_level": EXPECTED_COMPRESSION_LEVEL,
    }

    first_tile = catalog["tiles"][0]
    candidates = {
        candidate["candidate_id"]: candidate for candidate in first_tile["candidates"]
    }
    same_pdl_ids = {
        "ply__pdl_0p4",
        "drc__pdl_0p4__qp_8__cl_10",
        "drc__pdl_0p4__qp_10__cl_10",
        "drc__pdl_0p4__qp_12__cl_10",
    }
    assert same_pdl_ids <= set(candidates)
    assert {candidates[candidate_id]["pdl_ratio"] for candidate_id in same_pdl_ids} == {
        0.4
    }
    assert {candidates[candidate_id]["candidate_kind"] for candidate_id in same_pdl_ids} == {
        "ply_source",
        "drc_delivery",
    }

    for tile in catalog["tiles"]:
        for candidate in tile["candidates"]:
            assert candidate["r_bytes_provenance"] == "measured"
            assert candidate["d_ms_status"] == "pending"
            assert candidate["q_base_status"] == "pending"
            assert "d_ms" not in candidate
            assert "q_base" not in candidate
            assert candidate["availability"]["file_exists"] is True
            assert candidate["availability"]["size_matches_manifest"] is True
            assert not Path(candidate["asset_ref"]).is_absolute()

    assert "Stage2Input" in catalog["non_claims"][0]
    assert "network cost" in " ".join(catalog["non_claims"])


def test_path_escape_is_rejected(tmp_path: Path) -> None:
    def mutate(payloads: Payloads) -> None:
        first_asset(payloads)["relative_path"] = "../escape.ply"

    data_prep_root = make_synthetic_data_prep_root(tmp_path, mutate_payloads=mutate)

    with pytest.raises(MetadataBridgeError, match="must not contain"):
        build_frame1051_candidate_catalog(data_prep_root)


def test_source_and_drc_tile_set_mismatch_is_rejected(tmp_path: Path) -> None:
    def mutate(payloads: Payloads) -> None:
        variants = payloads["drc_manifest"]["variants"]
        old_tile_id = variants[0]["tile_id"]
        for variant in variants:
            if variant["tile_id"] == old_tile_id:
                variant["tile_id"] = "gx_extra_gy_0_gz_0"

    data_prep_root = make_synthetic_data_prep_root(tmp_path, mutate_payloads=mutate)

    with pytest.raises(MetadataBridgeError, match="source and DRC tile sets"):
        build_frame1051_candidate_catalog(data_prep_root)


def test_drc_variant_missing_source_ply_linkage_is_rejected(tmp_path: Path) -> None:
    def mutate(payloads: Payloads) -> None:
        payloads["drc_manifest"]["variants"][0][
            "source_ply_relpath"
        ] = "tiles/gx_0_gy_4_gz_0/missing_source.ply"

    data_prep_root = make_synthetic_data_prep_root(tmp_path, mutate_payloads=mutate)

    with pytest.raises(MetadataBridgeError, match="source PLY relpath does not match"):
        build_frame1051_candidate_catalog(data_prep_root)


def test_incomplete_count_or_combination_is_rejected(tmp_path: Path) -> None:
    def mutate(payloads: Payloads) -> None:
        payloads["drc_manifest"]["variants"].pop()

    data_prep_root = make_synthetic_data_prep_root(tmp_path, mutate_payloads=mutate)

    with pytest.raises(MetadataBridgeError, match="DRC variant record count"):
        build_frame1051_candidate_catalog(data_prep_root)


def test_manifest_size_mismatch_is_rejected(tmp_path: Path) -> None:
    def after_write(data_prep_root: Path, payloads: Payloads) -> None:
        relpath = first_asset(payloads)["relative_path"]
        (data_prep_root / SOURCE_ARTIFACT_ROOT / relpath).write_bytes(b"size-changed")

    data_prep_root = make_synthetic_data_prep_root(tmp_path, after_write=after_write)

    with pytest.raises(MetadataBridgeError, match="size mismatch"):
        build_frame1051_candidate_catalog(data_prep_root)


def test_profile_mismatch_is_rejected(tmp_path: Path) -> None:
    def mutate(payloads: Payloads) -> None:
        payloads["drc_profile"]["codec_id"] = "not_draco"

    data_prep_root = make_synthetic_data_prep_root(tmp_path, mutate_payloads=mutate)

    with pytest.raises(MetadataBridgeError, match="DRC profile codec_id"):
        build_frame1051_candidate_catalog(data_prep_root)


def test_validation_report_failure_is_rejected(tmp_path: Path) -> None:
    def mutate(payloads: Payloads) -> None:
        payloads["drc_validation"]["validation_passed"] = False

    data_prep_root = make_synthetic_data_prep_root(tmp_path, mutate_payloads=mutate)

    with pytest.raises(MetadataBridgeError, match="DRC validation report did not pass"):
        build_frame1051_candidate_catalog(data_prep_root)


def test_catalog_sorting_is_stable_when_manifest_record_order_changes(
    tmp_path: Path,
) -> None:
    ordered_root = make_synthetic_data_prep_root(tmp_path / "ordered")
    reversed_root = make_synthetic_data_prep_root(tmp_path / "reversed", reverse=True)

    ordered = build_frame1051_candidate_catalog(ordered_root)
    reversed_catalog = build_frame1051_candidate_catalog(reversed_root)

    assert ordered["summary"] == reversed_catalog["summary"]
    assert ordered["tiles"] == reversed_catalog["tiles"]
    assert [tile["tile_id"] for tile in ordered["tiles"]] == sorted(
        tile["tile_id"] for tile in ordered["tiles"]
    )
    for tile in ordered["tiles"]:
        assert [candidate["candidate_id"] for candidate in tile["candidates"]] == [
            "ply__pdl_0p2",
            "ply__pdl_0p4",
            "ply__pdl_0p6",
            "ply__pdl_0p8",
            "ply__pdl_1p0",
            "drc__pdl_0p2__qp_8__cl_10",
            "drc__pdl_0p2__qp_10__cl_10",
            "drc__pdl_0p2__qp_12__cl_10",
            "drc__pdl_0p4__qp_8__cl_10",
            "drc__pdl_0p4__qp_10__cl_10",
            "drc__pdl_0p4__qp_12__cl_10",
            "drc__pdl_0p6__qp_8__cl_10",
            "drc__pdl_0p6__qp_10__cl_10",
            "drc__pdl_0p6__qp_12__cl_10",
            "drc__pdl_0p8__qp_8__cl_10",
            "drc__pdl_0p8__qp_10__cl_10",
            "drc__pdl_0p8__qp_12__cl_10",
            "drc__pdl_1p0__qp_8__cl_10",
            "drc__pdl_1p0__qp_10__cl_10",
            "drc__pdl_1p0__qp_12__cl_10",
        ]


def make_synthetic_data_prep_root(
    tmp_path: Path,
    *,
    mutate_payloads: PayloadMutator | None = None,
    after_write: AfterWriteMutator | None = None,
    reverse: bool = False,
) -> Path:
    data_prep_root = tmp_path / "data_prep"
    (data_prep_root / SOURCE_PROFILE_CONFIG.parent).mkdir(parents=True, exist_ok=True)
    (data_prep_root / SOURCE_ARTIFACT_ROOT).mkdir(parents=True, exist_ok=True)
    (data_prep_root / DRC_ARTIFACT_ROOT).mkdir(parents=True, exist_ok=True)

    payloads = synthetic_payloads(data_prep_root)
    if reverse:
        payloads["source_tile_index"]["tiles"].reverse()
        for tile in payloads["source_tile_index"]["tiles"]:
            tile["quality_assets"].reverse()
        payloads["drc_manifest"]["variants"].reverse()
    if mutate_payloads is not None:
        mutate_payloads(payloads)

    write_json(data_prep_root / SOURCE_PROFILE_CONFIG, payloads["source_profile"])
    write_json(data_prep_root / DRC_PROFILE_CONFIG, payloads["drc_profile"])
    write_json(data_prep_root / SOURCE_GENERATION_MANIFEST, payloads["source_manifest"])
    write_json(data_prep_root / SOURCE_TILE_INDEX, payloads["source_tile_index"])
    write_json(data_prep_root / SOURCE_VALIDATION_REPORT, payloads["source_validation"])
    write_json(data_prep_root / DRC_GENERATION_MANIFEST, payloads["drc_manifest"])
    write_json(data_prep_root / DRC_VALIDATION_REPORT, payloads["drc_validation"])

    if after_write is not None:
        after_write(data_prep_root, payloads)

    return data_prep_root


def synthetic_payloads(data_prep_root: Path) -> Payloads:
    source_profile = {
        "sampling_profile_id": EXPECTED_SOURCE_PROFILE_ID,
        "dataset_id": EXPECTED_DATASET_ID,
        "frame_id": EXPECTED_FRAME_ID,
        "grid_profile_id": EXPECTED_GRID_PROFILE_ID,
        "quality_levels": list(EXPECTED_PDLS),
    }
    drc_profile = {
        "profile_id": EXPECTED_DRC_PROFILE_ID,
        "dataset_id": EXPECTED_DATASET_ID,
        "frame_id": EXPECTED_FRAME_ID,
        "grid_profile_id": EXPECTED_GRID_PROFILE_ID,
        "source_artifact_root": SOURCE_ARTIFACT_ROOT.as_posix(),
        "source_artifact_profile_id": EXPECTED_SOURCE_PROFILE_ID,
        "source_pdls": list(EXPECTED_PDLS),
        "qp_values": list(EXPECTED_QPS),
        "codec_id": "draco",
        "point_cloud_flag": "-point_cloud",
        "compression_level": EXPECTED_COMPRESSION_LEVEL,
        "output_root": DRC_ARTIFACT_ROOT.as_posix(),
    }
    source_manifest = {
        "artifact_profile_id": EXPECTED_SOURCE_PROFILE_ID,
        "dataset_id": EXPECTED_DATASET_ID,
        "frame_id": EXPECTED_FRAME_ID,
        "quality_levels": list(EXPECTED_PDLS),
        "non_empty_tile_count": EXPECTED_NON_EMPTY_TILE_COUNT,
        "generated_ply_file_count": EXPECTED_PLY_CANDIDATE_COUNT,
    }
    source_validation = {
        "passed": True,
        "artifact_profile_id": EXPECTED_SOURCE_PROFILE_ID,
        "frame_id": EXPECTED_FRAME_ID,
        "quality_levels": list(EXPECTED_PDLS),
        "non_empty_tile_count": EXPECTED_NON_EMPTY_TILE_COUNT,
        "generated_ply_file_count": EXPECTED_PLY_CANDIDATE_COUNT,
    }
    source_tile_index = {
        "artifact_profile_id": EXPECTED_SOURCE_PROFILE_ID,
        "grid_profile_id": EXPECTED_GRID_PROFILE_ID,
        "sampling_profile_id": EXPECTED_SOURCE_PROFILE_ID,
        "dataset_id": EXPECTED_DATASET_ID,
        "frame_id": EXPECTED_FRAME_ID,
        "quality_levels": list(EXPECTED_PDLS),
        "non_empty_tile_count": EXPECTED_NON_EMPTY_TILE_COUNT,
        "tiles": [],
    }
    drc_manifest = {
        "artifact_profile_id": EXPECTED_DRC_PROFILE_ID,
        "dataset_id": EXPECTED_DATASET_ID,
        "frame_id": EXPECTED_FRAME_ID,
        "grid_profile_id": EXPECTED_GRID_PROFILE_ID,
        "source_artifact_root": SOURCE_ARTIFACT_ROOT.as_posix(),
        "source_artifact_profile_id": EXPECTED_SOURCE_PROFILE_ID,
        "output_root": DRC_ARTIFACT_ROOT.as_posix(),
        "codec_id": "draco",
        "point_cloud_flag": "-point_cloud",
        "compression_level": EXPECTED_COMPRESSION_LEVEL,
        "source_pdls": list(EXPECTED_PDLS),
        "qp_values": list(EXPECTED_QPS),
        "expected_non_empty_tile_count": EXPECTED_NON_EMPTY_TILE_COUNT,
        "expected_variant_count": EXPECTED_DRC_CANDIDATE_COUNT,
        "variants": [],
        "generated_drc_file_count": EXPECTED_DRC_CANDIDATE_COUNT,
        "basic_decode_integrity_checked_variant_count": EXPECTED_DRC_CANDIDATE_COUNT,
        "generation_summary": {
            "non_empty_tile_count": EXPECTED_NON_EMPTY_TILE_COUNT,
            "expected_variant_count": EXPECTED_DRC_CANDIDATE_COUNT,
            "generated_drc_file_count": EXPECTED_DRC_CANDIDATE_COUNT,
            "basic_decode_integrity_pass": True,
        },
    }
    drc_validation = {
        "validation_passed": True,
        "artifact_root": DRC_ARTIFACT_ROOT.as_posix(),
        "variant_count": EXPECTED_DRC_CANDIDATE_COUNT,
        "checks": ["manifest_matrix_complete", "decode_all_drc"],
    }

    for tile_index in range(EXPECTED_NON_EMPTY_TILE_COUNT):
        tile_id = f"gx_{tile_index}_gy_4_gz_0"
        point_count = 1000 + tile_index
        quality_assets = []
        for pdl_index, pdl in enumerate(EXPECTED_PDLS):
            source_size = 1000 + tile_index * 100 + pdl_index * 10
            source_relpath = f"tiles/{tile_id}/pdl_{pdl:.1f}.ply"
            source_sha = f"source-sha-{tile_id}-{pdl:.1f}"
            write_bytes(data_prep_root / SOURCE_ARTIFACT_ROOT / source_relpath, source_size)
            quality_assets.append(
                {
                    "sampling_profile_id": EXPECTED_SOURCE_PROFILE_ID,
                    "sampling_scope": "tile_local",
                    "dataset_id": EXPECTED_DATASET_ID,
                    "frame_id": EXPECTED_FRAME_ID,
                    "grid_profile_id": EXPECTED_GRID_PROFILE_ID,
                    "tile_id": tile_id,
                    "target_pdl": pdl,
                    "source_point_count": point_count,
                    "retained_point_count": max(1, int(point_count * pdl)),
                    "actual_retained_ratio": pdl,
                    "sampling_method": "synthetic_sampling",
                    "relative_path": source_relpath,
                    "file_size_bytes": source_size,
                    "sha256": source_sha,
                    "provenance_kind": "synthetic",
                }
            )
            for qp in EXPECTED_QPS:
                drc_size = 200 + tile_index * 20 + pdl_index * 5 + qp
                drc_relpath = f"tiles/{tile_id}/pdl_{pdl:.1f}_cl10_qp{qp}.drc"
                write_bytes(data_prep_root / DRC_ARTIFACT_ROOT / drc_relpath, drc_size)
                drc_manifest["variants"].append(
                    {
                        "variant_id": f"{tile_id}__pdl_{pdl:.1f}__cl10__qp{qp}",
                        "tile_id": tile_id,
                        "source_pdl": pdl,
                        "codec_id": "draco",
                        "point_cloud_flag": "-point_cloud",
                        "compression_level": EXPECTED_COMPRESSION_LEVEL,
                        "qp": qp,
                        "source_ply_relpath": source_relpath,
                        "source_ply_sha256": source_sha.upper(),
                        "source_ply_file_size_bytes": source_size,
                        "source_point_count": max(1, int(point_count * pdl)),
                        "drc_relpath": drc_relpath,
                        "drc_sha256": f"drc-sha-{tile_id}-{pdl:.1f}-{qp}",
                        "drc_file_size_bytes": drc_size,
                        "basic_decode_integrity_pass": True,
                        "decoded_vertex_count": max(1, int(point_count * pdl)),
                        "rgb_multiset_exact": True,
                        "decoded_schema_fields": ["x", "y", "z", "red", "green", "blue"],
                    }
                )
        source_tile_index["tiles"].append(
            {
                "tile_id": tile_id,
                "grid_index": {"ix": tile_index, "iy": 4, "iz": 0},
                "tile_bbox_min": [float(tile_index), 0.0, 0.0],
                "tile_bbox_max": [float(tile_index + 1), 1.0, 1.0],
                "is_empty": False,
                "point_count": point_count,
                "asset_status": "generated_pdl_5",
                "quality_assets": quality_assets,
            }
        )

    return {
        "source_profile": source_profile,
        "drc_profile": drc_profile,
        "source_manifest": source_manifest,
        "source_tile_index": source_tile_index,
        "source_validation": source_validation,
        "drc_manifest": drc_manifest,
        "drc_validation": drc_validation,
    }


def first_asset(payloads: Payloads) -> dict[str, Any]:
    return payloads["source_tile_index"]["tiles"][0]["quality_assets"][0]


def write_bytes(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(deepcopy(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
