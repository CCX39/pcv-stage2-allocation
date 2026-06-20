from __future__ import annotations

import math

from .models import (
    DistanceLookup,
    FixedLambdaSelection,
    FixedLambdaTileSelection,
    LookupResolution,
    LookupRule,
    QualityLevel,
    Stage2Input,
    Tile,
)


class PreprocessError(ValueError):
    """Raised when Stage2 preprocessing cannot resolve lookup or candidates."""


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
            "not be treated as tile_id."
        )

    matches = [rule for rule in matches if rule.target_id is None]
    if len(matches) != 1:
        raise PreprocessError(
            f"{tile.tile_id} must match exactly one lookup rule in "
            f"{lookup.lookup_profile_id}, got {len(matches)}"
        )
    return matches[0]


def resolve_allowed_levels(tile: Tile, lookup: DistanceLookup) -> LookupResolution:
    if lookup.semantics != "cap":
        raise PreprocessError(
            f"{lookup.lookup_profile_id} uses unsupported lookup semantics "
            f"{lookup.semantics!r}; expected 'cap'"
        )

    rule = match_lookup_rule(tile, lookup)
    max_existing_level = tile.max_level_id
    cap_level = min(rule.lookup_level, max_existing_level)
    allowed_levels = tuple(
        sorted(level.level_id for level in tile.levels if level.level_id <= cap_level)
    )

    if not allowed_levels:
        raise PreprocessError(f"{tile.tile_id} has no allowed levels after lookup cap")

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
            f"but lookup file provides {lookup.lookup_profile_id!r}"
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
    if not math.isfinite(value) or value < 0:
        raise PreprocessError(f"{name} must be finite and non-negative, got {value!r}")


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
