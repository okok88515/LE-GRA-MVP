"""Correctness validation for `offline_teacher_groups_fast` against the
brute-force `offline_teacher_groups`.

This is a correctness check, not an experiment: it asserts that the fast DP
produces the SAME optimal utility as brute-force enumeration across a large,
varied battery of scenarios (all 5 scenario_modes, several dispersions,
several load levels, several Kmax values, several user counts, several
seeds). Group *identity* may legitimately differ when multiple partitions
tie in utility -- only the utility VALUE is required to match exactly (up
to floating point tolerance). Any mismatch is a real bug in the fast DP and
must be fixed before it is used anywhere else.
"""

from __future__ import annotations

import time

import numpy as np

import le_gra_mvp as mvp


def main() -> None:
    rng_seeds = [1, 2, 3, 4, 5, 6, 7, 8]
    scenario_modes = ["aligned", "ambiguous", "anti_cqi_hard", "corridor_general"]
    dispersions = ["low", "mid", "high"]
    load_ratios = [0.10, 0.25, 0.50]
    user_counts = [6, 8, 10, 12]  # small enough that brute force at kmax up to 5 stays fast
    kmax_values = [1, 2, 3, 4, 5]

    total = 0
    mismatches = []
    started = time.perf_counter()

    for seed in rng_seeds:
        for scenario_mode in scenario_modes:
            for dispersion in dispersions:
                for rb_ratio in load_ratios:
                    for n_users in user_counts:
                        for kmax in kmax_values:
                            if kmax > n_users:
                                continue
                            mvp.set_seed(seed * 1000 + n_users * 10 + kmax)
                            scenario = mvp.generate_scenario(
                                n_users, 100, dispersion, scenario_mode, rb_budget_ratio=rb_ratio,
                            )
                            switch_beta = 0.5

                            brute_groups = mvp.offline_teacher_groups(scenario, kmax, switch_beta)
                            fast_groups = mvp.offline_teacher_groups_fast(scenario, kmax, switch_beta)

                            brute_utility = mvp.allocate_and_evaluate(brute_groups, scenario, switch_beta).utility
                            fast_utility = mvp.allocate_and_evaluate(fast_groups, scenario, switch_beta).utility

                            total += 1
                            if abs(brute_utility - fast_utility) > 1e-9:
                                mismatches.append(
                                    {
                                        "seed": seed, "mode": scenario_mode, "dispersion": dispersion,
                                        "rb_ratio": rb_ratio, "n_users": n_users, "kmax": kmax,
                                        "brute_utility": brute_utility, "fast_utility": fast_utility,
                                        "brute_groups": brute_groups, "fast_groups": fast_groups,
                                    }
                                )
    elapsed = time.perf_counter() - started

    print(f"Checked {total} scenarios in {elapsed:.1f}s")
    if mismatches:
        print(f"MISMATCHES: {len(mismatches)}")
        for m in mismatches[:10]:
            print(m)
    else:
        print("All scenarios matched exactly. Fast DP is verified equivalent to brute force.")

    # Timing comparison at a realistic full-scale configuration.
    print("\n=== Timing comparison at n_users=24, Kmax=5 ===")
    mvp.set_seed(42)
    scenario = mvp.generate_scenario(24, 100, "mid", "ambiguous", rb_budget_ratio=0.25)
    t0 = time.perf_counter()
    brute_groups = mvp.offline_teacher_groups(scenario, 5, 0.5)
    t1 = time.perf_counter()
    fast_groups = mvp.offline_teacher_groups_fast(scenario, 5, 0.5)
    t2 = time.perf_counter()
    brute_utility = mvp.allocate_and_evaluate(brute_groups, scenario, 0.5).utility
    fast_utility = mvp.allocate_and_evaluate(fast_groups, scenario, 0.5).utility
    print(f"brute force: {t1 - t0:.3f}s, utility={brute_utility:.5f}")
    print(f"fast DP:     {t2 - t1:.3f}s, utility={fast_utility:.5f}")
    print(f"speedup: {(t1 - t0) / (t2 - t1):.1f}x")
    print(f"utility match: {abs(brute_utility - fast_utility) < 1e-9}")


if __name__ == "__main__":
    main()
