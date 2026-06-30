from __future__ import annotations

import math
import time
from dataclasses import dataclass

from .models import (
    DistanceLookup,
    FixedLambdaSelection,
    LambdaSearchConfig,
    LambdaSearchResult,
    LookupResolution,
    Stage2Input,
    Stage2LocalUpgradeAudit,
    Stage2LocalUpgradeStep,
    Stage2Message,
    Stage2SelectedTile,
    Stage2SolveResult,
    TransmissionCandidate,
)
from .preprocess import (
    PreprocessError,
    compute_net_utility,
    compute_spatial_utility,
    resolve_lookup_for_input,
    search_lambda_feasible_candidates,
)


RESULT_SCHEMA_VERSION = "0.2.0"
SOLVER_ALGORITHM = "phase2b1_generic_candidate_lambda_search_with_local_switch"
FLOAT_EPSILON = 1e-9


class InternalSolverInvariantError(RuntimeError):
    """Raised when assembled solver output violates an internal invariant."""


@dataclass(frozen=True)
class _SwitchCandidate:
    tile_id: str
    from_candidate_id: str
    to_candidate_id: str
    delta_r_bytes: float
    delta_net_utility: float
    gain_per_byte: float


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
        "lookup_projection": "candidate.pdl_ratio <= pdl_max_dist",
        "lambda_search_config": _lambda_config_to_dict(config),
        "local_repair": {
            "enabled_on_success": True,
            "rule": (
                "greedy_positive_delta_net_utility_per_delta_byte_candidate_switch"
            ),
        },
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


def _disabled_local_upgrade() -> Stage2LocalUpgradeAudit:
    return Stage2LocalUpgradeAudit(
        enabled=False,
        seed_best_feasible_trace_index=None,
        initial_total_bytes=None,
        initial_total_net_utility=None,
        initial_total_decode_ms=None,
        steps=(),
        termination_reason="NOT_RUN",
    )


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
                "selected_candidates": [
                    {
                        "tile_id": selected.tile_id,
                        "selected_candidate_id": selected.selected_candidate_id,
                    }
                    for selected in point.selected_candidates
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
            tile.candidate_by_id(candidate_id).r_bytes
            for candidate_id in resolution.allowed_candidate_ids
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
    local_upgrade: Stage2LocalUpgradeAudit | None = None,
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
        local_upgrade=local_upgrade or _disabled_local_upgrade(),
        runtime_ms=runtime_ms,
        config_snapshot=_config_snapshot(stage2_input, lookup, config),
        warnings=warnings,
        errors=errors,
    )


def _preprocess_error_status(error: PreprocessError) -> str:
    if error.code in {"INVALID_LOOKUP", "NO_ALLOWED_CANDIDATE", "INVALID_INPUT"}:
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
    candidate: FixedLambdaSelection | None,
    resolutions: tuple[LookupResolution, ...],
) -> tuple[tuple[Stage2SelectedTile, ...], float, float, float, float]:
    if candidate is None:
        raise InternalSolverInvariantError("missing success candidate")

    selections_by_tile = {
        selection.tile_id: selection.selected_candidate_id
        for selection in candidate.tile_selections
    }
    return _assemble_selection_from_candidate_ids(
        stage2_input,
        selections_by_tile,
        resolutions,
    )


def _assemble_selection_from_candidate_ids(
    stage2_input: Stage2Input,
    selected_candidate_ids: dict[str, str],
    resolutions: tuple[LookupResolution, ...],
) -> tuple[tuple[Stage2SelectedTile, ...], float, float, float, float]:
    if len(selected_candidate_ids) != len(stage2_input.tiles):
        raise InternalSolverInvariantError("candidate does not select one option per tile")

    resolutions_by_tile = {resolution.tile_id: resolution for resolution in resolutions}
    selected_tiles: list[Stage2SelectedTile] = []
    total_bytes = 0.0
    total_net_utility = 0.0
    total_spatial_utility = 0.0
    total_decode_ms = 0.0

    for tile in stage2_input.tiles:
        selected_candidate_id = selected_candidate_ids.get(tile.tile_id)
        resolution = resolutions_by_tile.get(tile.tile_id)
        if selected_candidate_id is None or resolution is None:
            raise InternalSolverInvariantError(
                f"candidate is missing selection or lookup resolution for {tile.tile_id}"
            )
        if selected_candidate_id not in resolution.allowed_candidate_ids:
            raise InternalSolverInvariantError(
                f"{tile.tile_id} selected candidate is outside allowed candidates"
            )

        candidate = tile.candidate_by_id(selected_candidate_id)
        spatial_utility = compute_spatial_utility(tile, candidate)
        net_utility = compute_net_utility(tile, candidate, stage2_input.eta)

        selected_tiles.append(
            Stage2SelectedTile(
                tile_id=tile.tile_id,
                selected_candidate_id=candidate.candidate_id,
                selected_candidate_snapshot=candidate.to_snapshot(),
                r_bytes=candidate.r_bytes,
                d_ms=candidate.d_ms,
                net_utility=net_utility,
                spatial_utility=spatial_utility,
                allowed_candidate_ids=resolution.allowed_candidate_ids,
                rejected_candidate_ids=resolution.rejected_candidate_ids,
                lookup_pdl_max_dist=resolution.pdl_max_dist,
            )
        )
        total_bytes += candidate.r_bytes
        total_net_utility += net_utility
        total_spatial_utility += spatial_utility
        total_decode_ms += candidate.d_ms

    return (
        tuple(selected_tiles),
        total_bytes,
        total_net_utility,
        total_spatial_utility,
        total_decode_ms,
    )


def _check_candidate_matches_assembled(
    candidate: FixedLambdaSelection,
    total_bytes: float,
    total_net_utility: float,
    total_decode_ms: float,
) -> None:
    if not candidate.is_budget_feasible:
        raise InternalSolverInvariantError("best feasible candidate is over budget")
    _check_close("candidate total_bytes", candidate.total_bytes, total_bytes)
    _check_close("candidate total_net_utility", candidate.total_net_utility, total_net_utility)
    _check_close(
        "candidate total_decode_ms",
        sum(selection.selected_d_ms for selection in candidate.tile_selections),
        total_decode_ms,
    )


def _candidate_net_utility(
    stage2_input: Stage2Input,
    tile_id: str,
    candidate: TransmissionCandidate,
) -> float:
    return compute_net_utility(
        stage2_input.tile_by_id(tile_id),
        candidate,
        stage2_input.eta,
    )


def _candidate_switch_for_tile(
    stage2_input: Stage2Input,
    tile_id: str,
    current_candidate_id: str,
    target_candidate_id: str,
) -> _SwitchCandidate:
    tile = stage2_input.tile_by_id(tile_id)
    current_candidate = tile.candidate_by_id(current_candidate_id)
    target_candidate = tile.candidate_by_id(target_candidate_id)
    delta_r_bytes = target_candidate.r_bytes - current_candidate.r_bytes
    delta_net_utility = _candidate_net_utility(
        stage2_input,
        tile_id,
        target_candidate,
    ) - _candidate_net_utility(stage2_input, tile_id, current_candidate)
    return _SwitchCandidate(
        tile_id=tile_id,
        from_candidate_id=current_candidate_id,
        to_candidate_id=target_candidate_id,
        delta_r_bytes=delta_r_bytes,
        delta_net_utility=delta_net_utility,
        gain_per_byte=delta_net_utility / delta_r_bytes
        if delta_r_bytes > 0
        else 0.0,
    )


def _find_switch_candidates(
    stage2_input: Stage2Input,
    resolutions: tuple[LookupResolution, ...],
    current_candidate_ids: dict[str, str],
    residual_budget: float,
) -> list[_SwitchCandidate]:
    candidates: list[_SwitchCandidate] = []
    for resolution in resolutions:
        current_candidate_id = current_candidate_ids[resolution.tile_id]
        for target_candidate_id in resolution.allowed_candidate_ids:
            if target_candidate_id == current_candidate_id:
                continue
            candidate = _candidate_switch_for_tile(
                stage2_input,
                resolution.tile_id,
                current_candidate_id,
                target_candidate_id,
            )
            if (
                candidate.delta_r_bytes > FLOAT_EPSILON
                and candidate.delta_r_bytes <= residual_budget + FLOAT_EPSILON
                and candidate.delta_net_utility > FLOAT_EPSILON
            ):
                candidates.append(candidate)
    candidates.sort(
        key=lambda item: (
            -item.gain_per_byte,
            -item.delta_net_utility,
            item.delta_r_bytes,
            item.tile_id,
            item.to_candidate_id,
        )
    )
    return candidates


def _apply_local_upgrade(
    stage2_input: Stage2Input,
    seed_candidate: FixedLambdaSelection,
    seed_best_feasible_trace_index: int,
    resolutions: tuple[LookupResolution, ...],
) -> tuple[
    tuple[Stage2SelectedTile, ...],
    float,
    float,
    float,
    float,
    Stage2LocalUpgradeAudit,
]:
    current_candidate_ids = {
        selection.tile_id: selection.selected_candidate_id
        for selection in seed_candidate.tile_selections
    }
    (
        _seed_selected_tiles,
        total_bytes,
        total_net_utility,
        _seed_spatial_utility,
        total_decode_ms,
    ) = _assemble_success_selection(stage2_input, seed_candidate, resolutions)
    _check_candidate_matches_assembled(
        seed_candidate,
        total_bytes,
        total_net_utility,
        total_decode_ms,
    )

    initial_total_bytes = total_bytes
    initial_total_net_utility = total_net_utility
    initial_total_decode_ms = total_decode_ms
    residual_budget = stage2_input.budget_total_bytes - total_bytes
    steps: list[Stage2LocalUpgradeStep] = []

    while residual_budget > FLOAT_EPSILON:
        candidates = _find_switch_candidates(
            stage2_input,
            resolutions,
            current_candidate_ids,
            residual_budget,
        )
        if not candidates:
            break

        candidate = candidates[0]
        tile = stage2_input.tile_by_id(candidate.tile_id)
        current_option = tile.candidate_by_id(candidate.from_candidate_id)
        target_option = tile.candidate_by_id(candidate.to_candidate_id)
        residual_budget_before = residual_budget
        total_bytes += candidate.delta_r_bytes
        total_net_utility += candidate.delta_net_utility
        total_decode_ms += target_option.d_ms - current_option.d_ms
        residual_budget -= candidate.delta_r_bytes
        current_candidate_ids[candidate.tile_id] = candidate.to_candidate_id
        steps.append(
            Stage2LocalUpgradeStep(
                step_index=len(steps),
                tile_id=candidate.tile_id,
                from_candidate_id=candidate.from_candidate_id,
                to_candidate_id=candidate.to_candidate_id,
                delta_r_bytes=candidate.delta_r_bytes,
                delta_net_utility=candidate.delta_net_utility,
                gain_per_byte=candidate.gain_per_byte,
                residual_budget_before=residual_budget_before,
                residual_budget_after=residual_budget,
                total_bytes_after=total_bytes,
                total_net_utility_after=total_net_utility,
                total_decode_ms_after=total_decode_ms,
            )
        )

    (
        final_selected_tiles,
        final_total_bytes,
        final_total_net_utility,
        final_total_spatial_utility,
        final_total_decode_ms,
    ) = _assemble_selection_from_candidate_ids(
        stage2_input,
        current_candidate_ids,
        resolutions,
    )
    _check_close("local-repair total_bytes", total_bytes, final_total_bytes)
    _check_close(
        "local-repair total_net_utility",
        total_net_utility,
        final_total_net_utility,
    )
    _check_close(
        "local-repair total_decode_ms",
        total_decode_ms,
        final_total_decode_ms,
    )
    if final_total_bytes > stage2_input.budget_total_bytes + FLOAT_EPSILON:
        raise InternalSolverInvariantError("local repair selected tiles exceed budget")
    if final_total_net_utility + FLOAT_EPSILON < initial_total_net_utility:
        raise InternalSolverInvariantError("local repair reduced total net utility")

    audit = Stage2LocalUpgradeAudit(
        enabled=True,
        seed_best_feasible_trace_index=seed_best_feasible_trace_index,
        initial_total_bytes=initial_total_bytes,
        initial_total_net_utility=initial_total_net_utility,
        initial_total_decode_ms=initial_total_decode_ms,
        steps=tuple(steps),
        termination_reason="NO_FEASIBLE_POSITIVE_SWITCH",
    )
    return (
        final_selected_tiles,
        final_total_bytes,
        final_total_net_utility,
        final_total_spatial_utility,
        final_total_decode_ms,
        audit,
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

    local_upgrade = _disabled_local_upgrade()
    try:
        if search_result.best_feasible_trace_index is None:
            raise InternalSolverInvariantError(
                "missing best feasible trace index for local repair seed"
            )
        (
            selected_tiles,
            total_bytes,
            total_net_utility,
            total_spatial_utility,
            total_decode_ms,
            local_upgrade,
        ) = _apply_local_upgrade(
            stage2_input,
            search_result.best_feasible_candidate,
            search_result.best_feasible_trace_index,
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
            local_upgrade=local_upgrade,
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
        local_upgrade=local_upgrade,
    )
