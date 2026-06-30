from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pcv_stage2.io import (
    load_distance_lookup,
    load_json,
    load_stage2_input,
    stage2_input_from_dict,
)
from pcv_stage2.models import LambdaSearchConfig
from pcv_stage2.solver import solve_stage2


FIXTURE = ROOT / "tests" / "fixtures" / "handcheck_3x3"
INPUT_SCHEMA = ROOT / "schemas" / "stage2_input.schema.json"
LOOKUP_SCHEMA = ROOT / "schemas" / "distance_lookup.schema.json"
RESULT_SCHEMA = ROOT / "schemas" / "stage2_result.schema.json"


def validator(schema_path: Path) -> Draft202012Validator:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def assert_schema_valid(payload: dict, schema_path: Path) -> None:
    validator(schema_path).validate(payload)


def assert_schema_invalid(payload: dict, schema_path: Path) -> None:
    errors = list(validator(schema_path).iter_errors(payload))
    assert errors


def test_generic_candidate_input_and_lookup_are_schema_valid() -> None:
    assert_schema_valid(load_json(FIXTURE / "input_success.json"), INPUT_SCHEMA)
    assert_schema_valid(load_json(FIXTURE / "input_infeasible.json"), INPUT_SCHEMA)
    assert_schema_valid(load_json(FIXTURE / "distance_lookup.json"), LOOKUP_SCHEMA)


def test_duplicate_candidate_id_is_rejected_by_schema_or_model_guardrail() -> None:
    payload = load_json(FIXTURE / "input_success.json")
    duplicated_exact = copy.deepcopy(payload)
    duplicated_exact["tiles"][0]["candidates"].append(
        copy.deepcopy(duplicated_exact["tiles"][0]["candidates"][0])
    )
    assert_schema_invalid(duplicated_exact, INPUT_SCHEMA)

    duplicated_by_id = copy.deepcopy(payload)
    duplicated_by_id["tiles"][0]["candidates"][1]["candidate_id"] = duplicated_by_id[
        "tiles"
    ][0]["candidates"][0]["candidate_id"]
    with pytest.raises(ValueError, match="duplicate candidate_id"):
        stage2_input_from_dict(duplicated_by_id)


def test_missing_pdl_ratio_is_rejected_when_pdl_lookup_is_enabled() -> None:
    payload = load_json(FIXTURE / "input_success.json")
    payload["tiles"][0]["candidates"][0].pop("pdl_ratio")
    assert_schema_valid(payload, INPUT_SCHEMA)

    stage2_input = stage2_input_from_dict(payload)
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    result = solve_stage2(
        stage2_input,
        lookup,
        LambdaSearchConfig(
            lambda_initial_high=0.1,
            lambda_max_bracket_steps=2,
            score_epsilon=1e-9,
            lambda_epsilon=0.0125,
            max_iterations=10,
        ),
    )

    assert result.status == "INVALID_INPUT"
    assert result.errors[0].code == "INVALID_INPUT"
    assert "missing pdl_ratio" in result.errors[0].message


def test_invalid_provenance_is_rejected_by_schema() -> None:
    payload = load_json(FIXTURE / "input_success.json")
    payload["tiles"][0]["candidates"][0]["provenance"]["r_bytes"] = "estimated"

    assert_schema_invalid(payload, INPUT_SCHEMA)


@pytest.mark.parametrize("field_name", ["r_bytes", "d_ms", "q_base"])
def test_missing_candidate_numeric_fields_are_rejected_by_schema(field_name: str) -> None:
    payload = load_json(FIXTURE / "input_success.json")
    payload["tiles"][0]["candidates"][0].pop(field_name)

    assert_schema_invalid(payload, INPUT_SCHEMA)


@pytest.mark.parametrize("field_name", ["r_bytes", "d_ms", "q_base"])
def test_invalid_candidate_numeric_fields_are_rejected_by_schema(field_name: str) -> None:
    payload = load_json(FIXTURE / "input_success.json")
    payload["tiles"][0]["candidates"][0][field_name] = -1

    assert_schema_invalid(payload, INPUT_SCHEMA)


def test_old_level_based_input_and_lookup_are_not_new_schema_valid() -> None:
    old_input = {
        "schema_version": "0.1.0",
        "scenario_id": "old",
        "budget_total_bytes": 1,
        "eta": 0,
        "lookup_profile_id": "old_lookup",
        "tiles": [
            {
                "tile_id": "A",
                "p_sal": 1,
                "visibility": 1,
                "screen_area": 1,
                "distance_norm": 1,
                "view_context": "full_body",
                "levels": [
                    {
                        "level_id": 1,
                        "pdl_ratio": 0.2,
                        "q_base": 1,
                        "r_bytes": 1,
                        "d_ms": 1
                    }
                ]
            }
        ],
        "provenance_summary": {}
    }
    old_lookup = {
        "schema_version": "0.1.0",
        "lookup_profile_id": "old_lookup",
        "semantics": "cap",
        "distance_unit": "normalized_render_distance",
        "quality_levels": [
            {
                "level_id": 1,
                "pdl_ratio": 0.2,
                "quality_label": "L1"
            }
        ],
        "source": {},
        "rules": [
            {
                "rule_id": "old_rule",
                "view_context": "full_body",
                "target_id": None,
                "distance_match": {
                    "exact_distance": 1
                },
                "lookup_level": 1,
                "threshold_profile": "old"
            }
        ]
    }

    assert_schema_invalid(old_input, INPUT_SCHEMA)
    assert_schema_invalid(old_lookup, LOOKUP_SCHEMA)


def test_result_selected_candidate_snapshot_and_provenance_are_schema_valid() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    result = solve_stage2(
        stage2_input,
        lookup,
        LambdaSearchConfig(
            lambda_initial_high=0.1,
            lambda_max_bracket_steps=2,
            score_epsilon=1e-9,
            lambda_epsilon=0.0125,
            max_iterations=10,
        ),
    )
    payload = result.to_dict()

    json.dumps(payload)
    assert_schema_valid(payload, RESULT_SCHEMA)
    for selected in payload["selected_tiles"]:
        snapshot = selected["selected_candidate_snapshot"]
        assert snapshot["candidate_id"] == selected["selected_candidate_id"]
        assert set(snapshot["provenance"]) >= {
            "r_bytes",
            "d_ms",
            "q_base",
            "pdl_ratio",
            "asset_ref",
        }
