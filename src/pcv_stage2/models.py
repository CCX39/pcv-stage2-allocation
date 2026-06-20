from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _as_tuple(items: tuple[Any, ...] | list[Any]) -> tuple[Any, ...]:
    return tuple(items)


@dataclass(frozen=True)
class QualityLevel:
    level_id: int
    quality_label: str
    pdl_ratio: float
    q_base: float
    r_bytes: float
    d_ms: float
    provenance: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.level_id < 1:
            raise ValueError(f"level_id must be >= 1, got {self.level_id}")


@dataclass(frozen=True)
class Tile:
    tile_id: str
    p_sal: float
    visibility: float
    screen_area: float
    distance_norm: float
    view_context: str
    levels: tuple[QualityLevel, ...]
    provenance: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "levels", _as_tuple(self.levels))
        if not self.levels:
            raise ValueError(f"{self.tile_id} must contain at least one quality level")

        level_ids = sorted(level.level_id for level in self.levels)
        if len(level_ids) != len(set(level_ids)):
            raise ValueError(f"{self.tile_id} has duplicate level_id values")

        expected = list(range(1, max(level_ids) + 1))
        if level_ids != expected:
            raise ValueError(
                f"{self.tile_id} level_id values must be contiguous from 1 "
                f"for the current MVP/handcheck fixture constraint: "
                f"expected {expected}, got {level_ids}"
            )

    @property
    def max_level_id(self) -> int:
        return max(level.level_id for level in self.levels)

    def level_by_id(self, level_id: int) -> QualityLevel:
        for level in self.levels:
            if level.level_id == level_id:
                return level
        raise KeyError(f"{self.tile_id} does not define level_id {level_id}")


@dataclass(frozen=True)
class LookupDistanceMatch:
    exact_distance: float | None = None
    distance_min: float | None = None
    distance_max: float | None = None

    def __post_init__(self) -> None:
        exact_mode = self.exact_distance is not None
        range_mode = self.distance_min is not None or self.distance_max is not None

        if exact_mode == range_mode:
            raise ValueError(
                "distance_match must use exactly one of exact_distance or "
                "distance_min/distance_max"
            )

        if range_mode:
            if self.distance_min is None or self.distance_max is None:
                raise ValueError("range distance_match requires both distance_min and distance_max")
            if self.distance_min > self.distance_max:
                raise ValueError("distance_min must be <= distance_max")

    def matches(self, distance_norm: float, epsilon: float = 1e-9) -> bool:
        if self.exact_distance is not None:
            return abs(distance_norm - self.exact_distance) <= epsilon
        assert self.distance_min is not None
        assert self.distance_max is not None
        return self.distance_min <= distance_norm <= self.distance_max


@dataclass(frozen=True)
class LookupRule:
    rule_id: str
    view_context: str
    target_id: str | None
    distance_match: LookupDistanceMatch
    lookup_level: int
    threshold_profile: str
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.lookup_level < 1:
            raise ValueError(f"{self.rule_id} lookup_level must be >= 1")


@dataclass(frozen=True)
class LookupQualityLevel:
    level_id: int
    pdl_ratio: float
    quality_label: str

    def __post_init__(self) -> None:
        if self.level_id < 1:
            raise ValueError(f"lookup quality level_id must be >= 1, got {self.level_id}")


@dataclass(frozen=True)
class DistanceLookup:
    schema_version: str
    lookup_profile_id: str
    semantics: str
    distance_unit: str
    quality_levels: tuple[LookupQualityLevel, ...]
    source: dict[str, Any]
    rules: tuple[LookupRule, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "quality_levels", _as_tuple(self.quality_levels))
        object.__setattr__(self, "rules", _as_tuple(self.rules))
        if not self.rules:
            raise ValueError(f"{self.lookup_profile_id} must contain at least one lookup rule")


@dataclass(frozen=True)
class Stage2Input:
    schema_version: str
    scenario_id: str
    budget_total_bytes: float
    eta: float
    lookup_profile_id: str
    tiles: tuple[Tile, ...]
    provenance_summary: dict[str, Any]
    description: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tiles", _as_tuple(self.tiles))
        if not self.tiles:
            raise ValueError(f"{self.scenario_id} must contain at least one tile")

        tile_ids = [tile.tile_id for tile in self.tiles]
        if len(tile_ids) != len(set(tile_ids)):
            raise ValueError(f"{self.scenario_id} has duplicate tile_id values")

    def tile_by_id(self, tile_id: str) -> Tile:
        for tile in self.tiles:
            if tile.tile_id == tile_id:
                return tile
        raise KeyError(f"{self.scenario_id} does not define tile_id {tile_id}")


@dataclass(frozen=True)
class LookupResolution:
    tile_id: str
    lookup_profile_id: str
    matched_rule_id: str
    lookup_level: int
    allowed_levels: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_levels", _as_tuple(self.allowed_levels))
        if not self.allowed_levels:
            raise ValueError(f"{self.tile_id} has no allowed levels")


@dataclass(frozen=True)
class FixedLambdaTileSelection:
    lambda_value: float
    tile_id: str
    allowed_level_ids: tuple[int, ...]
    selected_level_id: int
    selected_r_bytes: float
    selected_d_ms: float
    selected_net_utility: float
    selected_penalized_score: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_level_ids", _as_tuple(self.allowed_level_ids))
        if not self.allowed_level_ids:
            raise ValueError(f"{self.tile_id} has no allowed levels")
        if self.selected_level_id not in self.allowed_level_ids:
            raise ValueError(
                f"{self.tile_id} selected level {self.selected_level_id} "
                "is outside allowed_level_ids"
            )


@dataclass(frozen=True)
class FixedLambdaSelection:
    lambda_value: float
    tile_selections: tuple[FixedLambdaTileSelection, ...]
    total_bytes: float
    total_net_utility: float
    total_penalized_score: float
    budget_total_bytes: float
    is_budget_feasible: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "tile_selections", _as_tuple(self.tile_selections))
        if not self.tile_selections:
            raise ValueError("fixed-lambda selection must contain at least one tile")
