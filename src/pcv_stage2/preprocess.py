from __future__ import annotations

import math

from .models import (
    DistanceLookup,
    FixedLambdaSelection,
    FixedLambdaTileSelection,
    LambdaBracketResult,
    LambdaSearchConfig,
    LambdaSearchResult,
    LambdaSelectedLevel,
    LambdaTracePoint,
    LookupResolution,
    LookupRule,
    QualityLevel,
    Stage2Input,
    Tile,
)


class PreprocessError(ValueError):
    """Raised when Stage2 preprocessing cannot resolve lookup or candidates."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "INVALID_LOOKUP",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _rule_applies_to_tile(tile: Tile, rule: LookupRule) -> bool:
    return rule.view_context == tile.view_context and rule.distance_match.matches(
        tile.distance_norm
    )


def match_lookup_rule(tile: Tile, lookup: DistanceLookup) -> LookupRule:
    matches = [rule for rule in lookup.rules if _rule_applies_to_tile(tile, rule)]
    target_aware_matches = [rule for rule in matches if rule.target_id is not None]
    if target_aware_matches:
        rule_ids = ", ".join(rule.rule_id for rule in target_aware_matches)
        target_ids = ", ".join(str(rule.target_id) for rule in target_aware_matches)
        raise PreprocessError(
            "Stage2Input v0.1 does not provide the context required for "
            "target-aware lookup rules. Refusing lookup rule(s) "
            f"{rule_ids} with target_id value(s) {target_ids}; target_id must "
            "not be treated as tile_id.",
            code="INVALID_LOOKUP",
            details={
                "tile_id": tile.tile_id,
                "rule_ids": [rule.rule_id for rule in target_aware_matches],
                "target_ids": [rule.target_id for rule in target_aware_matches],
            },
        )

    matches = [rule for rule in matches if rule.target_id is None]
    if len(matches) != 1:
        raise PreprocessError(
            f"{tile.tile_id} must match exactly one lookup rule in "
            f"{lookup.lookup_profile_id}, got {len(matches)}",
            code="INVALID_LOOKUP",
            details={
                "tile_id": tile.tile_id,
                "lookup_profile_id": lookup.lookup_profile_id,
                "match_count": len(matches),
            },
        )
    return matches[0]


def resolve_allowed_levels(tile: Tile, lookup: DistanceLookup) -> LookupResolution:
    if lookup.semantics != "cap":
        raise PreprocessError(
            f"{lookup.lookup_profile_id} uses unsupported lookup semantics "
            f"{lookup.semantics!r}; expected 'cap'",
            code="INVALID_LOOKUP",
            details={
                "lookup_profile_id": lookup.lookup_profile_id,
                "semantics": lookup.semantics,
            },
        )

    rule = match_lookup_rule(tile, lookup)
    max_existing_level = tile.max_level_id
    cap_level = min(rule.lookup_level, max_existing_level)
    allowed_levels = tuple(
        sorted(level.level_id for level in tile.levels if level.level_id <= cap_level)
    )

    if not allowed_levels:
        raise PreprocessError(
            f"{tile.tile_id} has no allowed levels after lookup cap",
            code="NO_ALLOWED_LEVEL",
            details={
                "tile_id": tile.tile_id,
                "lookup_profile_id": lookup.lookup_profile_id,
                "matched_rule_id": rule.rule_id,
                "lookup_level": rule.lookup_level,
            },
        )

    return LookupResolution(
        tile_id=tile.tile_id,
        lookup_profile_id=lookup.lookup_profile_id,
        matched_rule_id=rule.rule_id,
        lookup_level=rule.lookup_level,
        allowed_levels=allowed_levels,
    )


def resolve_lookup_for_input(
    stage2_input: Stage2Input, lookup: DistanceLookup
) -> tuple[LookupResolution, ...]:
    if stage2_input.lookup_profile_id != lookup.lookup_profile_id:
        raise PreprocessError(
            f"input references lookup_profile_id {stage2_input.lookup_profile_id!r}, "
            f"but lookup file provides {lookup.lookup_profile_id!r}",
            code="INVALID_LOOKUP",
            details={
                "input_lookup_profile_id": stage2_input.lookup_profile_id,
                "lookup_profile_id": lookup.lookup_profile_id,
            },
        )
    return tuple(resolve_allowed_levels(tile, lookup) for tile in stage2_input.tiles)


def compute_spatial_utility(
    tile: Tile, level: QualityLevel, g_distance: float = 1.0
) -> float:
    return (
        tile.p_sal
        * tile.visibility
        * tile.screen_area
        * g_distance
        * level.q_base
    )


def compute_net_utility(tile: Tile, level: QualityLevel, eta: float) -> float:
    return compute_spatial_utility(tile, level) - eta * level.d_ms


def compute_b_min_feasible(stage2_input: Stage2Input, lookup: DistanceLookup) -> float:
    total = 0.0
    for tile in stage2_input.tiles:
        resolution = resolve_allowed_levels(tile, lookup)
        candidate_sizes = [
            tile.level_by_id(level_id).r_bytes for level_id in resolution.allowed_levels
        ]
        total += min(candidate_sizes)
    return total


def _require_finite_non_negative(value: float, name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise PreprocessError(
            f"{name} must be finite and non-negative, got {value!r}",
            code="INVALID_INPUT",
            details={"parameter": name, "value": repr(value)},
        )


def _is_better_fixed_lambda_candidate(
    *,
    candidate_level: QualityLevel,
    candidate_score: float,
    best_level: QualityLevel,
    best_score: float,
    score_epsilon: float,
) -> bool:
    if candidate_score > best_score + score_epsilon:
        return True
    if best_score > candidate_score + score_epsilon:
        return False

    # D0-3 fixed-lambda tie order: score, smaller bytes, smaller decode time,
    # then smaller level_id.
    return (
        candidate_level.r_bytes,
        candidate_level.d_ms,
        candidate_level.level_id,
    ) < (
        best_level.r_bytes,
        best_level.d_ms,
        best_level.level_id,
    )


def select_fixed_lambda(
    stage2_input: Stage2Input,
    lookup: DistanceLookup,
    lambda_value: float,
    *,
    score_epsilon: float = 1e-9,
) -> FixedLambdaSelection:
    _require_finite_non_negative(lambda_value, "lambda_value")
    _require_finite_non_negative(score_epsilon, "score_epsilon")

    tile_selections: list[FixedLambdaTileSelection] = []
    total_bytes = 0.0
    total_net_utility = 0.0
    total_penalized_score = 0.0
    resolutions = resolve_lookup_for_input(stage2_input, lookup)

    for tile, resolution in zip(stage2_input.tiles, resolutions, strict=True):
        best_level: QualityLevel | None = None
        best_net_utility = 0.0
        best_penalized_score = 0.0

        for level_id in resolution.allowed_levels:
            level = tile.level_by_id(level_id)
            net_utility = compute_net_utility(tile, level, stage2_input.eta)
            penalized_score = net_utility - lambda_value * level.r_bytes

            if best_level is None or _is_better_fixed_lambda_candidate(
                candidate_level=level,
                candidate_score=penalized_score,
                best_level=best_level,
                best_score=best_penalized_score,
                score_epsilon=score_epsilon,
            ):
                best_level = level
                best_net_utility = net_utility
                best_penalized_score = penalized_score

        assert best_level is not None

        tile_selections.append(
            FixedLambdaTileSelection(
                lambda_value=lambda_value,
                tile_id=tile.tile_id,
                allowed_level_ids=resolution.allowed_levels,
                selected_level_id=best_level.level_id,
                selected_r_bytes=best_level.r_bytes,
                selected_d_ms=best_level.d_ms,
                selected_net_utility=best_net_utility,
                selected_penalized_score=best_penalized_score,
            )
        )
        total_bytes += best_level.r_bytes
        total_net_utility += best_net_utility
        total_penalized_score += best_penalized_score

    return FixedLambdaSelection(
        lambda_value=lambda_value,
        tile_selections=tuple(tile_selections),
        total_bytes=total_bytes,
        total_net_utility=total_net_utility,
        total_penalized_score=total_penalized_score,
        budget_total_bytes=stage2_input.budget_total_bytes,
        is_budget_feasible=total_bytes <= stage2_input.budget_total_bytes,
    )


def _trace_point_from_fixed_lambda(
    step_index: int,
    candidate: FixedLambdaSelection,
) -> LambdaTracePoint:
    return LambdaTracePoint(
        step_index=step_index,
        lambda_value=candidate.lambda_value,
        total_bytes=candidate.total_bytes,
        total_net_utility=candidate.total_net_utility,
        total_decode_ms=sum(
            selection.selected_d_ms for selection in candidate.tile_selections
        ),
        is_budget_feasible=candidate.is_budget_feasible,
        selected_levels=tuple(
            LambdaSelectedLevel(
                tile_id=selection.tile_id,
                selected_level_id=selection.selected_level_id,
            )
            for selection in candidate.tile_selections
        ),
    )


def _candidate_total_decode_ms(candidate: FixedLambdaSelection) -> float:
    return sum(selection.selected_d_ms for selection in candidate.tile_selections)


def _candidate_budget_utilization(candidate: FixedLambdaSelection) -> float:
    if candidate.budget_total_bytes <= 0:
        return 0.0
    return candidate.total_bytes / candidate.budget_total_bytes


def _candidate_selection_key(candidate: FixedLambdaSelection) -> tuple[tuple[str, int], ...]:
    return tuple(
        (selection.tile_id, selection.selected_level_id)
        for selection in sorted(
            candidate.tile_selections,
            key=lambda selection: selection.tile_id,
        )
    )


def is_better_feasible_candidate(
    candidate: FixedLambdaSelection,
    incumbent: FixedLambdaSelection,
    *,
    score_epsilon: float,
) -> bool:
    if not candidate.is_budget_feasible or not incumbent.is_budget_feasible:
        raise ValueError("best-feasible comparison requires budget-feasible candidates")

    if candidate.total_net_utility > incumbent.total_net_utility + score_epsilon:
        return True
    if incumbent.total_net_utility > candidate.total_net_utility + score_epsilon:
        return False

    candidate_utilization = _candidate_budget_utilization(candidate)
    incumbent_utilization = _candidate_budget_utilization(incumbent)
    if candidate_utilization > incumbent_utilization + score_epsilon:
        return True
    if incumbent_utilization > candidate_utilization + score_epsilon:
        return False

    candidate_decode_ms = _candidate_total_decode_ms(candidate)
    incumbent_decode_ms = _candidate_total_decode_ms(incumbent)
    if candidate_decode_ms < incumbent_decode_ms - score_epsilon:
        return True
    if incumbent_decode_ms < candidate_decode_ms - score_epsilon:
        return False

    return _candidate_selection_key(candidate) < _candidate_selection_key(incumbent)


def bracket_lambda_for_feasible_candidate(
    stage2_input: Stage2Input,
    lookup: DistanceLookup,
    config: LambdaSearchConfig,
) -> LambdaBracketResult:
    b_min_feasible = compute_b_min_feasible(stage2_input, lookup)
    if stage2_input.budget_total_bytes < b_min_feasible:
        raise PreprocessError(
            "lambda bracketing requires a budget-feasible input; the final "
            "solve_stage2 layer must map this condition to INFEASIBLE_BUDGET.",
            code="INFEASIBLE_BUDGET",
            details={
                "budget_total_bytes": stage2_input.budget_total_bytes,
                "b_min_feasible": b_min_feasible,
            },
        )

    trace: list[LambdaTracePoint] = []
    zero_candidate = select_fixed_lambda(
        stage2_input,
        lookup,
        lambda_value=0.0,
        score_epsilon=config.score_epsilon,
    )
    trace.append(_trace_point_from_fixed_lambda(0, zero_candidate))

    if zero_candidate.is_budget_feasible:
        return LambdaBracketResult(
            bracket_found=True,
            feasible_at_zero=True,
            lower_infeasible_lambda=None,
            upper_feasible_lambda=0.0,
            feasible_candidate=zero_candidate,
            trace=tuple(trace),
        )

    lower_infeasible_lambda = 0.0
    lambda_value = config.lambda_initial_high

    for _ in range(config.lambda_max_bracket_steps):
        candidate = select_fixed_lambda(
            stage2_input,
            lookup,
            lambda_value=lambda_value,
            score_epsilon=config.score_epsilon,
        )
        trace.append(_trace_point_from_fixed_lambda(len(trace), candidate))

        if candidate.is_budget_feasible:
            return LambdaBracketResult(
                bracket_found=True,
                feasible_at_zero=False,
                lower_infeasible_lambda=lower_infeasible_lambda,
                upper_feasible_lambda=lambda_value,
                feasible_candidate=candidate,
                trace=tuple(trace),
            )

        lower_infeasible_lambda = lambda_value
        lambda_value *= 2

    return LambdaBracketResult(
        bracket_found=False,
        feasible_at_zero=False,
        lower_infeasible_lambda=lower_infeasible_lambda,
        upper_feasible_lambda=None,
        feasible_candidate=None,
        trace=tuple(trace),
    )


def search_lambda_feasible_candidates(
    stage2_input: Stage2Input,
    lookup: DistanceLookup,
    config: LambdaSearchConfig,
) -> LambdaSearchResult:
    bracket = bracket_lambda_for_feasible_candidate(stage2_input, lookup, config)
    trace = list(bracket.trace)

    if bracket.feasible_at_zero:
        return LambdaSearchResult(
            bracket_found=True,
            feasible_at_zero=True,
            bisection_performed=False,
            termination_reason="feasible_at_zero",
            lower_infeasible_lambda=None,
            upper_feasible_lambda=0.0,
            best_feasible_candidate=bracket.feasible_candidate,
            best_feasible_trace_index=0,
            trace=tuple(trace),
        )

    if not bracket.bracket_found:
        return LambdaSearchResult(
            bracket_found=False,
            feasible_at_zero=False,
            bisection_performed=False,
            termination_reason="bracket_failure",
            lower_infeasible_lambda=bracket.lower_infeasible_lambda,
            upper_feasible_lambda=None,
            best_feasible_candidate=None,
            best_feasible_trace_index=None,
            trace=tuple(trace),
        )

    assert bracket.lower_infeasible_lambda is not None
    assert bracket.upper_feasible_lambda is not None
    assert bracket.feasible_candidate is not None

    lambda_low = bracket.lower_infeasible_lambda
    lambda_high = bracket.upper_feasible_lambda
    best_feasible_candidate = bracket.feasible_candidate
    best_feasible_trace_index = len(trace) - 1
    bisection_performed = False
    termination_reason = "max_iterations"

    for _ in range(config.max_iterations):
        if lambda_high - lambda_low <= config.lambda_epsilon:
            termination_reason = "lambda_epsilon"
            break

        lambda_mid = (lambda_low + lambda_high) / 2
        if lambda_mid == lambda_low or lambda_mid == lambda_high:
            termination_reason = "floating_point_stall"
            break

        candidate = select_fixed_lambda(
            stage2_input,
            lookup,
            lambda_value=lambda_mid,
            score_epsilon=config.score_epsilon,
        )
        trace.append(_trace_point_from_fixed_lambda(len(trace), candidate))
        bisection_performed = True

        if candidate.is_budget_feasible:
            if is_better_feasible_candidate(
                candidate,
                best_feasible_candidate,
                score_epsilon=config.score_epsilon,
            ):
                best_feasible_candidate = candidate
                best_feasible_trace_index = len(trace) - 1
            lambda_high = lambda_mid
        else:
            lambda_low = lambda_mid
    else:
        termination_reason = "max_iterations"

    return LambdaSearchResult(
        bracket_found=True,
        feasible_at_zero=False,
        bisection_performed=bisection_performed,
        termination_reason=termination_reason,
        lower_infeasible_lambda=lambda_low,
        upper_feasible_lambda=lambda_high,
        best_feasible_candidate=best_feasible_candidate,
        best_feasible_trace_index=best_feasible_trace_index,
        trace=tuple(trace),
    )
