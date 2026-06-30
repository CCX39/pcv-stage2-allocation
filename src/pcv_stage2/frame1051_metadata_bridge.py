from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


CATALOG_TYPE = "frame1051_candidate_metadata_catalog"
CATALOG_VERSION = "0.1.0"

EXPECTED_DATASET_ID = "8i_longdress"
EXPECTED_FRAME_ID = 1051
EXPECTED_GRID_PROFILE_ID = "longdress_raw_g128_fullseq_pilot_v1"
EXPECTED_SOURCE_PROFILE_ID = "longdress_1051_g128_tilelocal_pdl5_v1"
EXPECTED_DRC_PROFILE_ID = "pilot_drc_corpus_longdress_1051_g128_pdl5_qp3_cl10_v1"
EXPECTED_PDLS = (0.2, 0.4, 0.6, 0.8, 1.0)
EXPECTED_QPS = (8, 10, 12)
EXPECTED_CODEC_ID = "draco"
EXPECTED_POINT_CLOUD_FLAG = "-point_cloud"
EXPECTED_COMPRESSION_LEVEL = 10
EXPECTED_NON_EMPTY_TILE_COUNT = 40
EXPECTED_PLY_CANDIDATE_COUNT = 200
EXPECTED_DRC_CANDIDATE_COUNT = 600
EXPECTED_TOTAL_CANDIDATE_COUNT = 800

SOURCE_PROFILE_CONFIG = Path(
    "configs/pilot_sampling_profile.longdress_1051_g128_tilelocal_pdl5_v1.json"
)
DRC_PROFILE_CONFIG = Path(
    "configs/pilot_drc_corpus.longdress_1051_g128_pdl5_qp3_cl10_v1.json"
)
SOURCE_ARTIFACT_ROOT = Path("artifacts/pilot_1051_g128_tilelocal_pdl5_v1")
DRC_ARTIFACT_ROOT = Path("artifacts/pilot_1051_g128_drc_pdl5_qp3_cl10_v1")
SOURCE_GENERATION_MANIFEST = SOURCE_ARTIFACT_ROOT / "generation_manifest.json"
SOURCE_TILE_INDEX = SOURCE_ARTIFACT_ROOT / "frame_1051_tile_index.json"
SOURCE_VALIDATION_REPORT = SOURCE_ARTIFACT_ROOT / "validation_report.json"
DRC_GENERATION_MANIFEST = DRC_ARTIFACT_ROOT / "generation_manifest.json"
DRC_VALIDATION_REPORT = DRC_ARTIFACT_ROOT / "validation_report.json"

NON_CLAIMS = (
    "This metadata catalog is not a Stage2Input and must not be passed directly to solve_stage2.",
    "r_bytes is the measured candidate file body size; it is not end-to-end network cost.",
    "d_ms is pending and is not inferred from file size, point count, PDL, qp, codec, or constants.",
    "q_base is pending and is not inferred from file size, point count, PDL, qp, codec, or constants.",
    "candidate_id, file_format, codec, qp, and pdl_ratio are not natural quality orderings.",
    "The DRC validation summary records basic decode-integrity only; it is not target-side latency or visual quality evidence.",
)


class MetadataBridgeError(ValueError):
    """Raised when the read-only frame 1051 metadata bridge refuses input."""


def build_frame1051_candidate_catalog(data_prep_root: str | Path) -> dict[str, Any]:
    """Build a metadata-only frame 1051 candidate catalog from data-prep JSON files."""

    root = Path(data_prep_root).resolve(strict=True)

    source_profile = _load_json(root, SOURCE_PROFILE_CONFIG)
    drc_profile = _load_json(root, DRC_PROFILE_CONFIG)
    source_manifest = _load_json(root, SOURCE_GENERATION_MANIFEST)
    source_tile_index = _load_json(root, SOURCE_TILE_INDEX)
    source_validation = _load_json(root, SOURCE_VALIDATION_REPORT)
    drc_manifest = _load_json(root, DRC_GENERATION_MANIFEST)
    drc_validation = _load_json(root, DRC_VALIDATION_REPORT)

    _validate_profiles(
        source_profile=source_profile,
        drc_profile=drc_profile,
        source_manifest=source_manifest,
        source_tile_index=source_tile_index,
        source_validation=source_validation,
        drc_manifest=drc_manifest,
        drc_validation=drc_validation,
    )

    source_by_tile = _collect_source_assets(
        root=root,
        source_tile_index=source_tile_index,
    )
    drc_by_tile = _collect_drc_variants(root=root, drc_manifest=drc_manifest)

    _validate_tile_sets(source_by_tile, drc_by_tile)
    _validate_drc_source_links(drc_by_tile, source_by_tile)

    tiles = []
    total_ply = 0
    total_drc = 0
    for tile_id in sorted(source_by_tile):
        source_tile = source_by_tile[tile_id]["tile"]
        ply_candidates = [
            _ply_candidate(tile_id, pdl, source_by_tile[tile_id]["assets"][pdl])
            for pdl in EXPECTED_PDLS
        ]
        drc_candidates = [
            _drc_candidate(
                tile_id=tile_id,
                pdl=pdl,
                qp=qp,
                variant=drc_by_tile[tile_id][(pdl, qp)],
                source_asset=source_by_tile[tile_id]["assets"][pdl],
            )
            for pdl in EXPECTED_PDLS
            for qp in EXPECTED_QPS
        ]
        candidates = ply_candidates + drc_candidates
        candidate_ids = [candidate["candidate_id"] for candidate in candidates]
        _expect(
            len(candidate_ids) == len(set(candidate_ids)),
            f"{tile_id} has duplicate candidate_id values",
        )

        tiles.append(
            {
                "tile_id": tile_id,
                "grid_index": source_tile.get("grid_index"),
                "tile_bbox_min": source_tile.get("tile_bbox_min"),
                "tile_bbox_max": source_tile.get("tile_bbox_max"),
                "point_count": source_tile.get("point_count"),
                "provenance": {
                    "tile_geometry": "measured",
                    "source_tile_index": SOURCE_TILE_INDEX.as_posix(),
                },
                "candidates": candidates,
            }
        )
        total_ply += len(ply_candidates)
        total_drc += len(drc_candidates)

    _expect_equal(total_ply, EXPECTED_PLY_CANDIDATE_COUNT, "PLY candidate count")
    _expect_equal(total_drc, EXPECTED_DRC_CANDIDATE_COUNT, "DRC candidate count")
    _expect_equal(
        total_ply + total_drc,
        EXPECTED_TOTAL_CANDIDATE_COUNT,
        "total candidate count",
    )

    validation_summary = {
        "source_validation_passed": bool(source_validation.get("passed")),
        "drc_validation_passed": bool(drc_validation.get("validation_passed")),
        "drc_validation_checks": list(drc_validation.get("checks", ())),
        "drc_validation_variant_count": drc_validation.get("variant_count"),
        "basic_decode_integrity_checked_variant_count": drc_manifest.get(
            "basic_decode_integrity_checked_variant_count"
        ),
        "basic_decode_integrity_pass": drc_manifest.get("generation_summary", {}).get(
            "basic_decode_integrity_pass"
        ),
    }

    return {
        "catalog_type": CATALOG_TYPE,
        "catalog_version": CATALOG_VERSION,
        "solver_ready": False,
        "dataset_id": EXPECTED_DATASET_ID,
        "frame_id": EXPECTED_FRAME_ID,
        "grid_profile_id": EXPECTED_GRID_PROFILE_ID,
        "source_data_prep": {
            "repo_logical_name": "pcv-stage2-data-prep",
            "artifact_roots": {
                "source_ply": SOURCE_ARTIFACT_ROOT.as_posix(),
                "drc": DRC_ARTIFACT_ROOT.as_posix(),
            },
            "source_artifact_profile_id": EXPECTED_SOURCE_PROFILE_ID,
            "drc_artifact_profile_id": EXPECTED_DRC_PROFILE_ID,
        },
        "read_inputs": [
            _fingerprint(root, rel_path)
            for rel_path in (
                SOURCE_PROFILE_CONFIG,
                DRC_PROFILE_CONFIG,
                SOURCE_GENERATION_MANIFEST,
                SOURCE_TILE_INDEX,
                SOURCE_VALIDATION_REPORT,
                DRC_GENERATION_MANIFEST,
                DRC_VALIDATION_REPORT,
            )
        ],
        "summary": {
            "non_empty_tile_count": len(tiles),
            "ply_candidate_count": total_ply,
            "drc_candidate_count": total_drc,
            "total_candidate_count": total_ply + total_drc,
            "pdl_values": list(EXPECTED_PDLS),
            "qp_values": list(EXPECTED_QPS),
            "codec_id": EXPECTED_CODEC_ID,
            "point_cloud_flag": EXPECTED_POINT_CLOUD_FLAG,
            "compression_level": EXPECTED_COMPRESSION_LEVEL,
        },
        "validation_summary": validation_summary,
        "non_claims": list(NON_CLAIMS),
        "tiles": tiles,
    }


def write_catalog(path: str | Path, catalog: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def inspection_summary(catalog: dict[str, Any], output_path: str | Path | None) -> str:
    summary = catalog["summary"]
    validation = catalog["validation_summary"]
    lines = [
        f"catalog_type: {catalog['catalog_type']}@{catalog['catalog_version']}",
        f"dataset/frame/grid: {catalog['dataset_id']} / {catalog['frame_id']} / {catalog['grid_profile_id']}",
        "read_inputs:",
    ]
    lines.extend(f"- {item['path']} sha256={item['sha256']}" for item in catalog["read_inputs"])
    lines.extend(
        [
            "counts:",
            f"- non_empty_tiles={summary['non_empty_tile_count']}",
            f"- ply_candidates={summary['ply_candidate_count']}",
            f"- drc_candidates={summary['drc_candidate_count']}",
            f"- total_candidates={summary['total_candidate_count']}",
            "path_and_size_check: passed",
            "validation:",
            f"- source_validation_passed={validation['source_validation_passed']}",
            f"- drc_validation_passed={validation['drc_validation_passed']}",
            f"- basic_decode_integrity_pass={validation['basic_decode_integrity_pass']}",
            f"output_path: {Path(output_path).as_posix() if output_path else '<not written>'}",
        ]
    )
    return "\n".join(lines)


def _load_json(root: Path, rel_path: Path) -> dict[str, Any]:
    path = root / rel_path
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MetadataBridgeError(f"required JSON file is missing: {rel_path.as_posix()}") from exc
    except json.JSONDecodeError as exc:
        raise MetadataBridgeError(
            f"{rel_path.as_posix()} is not valid JSON: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(data, dict):
        raise MetadataBridgeError(f"{rel_path.as_posix()} must contain a JSON object")
    return data


def _fingerprint(root: Path, rel_path: Path) -> dict[str, Any]:
    path = root / rel_path
    data = path.read_bytes()
    return {
        "path": rel_path.as_posix(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": path.stat().st_size,
    }


def _validate_profiles(
    *,
    source_profile: dict[str, Any],
    drc_profile: dict[str, Any],
    source_manifest: dict[str, Any],
    source_tile_index: dict[str, Any],
    source_validation: dict[str, Any],
    drc_manifest: dict[str, Any],
    drc_validation: dict[str, Any],
) -> None:
    for context, payload in (
        ("source sampling profile", source_profile),
        ("DRC profile", drc_profile),
        ("source manifest", source_manifest),
        ("source tile index", source_tile_index),
        ("DRC manifest", drc_manifest),
    ):
        _expect_equal(payload.get("dataset_id"), EXPECTED_DATASET_ID, f"{context} dataset_id")
        _expect_equal(payload.get("frame_id"), EXPECTED_FRAME_ID, f"{context} frame_id")

    for context, payload in (
        ("source sampling profile", source_profile),
        ("DRC profile", drc_profile),
        ("source tile index", source_tile_index),
        ("DRC manifest", drc_manifest),
    ):
        _expect_equal(
            payload.get("grid_profile_id"),
            EXPECTED_GRID_PROFILE_ID,
            f"{context} grid_profile_id",
        )

    _expect_equal(
        source_profile.get("sampling_profile_id"),
        EXPECTED_SOURCE_PROFILE_ID,
        "source sampling_profile_id",
    )
    _expect_equal(
        source_manifest.get("artifact_profile_id"),
        EXPECTED_SOURCE_PROFILE_ID,
        "source artifact_profile_id",
    )
    _expect_equal(
        source_tile_index.get("artifact_profile_id"),
        EXPECTED_SOURCE_PROFILE_ID,
        "source tile index artifact_profile_id",
    )
    _expect_equal(
        source_tile_index.get("sampling_profile_id"),
        EXPECTED_SOURCE_PROFILE_ID,
        "source tile index sampling_profile_id",
    )
    _expect_equal(
        drc_profile.get("profile_id"),
        EXPECTED_DRC_PROFILE_ID,
        "DRC profile_id",
    )
    _expect_equal(
        drc_manifest.get("artifact_profile_id"),
        EXPECTED_DRC_PROFILE_ID,
        "DRC artifact_profile_id",
    )
    _expect_equal(
        drc_manifest.get("source_artifact_profile_id"),
        EXPECTED_SOURCE_PROFILE_ID,
        "DRC source_artifact_profile_id",
    )
    _expect_equal(
        _path_string(drc_profile.get("source_artifact_root")),
        SOURCE_ARTIFACT_ROOT.as_posix(),
        "DRC profile source_artifact_root",
    )
    _expect_equal(
        _path_string(drc_manifest.get("source_artifact_root")),
        SOURCE_ARTIFACT_ROOT.as_posix(),
        "DRC manifest source_artifact_root",
    )
    _expect_equal(
        _path_string(drc_profile.get("output_root")),
        DRC_ARTIFACT_ROOT.as_posix(),
        "DRC profile output_root",
    )
    _expect_equal(
        _path_string(drc_manifest.get("output_root")),
        DRC_ARTIFACT_ROOT.as_posix(),
        "DRC manifest output_root",
    )

    _expect_pdl_sequence(source_profile.get("quality_levels"), "source profile quality_levels")
    _expect_pdl_sequence(source_manifest.get("quality_levels"), "source manifest quality_levels")
    _expect_pdl_sequence(source_tile_index.get("quality_levels"), "source tile index quality_levels")
    _expect_pdl_sequence(source_validation.get("quality_levels"), "source validation quality_levels")
    _expect_pdl_sequence(drc_profile.get("source_pdls"), "DRC profile source_pdls")
    _expect_pdl_sequence(drc_manifest.get("source_pdls"), "DRC manifest source_pdls")
    _expect_equal(tuple(drc_profile.get("qp_values", ())), EXPECTED_QPS, "DRC profile qp_values")
    _expect_equal(tuple(drc_manifest.get("qp_values", ())), EXPECTED_QPS, "DRC manifest qp_values")

    for context, payload in (("DRC profile", drc_profile), ("DRC manifest", drc_manifest)):
        _expect_equal(payload.get("codec_id"), EXPECTED_CODEC_ID, f"{context} codec_id")
        _expect_equal(
            payload.get("point_cloud_flag"),
            EXPECTED_POINT_CLOUD_FLAG,
            f"{context} point_cloud_flag",
        )
        _expect_equal(
            payload.get("compression_level"),
            EXPECTED_COMPRESSION_LEVEL,
            f"{context} compression_level",
        )

    _expect_equal(
        source_manifest.get("non_empty_tile_count"),
        EXPECTED_NON_EMPTY_TILE_COUNT,
        "source manifest non_empty_tile_count",
    )
    _expect_equal(
        source_tile_index.get("non_empty_tile_count"),
        EXPECTED_NON_EMPTY_TILE_COUNT,
        "source tile index non_empty_tile_count",
    )
    _expect_equal(
        source_validation.get("non_empty_tile_count"),
        EXPECTED_NON_EMPTY_TILE_COUNT,
        "source validation non_empty_tile_count",
    )
    _expect_equal(
        source_manifest.get("generated_ply_file_count"),
        EXPECTED_PLY_CANDIDATE_COUNT,
        "source manifest generated_ply_file_count",
    )
    _expect_equal(
        source_validation.get("generated_ply_file_count"),
        EXPECTED_PLY_CANDIDATE_COUNT,
        "source validation generated_ply_file_count",
    )
    _expect(source_validation.get("passed") is True, "source validation report did not pass")

    _expect_equal(
        drc_manifest.get("expected_non_empty_tile_count"),
        EXPECTED_NON_EMPTY_TILE_COUNT,
        "DRC expected_non_empty_tile_count",
    )
    _expect_equal(
        drc_manifest.get("expected_variant_count"),
        EXPECTED_DRC_CANDIDATE_COUNT,
        "DRC expected_variant_count",
    )
    _expect_equal(
        drc_manifest.get("generated_drc_file_count"),
        EXPECTED_DRC_CANDIDATE_COUNT,
        "DRC generated_drc_file_count",
    )
    _expect_equal(
        drc_manifest.get("basic_decode_integrity_checked_variant_count"),
        EXPECTED_DRC_CANDIDATE_COUNT,
        "DRC basic_decode_integrity_checked_variant_count",
    )
    generation_summary = drc_manifest.get("generation_summary", {})
    _expect_equal(
        generation_summary.get("non_empty_tile_count"),
        EXPECTED_NON_EMPTY_TILE_COUNT,
        "DRC generation_summary non_empty_tile_count",
    )
    _expect_equal(
        generation_summary.get("expected_variant_count"),
        EXPECTED_DRC_CANDIDATE_COUNT,
        "DRC generation_summary expected_variant_count",
    )
    _expect_equal(
        generation_summary.get("generated_drc_file_count"),
        EXPECTED_DRC_CANDIDATE_COUNT,
        "DRC generation_summary generated_drc_file_count",
    )
    _expect(
        generation_summary.get("basic_decode_integrity_pass") is True,
        "DRC generation_summary basic_decode_integrity_pass is not true",
    )

    _expect(drc_validation.get("validation_passed") is True, "DRC validation report did not pass")
    _expect_equal(
        _path_string(drc_validation.get("artifact_root")),
        DRC_ARTIFACT_ROOT.as_posix(),
        "DRC validation artifact_root",
    )
    _expect_equal(
        drc_validation.get("variant_count"),
        EXPECTED_DRC_CANDIDATE_COUNT,
        "DRC validation variant_count",
    )
    _expect(
        "decode_all_drc" in set(drc_validation.get("checks", ())),
        "DRC validation report does not record decode_all_drc",
    )


def _collect_source_assets(
    *,
    root: Path,
    source_tile_index: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    tiles = source_tile_index.get("tiles")
    _expect(isinstance(tiles, list), "source tile index tiles must be a list")
    non_empty_tiles = [tile for tile in tiles if tile.get("is_empty") is False]
    _expect_equal(
        len(non_empty_tiles),
        EXPECTED_NON_EMPTY_TILE_COUNT,
        "source non-empty tile count",
    )

    result: dict[str, dict[str, Any]] = {}
    source_root = root / SOURCE_ARTIFACT_ROOT
    for tile in non_empty_tiles:
        tile_id = _string(tile.get("tile_id"), "source tile_id")
        _expect(tile_id not in result, f"duplicate source tile_id {tile_id}")
        _expect_equal(tile.get("asset_status"), "generated_pdl_5", f"{tile_id} asset_status")
        assets = tile.get("quality_assets")
        _expect(isinstance(assets, list), f"{tile_id} quality_assets must be a list")
        _expect_equal(len(assets), len(EXPECTED_PDLS), f"{tile_id} source PLY asset count")

        by_pdl: dict[float, dict[str, Any]] = {}
        for asset in assets:
            pdl = _expected_pdl(asset.get("target_pdl"), f"{tile_id} target_pdl")
            _expect(pdl not in by_pdl, f"{tile_id} duplicate source PLY pdl {pdl}")
            _expect_equal(asset.get("tile_id"), tile_id, f"{tile_id} source asset tile_id")
            _expect_equal(asset.get("dataset_id"), EXPECTED_DATASET_ID, f"{tile_id} source asset dataset_id")
            _expect_equal(asset.get("frame_id"), EXPECTED_FRAME_ID, f"{tile_id} source asset frame_id")
            _expect_equal(
                asset.get("grid_profile_id"),
                EXPECTED_GRID_PROFILE_ID,
                f"{tile_id} source asset grid_profile_id",
            )
            _expect_equal(
                asset.get("sampling_profile_id"),
                EXPECTED_SOURCE_PROFILE_ID,
                f"{tile_id} source asset sampling_profile_id",
            )
            relpath = _safe_relative_path(asset.get("relative_path"), f"{tile_id} source PLY relative_path")
            manifest_size = _positive_int(asset.get("file_size_bytes"), f"{tile_id} source PLY file_size_bytes")
            stat_size = _stat_size(source_root, relpath, f"{tile_id} source PLY {relpath}")
            _expect_equal(stat_size, manifest_size, f"{tile_id} source PLY size mismatch for {relpath}")
            by_pdl[pdl] = {
                "record": asset,
                "relative_path": relpath,
                "file_size_bytes": manifest_size,
                "stat_size_bytes": stat_size,
                "sha256": _string(asset.get("sha256"), f"{tile_id} source PLY sha256"),
            }

        _expect_equal(
            tuple(sorted(by_pdl)),
            EXPECTED_PDLS,
            f"{tile_id} source PLY matrix incomplete",
        )
        result[tile_id] = {"tile": tile, "assets": by_pdl}

    return result


def _collect_drc_variants(
    *,
    root: Path,
    drc_manifest: dict[str, Any],
) -> dict[str, dict[tuple[float, int], dict[str, Any]]]:
    variants = drc_manifest.get("variants")
    _expect(isinstance(variants, list), "DRC manifest variants must be a list")
    _expect_equal(len(variants), EXPECTED_DRC_CANDIDATE_COUNT, "DRC variant record count")

    drc_root = root / DRC_ARTIFACT_ROOT
    result: dict[str, dict[tuple[float, int], dict[str, Any]]] = {}
    for variant in variants:
        tile_id = _string(variant.get("tile_id"), "DRC variant tile_id")
        pdl = _expected_pdl(variant.get("source_pdl"), f"{tile_id} DRC source_pdl")
        qp = _expected_qp(variant.get("qp"), f"{tile_id} DRC qp")
        key = (pdl, qp)
        result.setdefault(tile_id, {})
        _expect(key not in result[tile_id], f"{tile_id} duplicate DRC variant for pdl={pdl}, qp={qp}")

        _expect_equal(variant.get("codec_id"), EXPECTED_CODEC_ID, f"{tile_id} DRC codec_id")
        _expect_equal(variant.get("point_cloud_flag"), EXPECTED_POINT_CLOUD_FLAG, f"{tile_id} DRC point_cloud_flag")
        _expect_equal(
            variant.get("compression_level"),
            EXPECTED_COMPRESSION_LEVEL,
            f"{tile_id} DRC compression_level",
        )
        _expect(variant.get("basic_decode_integrity_pass") is True, f"{tile_id} DRC basic_decode_integrity_pass is not true")

        drc_relpath = _safe_relative_path(variant.get("drc_relpath"), f"{tile_id} DRC relpath")
        drc_manifest_size = _positive_int(variant.get("drc_file_size_bytes"), f"{tile_id} DRC file_size_bytes")
        drc_stat_size = _stat_size(drc_root, drc_relpath, f"{tile_id} DRC {drc_relpath}")
        _expect_equal(drc_stat_size, drc_manifest_size, f"{tile_id} DRC size mismatch for {drc_relpath}")

        source_relpath = _safe_relative_path(
            variant.get("source_ply_relpath"),
            f"{tile_id} DRC source_ply_relpath",
        )
        _positive_int(
            variant.get("source_ply_file_size_bytes"),
            f"{tile_id} DRC source_ply_file_size_bytes",
        )
        _string(variant.get("source_ply_sha256"), f"{tile_id} DRC source_ply_sha256")

        stored = dict(variant)
        stored["_drc_relpath"] = drc_relpath
        stored["_drc_stat_size_bytes"] = drc_stat_size
        stored["_source_ply_relpath"] = source_relpath
        result[tile_id][key] = stored

    for tile_id, variants_by_key in result.items():
        _expect_equal(
            tuple(sorted(variants_by_key)),
            tuple((pdl, qp) for pdl in EXPECTED_PDLS for qp in EXPECTED_QPS),
            f"{tile_id} DRC matrix incomplete",
        )
    return result


def _validate_tile_sets(
    source_by_tile: dict[str, dict[str, Any]],
    drc_by_tile: dict[str, dict[tuple[float, int], dict[str, Any]]],
) -> None:
    source_tiles = set(source_by_tile)
    drc_tiles = set(drc_by_tile)
    _expect_equal(len(source_tiles), EXPECTED_NON_EMPTY_TILE_COUNT, "source tile set size")
    _expect_equal(drc_tiles, source_tiles, "source and DRC tile sets")


def _validate_drc_source_links(
    drc_by_tile: dict[str, dict[tuple[float, int], dict[str, Any]]],
    source_by_tile: dict[str, dict[str, Any]],
) -> None:
    for tile_id, variants_by_key in drc_by_tile.items():
        for (pdl, qp), variant in variants_by_key.items():
            source_asset = source_by_tile.get(tile_id, {}).get("assets", {}).get(pdl)
            _expect(
                source_asset is not None,
                f"{tile_id} DRC variant pdl={pdl}, qp={qp} has no same-tile source PLY",
            )
            _expect_equal(
                variant["_source_ply_relpath"],
                source_asset["relative_path"],
                f"{tile_id} DRC source PLY relpath does not match source asset for pdl={pdl}, qp={qp}",
            )
            _expect_equal(
                variant["source_ply_file_size_bytes"],
                source_asset["file_size_bytes"],
                f"{tile_id} DRC source PLY size does not match source asset for pdl={pdl}, qp={qp}",
            )
            _expect_equal(
                _string(variant.get("source_ply_sha256"), f"{tile_id} DRC source_ply_sha256").lower(),
                source_asset["sha256"].lower(),
                f"{tile_id} DRC source PLY sha256 does not match source asset for pdl={pdl}, qp={qp}",
            )


def _ply_candidate(tile_id: str, pdl: float, source_asset: dict[str, Any]) -> dict[str, Any]:
    record = source_asset["record"]
    return {
        "candidate_id": f"ply__pdl_{_pdl_token(pdl)}",
        "candidate_kind": "ply_source",
        "pdl_ratio": pdl,
        "file_format": "ply",
        "codec": "binary_little_endian_ply",
        "codec_params": {
            "source_pdl": pdl,
            "sampling_scope": record.get("sampling_scope"),
            "sampling_method": record.get("sampling_method"),
        },
        "artifact_root": SOURCE_ARTIFACT_ROOT.as_posix(),
        "asset_ref": source_asset["relative_path"],
        "r_bytes": source_asset["file_size_bytes"],
        "r_bytes_provenance": "measured",
        "manifest_integrity": {
            "relative_path": source_asset["relative_path"],
            "sha256": source_asset["sha256"],
            "file_size_bytes": source_asset["file_size_bytes"],
            "file_exists": True,
            "stat_size_bytes": source_asset["stat_size_bytes"],
            "size_matches_manifest": True,
        },
        "source_metadata": {
            "source_point_count": record.get("source_point_count"),
            "retained_point_count": record.get("retained_point_count"),
            "actual_retained_ratio": record.get("actual_retained_ratio"),
            "provenance_kind": record.get("provenance_kind"),
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
        "non_claims": [
            "This source PLY candidate does not provide target-side d_ms or q_base.",
            "pdl_ratio is source point-density metadata, not a final visual quality ordering.",
        ],
    }


def _drc_candidate(
    *,
    tile_id: str,
    pdl: float,
    qp: int,
    variant: dict[str, Any],
    source_asset: dict[str, Any],
) -> dict[str, Any]:
    return {
        "candidate_id": f"drc__pdl_{_pdl_token(pdl)}__qp_{qp}__cl_{EXPECTED_COMPRESSION_LEVEL}",
        "candidate_kind": "drc_delivery",
        "pdl_ratio": pdl,
        "file_format": "drc",
        "codec": "draco",
        "codec_params": {
            "source_pdl": pdl,
            "qp": qp,
            "compression_level": EXPECTED_COMPRESSION_LEVEL,
            "point_cloud_mode": True,
        },
        "artifact_root": DRC_ARTIFACT_ROOT.as_posix(),
        "asset_ref": variant["_drc_relpath"],
        "r_bytes": variant["drc_file_size_bytes"],
        "r_bytes_provenance": "measured",
        "manifest_integrity": {
            "relative_path": variant["_drc_relpath"],
            "sha256": _string(variant.get("drc_sha256"), f"{tile_id} DRC sha256"),
            "file_size_bytes": variant["drc_file_size_bytes"],
            "file_exists": True,
            "stat_size_bytes": variant["_drc_stat_size_bytes"],
            "size_matches_manifest": True,
        },
        "source_ply_linkage": {
            "tile_id": tile_id,
            "source_pdl": pdl,
            "source_candidate_id": f"ply__pdl_{_pdl_token(pdl)}",
            "source_asset_ref": source_asset["relative_path"],
            "source_ply_sha256": source_asset["sha256"],
            "source_ply_file_size_bytes": source_asset["file_size_bytes"],
        },
        "roundtrip_validation_summary": {
            "basic_decode_integrity_pass": variant.get("basic_decode_integrity_pass"),
            "decoded_vertex_count": variant.get("decoded_vertex_count"),
            "rgb_multiset_exact": variant.get("rgb_multiset_exact"),
            "decoded_schema_fields": list(variant.get("decoded_schema_fields", ())),
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
            "source_ply_linkage": "derived",
        },
        "non_claims": [
            "This DRC candidate does not provide target-side d_ms or q_base.",
            "qp and codec metadata do not define a natural quality ordering.",
            "basic decode-integrity is not DRC-aware visual quality evidence.",
        ],
    }


def _safe_relative_path(value: Any, context: str) -> str:
    raw = _string(value, context)
    normalized = raw.replace("\\", "/")
    _expect(not PureWindowsPath(raw).is_absolute(), f"{context} must be relative, got absolute path")
    posix = PurePosixPath(normalized)
    _expect(not posix.is_absolute(), f"{context} must be relative, got absolute path")
    _expect(posix.parts, f"{context} must not be empty")
    _expect(
        all(part not in {"..", "."} for part in posix.parts),
        f"{context} must not contain '.' or '..'",
    )
    return posix.as_posix()


def _stat_size(artifact_root: Path, relpath: str, context: str) -> int:
    path = (artifact_root / relpath).resolve(strict=False)
    artifact_root_resolved = artifact_root.resolve(strict=True)
    _expect(_is_relative_to(path, artifact_root_resolved), f"{context} escapes artifact root")
    _expect(path.exists(), f"{context} referenced file is missing")
    _expect(path.is_file(), f"{context} is not a file")
    return path.stat().st_size


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _path_string(value: Any) -> str:
    return _string(value, "path").replace("\\", "/")


def _string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise MetadataBridgeError(f"{context} must be a non-empty string")
    return value


def _positive_int(value: Any, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise MetadataBridgeError(f"{context} must be a positive integer, got {value!r}")
    return value


def _expected_pdl(value: Any, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise MetadataBridgeError(f"{context} must be one of {EXPECTED_PDLS}, got {value!r}")
    numeric = float(value)
    for expected in EXPECTED_PDLS:
        if math.isclose(numeric, expected, rel_tol=0.0, abs_tol=1e-9):
            return expected
    raise MetadataBridgeError(f"{context} must be one of {EXPECTED_PDLS}, got {value!r}")


def _expected_qp(value: Any, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in EXPECTED_QPS:
        raise MetadataBridgeError(f"{context} must be one of {EXPECTED_QPS}, got {value!r}")
    return value


def _expect_pdl_sequence(values: Any, context: str) -> None:
    _expect(isinstance(values, list), f"{context} must be a list")
    normalized = tuple(_expected_pdl(value, context) for value in values)
    _expect_equal(normalized, EXPECTED_PDLS, context)


def _pdl_token(pdl: float) -> str:
    return f"{pdl:.1f}".replace(".", "p")


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise MetadataBridgeError(message)


def _expect_equal(actual: Any, expected: Any, context: str) -> None:
    if actual != expected:
        raise MetadataBridgeError(f"{context}: expected {expected!r}, got {actual!r}")
