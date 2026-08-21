"""Quantify the real cost of the "Offline teacher" contiguity assumption.

`offline_teacher_groups`/`offline_teacher_groups_fast` are only exact within
contiguous-by-sort-key partitions, not a true global optimum (see project
memory `teacher-contiguity-limitation`, found by inspecting the actual source
and a case study on `dispersion_metrics_breakdown_legra_n150_results`, where
"teacher" lost on its OWN utility metric in 600/600 low-dispersion scenarios).

This script compares, at small user counts where a true brute-force over ALL
partitions is tractable:
  - fast      = offline_teacher_groups_fast          (contiguous by resource cost)
  - multikey  = offline_teacher_groups_multikey       (best of a few sort-key DPs)
  - exact     = offline_teacher_groups_bruteforce_exact (true global optimum)

Reports, per (n_users, dispersion): how often `fast` strictly loses to `exact`,
the average utility gap, and how often `multikey` fully closes that gap.
"""

from __future__ import annotations

import argparse
import random
import time
from pathlib import Path

import le_gra_mvp as mvp
from run_standard_matrix import LOAD_RATIOS  # matches run_dispersion_metrics_breakdown_legra.py's import

DISPERSIONS = ["low", "mid_v2", "high"]

# Fewer seeds as n grows, since bruteforce cost explodes combinatorially.
N_TO_SEEDS = {
    6: 30,
    8: 20,
    10: 10,
    12: 5,
}


def progress(msg: str) -> None:
    print(msg, flush=True)


def run(args) -> list[dict]:
    rows = []
    started = time.perf_counter()
    for n_users in args.n_values:
        n_seeds = N_TO_SEEDS.get(n_users, 5)
        for dispersion in DISPERSIONS:
            for seed in range(1, n_seeds + 1):
                mvp.set_seed(seed)
                random.seed(seed)
                scenario = mvp.generate_scenario(
                    n_users, args.rbs, dispersion, "aligned", rb_budget_ratio=args.rb_budget_ratio
                )

                fast_groups = mvp.offline_teacher_groups_fast(scenario, args.kmax, args.switch_beta)
                fast_utility = mvp.allocate_and_evaluate(fast_groups, scenario, args.switch_beta).utility

                multikey_groups = mvp.offline_teacher_groups_multikey(scenario, args.kmax, args.switch_beta)
                multikey_utility = mvp.allocate_and_evaluate(multikey_groups, scenario, args.switch_beta).utility

                exact_groups = mvp.offline_teacher_groups_bruteforce_exact(scenario, args.kmax, args.switch_beta)
                exact_utility = mvp.allocate_and_evaluate(exact_groups, scenario, args.switch_beta).utility

                rows.append({
                    "n_users": n_users,
                    "dispersion": dispersion,
                    "seed": seed,
                    "fast_utility": fast_utility,
                    "multikey_utility": multikey_utility,
                    "exact_utility": exact_utility,
                    "fast_loses": fast_utility < exact_utility - 1e-9,
                    "multikey_matches_exact": abs(multikey_utility - exact_utility) < 1e-9,
                })
            elapsed = time.perf_counter() - started
            progress(f"  n={n_users} dispersion={dispersion} done ({elapsed:.1f}s elapsed)")
    return rows


def summarize(rows: list[dict]) -> list[dict]:
    summary = []
    keys = sorted({(r["n_users"], r["dispersion"]) for r in rows})
    for n_users, dispersion in keys:
        cell = [r for r in rows if r["n_users"] == n_users and r["dispersion"] == dispersion]
        n = len(cell)
        fast_loses_pct = 100.0 * sum(r["fast_loses"] for r in cell) / n
        multikey_matches_pct = 100.0 * sum(r["multikey_matches_exact"] for r in cell) / n
        avg_fast_gap_pct = 100.0 * sum(
            (r["exact_utility"] - r["fast_utility"]) / r["exact_utility"] for r in cell
        ) / n
        avg_multikey_gap_pct = 100.0 * sum(
            (r["exact_utility"] - r["multikey_utility"]) / r["exact_utility"] for r in cell
        ) / n
        summary.append({
            "n_users": n_users,
            "dispersion": dispersion,
            "n_scenarios": n,
            "fast_loses_pct": fast_loses_pct,
            "avg_fast_utility_gap_pct": avg_fast_gap_pct,
            "multikey_matches_exact_pct": multikey_matches_pct,
            "avg_multikey_utility_gap_pct": avg_multikey_gap_pct,
        })
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n-values", nargs="+", type=int, default=[6, 8, 10, 12])
    parser.add_argument("--rbs", type=int, default=100)
    parser.add_argument("--kmax", type=int, default=3)
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--rb-budget-ratio", type=float, default=LOAD_RATIOS["medium"])
    parser.add_argument("--out-dir", type=Path, default=Path("contiguity_validation_results"))
    args = parser.parse_args()

    started = time.perf_counter()
    progress(f"Protocol: n_values={args.n_values}, dispersions={DISPERSIONS}, seeds_per_n={N_TO_SEEDS}")
    rows = run(args)
    summary = summarize(rows)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    import csv

    with open(args.out_dir / "per_scenario_results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    with open(args.out_dir / "summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)

    progress(f"\nDone in {time.perf_counter() - started:.1f}s. Summary:")
    for row in summary:
        progress(
            f"  n={row['n_users']:>3} {row['dispersion']:8s}: "
            f"fast_loses={row['fast_loses_pct']:5.1f}% avg_fast_gap={row['avg_fast_utility_gap_pct']:5.2f}% "
            f"multikey_matches_exact={row['multikey_matches_exact_pct']:5.1f}% avg_multikey_gap={row['avg_multikey_utility_gap_pct']:5.2f}%"
        )


if __name__ == "__main__":
    main()
