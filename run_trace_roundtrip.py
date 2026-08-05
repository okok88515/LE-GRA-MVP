"""P3.0 acceptance test: Scenario -> CSV bundle -> Scenario."""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp
from trace_io import export_trace_bundle, load_trace_bundle


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", type=int, default=6)
    parser.add_argument("--users", type=int, default=24)
    parser.add_argument("--rbs", type=int, default=100)
    parser.add_argument("--kmax", type=int, default=3)
    parser.add_argument("--seed", type=int, default=9)
    parser.add_argument("--out-dir", type=Path, default=Path("p3_0_roundtrip_bundle"))
    args = parser.parse_args()

    mvp.set_seed(args.seed)
    source = [
        mvp.generate_scenario(
            args.users,
            args.rbs,
            random.choice(["high", "mid", "low"]),
            "ambiguous",
            rb_budget_ratio=0.25 if index % 2 else 0.50,
        )
        for index in range(args.scenarios)
    ]
    export_trace_bundle(
        source,
        args.out_dir,
        timestamps_s=[0.1 * index for index in range(args.scenarios)],
        serving_gnbs=["gnb_0"] * args.scenarios,
    )
    restored = load_trace_bundle(args.out_dir, feature_mode="history_cost_quality")
    if len(source) != len(restored):
        raise AssertionError("Scenario count changed during round trip")

    max_abs_error = 0.0
    for index, (before, after) in enumerate(zip(source, restored)):
        for name in (
            "cqi_history", "cqi_now", "rb_rates", "previous_quality",
            "distance", "speed", "direction_to_gnb",
        ):
            error = float(np.max(np.abs(getattr(before, name) - getattr(after, name))))
            max_abs_error = max(max_abs_error, error)
            if error != 0.0:
                raise AssertionError(f"{name} changed in scenario {index}: {error}")
        if before.rb_available != after.rb_available:
            raise AssertionError(f"RB budget changed in scenario {index}")

        before_groups = mvp.offline_teacher_groups(before, args.kmax, 0.5)
        after_groups = mvp.offline_teacher_groups(after, args.kmax, 0.5)
        if before_groups != after_groups:
            raise AssertionError(f"Teacher partition changed in scenario {index}")
        before_utility = mvp.allocate_and_evaluate(before_groups, before, 0.5).utility
        after_utility = mvp.allocate_and_evaluate(after_groups, after, 0.5).utility
        if before_utility != after_utility:
            raise AssertionError(f"Teacher utility changed in scenario {index}")
        print(
            f"scenario={index + 1}/{args.scenarios}, K={len(before_groups)}, "
            f"utility={before_utility:.6f}, roundtrip=exact",
            flush=True,
        )

    print(
        f"P3.0 PASS: {args.scenarios} scenarios round-tripped exactly; "
        f"max_abs_error={max_abs_error:.1f}",
        flush=True,
    )


if __name__ == "__main__":
    main()
