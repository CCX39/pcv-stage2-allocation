from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pcv_stage2.frame1051_behavior_pilot import (  # noqa: E402
    DEFAULT_PROFILE_PATH,
    BehaviorPilotError,
    behavior_pilot_console_summary,
    load_behavior_pilot_profile,
    profile_fingerprint,
    run_behavior_pilot,
    write_behavior_pilot_outputs,
)
from pcv_stage2.frame1051_metadata_bridge import (  # noqa: E402
    MetadataBridgeError,
    build_frame1051_candidate_catalog,
)


DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "frame1051_behavior_pilot"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Phase 2B.4 frame 1051 solver behavior pilot. The runner "
            "builds a metadata-only catalog via the read-only bridge, maps it "
            "through an explicit proxy profile, and writes all real outputs to "
            "an ignored output directory."
        )
    )
    parser.add_argument(
        "--data-prep-root",
        required=True,
        type=Path,
        help="Local pcv-stage2-data-prep repository root.",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=ROOT / DEFAULT_PROFILE_PATH,
        help="Version-controlled behavior pilot profile JSON.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Ignored directory for catalog snapshot, Stage2Input snapshots, results, and report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        profile = load_behavior_pilot_profile(args.profile)
        catalog = build_frame1051_candidate_catalog(args.data_prep_root)
        run = run_behavior_pilot(
            catalog,
            profile,
            profile_fingerprint_info=profile_fingerprint(args.profile),
        )
        write_behavior_pilot_outputs(args.output_dir, run)
        print(behavior_pilot_console_summary(run["report"], args.output_dir))
        return 0
    except (BehaviorPilotError, MetadataBridgeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
