from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import (
    DistanceLookup,
    LookupDistanceMatch,
    LookupPdlSupport,
    LookupRule,
    Stage2Input,
    Tile,
    TransmissionCandidate,
)


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def transmission_candidate_from_dict(data: dict[str, Any]) -> TransmissionCandidate:
    pdl_ratio = data.get("pdl_ratio")
    return TransmissionCandidate(
        candidate_id=str(data["candidate_id"]),
        pdl_ratio=None if pdl_ratio is None else float(pdl_ratio),
        file_format=str(data["file_format"]),
        codec=str(data["codec"]),
        codec_params=dict(data.get("codec_params", {})),
        asset_ref=str(data["asset_ref"]),
        q_base=float(data["q_base"]),
        r_bytes=float(data["r_bytes"]),
        d_ms=float(data["d_ms"]),
        provenance=dict(data["provenance"]),
    )


def tile_from_dict(data: dict[str, Any]) -> Tile:
    return Tile(
        tile_id=str(data["tile_id"]),
        p_sal=float(data["p_sal"]),
        visibility=float(data["visibility"]),
        screen_area=float(data["screen_area"]),
        distance_norm=float(data["distance_norm"]),
        view_context=str(data["view_context"]),
        candidates=tuple(
            transmission_candidate_from_dict(candidate)
            for candidate in data["candidates"]
        ),
        provenance=dict(data.get("provenance", {})),
    )


def stage2_input_from_dict(data: dict[str, Any]) -> Stage2Input:
    return Stage2Input(
        schema_version=str(data["schema_version"]),
        scenario_id=str(data["scenario_id"]),
        description=data.get("description"),
        budget_total_bytes=float(data["budget_total_bytes"]),
        eta=float(data["eta"]),
        lookup_profile_id=str(data["lookup_profile_id"]),
        tiles=tuple(tile_from_dict(tile) for tile in data["tiles"]),
        provenance_summary=dict(data["provenance_summary"]),
    )


def lookup_pdl_support_from_dict(data: dict[str, Any]) -> LookupPdlSupport:
    return LookupPdlSupport(
        pdl_ratio=float(data["pdl_ratio"]),
        quality_label=str(data["quality_label"]),
    )


def lookup_distance_match_from_dict(data: dict[str, Any]) -> LookupDistanceMatch:
    if "exact_distance" in data:
        return LookupDistanceMatch(exact_distance=float(data["exact_distance"]))
    return LookupDistanceMatch(
        distance_min=float(data["distance_min"]),
        distance_max=float(data["distance_max"]),
    )


def lookup_rule_from_dict(data: dict[str, Any]) -> LookupRule:
    target_id = data.get("target_id")
    return LookupRule(
        rule_id=str(data["rule_id"]),
        view_context=str(data["view_context"]),
        target_id=None if target_id is None else str(target_id),
        distance_match=lookup_distance_match_from_dict(data["distance_match"]),
        pdl_max_dist=float(data["pdl_max_dist"]),
        threshold_profile=str(data["threshold_profile"]),
        notes=data.get("notes"),
    )


def distance_lookup_from_dict(data: dict[str, Any]) -> DistanceLookup:
    return DistanceLookup(
        schema_version=str(data["schema_version"]),
        lookup_profile_id=str(data["lookup_profile_id"]),
        semantics=str(data["semantics"]),
        distance_unit=str(data["distance_unit"]),
        pdl_support=tuple(
            lookup_pdl_support_from_dict(item) for item in data.get("pdl_support", ())
        ),
        source=dict(data["source"]),
        rules=tuple(lookup_rule_from_dict(rule) for rule in data["rules"]),
    )


def load_stage2_input(path: str | Path) -> Stage2Input:
    return stage2_input_from_dict(load_json(path))


def load_distance_lookup(path: str | Path) -> DistanceLookup:
    return distance_lookup_from_dict(load_json(path))
