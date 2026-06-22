from __future__ import annotations

import math
import time

from .models import (
    DistanceLookup,
    FixedLambdaSelection,
    LambdaSearchConfig,
    LambdaSearchResult,
    LookupResolution,
    Stage2Input,
    Stage2Message,
    Stage2SelectedTile,
    Stage2SolveResult,
)
from .preprocess import (
    PreprocessError,
    compute_net_utility,
    compute_spatial_utility,
    resolve_lookup_for_input,
    search_lambda_feasible_candidates,
)


RESULT_SCHEMA_VERSION = "0.1.0"
SOLVER_ALGORITHM = "phase1e_lambda_search_no_local_upgrade"
FLOAT_EPSILON = 1e-9


class InternalSolverInvariantError(RuntimeError):
    """Raised when assembled solver output violates an internal invariant."""


def _lambda_config_to_dict(config: LambdaSearchConfig) -> dict[str, float | int]:
    return {
        "lambda_initial_high": config.lambda_initial_high,
        "lambda_max_bracket_steps": config.lambda_max_bracket_steps,
        "score_epsilon": config.score_epsilon,
        "lambda_epsilon": config.lambda_epsilon,
        "max_iterations": config.max_iterations,
    }


def _config_snapshot(
    stage2_input: Stage2Input,
    lookup: DistanceLookup,
    config: LambdaSearchConfig,
) -> dict[str, object]:
    return {
        "solver_version": RESULT_SCHEMA_VERSION,
        "algorithm": SOLVER_ALGORITHM,
        "eta": stage2_input.eta,
        "g_distance": 1.0,
        "lookup_profile_id": lookup.lookup_profile_id,
        "lookup_semantics": lookup.semantics,
        "lambda_search_config": _lambda_config_to_dict(config),
    }


def _disabled_lambda_search() -> dict[str, object]:
    return {
        "enabled": False,
        "lambda_initial_high": None,
        "lambda_max_bracket_steps": None,
        "score_epsilon": None,
        "lambda_epsilon": None,
        "max_iterations": None,
        "iterations": [],
        "best_feasible_iteration": None,
    }


def _enabled_lambda_search(
    search_result: LambdaSearchResult,
    config: LambdaSearchConfig,
) -> dict[str, object]:
    return {
        "enabled": True,
        "lambda_initial_high": config.lambda_initial_high,
        "lambda_max_bracket_steps": config.lambda_max_bracket_steps,
        "score_epsilon": config.score_epsilon,
        "lambda_epsilon": config.lambda_epsilon,
        "max_iterations": config.max_iterations,
        "iterations": [
            {
                "iteration": point.step_index,
                "lambda": point.lambda_value,
                "total_bytes": point.total_bytes,
                "total_net_utility": point.total_net_utility,
                "total_decode_ms": point.total_decode_ms,
                "selected_levels": [
                    {
                        "tile_id": selected.tile_id,
                        "selected_level_id": selected.selected_level_id,
                    }
                    for selected in point.selected_levels
                ],
                "is_budget_feasible": point.is_budget_feasible,
            }
            for point in search_result.trace
        ],
        "best_feasible_iteration": search_result.best_feasible_trace_index,
    }


def _b_min_from_resolutions(
    stage2_input: Stage2Input,
    resolutions: tuple[LookupResolution, ...],
) -> float:
    total = 0.0
    for tile, resolution in zip(stage2_input.tiles, resolutions, strict=True):
        total += min(
            tile.level_by_id(level_id).r_bytes
            for level_id in resolution.allowed_levels
        )
    return total


def _finish(
    *,
    start_time: float,
    stage2_input: Stage2Input,
    lookup: DistanceLookup,
    config: LambdaSearchConfig,
    status: str,
    b_min_feasible: float | None,
    budget_gap: float | None,
    total_bytes: float | None,
    total_net_utility: float | None,
    total_spatial_utility: float | None,
    total_decode_ms: float | None,
    budget_utilization: float | None,
    selected_tiles: tuple[Stage2SelectedTile, ...] = (),
    lookup_resolution: tuple[LookupResolution, ...] = (),
    lambda_search: dict[str, object] | None = None,
    warnings: tuple[Stage2Message, ...] = (),
    errors: tuple[Stage2Message, ...] = (),
) -> Stage2SolveResult:
    runtime_ms = max(0.0, (time.perf_counter() - start_time) * 1000.0)
    return Stage2SolveResult(
        schema_version=RESULT_SCHEMA_VERSION,
        scenario_id=stage2_input.scenario_id,
        status=status,
        budget_total_bytes=stage2_input.budget_total_bytes,
        b_min_feasible=b_min_feasible,
        budget_gap=budget_gap,
        total_bytes=total_bytes,
        total_net_utility=total_net_utility,
        total_spatial_utility=total_spatial_utility,
        total_decode_ms=total_decode_ms,
        budget_utilization=budget_utilization,
        selected_tiles=selected_tiles,
        lookup_resolution=lookup_resolution,
        lambda_search=lambda_search or _disabled_lambda_search(),
        runtime_ms=runtime_ms,
        config_snapshot=_config_snapshot(stage2_input, lookup, config),
        warnings=warnings,
        errors=errors,
    )


def _preprocess_error_status(error: PreprocessError) -> str:
    if error.code in {"INVALID_LOOKUP", "NO_ALLOWED_LEVEL", "INVALID_INPUT"}:
        return error.code
    return "INTERNAL_CONSTRAINT_VIOLATION"


def _preprocess_error_message(error: PreprocessError) -> Stage2Message:
    return Stage2Message(
        code=error.code,
        message=str(error),
        details=error.details,
    )


def _budget_utilization(total_bytes: float, budget_total_bytes: float) -> float:
    if budget_total_bytes <= 0:
        return 0.0
    return total_bytes / budget_total_bytes


def _check_close(name: str, left: float, right: float) -> None:
    if not math.isclose(left, right, rel_tol=FLOAT_EPSILON, abs_tol=FLOAT_EPSILON):
        raise InternalSolverInvariantError(
            f"{name} mismatch while assembling Stage2 result: {left!r} != {right!r}"
        )


def _assemble_success_selection(
    stage2_input: Stage2Input,
    candidate: FixedLambdaSelection,
    resolutions: tuple[LookupResolution, ...],
) -> tuple[tuple[Stage2SelectedTile, ...], float, float, float, float]:
    if not candidate.is_budget_feasible:
        raise InternalSolverInvariantError("best feasible candidate is over budget")

    if len(candidate.tile_selections) != len(stage2_input.tiles):
        raise InternalSolverInvariantError("candidate does not select one level per tile")

    selections_by_tile = {
        selection.tile_id: selection for selection in candidate.tile_selections
    }
    if len(selections_by_tile) != len(stage2_input.tiles):
        raise InternalSolverInvariantError("candidate has duplicate or missing tile ids")

    resolutions_by_tile = {resolution.tile_id: resolution for resolution in resolutions}
    selected_tiles: list[Stage2SelectedTile] = []
    total_bytes = 0.0
    total_net_utility = 0.0
    total_spatial_utility = 0.0
    total_decode_ms = 0.0

    for tile in stage2_input.tiles:
        selection = selections_by_tile.get(tile.tile_id)
        resolution = resolutions_by_tile.get(tile.tile_id)
        if selection is None or resolution is None:
            raise InternalSolverInvariantError(
                f"candidate is missing selection or lookup resolution for {tile.tile_id}"
            )
        if selection.selected_level_id not in resolution.allowed_levels:
            raise InternalSolverInvariantError(
                f"{tile.tile_id} selected level is outside allowed levels"
            )

        level = tile.level_by_id(selection.selected_level_id)
        spatial_utility = compute_spatial_utility(tile, level)
        net_utility = compute_net_utility(tile, level, stage2_input.eta)

        _check_close(f"{tile.tile_id} r_bytes", selection.selected_r_bytes, level.r_bytes)
        _check_close(f"{tile.tile_id} d_ms", selection.selected_d_ms, level.d_ms)
        _check_close(
            f"{tile.tile_id} net_utility",
            selection.selected_net_utility,
            net_utility,
        )

        selected_tiles.append(
            Stage2SelectedTile(
                tile_id=tile.tile_id,
                selected_level_id=level.level_id,
                r_bytes=level.r_bytes,
                d_ms=level.d_ms,
                net_utility=net_utility,
                spatial_utility=spatial_utility,
                allowed_levels=resolution.allowed_levels,
            )
        )
        total_bytes += level.r_bytes
        total_net_utility += net_utility
        total_spatial_utility += spatial_utility
        total_decode_ms += level.d_ms

    _check_close("candidate total_bytes", candidate.total_bytes, total_bytes)
    _check_close("candidate total_net_utility", candidate.total_net_utility, total_net_utility)
    if total_bytes > stage2_input.budget_total_bytes + FLOAT_EPSILON:
        raise InternalSolverInvariantError("assembled selected tiles exceed budget")

    return (
        tuple(selected_tiles),
        total_bytes,
        total_net_utility,
        total_spatial_utility,
        total_decode_ms,
    )


def solve_stage2(
    stage2_input: Stage2Input,
    lookup: DistanceLookup,
    config: LambdaSearchConfig,
) -> Stage2SolveResult:
    start_time = time.perf_counter()

    try:
        resolutions = resolve_lookup_for_input(stage2_input, lookup)
        b_min_feasible = _b_min_from_resolutions(stage2_input, resolutions)
    except PreprocessError as error:
        return _finish(
            start_time=start_time,
            stage2_input=stage2_input,
            lookup=lookup,
            config=config,
            status=_preprocess_error_status(error),
            b_min_feasible=None,
            budget_gap=None,
            total_bytes=None,
            total_net_utility=None,
            total_spatial_utility=None,
            total_decode_ms=None,
            budget_utilization=None,
            errors=(_preprocess_error_message(error),),
        )

    if stage2_input.budget_total_bytes < b_min_feasible:
        return _finish(
            start_time=start_time,
            stage2_input=stage2_input,
            lookup=lookup,
            config=config,
            status="INFEASIBLE_BUDGET",
            b_min_feasible=b_min_feasible,
            budget_gap=b_min_feasible - stage2_input.budget_total_bytes,
            total_bytes=None,
            total_net_utility=None,
            total_spatial_utility=None,
            total_decode_ms=None,
            budget_utilization=None,
            lookup_resolution=resolutions,
            lambda_search=_disabled_lambda_search(),
        )

    try:
        search_result = search_lambda_feasible_candidates(stage2_input, lookup, config)
    except PreprocessError as error:
        return _finish(
            start_time=start_time,
            stage2_input=stage2_input,
            lookup=lookup,
            config=config,
            status=_preprocess_error_status(error),
            b_min_feasible=b_min_feasible,
            budget_gap=0.0,
            total_bytes=None,
            total_net_utility=None,
            total_spatial_utility=None,
            total_decode_ms=None,
            budget_utilization=None,
            lookup_resolution=resolutions,
            errors=(_preprocess_error_message(error),),
        )

    lambda_search = _enabled_lambda_search(search_result, config)
    if search_result.best_feasible_candidate is None:
        return _finish(
            start_time=start_time,
            stage2_input=stage2_input,
            lookup=lookup,
            config=config,
            status="NUMERICAL_ERROR",
            b_min_feasible=b_min_feasible,
            budget_gap=0.0,
            total_bytes=None,
            total_net_utility=None,
            total_spatial_utility=None,
            total_decode_ms=None,
            budget_utilization=None,
            lookup_resolution=resolutions,
            lambda_search=lambda_search,
            errors=(
                Stage2Message(
                    code="LAMBDA_SEARCH_NO_FEASIBLE_CANDIDATE",
                    message=(
                        "B_min_feasible <= budget_total_bytes holds under the current "
                        "hard constraints, but the current lambda search configuration "
                        "did not recover a budget-feasible candidate."
                    ),
                    details={"termination_reason": search_result.termination_reason},
                ),
            ),
        )

    try:
        (
            selected_tiles,
            total_bytes,
            total_net_utility,
            total_spatial_utility,
            total_decode_ms,
        ) = _assemble_success_selection(
            stage2_input,
            search_result.best_feasible_candidate,
            resolutions,
        )
    except InternalSolverInvariantError as error:
        return _finish(
            start_time=start_time,
            stage2_input=stage2_input,
            lookup=lookup,
            config=config,
            status="INTERNAL_CONSTRAINT_VIOLATION",
            b_min_feasible=b_min_feasible,
            budget_gap=0.0,
            total_bytes=None,
            total_net_utility=None,
            total_spatial_utility=None,
            total_decode_ms=None,
            budget_utilization=None,
            lookup_resolution=resolutions,
            lambda_search=lambda_search,
            errors=(
                Stage2Message(
                    code="RESULT_INVARIANT_VIOLATION",
                    message=str(error),
                ),
            ),
        )

    return _finish(
        start_time=start_time,
        stage2_input=stage2_input,
        lookup=lookup,
        config=config,
        status="SUCCESS",
        b_min_feasible=b_min_feasible,
        budget_gap=0.0,
        total_bytes=total_bytes,
        total_net_utility=total_net_utility,
        total_spatial_utility=total_spatial_utility,
        total_decode_ms=total_decode_ms,
        budget_utilization=_budget_utilization(total_bytes, stage2_input.budget_total_bytes),
        selected_tiles=selected_tiles,
        lookup_resolution=resolutions,
        lambda_search=lambda_search,
    )
