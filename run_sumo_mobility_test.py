"""P3.1 acceptance test using a deterministic SUMO FCD fixture."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from sumo_mobility_io import export_mobility_staging


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-dir", type=Path, default=Path("p3_1_fixture"))
    parser.add_argument("--out-dir", type=Path, default=Path("p3_1_mobility_staging"))
    args = parser.parse_args()
    scenarios, rows = export_mobility_staging(
        args.fixture_dir / "mobility.fcd.xml",
        args.fixture_dir / "gnbs.csv",
        args.out_dir,
    )
    if len(scenarios) != 4 or len(rows) != 7:
        raise AssertionError(f"Unexpected output size: {len(scenarios)} snapshots, {len(rows)} rows")
    if len({row["ue_id"] for row in rows}) != 4:
        raise AssertionError("Stable UE IDs were not preserved")
    veh0 = [row for row in rows if row["ue_id"] == "veh0"]
    if [row["trajectory_step"] for row in veh0] != [0, 1]:
        raise AssertionError("Trajectory steps are not stable across time")
    if not all(math.isclose(row["direction_to_gnb"], 1.0, abs_tol=1e-12) for row in veh0):
        raise AssertionError("Direction-to-gNB calculation is incorrect")
    veh1 = [row for row in rows if row["ue_id"] == "veh1"]
    if not all(math.isclose(row["direction_to_gnb"], -1.0, abs_tol=1e-12) for row in veh1):
        raise AssertionError("Moving-away direction was not encoded as -1")
    veh3 = next(row for row in rows if row["ue_id"] == "veh3")
    if veh3["direction_to_gnb"] != 0.0:
        raise AssertionError("Stopped UE direction must be 0")

    capped_scenarios, capped_rows = export_mobility_staging(
        args.fixture_dir / "mobility.fcd.xml",
        args.fixture_dir / "gnbs.csv",
        args.out_dir / "capped",
        min_users=2,
        max_users=2,
    )
    if len(capped_scenarios) != 3 or any(row["user_count"] != 2 for row in capped_scenarios):
        raise AssertionError("min/max user snapshot filtering is incorrect")
    if len(capped_rows) != 6:
        raise AssertionError("Capped mobility row count is incorrect")
    print(
        "P3.1 PASS: FCD parsing, nearest-gNB assignment, stable trajectories, "
        "direction, and deterministic user filtering verified",
        flush=True,
    )


if __name__ == "__main__":
    main()
