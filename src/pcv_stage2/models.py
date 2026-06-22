from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


def _as_tuple(items: tuple[Any, ...] | list[Any]) -> tuple[Any, ...]:
    return tuple(items)


def _is_real_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


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


def _is_non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


@dataclass(frozen=True)
class LambdaSearchConfig:
    lambda_initial_high: float
    lambda_max_bracket_steps: int
    score_epsilon: float
    lambda_epsilon: float
    max_iterations: int

    def __post_init__(self) -> None:
        if (
            not _is_real_number(self.lambda_initial_high)
            or not math.isfinite(self.lambda_initial_high)
            or self.lambda_initial_high <= 0
        ):
            raise ValueError(
                "lambda_initial_high must be finite and positive, "
                f"got {self.lambda_initial_high!r}"
            )
        if not _is_non_negative_int(self.lambda_max_bracket_steps):
            raise ValueError(
                "lambda_max_bracket_steps must be a non-negative integer, "
                f"got {self.lambda_max_bracket_steps!r}"
            )
        if (
            not _is_real_number(self.score_epsilon)
            or not math.isfinite(self.score_epsilon)
            or self.score_epsilon < 0
        ):
            raise ValueError(
                "score_epsilon must be finite and non-negative, "
                f"got {self.score_epsilon!r}"
            )
        if (
            not _is_real_number(self.lambda_epsilon)
            or not math.isfinite(self.lambda_epsilon)
            or self.lambda_epsilon < 0
        ):
            raise ValueError(
                "lambda_epsilon must be finite and non-negative, "
                f"got {self.lambda_epsilon!r}"
            )
        if not _is_non_negative_int(self.max_iterations):
            raise ValueError(
                "max_iterations must be a non-negative integer, "
                f"got {self.max_iterations!r}"
            )


@dataclass(frozen=True)
class LambdaSelectedLevel:
    tile_id: str
    selected_level_id: int

    def __post_init__(self) -> None:
        if self.selected_level_id < 1:
            raise ValueError(
                f"{self.tile_id} selected_level_id must be >= 1, "
                f"got {self.selected_level_id}"
            )


@dataclass(frozen=True)
class LambdaTracePoint:
    step_index: int
    lambda_value: float
    total_bytes: float
    total_net_utility: float
    total_decode_ms: float
    is_budget_feasible: bool
    selected_levels: tuple[LambdaSelectedLevel, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "selected_levels", _as_tuple(self.selected_levels))
        if self.step_index < 0:
            raise ValueError(f"step_index must be >= 0, got {self.step_index}")
        if not math.isfinite(self.lambda_value) or self.lambda_value < 0:
            raise ValueError(
                f"lambda_value must be finite and non-negative, got {self.lambda_value!r}"
            )
        if self.total_bytes < 0:
            raise ValueError(f"total_bytes must be >= 0, got {self.total_bytes!r}")
        if self.total_decode_ms < 0:
            raise ValueError(
                f"total_decode_ms must be >= 0, got {self.total_decode_ms!r}"
            )


@dataclass(frozen=True)
class LambdaBracketResult:
    bracket_found: bool
    feasible_at_zero: bool
    lower_infeasible_lambda: float | None
    upper_feasible_lambda: float | None
    feasible_candidate: FixedLambdaSelection | None
    trace: tuple[LambdaTracePoint, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace", _as_tuple(self.trace))
        if not self.trace:
            raise ValueError("lambda bracket result must contain at least one trace point")
        if self.feasible_at_zero and (
            not self.bracket_found
            or self.lower_infeasible_lambda is not None
            or self.upper_feasible_lambda != 0
        ):
            raise ValueError("feasible-at-zero bracket result has inconsistent bounds")
        if self.bracket_found and self.feasible_candidate is None:
            raise ValueError("successful bracket result must include feasible_candidate")
        if not self.bracket_found and self.feasible_candidate is not None:
            raise ValueError("failed bracket result must not include feasible_candidate")


@dataclass(frozen=True)
class LambdaSearchResult:
    bracket_found: bool
    feasible_at_zero: bool
    bisection_performed: bool
    termination_reason: str
    lower_infeasible_lambda: float | None
    upper_feasible_lambda: float | None
    best_feasible_candidate: FixedLambdaSelection | None
    best_feasible_trace_index: int | None
    trace: tuple[LambdaTracePoint, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace", _as_tuple(self.trace))
        allowed_reasons = {
            "feasible_at_zero",
            "lambda_epsilon",
            "max_iterations",
            "bracket_failure",
            "floating_point_stall",
        }
        if self.termination_reason not in allowed_reasons:
            raise ValueError(f"unknown termination_reason {self.termination_reason!r}")
        if not self.trace:
            raise ValueError("lambda search result must contain at least one trace point")
        step_indices = [point.step_index for point in self.trace]
        expected = list(range(len(self.trace)))
        if step_indices != expected:
            raise ValueError(
                f"trace step_index values must be consecutive: expected {expected}, "
                f"got {step_indices}"
            )
        if (self.best_feasible_candidate is None) != (
            self.best_feasible_trace_index is None
        ):
            raise ValueError(
                "best_feasible_candidate and best_feasible_trace_index must both "
                "be present or both be null"
            )
        if self.best_feasible_trace_index is not None:
            if not 0 <= self.best_feasible_trace_index < len(self.trace):
                raise ValueError(
                    "best_feasible_trace_index must point inside the search trace"
                )
            if not self.trace[self.best_feasible_trace_index].is_budget_feasible:
                raise ValueError("best feasible trace point must be budget feasible")
