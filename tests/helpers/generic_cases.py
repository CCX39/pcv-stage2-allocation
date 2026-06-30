from __future__ import annotations

from pcv_stage2.models import (
    DistanceLookup,
    LookupDistanceMatch,
    LookupPdlSupport,
    LookupRule,
    Stage2Input,
    Tile,
    TransmissionCandidate,
)


def candidate(
    candidate_id: str,
    *,
    q_base: float,
    r_bytes: float,
    d_ms: float = 1.0,
    pdl_ratio: float | None = 0.5,
    file_format: str = "ply",
    codec: str = "raw_ply",
    codec_params: dict[str, object] | None = None,
    provenance_value: str = "synthetic",
) -> TransmissionCandidate:
    return TransmissionCandidate(
        candidate_id=candidate_id,
        pdl_ratio=pdl_ratio,
        file_format=file_format,
        codec=codec,
        codec_params=codec_params or {},
        asset_ref=f"synthetic://unit/{candidate_id}",
        q_base=q_base,
        r_bytes=r_bytes,
        d_ms=d_ms,
        provenance={
            "pdl_ratio": provenance_value,
            "q_base": provenance_value,
            "r_bytes": provenance_value,
            "d_ms": provenance_value,
            "asset_ref": provenance_value,
        },
    )


def tile(
    tile_id: str,
    *,
    distance_norm: float,
    candidates: tuple[TransmissionCandidate, ...],
    view_context: str = "synthetic_context",
    p_sal: float = 1.0,
    visibility: float = 1.0,
    screen_area: float = 1.0,
) -> Tile:
    return Tile(
        tile_id=tile_id,
        p_sal=p_sal,
        visibility=visibility,
        screen_area=screen_area,
        distance_norm=distance_norm,
        view_context=view_context,
        candidates=candidates,
        provenance={
            "p_sal": "synthetic",
            "visibility": "synthetic",
            "screen_area": "synthetic",
            "distance_norm": "synthetic",
            "view_context": "synthetic",
        },
    )


def stage2_case(
    *,
    scenario_id: str,
    budget_total_bytes: float,
    tiles: tuple[Tile, ...],
    lookup_profile_id: str,
    eta: float = 0.0,
) -> Stage2Input:
    return Stage2Input(
        schema_version="0.2.0",
        scenario_id=scenario_id,
        budget_total_bytes=budget_total_bytes,
        eta=eta,
        lookup_profile_id=lookup_profile_id,
        tiles=tiles,
        provenance_summary={
            "default_type": "synthetic",
            "source_ids": [scenario_id],
        },
        description="Synthetic generic-candidate test case.",
    )


def lookup_for_tiles(
    *,
    profile_id: str,
    tiles: tuple[Tile, ...],
    pdl_max_by_tile: dict[str, float],
) -> DistanceLookup:
    support = sorted(
        {
            item.pdl_ratio
            for tile_item in tiles
            for item in tile_item.candidates
            if item.pdl_ratio is not None
        }
    )
    return DistanceLookup(
        schema_version="0.2.0",
        lookup_profile_id=profile_id,
        semantics="cap",
        distance_unit="normalized_render_distance",
        pdl_support=tuple(
            LookupPdlSupport(
                pdl_ratio=pdl_ratio,
                quality_label=f"PDL_{pdl_ratio:g}",
            )
            for pdl_ratio in support
        ),
        source={
            "dataset": "synthetic",
            "renderer": "synthetic",
            "metric": "synthetic",
            "threshold_profile": "synthetic",
            "source_runs": [],
        },
        rules=tuple(
            LookupRule(
                rule_id=f"rule_{item.tile_id}",
                view_context=item.view_context,
                target_id=None,
                distance_match=LookupDistanceMatch(
                    exact_distance=item.distance_norm,
                ),
                pdl_max_dist=pdl_max_by_tile[item.tile_id],
                threshold_profile="synthetic",
            )
            for item in tiles
        ),
    )
