"""P3.2 acceptance test for SUMO mobility + normalized Simu5G radio join."""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp
from simu5g_trace_io import build_trace_bundle
from sumo_mobility_io import export_mobility_staging
from trace_io import load_trace_bundle


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-dir", type=Path, default=Path("p3_2_fixture"))
    parser.add_argument("--work-dir", type=Path, default=Path("p3_2_join_test"))
    args = parser.parse_args()
    mobility_dir, bundle_dir = args.work_dir / "mobility", args.work_dir / "bundle"
    export_mobility_staging(
        args.fixture_dir / "mobility.fcd.xml",
        args.fixture_dir / "gnbs.csv",
        mobility_dir,
    )
    stats = build_trace_bundle(mobility_dir, args.fixture_dir, bundle_dir, min_users=2)
    expected = {"scenarios": 2, "users": 4, "rb_rows": 16, "dropped_warmup_user_rows": 8}
    if stats != expected:
        raise AssertionError(f"Unexpected join stats: {stats}")
    scenarios = load_trace_bundle(bundle_dir, feature_mode="history_cost_quality")
    if len(scenarios) != 2:
        raise AssertionError("Expected two post-warmup scenarios")
    if scenarios[0].cqi_history.tolist() != [[8, 9, 10, 11, 12], [10, 9, 8, 7, 6]]:
        raise AssertionError(f"CQI history join failed: {scenarios[0].cqi_history}")
    if scenarios[0].rb_rates.shape != (2, 4) or scenarios[1].rb_available != 2:
        raise AssertionError("RB matrix or time-varying budget was not preserved")
    if scenarios[0].features.shape[1] != 12:
        raise AssertionError("history_cost_quality features were not reconstructed")
    for scenario in scenarios:
        groups = mvp.offline_teacher_groups(scenario, 2, 0.5)
        utility = mvp.allocate_and_evaluate(groups, scenario, 0.5).utility
        if not np.isfinite(utility):
            raise AssertionError("Teacher failed on joined trace")

    invalid_dir = args.work_dir / "invalid_radio"
    if invalid_dir.exists():
        shutil.rmtree(invalid_dir)
    shutil.copytree(args.fixture_dir, invalid_dir)
    rb_path = invalid_dir / "radio_rbs.csv"
    with rb_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    with rb_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows[:-1])
    try:
        build_trace_bundle(mobility_dir, invalid_dir, args.work_dir / "invalid_bundle", min_users=2)
    except ValueError as error:
        if "Incomplete RB vector" not in str(error):
            raise
    else:
        raise AssertionError("Incomplete Simu5G RB vector was silently accepted")
    print(
        "P3.2 PASS: mobility/radio join, five-step CQI history, Simu5G serving "
        "state, RB matrices, budgets, full-bundle loading, teacher execution, "
        "and incomplete-RB rejection verified",
        flush=True,
    )


if __name__ == "__main__":
    main()
