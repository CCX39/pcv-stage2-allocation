from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from math import prod

from pcv_stage2.models import LookupResolution, Stage2Input
from pcv_stage2.preprocess import compute_net_utility, compute_spatial_utility


DEFAULT_MAX_ENUMERATED_COMBINATIONS = 100_000


@dataclass(frozen=True)
class ExhaustiveOracleSelectedTile:
    tile_id: str
    selected_candidate_id: str
    r_bytes: float
    d_ms: float
    net_utility: float
    spatial_utility: float
    allowed_candidate_ids: tuple[str, ...]


@dataclass(frozen=True)
class ExhaustiveOracleResult:
    budget_total_bytes: float
    total_bytes: float
    total_net_utility: float
    total_spatial_utility: float
    total_decode_ms: float
    budget_utilization: float
    selected_tiles: tuple[ExhaustiveOracleSelectedTile, ...]
    sorted_selection: tuple[tuple[str, str], ...]
    combination_count: int


def _resolution_by_tile(
    stage2_input: Stage2Input,
    resolutions: tuple[LookupResolution, ...],
) -> dict[str, LookupResolution]:
    if len(resolutions) != len(stage2_input.tiles):
        raise ValueError("exhaustive oracle requires one lookup resolution per tile")

    result = {resolution.tile_id: resolution for resolution in resolutions}
    if len(result) != len(resolutions):
        raise ValueError("exhaustive oracle received duplicate lookup resolutions")

    missing = [tile.tile_id for tile in stage2_input.tiles if tile.tile_id not in result]
    if missing:
        raise ValueError(
            "exhaustive oracle lookup resolutions do not cover tile(s): "
            + ", ".join(missing)
        )
    return result


def _budget_utilization(total_bytes: float, budget_total_bytes: float) -> float:
    if budget_total_bytes <= 0:
        return 0.0
    return total_bytes / budget_total_bytes


def _candidate_is_better(
    candidate: ExhaustiveOracleResult,
    incumbent: ExhaustiveOracleResult,
    *,
    score_epsilon: float,
) -> bool:
    if candidate.total_net_utility > incumbent.total_net_utility + score_epsilon:
        return True
    if incumbent.total_net_utility > candidate.total_net_utility + score_epsilon:
        return False

    if candidate.budget_utilization > incumbent.budget_utilization + score_epsilon:
        return True
    if incumbent.budget_utilization > candidate.budget_utilization + score_epsilon:
        return False

    if candidate.total_decode_ms < incumbent.total_decode_ms - score_epsilon:
        return True
    if incumbent.total_decode_ms < candidate.total_decode_ms - score_epsilon:
        return False

    return candidate.sorted_selection < incumbent.sorted_selection


def exact_feasible_reference(
    stage2_input: Stage2Input,
    resolutions: tuple[LookupResolution, ...],
    *,
    score_epsilon: float = 1e-9,
    max_enumerated_combinations: int = DEFAULT_MAX_ENUMERATED_COMBINATIONS,
) -> ExhaustiveOracleResult:
    """Enumerate a tiny preprocessed Stage2 instance for tests only.

    This helper consumes already-resolved lookup cap data. It deliberately does
    not call production lambda search, local repair, or solve_stage2.
    """

    resolutions_by_tile = _resolution_by_tile(stage2_input, resolutions)
    allowed_candidate_sets = tuple(
        resolutions_by_tile[tile.tile_id].allowed_candidate_ids
        for tile in stage2_input.tiles
    )
    combination_count = prod(
        len(allowed_candidates) for allowed_candidates in allowed_candidate_sets
    )

    if combination_count > max_enumerated_combinations:
        raise ValueError(
            "test-only exhaustive oracle input scale exceeds the allowed enumeration "
            f"limit: {combination_count} combinations > "
            f"{max_enumerated_combinations}. Do not use this helper for normal "
            "runtime paths, large-scale experiments, batch runs, or approximate "
            "fallback solving."
        )

    best: ExhaustiveOracleResult | None = None
    for selected_candidate_ids in product(*allowed_candidate_sets):
        selected_tiles: list[ExhaustiveOracleSelectedTile] = []
        total_bytes = 0.0
        total_net_utility = 0.0
        total_spatial_utility = 0.0
        total_decode_ms = 0.0

        for tile, selected_candidate_id in zip(
            stage2_input.tiles,
            selected_candidate_ids,
            strict=True,
        ):
            resolution = resolutions_by_tile[tile.tile_id]
            candidate = tile.candidate_by_id(selected_candidate_id)
            spatial_utility = compute_spatial_utility(tile, candidate)
            net_utility = compute_net_utility(tile, candidate, stage2_input.eta)

            selected_tiles.append(
                ExhaustiveOracleSelectedTile(
                    tile_id=tile.tile_id,
                    selected_candidate_id=selected_candidate_id,
                    r_bytes=candidate.r_bytes,
                    d_ms=candidate.d_ms,
                    net_utility=net_utility,
                    spatial_utility=spatial_utility,
                    allowed_candidate_ids=resolution.allowed_candidate_ids,
                )
            )
            total_bytes += candidate.r_bytes
            total_net_utility += net_utility
            total_spatial_utility += spatial_utility
            total_decode_ms += candidate.d_ms

        if total_bytes > stage2_input.budget_total_bytes:
            continue

        sorted_selection = tuple(
            sorted(
                (tile.tile_id, candidate_id)
                for tile, candidate_id in zip(
                    stage2_input.tiles,
                    selected_candidate_ids,
                    strict=True,
                )
            )
        )
        candidate_result = ExhaustiveOracleResult(
            budget_total_bytes=stage2_input.budget_total_bytes,
            total_bytes=total_bytes,
            total_net_utility=total_net_utility,
            total_spatial_utility=total_spatial_utility,
            total_decode_ms=total_decode_ms,
            budget_utilization=_budget_utilization(
                total_bytes,
                stage2_input.budget_total_bytes,
            ),
            selected_tiles=tuple(selected_tiles),
            sorted_selection=sorted_selection,
            combination_count=combination_count,
        )

        if best is None or _candidate_is_better(
            candidate_result,
            best,
            score_epsilon=score_epsilon,
        ):
            best = candidate_result

    if best is None:
        raise ValueError(
            "test-only exhaustive oracle found no budget-feasible combination under "
            "the current hard constraints."
        )
    return best
