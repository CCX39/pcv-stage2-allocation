from __future__ import annotations

from .models import (
    DistanceLookup,
    LookupResolution,
    LookupRule,
    QualityLevel,
    Stage2Input,
    Tile,
)


class PreprocessError(ValueError):
    """Raised when Stage2 preprocessing cannot resolve lookup or candidates."""


def _rule_applies_to_tile(tile: Tile, rule: LookupRule) -> bool:
    if rule.view_context != tile.view_context:
        return False
    if rule.target_id is not None and rule.target_id != tile.tile_id:
        return False
    return rule.distance_match.matches(tile.distance_norm)


def match_lookup_rule(tile: Tile, lookup: DistanceLookup) -> LookupRule:
    matches = [rule for rule in lookup.rules if _rule_applies_to_tile(tile, rule)]
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
