from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from .frame1051_metadata_bridge import CATALOG_TYPE
from .io import distance_lookup_from_dict, load_json, stage2_input_from_dict
from .models import DistanceLookup, LambdaSearchConfig, Stage2Input, Stage2SolveResult
from .preprocess import resolve_lookup_for_input
from .solver import solve_stage2


DEFAULT_PROFILE_PATH = Path("configs/frame1051_fullbody_proxy_behavior_v1.json")
FLOAT_EPSILON = 1e-9


class BehaviorPilotError(ValueError):
    """Raised when the frame 1051 behavior pilot refuses an invalid input."""


def load_behavior_pilot_profile(path: str | Path = DEFAULT_PROFILE_PATH) -> dict[str, Any]:
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise BehaviorPilotError("behavior pilot profile must be a JSON object")
    return payload


def profile_fingerprint(path: str | Path) -> dict[str, Any]:
    profile_path = Path(path)
    data = profile_path.read_bytes()
    try:
        display_path = profile_path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        display_path = profile_path.as_posix()
    return {
        "path": display_path,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": profile_path.stat().st_size,
    }


def stable_json_fingerprint(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def validate_catalog_for_behavior_pilot(
    catalog: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    contract = profile.get("catalog_contract", {})
    expected_catalog_type = contract.get("required_catalog_type", CATALOG_TYPE)
    expected_solver_ready = contract.get("required_solver_ready", False)
    expected_d_ms_status = contract.get("required_candidate_d_ms_status", "pending")
    expected_q_base_status = contract.get("required_candidate_q_base_status", "pending")

    _expect_equal(catalog.get("catalog_type"), expected_catalog_type, "catalog_type")
    _expect_equal(catalog.get("solver_ready"), expected_solver_ready, "solver_ready")

    summary = catalog.get("summary", {})
    _expect_equal(summary.get("non_empty_tile_count"), 40, "catalog non_empty_tile_count")
    _expect_equal(summary.get("ply_candidate_count"), 200, "catalog ply_candidate_count")
    _expect_equal(summary.get("drc_candidate_count"), 600, "catalog drc_candidate_count")
    _expect_equal(summary.get("total_candidate_count"), 800, "catalog total_candidate_count")

    tiles = catalog.get("tiles")
    _expect(isinstance(tiles, list), "catalog tiles must be a list")
    _expect_equal(len(tiles), 40, "catalog tile count")

    for tile in tiles:
        tile_id = _string(tile.get("tile_id"), "catalog tile_id")
        candidates = tile.get("candidates")
        _expect(isinstance(candidates, list), f"{tile_id} candidates must be a list")
        _expect_equal(len(candidates), 20, f"{tile_id} candidate count")
        candidate_ids = [_string(item.get("candidate_id"), f"{tile_id} candidate_id") for item in candidates]
        _expect_equal(len(candidate_ids), len(set(candidate_ids)), f"{tile_id} candidate_id uniqueness")
        for candidate in candidates:
            candidate_id = _string(candidate.get("candidate_id"), f"{tile_id} candidate_id")
            _expect_equal(
                candidate.get("d_ms_status"),
                expected_d_ms_status,
                f"{tile_id}/{candidate_id} d_ms_status",
            )
            _expect_equal(
                candidate.get("q_base_status"),
                expected_q_base_status,
                f"{tile_id}/{candidate_id} q_base_status",
            )
            _expect("d_ms" not in candidate, f"{tile_id}/{candidate_id} must not carry d_ms")
            _expect("q_base" not in candidate, f"{tile_id}/{candidate_id} must not carry q_base")
            _expect_equal(
                candidate.get("r_bytes_provenance"),
                "measured",
                f"{tile_id}/{candidate_id} r_bytes_provenance",
            )
            _positive_number(candidate.get("r_bytes"), f"{tile_id}/{candidate_id} r_bytes")
            _pdl_ratio(candidate.get("pdl_ratio"), f"{tile_id}/{candidate_id} pdl_ratio")
            _expect(
                candidate.get("candidate_kind") in {"ply_source", "drc_delivery"},
                f"{tile_id}/{candidate_id} candidate_kind must be ply_source or drc_delivery",
            )


def build_behavior_lookup_payload(profile: dict[str, Any]) -> dict[str, Any]:
    lookup = profile["lookup"]
    return {
        "schema_version": "0.2.0",
        "lookup_profile_id": lookup["lookup_profile_id"],
        "semantics": lookup["semantics"],
        "distance_unit": lookup["distance_unit"],
        "pdl_support": lookup["pdl_support"],
        "source": {
            "dataset": "8i_longdress",
            "renderer": "web_threejs_full_body_calibration",
            "metric": "ssim_p10",
            "threshold_profile": lookup["threshold_profile"],
            "source_runs": lookup["source_runs"],
            "source_boundary_zh": lookup["source_boundary_zh"],
        },
        "rules": lookup["rules"],
    }


def build_behavior_lookup(profile: dict[str, Any]) -> DistanceLookup:
    return distance_lookup_from_dict(build_behavior_lookup_payload(profile))


def derive_budget_points(
    catalog: dict[str, Any],
    profile: dict[str, Any],
    observation: dict[str, Any],
) -> dict[str, Any]:
    pdl_max_dist = _pdl_cap_for_observation(profile, observation)
    per_tile: dict[str, dict[str, Any]] = {}
    total_allowed = 0
    min_total = 0
    max_total = 0

    for tile in sorted(catalog["tiles"], key=lambda item: item["tile_id"]):
        allowed = [
            candidate
            for candidate in tile["candidates"]
            if candidate["pdl_ratio"] <= pdl_max_dist + 1e-12
        ]
        _expect(allowed, f"{tile['tile_id']} has no allowed candidate for pdl cap {pdl_max_dist}")
        sizes = [int(candidate["r_bytes"]) for candidate in allowed]
        total_allowed += len(allowed)
        per_tile[tile["tile_id"]] = {
            "allowed_candidate_count": len(allowed),
            "min_r_bytes": min(sizes),
            "max_r_bytes": max(sizes),
        }
        min_total += min(sizes)
        max_total += max(sizes)

    midpoint = math.floor((min_total + max_total) / 2)
    ordered = [
        {
            "budget_id": "min_feasible",
            "budget_total_bytes": min_total,
            "formula": "B_min = sum_i min_j R_i,j over lookup-allowed candidates",
        },
        {
            "budget_id": "midpoint",
            "budget_total_bytes": midpoint,
            "formula": "B_mid = floor((B_min + B_reference_max) / 2)",
        },
        {
            "budget_id": "reference_max",
            "budget_total_bytes": max_total,
            "formula": "B_reference_max = sum_i max_j R_i,j over lookup-allowed candidates",
        },
    ]

    seen: dict[int, str] = {}
    unique_points: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    for point in ordered:
        budget_value = int(point["budget_total_bytes"])
        if budget_value in seen:
            duplicates.append(
                {
                    "budget_id": point["budget_id"],
                    "budget_total_bytes": budget_value,
                    "duplicate_of": seen[budget_value],
                }
            )
            continue
        seen[budget_value] = point["budget_id"]
        unique_points.append(point)

    return {
        "pdl_max_dist": pdl_max_dist,
        "total_allowed_candidate_count": total_allowed,
        "allowed_candidate_counts_by_tile": {
            tile_id: item["allowed_candidate_count"] for tile_id, item in per_tile.items()
        },
        "per_tile_budget_extremes": per_tile,
        "B_min": min_total,
        "B_reference_max": max_total,
        "budget_points": unique_points,
        "deduplicated_budget_points": duplicates,
    }


def build_stage2_input_payload(
    catalog: dict[str, Any],
    profile: dict[str, Any],
    observation: dict[str, Any],
    budget_point: dict[str, Any],
) -> dict[str, Any]:
    profile_id = profile["profile_id"]
    scenario_id = (
        f"{profile_id}__{observation['context_id']}__{budget_point['budget_id']}"
    )
    tile_proxy = profile["tile_proxy_fields"]
    candidate_proxy = profile["candidate_proxy_fields"]

    tiles = []
    for tile in sorted(catalog["tiles"], key=lambda item: item["tile_id"]):
        candidates = []
        for candidate in sorted(tile["candidates"], key=_candidate_sort_key):
            pdl_ratio = _pdl_ratio(candidate["pdl_ratio"], f"{tile['tile_id']} pdl_ratio")
            candidates.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "pdl_ratio": pdl_ratio,
                    "file_format": candidate["file_format"],
                    "codec": candidate["codec"],
                    "codec_params": _json_compatible(candidate.get("codec_params", {})),
                    "asset_ref": _candidate_asset_ref(candidate),
                    "r_bytes": float(candidate["r_bytes"]),
                    "d_ms": float(candidate_proxy["d_ms"]),
                    "q_base": pdl_ratio,
                    "provenance": {
                        "r_bytes": "measured",
                        "d_ms": candidate_proxy["d_ms_provenance"],
                        "q_base": candidate_proxy["q_base_provenance"],
                        "pdl_ratio": "derived",
                        "asset_ref": "derived",
                    },
                }
            )
        tiles.append(
            {
                "tile_id": tile["tile_id"],
                "p_sal": float(tile_proxy["p_sal"]),
                "visibility": float(tile_proxy["visibility"]),
                "screen_area": float(tile_proxy["screen_area"]),
                "distance_norm": float(observation["distance_norm"]),
                "view_context": observation["view_context"],
                "candidates": candidates,
                "provenance": {
                    "p_sal": tile_proxy["provenance"],
                    "visibility": tile_proxy["provenance"],
                    "screen_area": tile_proxy["provenance"],
                    "distance_norm": observation["distance_assignment_provenance"],
                    "view_context": "derived",
                },
            }
        )

    return {
        "schema_version": "0.2.0",
        "scenario_id": scenario_id,
        "description": (
            "Phase 2B.4 frame 1051 solver behavior pilot input. "
            "Uses real candidate identity and measured file body r_bytes with "
            "explicit proxy q_base/d_ms/spatial fields."
        ),
        "budget_total_bytes": float(budget_point["budget_total_bytes"]),
        "eta": float(candidate_proxy["eta"]),
        "lookup_profile_id": profile["lookup"]["lookup_profile_id"],
        "tiles": tiles,
        "provenance_summary": {
            "pilot_profile_id": profile_id,
            "phase": "Phase 2B.4",
            "catalog_type": catalog["catalog_type"],
            "candidate_identity": "measured",
            "r_bytes": "measured",
            "q_base": candidate_proxy["q_base_provenance"],
            "d_ms": candidate_proxy["d_ms_provenance"],
            "spatial_fields": tile_proxy["provenance"],
            "distance_norm": observation["distance_assignment_provenance"],
            "budget_total_bytes": profile["budget_total_bytes_provenance"],
            "non_claims": list(profile["non_claims"]),
        },
    }


def build_stage2_input(
    catalog: dict[str, Any],
    profile: dict[str, Any],
    observation: dict[str, Any],
    budget_point: dict[str, Any],
) -> Stage2Input:
    return stage2_input_from_dict(
        build_stage2_input_payload(catalog, profile, observation, budget_point)
    )


def lambda_config_from_profile(profile: dict[str, Any]) -> LambdaSearchConfig:
    config = profile["solver_config"]
    return LambdaSearchConfig(
        lambda_initial_high=float(config["lambda_initial_high"]),
        lambda_max_bracket_steps=int(config["lambda_max_bracket_steps"]),
        score_epsilon=float(config["score_epsilon"]),
        lambda_epsilon=float(config["lambda_epsilon"]),
        max_iterations=int(config["max_iterations"]),
    )


def run_behavior_pilot(
    catalog: dict[str, Any],
    profile: dict[str, Any],
    *,
    profile_fingerprint_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_catalog_for_behavior_pilot(catalog, profile)
    lookup_payload = build_behavior_lookup_payload(profile)
    lookup = distance_lookup_from_dict(lookup_payload)
    config = lambda_config_from_profile(profile)
    catalog_index = _catalog_index(catalog)

    scenario_artifacts = []
    scenario_reports = []

    for observation in profile["observation_contexts"]:
        budget_context = derive_budget_points(catalog, profile, observation)
        _expect_equal(
            budget_context["pdl_max_dist"],
            float(observation["expected_pdl_max_dist"]),
            f"{observation['context_id']} pdl_max_dist",
        )
        for budget_point in budget_context["budget_points"]:
            input_payload = build_stage2_input_payload(
                catalog,
                profile,
                observation,
                budget_point,
            )
            stage2_input = stage2_input_from_dict(input_payload)
            result = solve_stage2(stage2_input, lookup, config)
            result_payload = result.to_dict()
            invariants = check_result_invariants(
                stage2_input=stage2_input,
                result=result,
                catalog_index=catalog_index,
            )
            scenario_report = _scenario_report(
                observation=observation,
                budget_context=budget_context,
                budget_point=budget_point,
                stage2_input=stage2_input,
                result=result,
                invariants=invariants,
                catalog_index=catalog_index,
            )
            scenario_artifacts.append(
                {
                    "scenario_id": stage2_input.scenario_id,
                    "input_payload": input_payload,
                    "result_payload": result_payload,
                }
            )
            scenario_reports.append(scenario_report)

    report = {
        "report_type": "frame1051_solver_behavior_pilot_report",
        "report_version": "0.1.0",
        "pilot_profile": {
            "profile_id": profile["profile_id"],
            "fingerprint": profile_fingerprint_info,
        },
        "bridge_catalog": {
            "catalog_type": catalog["catalog_type"],
            "catalog_version": catalog.get("catalog_version"),
            "fingerprint": stable_json_fingerprint(catalog),
            "source_metadata_fingerprints": list(catalog.get("read_inputs", ())),
        },
        "lookup": {
            "lookup_profile_id": lookup.lookup_profile_id,
            "distance_unit": lookup.distance_unit,
            "semantics": lookup.semantics,
            "source_boundary_zh": profile["lookup"]["source_boundary_zh"],
        },
        "proxy_assumptions": {
            "tile_proxy_fields": dict(profile["tile_proxy_fields"]),
            "candidate_proxy_fields": dict(profile["candidate_proxy_fields"]),
            "budget_total_bytes_provenance": profile["budget_total_bytes_provenance"],
        },
        "scenario_count": len(scenario_reports),
        "scenarios": scenario_reports,
        "all_invariants_passed": all(
            item["invariants"]["all_passed"] for item in scenario_reports
        ),
        "non_claims": list(profile["non_claims"]),
    }

    return {
        "catalog": catalog,
        "lookup_payload": lookup_payload,
        "report": report,
        "scenario_artifacts": scenario_artifacts,
    }


def check_result_invariants(
    *,
    stage2_input: Stage2Input,
    result: Stage2SolveResult,
    catalog_index: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    details: list[str] = []

    checks["status_success"] = result.status == "SUCCESS"
    if not checks["status_success"]:
        details.append(f"status is {result.status}, expected SUCCESS")

    checks["one_selection_per_tile"] = len(result.selected_tiles) == len(stage2_input.tiles)
    selected_tile_ids = [item.tile_id for item in result.selected_tiles]
    checks["unique_selected_tiles"] = len(selected_tile_ids) == len(set(selected_tile_ids))
    checks["total_bytes_within_budget"] = (
        result.total_bytes is not None
        and result.total_bytes <= stage2_input.budget_total_bytes + FLOAT_EPSILON
    )

    resolution_by_tile = {item.tile_id: item for item in result.lookup_resolution}
    selected_total = 0.0
    selected_catalog_ok = True
    selected_allowed_ok = True
    selected_r_ok = True
    selected_provenance_ok = True

    for selected in result.selected_tiles:
        key = (selected.tile_id, selected.selected_candidate_id)
        catalog_candidate = catalog_index.get(key)
        if catalog_candidate is None:
            selected_catalog_ok = False
            details.append(f"{selected.tile_id}/{selected.selected_candidate_id} missing from catalog")
            continue
        resolution = resolution_by_tile.get(selected.tile_id)
        if resolution is None or selected.selected_candidate_id not in resolution.allowed_candidate_ids:
            selected_allowed_ok = False
            details.append(f"{selected.tile_id}/{selected.selected_candidate_id} outside allowed candidates")
        if not math.isclose(
            selected.r_bytes,
            float(catalog_candidate["r_bytes"]),
            rel_tol=FLOAT_EPSILON,
            abs_tol=FLOAT_EPSILON,
        ):
            selected_r_ok = False
            details.append(f"{selected.tile_id}/{selected.selected_candidate_id} r_bytes mismatch")
        snapshot_provenance = selected.selected_candidate_snapshot.get("provenance", {})
        if (
            snapshot_provenance.get("r_bytes") != "measured"
            or snapshot_provenance.get("q_base") != "proxy"
            or snapshot_provenance.get("d_ms") != "proxy"
        ):
            selected_provenance_ok = False
            details.append(f"{selected.tile_id}/{selected.selected_candidate_id} provenance mismatch")
        selected_total += selected.r_bytes

    checks["selected_candidates_in_catalog"] = selected_catalog_ok
    checks["selected_candidates_allowed"] = selected_allowed_ok
    checks["selected_r_bytes_match_catalog"] = selected_r_ok
    checks["selected_provenance_boundary"] = selected_provenance_ok
    checks["selected_sum_matches_total"] = (
        result.total_bytes is not None
        and math.isclose(selected_total, result.total_bytes, rel_tol=FLOAT_EPSILON, abs_tol=FLOAT_EPSILON)
    )
    checks["result_json_serializable"] = _json_serializable(result.to_dict())

    return {
        "checks": checks,
        "all_passed": all(checks.values()),
        "details": details,
    }


def write_behavior_pilot_outputs(output_dir: str | Path, run: dict[str, Any]) -> None:
    base = Path(output_dir)
    base.mkdir(parents=True, exist_ok=True)
    _write_json(base / "catalog_snapshot.json", run["catalog"])
    _write_json(base / "lookup_snapshot.json", run["lookup_payload"])
    _write_json(base / "report.json", run["report"])
    inputs_dir = base / "inputs"
    results_dir = base / "results"
    inputs_dir.mkdir(exist_ok=True)
    results_dir.mkdir(exist_ok=True)
    for item in run["scenario_artifacts"]:
        scenario_id = item["scenario_id"]
        _write_json(inputs_dir / f"{scenario_id}.stage2_input.json", item["input_payload"])
        _write_json(results_dir / f"{scenario_id}.stage2_result.json", item["result_payload"])


def behavior_pilot_console_summary(report: dict[str, Any], output_dir: str | Path) -> str:
    lines = [
        f"pilot_profile: {report['pilot_profile']['profile_id']}",
        f"scenario_count: {report['scenario_count']}",
        f"all_invariants_passed: {report['all_invariants_passed']}",
        f"output_dir: {Path(output_dir).as_posix()}",
    ]
    for scenario in report["scenarios"]:
        summary = scenario["selection_summary"]
        lines.append(
            (
                f"- {scenario['scenario_id']}: status={scenario['status']}, "
                f"pdl_cap={scenario['lookup_context']['pdl_max_dist']}, "
                f"budget={scenario['budget']['budget_total_bytes']}, "
                f"total_bytes={scenario['total_bytes']}, "
                f"utilization={scenario['budget_utilization']}, "
                f"selected_kind={summary['by_candidate_kind']}, "
                f"selected_pdl={summary['by_pdl_ratio']}"
            )
        )
    return "\n".join(lines)


def _scenario_report(
    *,
    observation: dict[str, Any],
    budget_context: dict[str, Any],
    budget_point: dict[str, Any],
    stage2_input: Stage2Input,
    result: Stage2SolveResult,
    invariants: dict[str, Any],
    catalog_index: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    lambda_iterations = result.lambda_search.get("iteration_count")
    if lambda_iterations is None:
        lambda_iterations = len(result.lambda_search.get("iterations", ()))
    return {
        "scenario_id": stage2_input.scenario_id,
        "lookup_context": {
            "context_id": observation["context_id"],
            "view_context": observation["view_context"],
            "distance_norm": observation["distance_norm"],
            "distance_assignment_provenance": observation["distance_assignment_provenance"],
            "pdl_max_dist": budget_context["pdl_max_dist"],
            "total_catalog_candidate_count": 800,
            "total_allowed_candidate_count": budget_context["total_allowed_candidate_count"],
            "allowed_candidate_counts_by_tile": budget_context["allowed_candidate_counts_by_tile"],
        },
        "budget": {
            "budget_id": budget_point["budget_id"],
            "budget_total_bytes": budget_point["budget_total_bytes"],
            "formula": budget_point["formula"],
            "B_min": budget_context["B_min"],
            "B_reference_max": budget_context["B_reference_max"],
            "provenance": "derived",
            "deduplicated_budget_points": budget_context["deduplicated_budget_points"],
        },
        "status": result.status,
        "b_min_feasible": result.b_min_feasible,
        "total_bytes": result.total_bytes,
        "budget_utilization": result.budget_utilization,
        "total_net_utility": result.total_net_utility,
        "lambda_search_iteration_count": lambda_iterations,
        "local_repair_step_count": len(result.local_upgrade.steps),
        "selection_summary": _selection_summary(result, catalog_index),
        "invariants": invariants,
    }


def _selection_summary(
    result: Stage2SolveResult,
    catalog_index: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, dict[str, int]]:
    by_kind: Counter[str] = Counter()
    by_pdl: Counter[str] = Counter()
    by_codec_qp: Counter[str] = Counter()
    for selected in result.selected_tiles:
        candidate = catalog_index[(selected.tile_id, selected.selected_candidate_id)]
        by_kind[candidate["candidate_kind"]] += 1
        by_pdl[_pdl_key(candidate["pdl_ratio"])] += 1
        codec = candidate["codec"]
        qp = candidate.get("codec_params", {}).get("qp")
        cl = candidate.get("codec_params", {}).get("compression_level")
        if qp is None:
            by_codec_qp[codec] += 1
        else:
            by_codec_qp[f"{codec}_qp_{qp}_cl_{cl}"] += 1
    return {
        "by_candidate_kind": _sorted_counter(by_kind),
        "by_pdl_ratio": _sorted_counter(by_pdl),
        "by_codec_qp": _sorted_counter(by_codec_qp),
    }


def _catalog_index(catalog: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for tile in catalog["tiles"]:
        for candidate in tile["candidates"]:
            result[(tile["tile_id"], candidate["candidate_id"])] = candidate
    return result


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[float, int, int, str]:
    kind_order = {"ply_source": 0, "drc_delivery": 1}
    qp = candidate.get("codec_params", {}).get("qp")
    return (
        float(candidate["pdl_ratio"]),
        kind_order.get(candidate.get("candidate_kind"), 99),
        -1 if qp is None else int(qp),
        str(candidate["candidate_id"]),
    )


def _candidate_asset_ref(candidate: dict[str, Any]) -> str:
    artifact_root = str(candidate.get("artifact_root", "")).strip("/")
    asset_ref = str(candidate["asset_ref"]).replace("\\", "/").strip("/")
    return f"{artifact_root}/{asset_ref}" if artifact_root else asset_ref


def _pdl_cap_for_observation(profile: dict[str, Any], observation: dict[str, Any]) -> float:
    view_context = observation["view_context"]
    distance_norm = float(observation["distance_norm"])
    matches = []
    for rule in profile["lookup"]["rules"]:
        match = rule["distance_match"]
        if (
            rule["view_context"] == view_context
            and "exact_distance" in match
            and math.isclose(float(match["exact_distance"]), distance_norm, abs_tol=1e-12)
        ):
            matches.append(rule)
    _expect_equal(len(matches), 1, f"{observation['context_id']} lookup rule match count")
    return float(matches[0]["pdl_max_dist"])


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _json_serializable(payload: dict[str, Any]) -> bool:
    try:
        json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return False
    return True


def _json_compatible(value: Any) -> Any:
    if isinstance(value, tuple | list):
        return [_json_compatible(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    return value


def _sorted_counter(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _pdl_key(value: Any) -> str:
    return f"{float(value):.1f}"


def _string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise BehaviorPilotError(f"{context} must be a non-empty string")
    return value


def _positive_number(value: Any, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value <= 0:
        raise BehaviorPilotError(f"{context} must be a positive finite number, got {value!r}")
    return float(value)


def _pdl_ratio(value: Any, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise BehaviorPilotError(f"{context} must be a finite PDL ratio, got {value!r}")
    numeric = float(value)
    if numeric <= 0 or numeric > 1:
        raise BehaviorPilotError(f"{context} must be in (0, 1], got {value!r}")
    return numeric


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise BehaviorPilotError(message)


def _expect_equal(actual: Any, expected: Any, context: str) -> None:
    if actual != expected:
        raise BehaviorPilotError(f"{context}: expected {expected!r}, got {actual!r}")
