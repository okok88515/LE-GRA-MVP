"""Does multi-feature (or resource-cost) k-means beat CQI k-means once the
candidate-selection objective is swapped from the project's default
fairness-weighted log-utility to raw ADR?

User's hypothesis (2026-08-25): their published paper's method -- k-means++
clustering, then actually allocating resources to each k-candidate and
picking the partition with the highest REALIZED total utility -- beat CQI
k-means. That "build candidates, allocate, keep the best" mechanism is
exactly what `best_kmeans_groups` already does for CQI/resource-cost/multi-
feature k-means in this repo, and is conceptually close to "resource-cost":
it factors in the actual resource-allocation outcome, not just raw CQI
similarity. But under the CURRENT default objective (log-bitrate + fairness/
switching penalty), multi-feature does not reliably beat CQI (see project
memory `real-data-multiseed-baseline`, `teacher-contiguity-limitation`).

This script re-runs the SAME candidate-selection mechanism with the
objective swapped to `group_adr_value` (raw ADR, no fairness/switching term)
via `le_gra_mvp.py`'s new `value_fn` parameter on `best_kmeans_groups` /
`allocate_and_evaluate` (both additive, default behavior unchanged), and
reports each method under BOTH objectives so the comparison is apples to
apples:
  - "<method> (log-utility obj)"  -- today's default candidate selection
  - "<method> (ADR obj)"          -- candidates selected to maximize raw ADR

Same synthetic dispersion-stratified protocol as
`run_dispersion_metrics_breakdown_legra.py` (aligned mode, medium load =
`run_standard_matrix.LOAD_RATIOS["medium"]` = 0.25 -- that script imports
this constant rather than defining its own; a previous script in this
project mistakenly hardcoded 1.0 from a DIFFERENT sibling script's local
constant, see project memory `real-data-multiseed-baseline` for that
incident) so results are directly comparable to the existing
dispersion-breakdown slides.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp
from run_standard_matrix import LOAD_RATIOS  # matches run_dispersion_metrics_breakdown_legra.py's import

KMAX = 3
SWITCH_BETA = 0.5
KMEANS_N_INIT = 10
USERS = 150
RBS = 100
RB_BUDGET_RATIO = LOAD_RATIOS["medium"]
DISPERSIONS = ["low", "mid_v2", "high"]
SEEDS = list(range(1, 31))
SCENARIOS_PER_SEED = 20
OUT_DIR = Path("adr_objective_experiment_results")


def representation_for(method: str, scenario: mvp.Scenario) -> np.ndarray:
    if method == "CQI k-means":
        return scenario.cqi_now.reshape(-1, 1).astype(float)
    if method == "Resource-cost k-means":
        return mvp.user_resource_cost_vector(scenario.rb_rates)
    if method == "Multi-feature k-means":
        rep = mvp.build_feature_matrix(scenario, "full")
        mean, std = rep.mean(axis=0), rep.std(axis=0) + 1e-6
        return ((rep - mean) / std).astype(np.float32)
    raise ValueError(method)


METHODS = ["No grouping", "CQI k-means", "Resource-cost k-means", "Multi-feature k-means"]
OBJECTIVES = {
    "log-utility": None,  # None -> allocate_and_evaluate's default (group_quality_value)
    "ADR": mvp.group_adr_value,
}


def groups_for(method: str, scenario: mvp.Scenario, value_fn) -> list[list[int]]:
    if method == "No grouping":
        return [list(range(len(scenario.cqi_now)))]
    rep = representation_for(method, scenario)
    return mvp.best_kmeans_groups(
        scenario, rep, KMAX, SWITCH_BETA, kmeans_n_init=KMEANS_N_INIT, value_fn=value_fn
    )


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
                for obj_name, value_fn in OBJECTIVES.items():
                    for method in METHODS:
                        groups = groups_for(method, scenario, value_fn)
                        # Always report BOTH the objective's own value and the
                        # fixed adr_kbps/utility(log) metrics for the SAME
                        # groups, so we can see what each objective trades off.
                        result_native = mvp.allocate_and_evaluate(groups, scenario, SWITCH_BETA, value_fn=value_fn)
                        result_log = mvp.allocate_and_evaluate(groups, scenario, SWITCH_BETA)  # default log-utility scoring of the SAME groups
                        rows.append({
                            "dispersion": dispersion, "seed": seed, "scenario_index": scenario_index,
                            "method": method, "objective": obj_name,
                            "adr_kbps": result_native.adr_kbps,
                            "log_utility": result_log.utility,
                        })
        progress(f"  dispersion={dispersion} done")

    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "per_scenario_results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    progress("\n=== Summary: mean ADR (kbps) and mean log-utility, by dispersion x objective x method ===")
    summary_rows = []
    for dispersion in DISPERSIONS:
        for obj_name in OBJECTIVES:
            cell = [r for r in rows if r["dispersion"] == dispersion and r["objective"] == obj_name]
            cqi_adr = np.mean([r["adr_kbps"] for r in cell if r["method"] == "CQI k-means"])
            for method in METHODS:
                sub = [r for r in cell if r["method"] == method]
                mean_adr = float(np.mean([r["adr_kbps"] for r in sub]))
                mean_log_u = float(np.mean([r["log_utility"] for r in sub]))
                summary_rows.append({
                    "dispersion": dispersion, "objective": obj_name, "method": method,
                    "mean_adr_kbps": mean_adr, "mean_log_utility": mean_log_u,
                    "adr_vs_cqi_pct": 100.0 * mean_adr / cqi_adr if cqi_adr else float("nan"),
                })
                progress(
                    f"  {dispersion:8s} obj={obj_name:11s} {method:24s} "
                    f"mean_adr={mean_adr:8.1f} ({100.0*mean_adr/cqi_adr:6.1f}% of CQI)  mean_log_utility={mean_log_u:+.4f}"
                )

    with open(OUT_DIR / "summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)
    progress(f"\nWrote results to {OUT_DIR}/")


if __name__ == "__main__":
    main()
