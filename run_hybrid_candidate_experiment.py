"""Does the user's published paper's actual method -- CQI k-means++ unioned
with resource-cost k-means++ candidates, picking whichever the exact-DP
allocator scores highest -- beat plain CQI k-means, across all three
dispersion levels (not just mid, as `run_adr_objective_experiment.py`
found for resource-cost-only clustering)?

`cqi_resource_hybrid_kmeans_grouping` (added 2026-08-25 to le_gra_mvp.py)
implements this: k-means++ seeding (not this project's default plain-random
restart) on BOTH the CQI representation and the resource-cost representation,
unioned into one candidate pool, scored by the same exact-DP utility used
everywhere else. Same synthetic dispersion-stratified protocol as
`run_dispersion_metrics_breakdown_legra.py` (aligned mode, medium load =
run_standard_matrix.LOAD_RATIOS["medium"] = 0.25) for direct comparability.

Now reports all 5 non-fairness metrics (utility, adr_kbps, served_ratio,
average_quality, system_spectral_efficiency) plus fairness (Jain's index),
and includes the 3-way (+joint) and 4-way (+switching-state-aware) unions.
"Offline teacher (fast, cheap ceiling)" uses the cheap contiguity-restricted
DP, not the multikey-corrected version -- fine as a reference for these
non-utility metrics; for the utility metric specifically, use the separately
validated multikey values (see project memory `teacher-contiguity-limitation`)
since `_fast` is known to lose to heuristics at low dispersion there.
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
DISPERSIONS = ["low", "mid_v2", "high"]
SEEDS = list(range(1, 31))
SCENARIOS_PER_SEED = 20
OUT_DIR = Path("hybrid_candidate_experiment_results")

def _multi_feature_rep(s):
    rep = mvp.build_feature_matrix(s, "full")
    mean, std = rep.mean(axis=0), rep.std(axis=0) + 1e-6
    return ((rep - mean) / std).astype(np.float32)


METHODS = {
    "No grouping": lambda s: [list(range(len(s.cqi_now)))],
    "CQI k-means": lambda s: mvp.cqi_kmeans_grouping(s, KMAX, SWITCH_BETA, KMEANS_N_INIT),
    "CQI k-means (k-means++)": lambda s: mvp.best_kmeans_groups(
        s, s.cqi_now.reshape(-1, 1).astype(float), KMAX, SWITCH_BETA,
        kmeans_n_init=KMEANS_N_INIT, init="kmeans++",
    ),
    "Resource-cost k-means": lambda s: mvp.resource_cost_kmeans_grouping(s, KMAX, SWITCH_BETA, KMEANS_N_INIT),
    "Resource-cost k-means (k-means++)": lambda s: mvp.best_kmeans_groups(
        s, mvp.user_resource_cost_vector(s.rb_rates), KMAX, SWITCH_BETA,
        kmeans_n_init=KMEANS_N_INIT, init="kmeans++",
    ),
    "Multi-feature k-means": lambda s: mvp.multi_feature_kmeans_grouping(
        s, KMAX, SWITCH_BETA, feature_mode="full", kmeans_n_init=KMEANS_N_INIT
    ),
    "Multi-feature k-means (k-means++)": lambda s: mvp.best_kmeans_groups(
        s, _multi_feature_rep(s), KMAX, SWITCH_BETA, kmeans_n_init=KMEANS_N_INIT, init="kmeans++",
    ),
    "CQI+resource-cost joint k-means (single clustering)": lambda s: mvp.cqi_resource_joint_kmeans_grouping(
        s, KMAX, SWITCH_BETA, KMEANS_N_INIT
    ),
    "CQI+resource-cost hybrid (paper method, union)": lambda s: mvp.cqi_resource_hybrid_kmeans_grouping(
        s, KMAX, SWITCH_BETA, KMEANS_N_INIT
    ),
    "CQI+cost+joint 3-way union": lambda s: mvp.cqi_resource_joint_hybrid_kmeans_grouping(
        s, KMAX, SWITCH_BETA, KMEANS_N_INIT
    ),
    "CQI+cost+joint+switching 4-way union": lambda s: mvp.cqi_resource_switching_hybrid_kmeans_grouping(
        s, KMAX, SWITCH_BETA, KMEANS_N_INIT
    ),
    "Offline teacher (fast, cheap ceiling)": lambda s: mvp.offline_teacher_groups_fast(s, KMAX, SWITCH_BETA),
}


def progress(msg: str) -> None:
    print(msg, flush=True)


def main() -> None:
    rows = []
    for dispersion in DISPERSIONS:
        for seed in SEEDS:
            mvp.set_seed(seed)
            random.seed(seed)
            scenarios = [
                mvp.generate_scenario(USERS, RBS, dispersion, "aligned", rb_budget_ratio=RB_BUDGET_RATIO)
                for _ in range(SCENARIOS_PER_SEED)
            ]
            for scenario_index, scenario in enumerate(scenarios):
                for name, fn in METHODS.items():
                    groups = fn(scenario)
                    result = mvp.allocate_and_evaluate(groups, scenario, SWITCH_BETA)
                    rows.append({
                        "dispersion": dispersion, "seed": seed, "scenario_index": scenario_index,
                        "method": name, "utility": result.utility, "adr_kbps": result.adr_kbps,
                        "served_ratio": result.served_ratio, "average_quality": result.average_quality,
                        "system_spectral_efficiency": result.system_spectral_efficiency,
                        "fairness": result.fairness,
                    })
        progress(f"  dispersion={dispersion} done")

    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "per_scenario_results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    progress("\n=== Summary: mean utility & ADR, by dispersion x method (vs plain CQI k-means) ===")
    summary_rows = []
    for dispersion in DISPERSIONS:
        cell = [r for r in rows if r["dispersion"] == dispersion]
        cqi_u = np.array([r["utility"] for r in cell if r["method"] == "CQI k-means"])
        for name in METHODS:
            sub = [r for r in cell if r["method"] == name]
            u = np.array([r["utility"] for r in sub])
            adr = np.array([r["adr_kbps"] for r in sub])
            served = np.array([r["served_ratio"] for r in sub])
            quality = np.array([r["average_quality"] for r in sub])
            spectral = np.array([r["system_spectral_efficiency"] for r in sub])
            fair = np.array([r["fairness"] for r in sub])
            diff = u - cqi_u
            summary_rows.append({
                "dispersion": dispersion, "method": name,
                "mean_utility": float(u.mean()), "mean_adr_kbps": float(adr.mean()),
                "mean_served_ratio": float(served.mean()), "mean_average_quality": float(quality.mean()),
                "mean_system_spectral_efficiency": float(spectral.mean()),
                "mean_fairness": float(fair.mean()),
                "mean_diff_vs_cqi": float(diff.mean()),
                "win": int((diff > 1e-9).sum()), "tie": int((np.abs(diff) <= 1e-9).sum()), "loss": int((diff < -1e-9).sum()),
            })
            progress(
                f"  {dispersion:8s} {name:42s} utility={u.mean():+.4f} adr={adr.mean():8.1f} "
                f"served={served.mean():.4f} quality={quality.mean():.3f} spectral={spectral.mean():7.2f} fairness={fair.mean():.4f} "
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
