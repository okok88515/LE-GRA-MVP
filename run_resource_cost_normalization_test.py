"""Phase 5 confirmatory test: does z-score normalizing the resource-cost
per-tier feature (before k-means) fix its regime-dependent heavy-load losses?

Why this script exists
-----------------------
`run_dispersion_confirmatory_validation.py` found that raw
`resource_cost_kmeans_grouping` beats CQI k-means significantly under
high-dispersion + light load (+2.4%/+2.7% mean utility) but loses
significantly worse under high-dispersion + heavy load (-11.7%/-14.8%).
Inspecting `user_resource_cost_vector`'s output showed why: the per-tier
RB-cost has cross-user std of ~0.2 at the cheapest quality tier vs ~22.7 at
the most expensive tier (~100x), and `resource_cost_kmeans_grouping` feeds
this raw, unnormalized 6-D vector directly into k-means's Euclidean-distance
clustering -- so the partition is driven almost entirely by cross-user
differences at the *most expensive* tier, even though under heavy load only
the *cheapest* 1-2 tiers are ever reachable. A constructed 4-user toy example
confirmed this mechanism directly with the repo's own `kmeans()` call.

This script tests the fix predicted by that mechanism:
`resource_cost_kmeans_grouping_normalized` (added in `le_gra_mvp.py` right
after `resource_cost_kmeans_grouping`) z-scores each of the 6 tier-cost
dimensions across users, within the scenario, before clustering -- the same
normalization `multi_feature_kmeans_grouping` already applies. If the
diagnosis is correct, normalizing should recover most or all of the heavy-load
loss without erasing the light-load win (since normalization only reweights
the tiers' relative influence on distance, it does not remove tier-1/2
information, which was always present in the vector, just swamped).

Pre-registered protocol
------------------------
- dispersion: high only (fixed -- the regime where the raw effect was
  significant in both directions; this script isolates the load interaction,
  not the dispersion interaction, which is already characterized).
- scenario_mode: {aligned, ambiguous} (same two modes as the prior script).
- load_level: {light, medium, heavy}.
- seeds: same 6 as prior scripts (9, 17, 23, 31, 42, 58); 120 scenarios per
  (mode, load, seed) cell -- same budget as
  `run_dispersion_confirmatory_validation.py` for direct comparability.
- Kmax=3, switch_beta=0.5, users=24, rbs=100 (repo defaults).
- Methods: CQI k-means, Resource-cost k-means (raw), Resource-cost k-means
  (normalized).

Primary confirmatory test: for each of the 6 (mode, load) cells, paired
bootstrap mean of (normalized - raw) and (normalized - cqi), Holm-corrected
across all 12 tests. A positive, significant (normalized - raw) in the heavy
cells with no corresponding new loss in the light cells (i.e. normalized
stays close to or above cqi where raw already won) supports the fix.
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

MODES = ["aligned", "ambiguous"]
DEFAULT_SEEDS = [9, 17, 23, 31, 42, 58]

METHODS = {
    "CQI k-means": lambda s, kmax, beta, n_init: mvp.cqi_kmeans_grouping(s, kmax, beta, n_init),
    "Resource-cost k-means (raw)": lambda s, kmax, beta, n_init: mvp.resource_cost_kmeans_grouping(
        s, kmax, beta, n_init
    ),
    "Resource-cost k-means (normalized)": lambda s, kmax, beta, n_init: mvp.resource_cost_kmeans_grouping_normalized(
        s, kmax, beta, n_init
    ),
}


def progress(message: str) -> None:
    print(message, flush=True)


def run_matrix(args) -> list[dict]:
    rows = []
    total_jobs = len(MODES) * len(args.load_levels) * len(args.seeds)
    job = 0
    started = time.perf_counter()
    for scenario_mode in MODES:
        for load_level in args.load_levels:
            rb_budget_ratio = LOAD_RATIOS[load_level]
            for seed in args.seeds:
                job += 1
                progress(
                    f"job {job}/{total_jobs} mode={scenario_mode} load={load_level} seed={seed} "
                    f"({time.perf_counter() - started:.1f}s elapsed)"
                )
                mvp.set_seed(seed)
                random.seed(seed)
                scenarios = [
                    mvp.generate_scenario(
                        args.users, args.rbs, "high", scenario_mode, rb_budget_ratio=rb_budget_ratio
                    )
                    for _ in range(args.scenarios_per_condition)
                ]
                for scenario_index, scenario in enumerate(scenarios):
                    for method_name, method_fn in METHODS.items():
                        groups = method_fn(scenario, args.kmax, args.switch_beta, args.kmeans_n_init)
                        result = mvp.allocate_and_evaluate(groups, scenario, args.switch_beta)
                        rows.append(
                            {
                                "scenario_mode": scenario_mode,
                                "load_level": load_level,
                                "seed": seed,
                                "scenario_index": scenario_index,
                                "method": method_name,
                                "utility": result.utility,
                            }
                        )
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


def bootstrap_ci(diffs: np.ndarray, n_boot: int, rng: np.random.Generator) -> tuple[float, float, float, float]:
    if len(diffs) == 0:
        return float("nan"), float("nan"), float("nan"), float("nan")
    mean = float(diffs.mean())
    n = len(diffs)
    boot_means = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        boot_means[i] = diffs[rng.integers(0, n, size=n)].mean()
    lo, hi = np.percentile(boot_means, [2.5, 97.5])
    p_pos = float(np.mean(boot_means <= 0.0))
    p_neg = float(np.mean(boot_means >= 0.0))
    return mean, float(lo), float(hi), float(min(1.0, 2.0 * min(p_pos, p_neg)))


def holm_correction(p_values: list[float]) -> list[float]:
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    adjusted = [0.0] * len(p_values)
    running_max = 0.0
    for rank, idx in enumerate(order):
        adj = (len(p_values) - rank) * p_values[idx]
        running_max = max(running_max, adj)
        adjusted[idx] = min(1.0, running_max)
    return adjusted


def cell_table(rows: list[dict], comparisons: list[tuple], n_boot: int, rng: np.random.Generator) -> list[dict]:
    records = []
    p_values = []
    cells = [(m, l) for m in MODES for l in sorted({r["load_level"] for r in rows})]
    for label, method_a, method_b in comparisons:
        for scenario_mode, load_level in cells:
            cell_rows = [
                r for r in rows if r["scenario_mode"] == scenario_mode and r["load_level"] == load_level
            ]
            by_unit: dict[tuple, dict] = {}
            for row in cell_rows:
                unit = (row["seed"], row["scenario_index"])
                by_unit.setdefault(unit, {})[row["method"]] = row["utility"]
            diffs = np.array(
                [v[method_a] - v[method_b] for v in by_unit.values() if method_a in v and method_b in v],
                dtype=float,
            )
            mean, lo, hi, p = bootstrap_ci(diffs, n_boot, rng)
            cqi_mean = float(np.mean([v["CQI k-means"] for v in by_unit.values() if "CQI k-means" in v]))
            win_rate = float(np.mean(diffs > 0)) if len(diffs) else float("nan")
            records.append(
                {
                    "comparison": label,
                    "scenario_mode": scenario_mode,
                    "load_level": load_level,
                    "mean_diff_a_minus_b": mean,
                    "pct_of_cqi_mean": (mean / abs(cqi_mean) * 100.0) if cqi_mean else float("nan"),
                    "ci95_lo": lo,
                    "ci95_hi": hi,
                    "p_value_raw": p,
                    "p_value_holm": None,
                    "win_rate_a_over_b": win_rate,
                    "n": len(diffs),
                }
            )
            p_values.append(p)
    adjusted = holm_correction(p_values)
    for record, adj in zip(records, adjusted):
        record["p_value_holm"] = adj
    return records


def print_cell_table(label: str, records: list[dict]) -> None:
    print(f"\n=== {label} (Holm-corrected across all cells+comparisons in this table) ===")
    for r in records:
        sig = "significant" if r["p_value_holm"] < 0.05 else "not significant"
        print(
            f"{r['comparison']:38s} mode={r['scenario_mode']:9s} load={r['load_level']:6s}: "
            f"mean(a-b)={r['mean_diff_a_minus_b']:+.5f} ({r['pct_of_cqi_mean']:+.2f}% of CQI mean) "
            f"95% CI=[{r['ci95_lo']:+.5f},{r['ci95_hi']:+.5f}] holm_p={r['p_value_holm']:.4f} ({sig}) "
            f"win_rate={r['win_rate_a_over_b']:.3f} n={r['n']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--users", type=int, default=24)
    parser.add_argument("--rbs", type=int, default=100)
    parser.add_argument("--kmax", type=int, default=3)
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--kmeans-n-init", type=int, default=10)
    parser.add_argument("--load-levels", nargs="+", choices=list(LOAD_RATIOS), default=["light", "medium", "heavy"])
    parser.add_argument("--scenarios-per-condition", type=int, default=120)
    parser.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--n-boot", type=int, default=10000)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    parser.add_argument("--out-dir", type=Path, default=Path("resource_cost_normalization_test_results"))
    args = parser.parse_args()

    started = time.perf_counter()
    progress(
        f"Pre-registered protocol: dispersion=high, scenario_modes={MODES}, load_levels={args.load_levels}, "
        f"kmax={args.kmax}, seeds={args.seeds}, scenarios_per_condition={args.scenarios_per_condition}"
    )
    rows = run_matrix(args)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "per_scenario_results.csv", rows)

    rng = np.random.default_rng(args.bootstrap_seed)
    comparisons = [
        ("normalized_vs_raw", "Resource-cost k-means (normalized)", "Resource-cost k-means (raw)"),
        ("normalized_vs_cqi", "Resource-cost k-means (normalized)", "CQI k-means"),
        ("raw_vs_cqi", "Resource-cost k-means (raw)", "CQI k-means"),
    ]
    records = cell_table(rows, comparisons, args.n_boot, rng)
    print_cell_table("PRIMARY: does normalizing the resource-cost feature fix the heavy-load loss?", records)
    write_csv(args.out_dir / "normalization_comparison.csv", records)

    progress(f"Done in {time.perf_counter() - started:.1f}s. Wrote {args.out_dir}/")


if __name__ == "__main__":
    main()
