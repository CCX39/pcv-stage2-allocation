from __future__ import annotations

from dataclasses import replace
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pcv_stage2.io import load_distance_lookup, load_stage2_input
from pcv_stage2.models import LambdaSearchConfig
from pcv_stage2.preprocess import (
    PreprocessError,
    bracket_lambda_for_feasible_candidate,
)


FIXTURE = ROOT / "tests" / "fixtures" / "handcheck_3x3"


def search_config(
    *,
    lambda_initial_high: float = 0.1,
    lambda_max_bracket_steps: int = 2,
    score_epsilon: float = 1e-9,
    lambda_epsilon: float = 0.0,
    max_iterations: int = 0,
) -> LambdaSearchConfig:
    return LambdaSearchConfig(
        lambda_initial_high=lambda_initial_high,
        lambda_max_bracket_steps=lambda_max_bracket_steps,
        score_epsilon=score_epsilon,
        lambda_epsilon=lambda_epsilon,
        max_iterations=max_iterations,
    )


def selected_candidate_pairs(trace_point):
    return [
        (item.tile_id, item.selected_candidate_id)
        for item in trace_point.selected_candidates
    ]


def test_handcheck_bracket_finds_first_feasible_positive_lambda() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    config = search_config()

    result = bracket_lambda_for_feasible_candidate(stage2_input, lookup, config)

    assert result.bracket_found is True
    assert result.feasible_at_zero is False
    assert result.lower_infeasible_lambda == pytest.approx(0.1)
    assert result.upper_feasible_lambda == pytest.approx(0.2)
    assert result.feasible_candidate is not None
    assert result.feasible_candidate.total_bytes == pytest.approx(200)
    assert result.feasible_candidate.total_net_utility == pytest.approx(39.5)

    assert [point.lambda_value for point in result.trace] == pytest.approx(
        [0.0, 0.1, 0.2]
    )
    assert [point.total_bytes for point in result.trace] == pytest.approx(
        [240, 240, 200]
    )
    assert [point.total_net_utility for point in result.trace] == pytest.approx(
        [45.4, 45.4, 39.5]
    )
    assert [point.total_decode_ms for point in result.trace] == pytest.approx(
        [6, 6, 5]
    )
    assert [point.is_budget_feasible for point in result.trace] == [
        False,
        False,
        True,
    ]
    assert selected_candidate_pairs(result.trace[0]) == [
        ("T1_near_important", "pdl_1_0"),
        ("T2_mid_visible", "pdl_0_6"),
        ("T3_far_capped", "pdl_0_2"),
    ]
    assert selected_candidate_pairs(result.trace[2]) == [
        ("T1_near_important", "pdl_1_0"),
        ("T2_mid_visible", "pdl_0_2"),
        ("T3_far_capped", "pdl_0_2"),
    ]


def test_handcheck_bracket_stops_when_zero_lambda_is_feasible() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    stage2_input = replace(stage2_input, budget_total_bytes=240.0)
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    config = search_config()

    result = bracket_lambda_for_feasible_candidate(stage2_input, lookup, config)

    assert result.bracket_found is True
    assert result.feasible_at_zero is True
    assert result.lower_infeasible_lambda is None
    assert result.upper_feasible_lambda == pytest.approx(0.0)
    assert result.feasible_candidate is not None
    assert result.feasible_candidate.lambda_value == pytest.approx(0.0)
    assert len(result.trace) == 1
    assert result.trace[0].total_bytes == pytest.approx(240)
    assert result.trace[0].is_budget_feasible is True


def test_handcheck_bracket_failure_does_not_fabricate_feasible_candidate() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    config = search_config(lambda_max_bracket_steps=1)

    result = bracket_lambda_for_feasible_candidate(stage2_input, lookup, config)

    assert result.bracket_found is False
    assert result.feasible_at_zero is False
    assert result.lower_infeasible_lambda == pytest.approx(0.1)
    assert result.upper_feasible_lambda is None
    assert result.feasible_candidate is None
    assert [point.lambda_value for point in result.trace] == pytest.approx([0.0, 0.1])
    assert [point.total_bytes for point in result.trace] == pytest.approx([240, 240])


def test_infeasible_budget_input_is_rejected_before_bracketing() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_infeasible.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    config = search_config()

    with pytest.raises(
        PreprocessError,
        match="lambda bracketing requires a budget-feasible input",
    ):
        bracket_lambda_for_feasible_candidate(stage2_input, lookup, config)


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        (
            {
                "lambda_initial_high": 0.0,
                "lambda_max_bracket_steps": 2,
                "score_epsilon": 1e-9,
                "lambda_epsilon": 0.0,
                "max_iterations": 0,
            },
            "lambda_initial_high",
        ),
        (
            {
                "lambda_initial_high": math.nan,
                "lambda_max_bracket_steps": 2,
                "score_epsilon": 1e-9,
                "lambda_epsilon": 0.0,
                "max_iterations": 0,
            },
            "lambda_initial_high",
        ),
        (
            {
                "lambda_initial_high": math.inf,
                "lambda_max_bracket_steps": 2,
                "score_epsilon": 1e-9,
                "lambda_epsilon": 0.0,
                "max_iterations": 0,
            },
            "lambda_initial_high",
        ),
        (
            {
                "lambda_initial_high": True,
                "lambda_max_bracket_steps": 2,
                "score_epsilon": 1e-9,
                "lambda_epsilon": 0.0,
                "max_iterations": 0,
            },
            "lambda_initial_high",
        ),
        (
            {
                "lambda_initial_high": 0.1,
                "lambda_max_bracket_steps": -1,
                "score_epsilon": 1e-9,
                "lambda_epsilon": 0.0,
                "max_iterations": 0,
            },
            "lambda_max_bracket_steps",
        ),
        (
            {
                "lambda_initial_high": 0.1,
                "lambda_max_bracket_steps": 1.5,
                "score_epsilon": 1e-9,
                "lambda_epsilon": 0.0,
                "max_iterations": 0,
            },
            "lambda_max_bracket_steps",
        ),
        (
            {
                "lambda_initial_high": 0.1,
                "lambda_max_bracket_steps": True,
                "score_epsilon": 1e-9,
                "lambda_epsilon": 0.0,
                "max_iterations": 0,
            },
            "lambda_max_bracket_steps",
        ),
        (
            {
                "lambda_initial_high": 0.1,
                "lambda_max_bracket_steps": 2,
                "score_epsilon": -1e-9,
                "lambda_epsilon": 0.0,
                "max_iterations": 0,
            },
            "score_epsilon",
        ),
        (
            {
                "lambda_initial_high": 0.1,
                "lambda_max_bracket_steps": 2,
                "score_epsilon": math.nan,
                "lambda_epsilon": 0.0,
                "max_iterations": 0,
            },
            "score_epsilon",
        ),
        (
            {
                "lambda_initial_high": 0.1,
                "lambda_max_bracket_steps": 2,
                "score_epsilon": math.inf,
                "lambda_epsilon": 0.0,
                "max_iterations": 0,
            },
            "score_epsilon",
        ),
        (
            {
                "lambda_initial_high": 0.1,
                "lambda_max_bracket_steps": 2,
                "score_epsilon": True,
                "lambda_epsilon": 0.0,
                "max_iterations": 0,
            },
            "score_epsilon",
        ),
    ],
)
def test_lambda_search_config_rejects_invalid_bracket_values(kwargs, expected: str) -> None:
    with pytest.raises(ValueError, match=expected):
        LambdaSearchConfig(**kwargs)


def test_handcheck_trace_total_bytes_do_not_increase_with_lambda() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    config = search_config()

    result = bracket_lambda_for_feasible_candidate(stage2_input, lookup, config)
    total_bytes = [point.total_bytes for point in result.trace]

    assert all(
        next_total <= current_total
        for current_total, next_total in zip(total_bytes, total_bytes[1:])
    )
