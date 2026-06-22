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
from pcv_stage2.models import (
    FixedLambdaSelection,
    FixedLambdaTileSelection,
    LambdaSearchConfig,
)
from pcv_stage2.preprocess import (
    is_better_feasible_candidate,
    search_lambda_feasible_candidates,
)


FIXTURE = ROOT / "tests" / "fixtures" / "handcheck_3x3"


def search_config(
    *,
    lambda_initial_high: float = 0.1,
    lambda_max_bracket_steps: int = 2,
    score_epsilon: float = 1e-9,
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


def synthetic_candidate(
    *,
    total_bytes: float,
    total_net_utility: float,
    selected_levels: tuple[tuple[str, int], ...],
    total_decode_ms: float = 10.0,
    budget_total_bytes: float = 100.0,
) -> FixedLambdaSelection:
    per_tile_decode = total_decode_ms / len(selected_levels)
    return FixedLambdaSelection(
        lambda_value=0.0,
        tile_selections=tuple(
            FixedLambdaTileSelection(
                lambda_value=0.0,
                tile_id=tile_id,
                allowed_level_ids=(1, 2, 3),
                selected_level_id=level_id,
                selected_r_bytes=0.0,
                selected_d_ms=per_tile_decode,
                selected_net_utility=0.0,
                selected_penalized_score=0.0,
            )
            for tile_id, level_id in selected_levels
        ),
        total_bytes=total_bytes,
        total_net_utility=total_net_utility,
        total_penalized_score=total_net_utility,
        budget_total_bytes=budget_total_bytes,
        is_budget_feasible=total_bytes <= budget_total_bytes,
    )


def test_handcheck_bisection_search_keeps_budget_feasible_best_candidate() -> None:
    # Synthetic handcheck data, not real Longdress experiment output.
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")

    result = search_lambda_feasible_candidates(stage2_input, lookup, search_config())

    assert result.bracket_found is True
    assert result.feasible_at_zero is False
    assert result.bisection_performed is True
    assert result.termination_reason == "lambda_epsilon"
    assert [point.lambda_value for point in result.trace[:3]] == pytest.approx(
        [0.0, 0.1, 0.2]
    )
    assert result.trace[2].is_budget_feasible is True
    assert result.trace[2].total_bytes == pytest.approx(200)
    assert all(0.1 < point.lambda_value < 0.2 for point in result.trace[3:])
    assert result.best_feasible_candidate is not None
    assert result.best_feasible_trace_index is not None
    assert result.best_feasible_candidate.is_budget_feasible is True
    assert (
        result.best_feasible_candidate.total_bytes
        <= result.best_feasible_candidate.budget_total_bytes
    )
    assert result.lower_infeasible_lambda == pytest.approx(0.14375)
    assert result.upper_feasible_lambda == pytest.approx(0.15)

    sorted_trace = sorted(result.trace, key=lambda point: point.lambda_value)
    total_bytes = [point.total_bytes for point in sorted_trace]
    assert all(
        next_total <= current_total
        for current_total, next_total in zip(total_bytes, total_bytes[1:])
    )


def test_search_stops_when_zero_lambda_is_feasible() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    stage2_input = replace(stage2_input, budget_total_bytes=240.0)
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")

    result = search_lambda_feasible_candidates(stage2_input, lookup, search_config())

    assert result.bracket_found is True
    assert result.feasible_at_zero is True
    assert result.bisection_performed is False
    assert result.termination_reason == "feasible_at_zero"
    assert result.best_feasible_candidate is not None
    assert result.best_feasible_candidate.lambda_value == pytest.approx(0.0)
    assert result.best_feasible_trace_index == 0
    assert len(result.trace) == 1


def test_search_with_zero_iterations_keeps_bracket_upper_candidate() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    config = search_config(max_iterations=0)

    result = search_lambda_feasible_candidates(stage2_input, lookup, config)

    assert result.bracket_found is True
    assert result.feasible_at_zero is False
    assert result.bisection_performed is False
    assert result.termination_reason == "max_iterations"
    assert result.best_feasible_candidate is not None
    assert result.best_feasible_candidate.lambda_value == pytest.approx(0.2)
    assert result.best_feasible_candidate.total_bytes == pytest.approx(200)
    assert result.best_feasible_trace_index == 2
    assert [point.lambda_value for point in result.trace] == pytest.approx(
        [0.0, 0.1, 0.2]
    )


def test_search_can_stop_on_lambda_epsilon_before_midpoint_probe() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    config = search_config(lambda_epsilon=1.0)

    result = search_lambda_feasible_candidates(stage2_input, lookup, config)

    assert result.bracket_found is True
    assert result.bisection_performed is False
    assert result.termination_reason == "lambda_epsilon"
    assert result.best_feasible_candidate is not None
    assert result.best_feasible_candidate.total_bytes == pytest.approx(200)
    assert [point.lambda_value for point in result.trace] == pytest.approx(
        [0.0, 0.1, 0.2]
    )


def test_search_reports_bracket_failure_without_feasible_candidate() -> None:
    stage2_input = load_stage2_input(FIXTURE / "input_success.json")
    lookup = load_distance_lookup(FIXTURE / "distance_lookup.json")
    config = search_config(lambda_max_bracket_steps=1)

    result = search_lambda_feasible_candidates(stage2_input, lookup, config)

    assert result.bracket_found is False
    assert result.feasible_at_zero is False
    assert result.bisection_performed is False
    assert result.termination_reason == "bracket_failure"
    assert result.best_feasible_candidate is None
    assert result.best_feasible_trace_index is None
    assert [point.lambda_value for point in result.trace] == pytest.approx([0.0, 0.1])


def test_best_feasible_comparator_prefers_higher_net_utility() -> None:
    incumbent = synthetic_candidate(
        total_bytes=90,
        total_net_utility=10,
        selected_levels=(("A", 1),),
    )
    candidate = synthetic_candidate(
        total_bytes=80,
        total_net_utility=11,
        selected_levels=(("A", 1),),
    )

    assert is_better_feasible_candidate(
        candidate,
        incumbent,
        score_epsilon=1e-9,
    )


def test_best_feasible_comparator_prefers_budget_utilization_when_utility_ties() -> None:
    incumbent = synthetic_candidate(
        total_bytes=80,
        total_net_utility=10.0 + 5e-7,
        selected_levels=(("A", 1),),
    )
    candidate = synthetic_candidate(
        total_bytes=90,
        total_net_utility=10.0,
        selected_levels=(("A", 1),),
    )

    assert is_better_feasible_candidate(
        candidate,
        incumbent,
        score_epsilon=1e-6,
    )


def test_best_feasible_comparator_prefers_lower_decode_when_utility_and_bytes_tie() -> None:
    incumbent = synthetic_candidate(
        total_bytes=80,
        total_net_utility=10,
        total_decode_ms=5,
        selected_levels=(("A", 1),),
        budget_total_bytes=0,
    )
    candidate = synthetic_candidate(
        total_bytes=0,
        total_net_utility=10,
        total_decode_ms=4,
        selected_levels=(("A", 1),),
        budget_total_bytes=0,
    )
    incumbent = replace(incumbent, total_bytes=0, is_budget_feasible=True)

    assert is_better_feasible_candidate(
        candidate,
        incumbent,
        score_epsilon=1e-9,
    )


def test_best_feasible_comparator_uses_deterministic_level_order_last() -> None:
    incumbent = synthetic_candidate(
        total_bytes=80,
        total_net_utility=10,
        total_decode_ms=5,
        selected_levels=(("B", 1), ("A", 2)),
    )
    candidate = synthetic_candidate(
        total_bytes=80,
        total_net_utility=10,
        total_decode_ms=5,
        selected_levels=(("B", 2), ("A", 1)),
    )

    assert is_better_feasible_candidate(
        candidate,
        incumbent,
        score_epsilon=1e-9,
    )


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"lambda_epsilon": -1e-9}, "lambda_epsilon"),
        ({"lambda_epsilon": math.nan}, "lambda_epsilon"),
        ({"lambda_epsilon": math.inf}, "lambda_epsilon"),
        ({"lambda_epsilon": True}, "lambda_epsilon"),
        ({"max_iterations": -1}, "max_iterations"),
        ({"max_iterations": 1.5}, "max_iterations"),
        ({"max_iterations": True}, "max_iterations"),
    ],
)
def test_lambda_search_config_rejects_invalid_bisection_values(
    kwargs,
    expected: str,
) -> None:
    values = {
        "lambda_initial_high": 0.1,
        "lambda_max_bracket_steps": 2,
        "score_epsilon": 1e-9,
        "lambda_epsilon": 0.0,
        "max_iterations": 10,
    }
    values.update(kwargs)

    with pytest.raises(ValueError, match=expected):
        LambdaSearchConfig(**values)
