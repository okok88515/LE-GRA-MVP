"""Paper-style dispersion breakdown: for each of low/mid/high CQI dispersion,
compare No grouping / CQI k-means / Resource-cost k-means / Multi-feature
k-means / Offline teacher across all 5 metrics, reporting each method's value
as a percentage of the best method in that cell -- mirroring
`Resource_Allocation_for_5G_..._k-means_Grouping_Method.pdf` Figure 4's
"percentage above each bar" style.

Why this script exists
-----------------------
The pooled metrics deck (`run_clean_resource_cost_validation.py` data) draws
`dispersion` randomly per scenario, which dilutes the dramatic collapse of
"No grouping" that only shows up at high dispersion (confirmed directly: at
aligned/medium load, no-grouping ADR is ~118% of CQI k-means at low
dispersion but only ~30% at high dispersion). This script controls dispersion
explicitly instead of averaging over it, matching the published paper's own
comparison structure.

Protocol (fixed before running)
--------------------------------
- scenario_mode: aligned only -- the mode whose RB-rate generation is a
  distance-driven, non-adversarial CQI profile, closest in spirit to the
  paper's own distance/pathloss-driven scenario (no hidden-family or
  corridor-general adversarial structure).
- dispersion: low, mid, high (le_gra_mvp.generate_scenario's own levels).
- load_level: medium only (rb_budget_ratio=0.25) -- fixed so this is a clean
  single-axis (dispersion) comparison, the same way the paper's Figure 4 only
  varies dispersion, not load, across its panels.
- methods: No grouping, CQI k-means, Resource-cost k-means, Multi-feature
  k-means, Offline teacher (exact DP). LE-GRA is NOT included here -- it
  would need a freshly trained model per dispersion level, which is out of
  scope for this pass; it already has its own (pooled) comparison elsewhere.
- users=24, rbs=100, Kmax=3, switch_beta=0.5, kmeans_n_init=10 (repo defaults).
- seeds: 30, scenarios_per_condition: 20 (600 scenarios per dispersion level,
  1800 total) -- enough for stable means without requiring training.

Output: per-scenario CSV plus a summary CSV with, for every
(dispersion, metric, method) cell, the mean value AND that mean as a
percentage of the best method's mean in that (dispersion, metric) cell.
"""

from __future__ import annotations

import argparse
import csv
import random
import time
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp
from run_standard_matrix import LOAD_RATIOS

DISPERSIONS = ["low", "mid_v2", "high"]
METRICS = ["utility", "adr_kbps", "served_ratio", "average_quality", "system_spectral_efficiency"]

METHODS = {
    "No grouping": lambda s, kmax, beta, n_init: [list(range(len(s.cqi_now)))],
    "CQI k-means": lambda s, kmax, beta, n_init: mvp.cqi_kmeans_grouping(s, kmax, beta, n_init),
    "Resource-cost k-means": lambda s, kmax, beta, n_init: mvp.resource_cost_kmeans_grouping(s, kmax, beta, n_init),
    "Multi-feature k-means": lambda s, kmax, beta, n_init: mvp.multi_feature_kmeans_grouping(
        s, kmax, beta, feature_mode="full", kmeans_n_init=n_init
    ),
    "Offline teacher": lambda s, kmax, beta, n_init: mvp.offline_teacher_groups_fast(s, kmax, beta),
}


def progress(message: str) -> None:
    print(message, flush=True)


def run_matrix(args) -> list[dict]:
    rows = []
    total_jobs = len(DISPERSIONS) * len(args.seeds)
    job = 0
    started = time.perf_counter()
    for dispersion in DISPERSIONS:
        for seed in args.seeds:
            job += 1
            progress(f"job {job}/{total_jobs} dispersion={dispersion} seed={seed} ({time.perf_counter() - started:.1f}s elapsed)")
            mvp.set_seed(seed)
            random.seed(seed)
            scenarios = [
                mvp.generate_scenario(
                    args.users, args.rbs, dispersion, "aligned", rb_budget_ratio=args.rb_budget_ratio
                )
                for _ in range(args.scenarios_per_condition)
            ]
            for scenario_index, scenario in enumerate(scenarios):
                for method_name, method_fn in METHODS.items():
                    groups = method_fn(scenario, args.kmax, args.switch_beta, args.kmeans_n_init)
                    result = mvp.allocate_and_evaluate(groups, scenario, args.switch_beta)
                    rows.append({
                        "dispersion": dispersion,
                        "seed": seed,
                        "scenario_index": scenario_index,
                        "method": method_name,
                        "utility": result.utility,
                        "adr_kbps": result.adr_kbps,
                        "served_ratio": result.served_ratio,
                        "average_quality": result.average_quality,
                        "system_spectral_efficiency": result.system_spectral_efficiency,
                    })
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict]) -> list[dict]:
    summary = []
    for dispersion in DISPERSIONS:
        cell = [r for r in rows if r["dispersion"] == dispersion]
        for metric in METRICS:
            means = {}
            for method in METHODS:
                vals = [r[metric] for r in cell if r["method"] == method]
                means[method] = float(np.mean(vals))
            best = max(means.values())
            for method in METHODS:
                pct = (means[method] / best * 100.0) if best != 0 else float("nan")
                summary.append({
                    "dispersion": dispersion,
                    "metric": metric,
                    "method": method,
                    "mean": means[method],
                    "pct_of_best": pct,
                })
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--users", type=int, default=50)
    parser.add_argument("--rbs", type=int, default=100)
    parser.add_argument("--kmax", type=int, default=3)
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--kmeans-n-init", type=int, default=10)
    parser.add_argument("--rb-budget-ratio", type=float, default=LOAD_RATIOS["medium"])
    parser.add_argument("--scenarios-per-condition", type=int, default=20)
    parser.add_argument("--seeds", nargs="+", type=int, default=list(range(1, 31)))
    parser.add_argument("--out-dir", type=Path, default=Path("dispersion_metrics_breakdown_results"))
    args = parser.parse_args()

    started = time.perf_counter()
    progress(
        f"Protocol: scenario_mode=aligned, dispersions={DISPERSIONS}, load=medium "
        f"(rb_budget_ratio={args.rb_budget_ratio}), seeds={len(args.seeds)}, "
        f"scenarios_per_condition={args.scenarios_per_condition}, methods={list(METHODS)}"
    )
    rows = run_matrix(args)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "per_scenario_results.csv", rows)

    summary = summarize(rows)
    write_csv(args.out_dir / "summary_pct_of_best.csv", summary)

    print("\n=== Summary: mean and % of best method, by dispersion x metric ===")
    for dispersion in DISPERSIONS:
        print(f"\n-- dispersion={dispersion} --")
        for metric in METRICS:
            print(f"  {metric}:")
            for r in summary:
                if r["dispersion"] == dispersion and r["metric"] == metric:
                    print(f"    {r['method']:24s} mean={r['mean']:10.4f}  {r['pct_of_best']:6.2f}% of best")

    progress(f"\nDone in {time.perf_counter() - started:.1f}s. Wrote {args.out_dir}/")


if __name__ == "__main__":
    main()
