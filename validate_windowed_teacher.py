"""Validation for `offline_teacher_groups_windowed`: the windowed,
linear-in-N approximation of the exact teacher DP, built for venue-scale
MBS populations (stadium/concert-scale, thousands of subscribers) where the
monolithic `offline_teacher_groups_fast` becomes impractical.

Two things are measured, not assumed:
1. Quality gap: at a scale where the monolithic exact DP is still feasible,
   how much utility does windowing give up relative to the true global
   optimum, and how does that gap depend on window_size?
2. Scaling: at venue scale (thousands to tens of thousands of users), is the
   windowed DP's runtime actually linear and actually fast enough to be
   useful?
"""

from __future__ import annotations

import time

import numpy as np

import le_gra_mvp as mvp


def quality_gap_study() -> None:
    print("=== Quality gap: windowed vs monolithic exact DP ===")
    print("(monolithic DP is only run at scales where it stays fast)")
    seeds = [1, 2, 3, 4, 5]
    n_users_values = [60, 100, 150]
    window_sizes = [15, 25, 50]
    kmax = 4
    switch_beta = 0.5

    for n_users in n_users_values:
        # Build the scenarios and the (expensive) full-DP result ONCE per
        # seed, then reuse across all window_size choices for that n_users.
        scenarios = []
        full_utilities = []
        for seed in seeds:
            mvp.set_seed(seed * 97 + n_users)
            scenario = mvp.generate_scenario(n_users, 100, "mid", "ambiguous", rb_budget_ratio=0.25)
            full_groups = mvp.offline_teacher_groups_fast(scenario, kmax, switch_beta)
            full_utilities.append(mvp.allocate_and_evaluate(full_groups, scenario, switch_beta).utility)
            scenarios.append(scenario)

        for window_size in window_sizes:
            if window_size > n_users:
                continue
            gaps = []
            for scenario, full_utility in zip(scenarios, full_utilities):
                windowed_groups = mvp.offline_teacher_groups_windowed(scenario, kmax, switch_beta, window_size)
                windowed_utility = mvp.allocate_and_evaluate(windowed_groups, scenario, switch_beta).utility
                gaps.append(full_utility - windowed_utility)
            gaps = np.array(gaps)
            print(
                f"n_users={n_users:4d} window_size={window_size:3d}: "
                f"mean_gap={gaps.mean():+.5f} max_gap={gaps.max():+.5f} "
                f"(relative to full utility ~0.6-0.8, n_windows~{-(-n_users // window_size)})"
            )


def scaling_study() -> None:
    print("\n=== Scaling at venue scale (aligned mode: fully vectorized generation) ===")
    kmax_per_window = 3
    switch_beta = 0.5
    window_size = 150
    for n_users in [1000, 5000, 20000, 50000]:
        mvp.set_seed(7)
        t0 = time.perf_counter()
        scenario = mvp.generate_scenario(n_users, 100, "mid", "aligned", rb_budget_ratio=0.25)
        t1 = time.perf_counter()
        groups = mvp.offline_teacher_groups_windowed(scenario, kmax_per_window, switch_beta, window_size)
        t2 = time.perf_counter()
        result = mvp.allocate_and_evaluate(groups, scenario, switch_beta)
        t3 = time.perf_counter()
        print(
            f"n_users={n_users:6d}: generate={t1 - t0:.2f}s windowed_dp={t2 - t1:.2f}s "
            f"evaluate={t3 - t2:.2f}s utility={result.utility:.5f} n_groups={len(groups)}"
        )


if __name__ == "__main__":
    quality_gap_study()
    scaling_study()
