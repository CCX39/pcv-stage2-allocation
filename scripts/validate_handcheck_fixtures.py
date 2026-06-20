from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError, ValidationError
except ImportError as exc:  # pragma: no cover - exercised only when deps are missing
    print(
        "Missing dependency: jsonschema. Run `python -m pip install -r requirements.txt`.",
        file=sys.stderr,
    )
    raise SystemExit(2) from exc

from pcv_stage2.io import load_distance_lookup, load_stage2_input
from pcv_stage2.models import LookupResolution, Stage2Input
from pcv_stage2.preprocess import (
    compute_b_min_feasible,
    compute_net_utility,
    compute_spatial_utility,
    resolve_lookup_for_input,
)


SCHEMAS = ROOT / "schemas"
FIXTURE = ROOT / "tests" / "fixtures" / "handcheck_3x3"
EPSILON = 1e-9


class FixtureValidationError(Exception):
    """Raised when the handcheck fixture does not match its contract."""


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FixtureValidationError(
            f"{rel(path)} is not valid JSON: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise FixtureValidationError(f"Could not read {rel(path)}: {exc}") from exc


def fail(message: str) -> None:
    raise FixtureValidationError(message)


def expect_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        fail(f"{label}: expected {expected!r}, got {actual!r}")


def expect_close(actual: float, expected: float, label: str) -> None:
    if not math.isclose(actual, expected, rel_tol=EPSILON, abs_tol=EPSILON):
        fail(f"{label}: expected {expected!r}, got {actual!r}")


def format_json_path(error: ValidationError) -> str:
    if not error.path:
        return "$"
    return "$." + ".".join(str(part) for part in error.path)


def validate_instance(instance: Any, schema: dict[str, Any], instance_name: str) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.path))
    if errors:
        formatted = "\n".join(
            f"- {format_json_path(error)}: {error.message}" for error in errors
        )
        fail(f"{instance_name} failed schema validation:\n{formatted}")


def validate_schema(schema: dict[str, Any], path: Path) -> None:
    expect_equal(
        schema.get("$schema"),
        "https://json-schema.org/draft/2020-12/schema",
        f"{rel(path)} $schema",
    )
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise FixtureValidationError(
            f"{rel(path)} is not a valid Draft 2020-12 schema: {exc.message}"
        ) from exc


def resolution_to_dict(resolution: LookupResolution) -> dict[str, Any]:
    return {
        "tile_id": resolution.tile_id,
        "lookup_profile_id": resolution.lookup_profile_id,
        "matched_rule_id": resolution.matched_rule_id,
        "lookup_level": resolution.lookup_level,
        "allowed_levels": list(resolution.allowed_levels),
    }


def expect_lookup_resolution(
    expected_result: dict[str, Any], computed: tuple[LookupResolution, ...], label: str
) -> None:
    actual = sorted(expected_result["lookup_resolution"], key=lambda item: item["tile_id"])
    wanted = sorted(
        (resolution_to_dict(resolution) for resolution in computed),
        key=lambda item: item["tile_id"],
    )
    expect_equal(actual, wanted, f"{label} lookup_resolution")


def expect_success_result(
    stage2_input: Stage2Input,
    lookup_path: Path,
    expected_result: dict[str, Any],
) -> None:
    lookup = load_distance_lookup(lookup_path)
    expect_equal(expected_result["status"], "SUCCESS", "success status")
    expect_equal(stage2_input.budget_total_bytes, 210.0, "success input budget_total_bytes")
    expect_equal(expected_result["budget_total_bytes"], 210, "success result budget_total_bytes")

    computed_lookup = resolve_lookup_for_input(stage2_input, lookup)
    expect_lookup_resolution(expected_result, computed_lookup, "success")

    b_min = compute_b_min_feasible(stage2_input, lookup)
    expect_close(b_min, 120, "success computed B_min_feasible")
    expect_close(expected_result["b_min_feasible"], b_min, "success result b_min_feasible")
    expect_close(expected_result["budget_gap"], 0, "success budget_gap")

    expected_selection = {
        "T1_near_important": 3,
        "T2_mid_visible": 1,
        "T3_far_capped": 1,
    }
    actual_selection = {
        tile["tile_id"]: tile["selected_level_id"]
        for tile in expected_result["selected_tiles"]
    }
    expect_equal(actual_selection, expected_selection, "success selected levels")

    computed_allowed = {
        resolution.tile_id: list(resolution.allowed_levels)
        for resolution in computed_lookup
    }
    total_bytes = 0.0
    total_net = 0.0
    total_spatial = 0.0
    total_decode = 0.0

    for selected in expected_result["selected_tiles"]:
        tile = stage2_input.tile_by_id(selected["tile_id"])
        level_id = selected["selected_level_id"]
        if level_id not in computed_allowed[tile.tile_id]:
            fail(f"{tile.tile_id} selected level {level_id} is outside allowed_levels")

        level = tile.level_by_id(level_id)
        selected_spatial = compute_spatial_utility(tile, level)
        selected_net = compute_net_utility(tile, level, stage2_input.eta)

        expect_close(selected["r_bytes"], level.r_bytes, f"{tile.tile_id} r_bytes")
        expect_close(selected["d_ms"], level.d_ms, f"{tile.tile_id} d_ms")
        expect_close(
            selected["spatial_utility"], selected_spatial, f"{tile.tile_id} spatial_utility"
        )
        expect_close(selected["net_utility"], selected_net, f"{tile.tile_id} net_utility")
        expect_equal(
            selected["allowed_levels"],
            computed_allowed[tile.tile_id],
            f"{tile.tile_id} allowed_levels",
        )

        total_bytes += level.r_bytes
        total_net += selected_net
        total_spatial += selected_spatial
        total_decode += level.d_ms

    expect_close(total_bytes, 200, "success computed total_bytes")
    expect_close(total_net, 39.5, "success computed total_net_utility")
    expect_close(expected_result["total_bytes"], total_bytes, "success result total_bytes")
    expect_close(expected_result["total_net_utility"], total_net, "success result total_net_utility")
    expect_close(
        expected_result["total_spatial_utility"],
        total_spatial,
        "success result total_spatial_utility",
    )
    expect_close(expected_result["total_decode_ms"], total_decode, "success result total_decode_ms")
    expect_close(
        expected_result["budget_utilization"],
        total_bytes / stage2_input.budget_total_bytes,
        "success budget_utilization",
    )
    expect_equal(expected_result["lambda_search"]["enabled"], False, "success lambda_search.enabled")


def expect_infeasible_result(
    stage2_input: Stage2Input,
    lookup_path: Path,
    expected_result: dict[str, Any],
) -> None:
    lookup = load_distance_lookup(lookup_path)
    expect_equal(expected_result["status"], "INFEASIBLE_BUDGET", "infeasible status")
    expect_equal(stage2_input.budget_total_bytes, 100.0, "infeasible input budget_total_bytes")
    expect_equal(expected_result["budget_total_bytes"], 100, "infeasible result budget_total_bytes")
    expect_equal(expected_result["selected_tiles"], [], "infeasible selected_tiles")

    computed_lookup = resolve_lookup_for_input(stage2_input, lookup)
    expect_lookup_resolution(expected_result, computed_lookup, "infeasible")

    b_min = compute_b_min_feasible(stage2_input, lookup)
    gap = b_min - stage2_input.budget_total_bytes
    if gap <= 0:
        fail("infeasible input must have budget_total_bytes below computed B_min_feasible")

    expect_close(b_min, 120, "infeasible computed B_min_feasible")
    expect_close(gap, 20, "infeasible computed budget_gap")
    expect_close(expected_result["b_min_feasible"], b_min, "infeasible result b_min_feasible")
    expect_close(expected_result["budget_gap"], gap, "infeasible result budget_gap")
    expect_equal(expected_result["total_bytes"], None, "infeasible total_bytes")
    expect_equal(expected_result["total_net_utility"], None, "infeasible total_net_utility")
    expect_equal(expected_result["lambda_search"]["enabled"], False, "infeasible lambda_search.enabled")

    error_codes = {error["code"] for error in expected_result["errors"]}
    if "INFEASIBLE_BUDGET" not in error_codes:
        fail("infeasible result must include an INFEASIBLE_BUDGET error")


def main() -> int:
    schema_paths = {
        "stage2_input": SCHEMAS / "stage2_input.schema.json",
        "distance_lookup": SCHEMAS / "distance_lookup.schema.json",
        "stage2_result": SCHEMAS / "stage2_result.schema.json",
    }
    fixture_paths = {
        "input_success": FIXTURE / "input_success.json",
        "input_infeasible": FIXTURE / "input_infeasible.json",
        "distance_lookup": FIXTURE / "distance_lookup.json",
        "expected_success_result": FIXTURE / "expected_success_result.json",
        "expected_infeasible_result": FIXTURE / "expected_infeasible_result.json",
    }

    schemas = {name: load_json(path) for name, path in schema_paths.items()}
    fixtures = {name: load_json(path) for name, path in fixture_paths.items()}
    print("[OK] fixture JSON files are valid JSON")

    for name, schema in schemas.items():
        validate_schema(schema, schema_paths[name])
    print("[OK] schemas are valid Draft 2020-12 schemas")

    validate_instance(fixtures["input_success"], schemas["stage2_input"], "input_success.json")
    validate_instance(fixtures["input_infeasible"], schemas["stage2_input"], "input_infeasible.json")
    validate_instance(fixtures["distance_lookup"], schemas["distance_lookup"], "distance_lookup.json")
    validate_instance(
        fixtures["expected_success_result"],
        schemas["stage2_result"],
        "expected_success_result.json",
    )
    validate_instance(
        fixtures["expected_infeasible_result"],
        schemas["stage2_result"],
        "expected_infeasible_result.json",
    )
    print("[OK] fixture JSON files are schema-valid")

    success_input = load_stage2_input(fixture_paths["input_success"])
    infeasible_input = load_stage2_input(fixture_paths["input_infeasible"])
    lookup = load_distance_lookup(fixture_paths["distance_lookup"])
    success_lookup = resolve_lookup_for_input(success_input, lookup)
    infeasible_lookup = resolve_lookup_for_input(infeasible_input, lookup)
    expect_lookup_resolution(fixtures["expected_success_result"], success_lookup, "success")
    expect_lookup_resolution(fixtures["expected_infeasible_result"], infeasible_lookup, "infeasible")
    print("[OK] lookup cap resolution matches hand calculation")

    expect_success_result(
        success_input,
        fixture_paths["distance_lookup"],
        fixtures["expected_success_result"],
    )
    print("[OK] success expected result matches hand calculation")

    expect_infeasible_result(
        infeasible_input,
        fixture_paths["distance_lookup"],
        fixtures["expected_infeasible_result"],
    )
    print("[OK] infeasible expected result matches hand calculation")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FixtureValidationError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
