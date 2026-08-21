"""Re-evaluate the n=150 dispersion breakdown's "Offline teacher" utility using
`offline_teacher_groups_multikey` (best of 3 sort-key DPs) instead of just
`offline_teacher_groups_fast` (resource-cost order only), and check how much
this closes the low-dispersion gap found in
`dispersion_metrics_breakdown_legra_n150_results` (see project memory
`teacher-contiguity-limitation`).

Regenerates the exact same scenarios as `run_dispersion_metrics_breakdown_legra.py`
(same seed protocol, users=150, aligned mode, medium load) so results line up
1:1 with the existing `per_scenario_results.csv`, reused here for the other
5 methods (No grouping / CQI / Resource-cost / Multi-feature / LE-GRA) so this
script does NOT need to retrain LE-GRA -- only the two teacher DP variants are
recomputed.
"""

from __future__ import annotations

import csv
import random
import time
from collections import defaultdict
from pathlib import Path

import le_gra_mvp as mvp
from run_standard_matrix import LOAD_RATIOS  # matches run_dispersion_metrics_breakdown_legra.py's import

DISPERSIONS = ["low", "mid_v2", "high"]
USERS = 150
RBS = 100
KMAX = 3
SWITCH_BETA = 0.5
SEEDS = list(range(1, 31))
SCENARIOS_PER_SEED = 20
SOURCE_CSV = Path("dispersion_metrics_breakdown_legra_n150_results/per_scenario_results.csv")
OUT_DIR = Path("teacher_multikey_full_scale_results")


def progress(msg: str) -> None:
    print(msg, flush=True)


def teacher_variants(scenario) -> dict[str, float]:
    """One pass over the 3 sort-key DP candidates: cost-order alone reproduces
    `offline_teacher_groups_fast`; the max over all 3 reproduces
    `offline_teacher_groups_multikey` -- computed together to avoid running
    the cost-order DP twice."""

    cost_vec = mvp.user_resource_cost_vector(scenario.rb_rates)
    cost_score = cost_vec.mean(axis=1)
    import numpy as np
    orders = {
        "cost": np.argsort(cost_score),
        "cqi": np.argsort(scenario.cqi_now),
        "cqi_then_cost": np.lexsort((cost_score, scenario.cqi_now)),
    }
    utilities = {}
    for key, order in orders.items():
        groups = mvp._offline_teacher_groups_fast_core(order, scenario.rb_available, scenario, KMAX, SWITCH_BETA)
        utilities[key] = mvp.allocate_and_evaluate(groups, scenario, SWITCH_BETA).utility
    return {
        "fast_utility": utilities["cost"],
        "multikey_utility": max(utilities.values()),
        "winning_key": max(utilities, key=utilities.get),
    }


def load_other_methods() -> dict[tuple, dict[str, float]]:
    by_scenario: dict[tuple, dict[str, float]] = defaultdict(dict)
    with open(SOURCE_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["method"] == "Offline teacher":
                continue  # replaced by fast_utility/multikey_utility computed fresh here
            key = (row["dispersion"], row["seed"], row["scenario_index"])
            by_scenario[key][row["method"]] = float(row["utility"])
    return by_scenario


def main() -> None:
    started = time.perf_counter()
    other_methods = load_other_methods()
    progress(f"Loaded cached utility for other methods: {len(other_methods)} scenario rows")

    rows = []
    for dispersion in DISPERSIONS:
        job_idx = 0
        for seed in SEEDS:
            mvp.set_seed(seed)
            random.seed(seed)
            scenarios = [
                mvp.generate_scenario(USERS, RBS, dispersion, "aligned", rb_budget_ratio=LOAD_RATIOS["medium"])
                for _ in range(SCENARIOS_PER_SEED)
            ]
            for scenario_index, scenario in enumerate(scenarios):
                job_idx += 1
                variants = teacher_variants(scenario)
                key = (dispersion, str(seed), str(scenario_index))
                others = other_methods.get(key, {})
                rows.append({
                    "dispersion": dispersion,
                    "seed": seed,
                    "scenario_index": scenario_index,
                    **variants,
                    **others,
                })
                if job_idx % 50 == 0:
                    progress(f"  [{dispersion}] {job_idx}/{len(SEEDS) * SCENARIOS_PER_SEED} "
                             f"({time.perf_counter() - started:.1f}s elapsed)")

    OUT_DIR.mkdir(exist_ok=True)
    fieldnames = list(rows[0].keys())
    with open(OUT_DIR / "per_scenario_results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Summary: for each dispersion, compare pct_of_best using fast vs multikey as "teacher".
    other_method_names = ["No grouping", "CQI k-means", "Resource-cost k-means", "Multi-feature k-means", "LE-GRA MVP"]
    progress("\n=== Summary (utility metric only) ===")
    summary_rows = []
    for dispersion in DISPERSIONS:
        cell = [r for r in rows if r["dispersion"] == dispersion]
        n = len(cell)
        fast_loses_pct = 100.0 * sum(
            1 for r in cell if r["fast_utility"] < max(r[m] for m in other_method_names) - 1e-9
        ) / n
        multikey_loses_pct = 100.0 * sum(
            1 for r in cell if r["multikey_utility"] < max(r[m] for m in other_method_names) - 1e-9
        ) / n
        mean_fast = sum(r["fast_utility"] for r in cell) / n
        mean_multikey = sum(r["multikey_utility"] for r in cell) / n
        mean_others = {m: sum(r[m] for r in cell) / n for m in other_method_names}
        best_other = max(mean_others.values())
        fast_pct_of_best = 100.0 * mean_fast / max(mean_fast, mean_multikey, best_other)
        multikey_pct_of_best = 100.0 * mean_multikey / max(mean_fast, mean_multikey, best_other)
        progress(
            f"  {dispersion:8s}: fast_loses={fast_loses_pct:5.1f}% multikey_loses={multikey_loses_pct:5.1f}%  "
            f"mean_fast={mean_fast:.4f}({fast_pct_of_best:.1f}%) mean_multikey={mean_multikey:.4f}({multikey_pct_of_best:.1f}%) "
            f"best_other={best_other:.4f}"
        )
        summary_rows.append({
            "dispersion": dispersion, "n_scenarios": n,
            "fast_loses_pct": fast_loses_pct, "multikey_loses_pct": multikey_loses_pct,
            "mean_fast_utility": mean_fast, "mean_multikey_utility": mean_multikey,
            "fast_pct_of_best": fast_pct_of_best, "multikey_pct_of_best": multikey_pct_of_best,
            "best_other_mean_utility": best_other,
        })

    with open(OUT_DIR / "summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    progress(f"\nDone in {time.perf_counter() - started:.1f}s")


if __name__ == "__main__":
    main()
