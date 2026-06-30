from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pcv_stage2.frame1051_metadata_bridge import (  # noqa: E402
    MetadataBridgeError,
    build_frame1051_candidate_catalog,
    inspection_summary,
    write_catalog,
)


DEFAULT_OUTPUT = ROOT / "outputs" / "frame1051_candidate_metadata_catalog.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a metadata-only frame 1051 candidate catalog from a local "
            "pcv-stage2-data-prep root. The script reads only JSON manifests and "
            "uses file stat sizes; it does not read PLY/DRC payload bytes."
        )
    )
    parser.add_argument(
        "--data-prep-root",
        required=True,
        type=Path,
        help="Local pcv-stage2-data-prep repository root.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Catalog output path. Defaults to allocation outputs/.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Validate and print the inspection summary without writing catalog JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        catalog = build_frame1051_candidate_catalog(args.data_prep_root)
        if not args.no_write:
            write_catalog(args.output, catalog)
        print(inspection_summary(catalog, None if args.no_write else args.output))
        return 0
    except MetadataBridgeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
