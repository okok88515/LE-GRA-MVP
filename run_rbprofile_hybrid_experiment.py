"""Does adding a THIRD candidate family -- clustering on per-RB rate PROFILE
SHAPE (rb_stats: mean/min/max/std), not just CQI + resource-cost -- help
beyond `cqi_resource_hybrid_kmeans_grouping`?

Hypothesis: in `scenario_mode="aligned"` (used throughout the dispersion-
stratified slides), rb_rates is literally `cqi_now + noise`, so there's no
genuine frequency-selective structure for an RB-profile candidate to exploit
-- it should add little there. It should matter more in `"ambiguous"` mode,
which deliberately gives users the SAME wideband CQI but DIFFERENT per-RB
profile shapes (see `generate_cqi_ambiguous_rb_cqi` in le_gra_mvp.py) -- the
kind of structural blind spot CQI/resource-cost's SCALAR representations
can't see but a profile-SHAPE clustering might.

Tests both `scenario_mode`s x {mid_v2, high} dispersion (skips low --
established ceiling effect there dominates regardless of method) x 4
methods: CQI k-means (today's baseline), the 2-way hybrid (CQI+resource-cost,
already validated to beat CQI at all dispersions in aligned mode), the new
3-way hybrid (+ RB-profile), and Multi-feature k-means for reference (it
already sees rb_stats as part of its "full" feature mode, so it's the
closest existing baseline to what the 3-way hybrid should beat if RB-profile
information is genuinely useful here).
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp
from run_standard_matrix import LOAD_RATIOS

KMAX = 3
SWITCH_BETA = 0.5
KMEANS_N_INIT = 10
USERS = 150
RBS = 100
RB_BUDGET_RATIO = LOAD_RATIOS["medium"]
SCENARIO_MODES = ["aligned", "ambiguous"]
DISPERSIONS = ["mid_v2", "high"]
SEEDS = list(range(1, 31))
SCENARIOS_PER_SEED = 20
OUT_DIR = Path("rbprofile_hybrid_experiment_results")

METHODS = {
    "CQI k-means": lambda s: mvp.cqi_kmeans_grouping(s, KMAX, SWITCH_BETA, KMEANS_N_INIT),
    "Multi-feature k-means": lambda s: mvp.multi_feature_kmeans_grouping(
        s, KMAX, SWITCH_BETA, feature_mode="full", kmeans_n_init=KMEANS_N_INIT
    ),
    "CQI+cost hybrid (2-way)": lambda s: mvp.cqi_resource_hybrid_kmeans_grouping(s, KMAX, SWITCH_BETA, KMEANS_N_INIT),
    "CQI+cost+RBprofile hybrid (3-way)": lambda s: mvp.cqi_resource_rbprofile_hybrid_kmeans_grouping(
        s, KMAX, SWITCH_BETA, KMEANS_N_INIT
    ),
}


def progress(msg: str) -> None:
    print(msg, flush=True)


def main() -> None:
    rows = []
    for mode in SCENARIO_MODES:
        for dispersion in DISPERSIONS:
            for seed in SEEDS:
                mvp.set_seed(seed)
                random.seed(seed)
                scenarios = [
                    mvp.generate_scenario(USERS, RBS, dispersion, mode, rb_budget_ratio=RB_BUDGET_RATIO)
                    for _ in range(SCENARIOS_PER_SEED)
                ]
                for scenario_index, scenario in enumerate(scenarios):
                    for name, fn in METHODS.items():
                        groups = fn(scenario)
                        result = mvp.allocate_and_evaluate(groups, scenario, SWITCH_BETA)
                        rows.append({
                            "mode": mode, "dispersion": dispersion, "seed": seed,
                            "scenario_index": scenario_index, "method": name,
                            "utility": result.utility,
                        })
            progress(f"  mode={mode} dispersion={dispersion} done")

    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "per_scenario_results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    progress("\n=== Summary: mean utility, by mode x dispersion x method (vs CQI k-means) ===")
    summary_rows = []
    for mode in SCENARIO_MODES:
        for dispersion in DISPERSIONS:
            cell = [r for r in rows if r["mode"] == mode and r["dispersion"] == dispersion]
            cqi_u = np.array([r["utility"] for r in cell if r["method"] == "CQI k-means"])
            for name in METHODS:
                sub = [r for r in cell if r["method"] == name]
                u = np.array([r["utility"] for r in sub])
                diff = u - cqi_u
                summary_rows.append({
                    "mode": mode, "dispersion": dispersion, "method": name,
                    "mean_utility": float(u.mean()), "mean_diff_vs_cqi": float(diff.mean()),
                    "win": int((diff > 1e-9).sum()), "tie": int((np.abs(diff) <= 1e-9).sum()), "loss": int((diff < -1e-9).sum()),
                })
                progress(
                    f"  {mode:10s} {dispersion:7s} {name:36s} mean_utility={u.mean():+.4f} "
                    f"diff_vs_cqi={diff.mean():+.5f} win={int((diff>1e-9).sum())} "
                    f"tie={int((np.abs(diff)<=1e-9).sum())} loss={int((diff<-1e-9).sum())} (/{len(sub)})"
                )

    with open(OUT_DIR / "summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)
    progress(f"\nWrote results to {OUT_DIR}/")


if __name__ == "__main__":
    main()
