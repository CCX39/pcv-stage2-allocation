from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


PROVENANCE_TERMS = frozenset({"measured", "calibrated", "derived", "proxy", "synthetic"})
REQUIRED_CANDIDATE_PROVENANCE_FIELDS = frozenset(
    {"r_bytes", "d_ms", "q_base", "pdl_ratio", "asset_ref"}
)


def _as_tuple(items: tuple[Any, ...] | list[Any]) -> tuple[Any, ...]:
    return tuple(items)


def _is_real_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_finite_non_negative(value: float, name: str) -> None:
    if not _is_real_number(value) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and non-negative, got {value!r}")


def _require_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _validate_provenance_map(provenance: dict[str, str], *, context: str) -> None:
    for key, value in provenance.items():
        if not isinstance(key, str) or not key:
            raise ValueError(f"{context} provenance keys must be non-empty strings")
        if value not in PROVENANCE_TERMS:
            raise ValueError(
                f"{context} provenance value for {key!r} must be one of "
                f"{sorted(PROVENANCE_TERMS)}, got {value!r}"
            )


@dataclass(frozen=True)
class TransmissionCandidate:
    candidate_id: str
    file_format: str
    codec: str
    codec_params: dict[str, Any]
    asset_ref: str
    q_base: float
    r_bytes: float
    d_ms: float
    provenance: dict[str, str]
    pdl_ratio: float | None = None

    def __post_init__(self) -> None:
        _require_non_empty_string(self.candidate_id, "candidate_id")
        _require_non_empty_string(self.file_format, "file_format")
        _require_non_empty_string(self.codec, "codec")
        _require_non_empty_string(self.asset_ref, "asset_ref")
        object.__setattr__(self, "codec_params", dict(self.codec_params))
        object.__setattr__(self, "provenance", dict(self.provenance))
        _require_finite_non_negative(self.q_base, "q_base")
        _require_finite_non_negative(self.r_bytes, "r_bytes")
        _require_finite_non_negative(self.d_ms, "d_ms")
        if self.pdl_ratio is not None:
            if (
                not _is_real_number(self.pdl_ratio)
                or not math.isfinite(self.pdl_ratio)
                or self.pdl_ratio <= 0
                or self.pdl_ratio > 1
            ):
                raise ValueError(
                    "pdl_ratio must be finite and in (0, 1] when present, "
                    f"got {self.pdl_ratio!r}"
                )
        _validate_provenance_map(self.provenance, context=self.candidate_id)
        missing = REQUIRED_CANDIDATE_PROVENANCE_FIELDS - set(self.provenance)
        if missing:
            raise ValueError(
                f"{self.candidate_id} provenance must include "
                f"{sorted(REQUIRED_CANDIDATE_PROVENANCE_FIELDS)}, missing {sorted(missing)}"
            )

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "pdl_ratio": self.pdl_ratio,
            "file_format": self.file_format,
            "codec": self.codec,
            "codec_params": _json_compatible(self.codec_params),
            "asset_ref": self.asset_ref,
            "r_bytes": self.r_bytes,
            "d_ms": self.d_ms,
            "q_base": self.q_base,
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True)
class Tile:
    tile_id: str
    p_sal: float
    visibility: float
    screen_area: float
    distance_norm: float
    view_context: str
    candidates: tuple[TransmissionCandidate, ...]
    provenance: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_string(self.tile_id, "tile_id")
        _require_non_empty_string(self.view_context, "view_context")
        _require_finite_non_negative(self.p_sal, f"{self.tile_id}.p_sal")
        _require_finite_non_negative(self.visibility, f"{self.tile_id}.visibility")
        _require_finite_non_negative(self.screen_area, f"{self.tile_id}.screen_area")
        if not math.isfinite(self.distance_norm):
            raise ValueError(f"{self.tile_id}.distance_norm must be finite")
        object.__setattr__(self, "candidates", _as_tuple(self.candidates))
        object.__setattr__(self, "provenance", dict(self.provenance))
        if not self.candidates:
            raise ValueError(f"{self.tile_id} must contain at least one candidate")

        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError(f"{self.tile_id} has duplicate candidate_id values")
        _validate_provenance_map(self.provenance, context=self.tile_id)

    def candidate_by_id(self, candidate_id: str) -> TransmissionCandidate:
        for candidate in self.candidates:
            if candidate.candidate_id == candidate_id:
                return candidate
        raise KeyError(f"{self.tile_id} does not define candidate_id {candidate_id!r}")


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
    pdl_max_dist: float
    threshold_profile: str
    notes: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_string(self.rule_id, "rule_id")
        _require_non_empty_string(self.view_context, "view_context")
        _require_non_empty_string(self.threshold_profile, "threshold_profile")
        if (
            not _is_real_number(self.pdl_max_dist)
            or not math.isfinite(self.pdl_max_dist)
            or self.pdl_max_dist <= 0
            or self.pdl_max_dist > 1
        ):
            raise ValueError(
                f"{self.rule_id} pdl_max_dist must be finite and in (0, 1], "
                f"got {self.pdl_max_dist!r}"
            )


@dataclass(frozen=True)
class LookupPdlSupport:
    pdl_ratio: float
    quality_label: str

    def __post_init__(self) -> None:
        if (
            not _is_real_number(self.pdl_ratio)
            or not math.isfinite(self.pdl_ratio)
            or self.pdl_ratio <= 0
            or self.pdl_ratio > 1
        ):
            raise ValueError(f"lookup pdl_ratio must be finite and in (0, 1]")


@dataclass(frozen=True)
class DistanceLookup:
    schema_version: str
    lookup_profile_id: str
    semantics: str
    distance_unit: str
    pdl_support: tuple[LookupPdlSupport, ...]
    source: dict[str, Any]
    rules: tuple[LookupRule, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "pdl_support", _as_tuple(self.pdl_support))
        object.__setattr__(self, "source", dict(self.source))
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
        object.__setattr__(self, "provenance_summary", dict(self.provenance_summary))
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
    pdl_max_dist: float
    allowed_candidate_ids: tuple[str, ...]
    rejected_candidate_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_candidate_ids", _as_tuple(self.allowed_candidate_ids))
        object.__setattr__(self, "rejected_candidate_ids", _as_tuple(self.rejected_candidate_ids))
        if not self.allowed_candidate_ids:
            raise ValueError(f"{self.tile_id} has no allowed candidates")


@dataclass(frozen=True)
class FixedLambdaTileSelection:
    lambda_value: float
    tile_id: str
    allowed_candidate_ids: tuple[str, ...]
    selected_candidate_id: str
    selected_r_bytes: float
    selected_d_ms: float
    selected_net_utility: float
    selected_penalized_score: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_candidate_ids", _as_tuple(self.allowed_candidate_ids))
        if not self.allowed_candidate_ids:
            raise ValueError(f"{self.tile_id} has no allowed candidates")
        if self.selected_candidate_id not in self.allowed_candidate_ids:
            raise ValueError(
                f"{self.tile_id} selected candidate {self.selected_candidate_id!r} "
                "is outside allowed_candidate_ids"
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


def _float_close(left: float, right: float, epsilon: float = 1e-9) -> bool:
    return abs(left - right) <= epsilon


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
class LambdaSelectedCandidate:
    tile_id: str
    selected_candidate_id: str

    def __post_init__(self) -> None:
        _require_non_empty_string(self.tile_id, "tile_id")
        _require_non_empty_string(self.selected_candidate_id, "selected_candidate_id")


@dataclass(frozen=True)
class LambdaTracePoint:
    step_index: int
    lambda_value: float
    total_bytes: float
    total_net_utility: float
    total_decode_ms: float
    is_budget_feasible: bool
    selected_candidates: tuple[LambdaSelectedCandidate, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "selected_candidates", _as_tuple(self.selected_candidates))
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
            trace_point = self.trace[self.best_feasible_trace_index]
            if not trace_point.is_budget_feasible:
                raise ValueError("best feasible trace point must be budget feasible")
            assert self.best_feasible_candidate is not None
            candidate_decode_ms = sum(
                selection.selected_d_ms
                for selection in self.best_feasible_candidate.tile_selections
            )
            candidate_selected_candidates = tuple(
                LambdaSelectedCandidate(
                    tile_id=selection.tile_id,
                    selected_candidate_id=selection.selected_candidate_id,
                )
                for selection in self.best_feasible_candidate.tile_selections
            )
            if not (
                _float_close(
                    trace_point.lambda_value,
                    self.best_feasible_candidate.lambda_value,
                )
                and _float_close(
                    trace_point.total_bytes,
                    self.best_feasible_candidate.total_bytes,
                )
                and _float_close(
                    trace_point.total_net_utility,
                    self.best_feasible_candidate.total_net_utility,
                )
                and _float_close(trace_point.total_decode_ms, candidate_decode_ms)
                and trace_point.selected_candidates == candidate_selected_candidates
            ):
                raise ValueError(
                    "best_feasible_candidate must match the referenced trace point"
                )


def _json_compatible(value: Any) -> Any:
    if isinstance(value, tuple | list):
        return [_json_compatible(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class Stage2Message:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "code": self.code,
            "message": self.message,
        }
        if self.details:
            result["details"] = _json_compatible(self.details)
        return result


@dataclass(frozen=True)
class Stage2SelectedTile:
    tile_id: str
    selected_candidate_id: str
    selected_candidate_snapshot: dict[str, Any]
    r_bytes: float
    d_ms: float
    net_utility: float
    spatial_utility: float
    allowed_candidate_ids: tuple[str, ...]
    rejected_candidate_ids: tuple[str, ...]
    lookup_pdl_max_dist: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_candidate_ids", _as_tuple(self.allowed_candidate_ids))
        object.__setattr__(self, "rejected_candidate_ids", _as_tuple(self.rejected_candidate_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "tile_id": self.tile_id,
            "selected_candidate_id": self.selected_candidate_id,
            "selected_candidate_snapshot": _json_compatible(
                self.selected_candidate_snapshot
            ),
            "r_bytes": self.r_bytes,
            "d_ms": self.d_ms,
            "net_utility": self.net_utility,
            "spatial_utility": self.spatial_utility,
            "allowed_candidate_ids": list(self.allowed_candidate_ids),
            "rejected_candidate_ids": list(self.rejected_candidate_ids),
            "lookup_pdl_max_dist": self.lookup_pdl_max_dist,
        }


@dataclass(frozen=True)
class Stage2LocalUpgradeStep:
    step_index: int
    tile_id: str
    from_candidate_id: str
    to_candidate_id: str
    delta_r_bytes: float
    delta_net_utility: float
    gain_per_byte: float
    residual_budget_before: float
    residual_budget_after: float
    total_bytes_after: float
    total_net_utility_after: float
    total_decode_ms_after: float
    selection_reason: str = "max_gain_per_byte_candidate_switch"

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "tile_id": self.tile_id,
            "from_candidate_id": self.from_candidate_id,
            "to_candidate_id": self.to_candidate_id,
            "delta_r_bytes": self.delta_r_bytes,
            "delta_net_utility": self.delta_net_utility,
            "gain_per_byte": self.gain_per_byte,
            "residual_budget_before": self.residual_budget_before,
            "residual_budget_after": self.residual_budget_after,
            "total_bytes_after": self.total_bytes_after,
            "total_net_utility_after": self.total_net_utility_after,
            "total_decode_ms_after": self.total_decode_ms_after,
            "selection_reason": self.selection_reason,
        }


@dataclass(frozen=True)
class Stage2LocalUpgradeAudit:
    enabled: bool
    seed_best_feasible_trace_index: int | None
    initial_total_bytes: float | None
    initial_total_net_utility: float | None
    initial_total_decode_ms: float | None
    steps: tuple[Stage2LocalUpgradeStep, ...]
    termination_reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "steps", _as_tuple(self.steps))

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "seed_best_feasible_trace_index": self.seed_best_feasible_trace_index,
            "initial_total_bytes": self.initial_total_bytes,
            "initial_total_net_utility": self.initial_total_net_utility,
            "initial_total_decode_ms": self.initial_total_decode_ms,
            "steps": [step.to_dict() for step in self.steps],
            "termination_reason": self.termination_reason,
        }


@dataclass(frozen=True)
class Stage2SolveResult:
    schema_version: str
    scenario_id: str
    status: str
    budget_total_bytes: float
    b_min_feasible: float | None
    budget_gap: float | None
    total_bytes: float | None
    total_net_utility: float | None
    total_spatial_utility: float | None
    total_decode_ms: float | None
    budget_utilization: float | None
    selected_tiles: tuple[Stage2SelectedTile, ...]
    lookup_resolution: tuple[LookupResolution, ...]
    lambda_search: dict[str, Any]
    local_upgrade: Stage2LocalUpgradeAudit
    runtime_ms: float | None
    config_snapshot: dict[str, Any]
    warnings: tuple[Stage2Message, ...] = ()
    errors: tuple[Stage2Message, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "selected_tiles", _as_tuple(self.selected_tiles))
        object.__setattr__(self, "lookup_resolution", _as_tuple(self.lookup_resolution))
        object.__setattr__(self, "warnings", _as_tuple(self.warnings))
        object.__setattr__(self, "errors", _as_tuple(self.errors))
        if self.runtime_ms is not None and self.runtime_ms < 0:
            raise ValueError("runtime_ms must be non-negative when present")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "scenario_id": self.scenario_id,
            "status": self.status,
            "budget_total_bytes": self.budget_total_bytes,
            "b_min_feasible": self.b_min_feasible,
            "budget_gap": self.budget_gap,
            "total_bytes": self.total_bytes,
            "total_net_utility": self.total_net_utility,
            "total_spatial_utility": self.total_spatial_utility,
            "total_decode_ms": self.total_decode_ms,
            "budget_utilization": self.budget_utilization,
            "selected_tiles": [item.to_dict() for item in self.selected_tiles],
            "lookup_resolution": [
                {
                    "tile_id": item.tile_id,
                    "lookup_profile_id": item.lookup_profile_id,
                    "matched_rule_id": item.matched_rule_id,
                    "pdl_max_dist": item.pdl_max_dist,
                    "allowed_candidate_ids": list(item.allowed_candidate_ids),
                    "rejected_candidate_ids": list(item.rejected_candidate_ids),
                }
                for item in self.lookup_resolution
            ],
            "lambda_search": _json_compatible(self.lambda_search),
            "local_upgrade": self.local_upgrade.to_dict(),
            "runtime_ms": self.runtime_ms,
            "config_snapshot": _json_compatible(self.config_snapshot),
            "warnings": [item.to_dict() for item in self.warnings],
            "errors": [item.to_dict() for item in self.errors],
        }
