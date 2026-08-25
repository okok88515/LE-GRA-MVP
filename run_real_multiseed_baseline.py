"""CQI / resource-cost / multi-feature k-means comparison on the 10-seed real
Simu5G+SUMO+Veins multi-seed dataset (`real_simu5g_multiseed_data/`).

This is the seed-expanded successor to `run_real_data_validation.py` (which
ran the same comparison on a single real run per dispersion). Each run still
only yields 15 usable one-second snapshots (same limitation, see
`parse_real_simu5g_data.py`'s docstring) -- those 15 snapshots come from one
90s trajectory and are NOT independent samples. The independent unit here is
the SEED (10 per dispersion), not the snapshot (150 per dispersion). Every
statistic reported at the "seed" level (per_seed_summary.csv,
summary_across_seeds.csv) first averages within each seed's 15 snapshots,
then treats the resulting 10 numbers as the sample -- this project's own
completion doc explicitly warns against skipping that step
(`REAL_SIMU5G_DATA_COMPLETION.md`, "Remaining measurement limitations").

Per the project's own stated bar, 10 seeds is an "exploratory" sample (20
seeds is the stated "confirmatory" target) -- report point estimates and
win/tie/loss counts across seeds, not p-values or tight confidence
intervals.

LE-GRA is NOT evaluated here, same reason as the single-seed pass: 150
scenarios/dispersion is far short of the ~60-90 training scenarios the
synthetic protocol uses, nowhere near enough to train a model.

"Offline teacher" uses `offline_teacher_groups_multikey` (not
`_fast`) -- see project memory `teacher-contiguity-limitation`: the
cost-order-only DP is contiguity-restricted and demonstrably loses to
heuristics at low CQI dispersion; multikey closes that gap at ~3x the DP
cost, which is negligible at n_users=24.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp
from parse_real_simu5g_data import build_scenarios

KMAX = 3
SWITCH_BETA = 0.5
KMEANS_N_INIT = 10
SEEDS = [f"seed_{i:04d}" for i in range(1, 11)]
DISPERSIONS = ["low", "mid", "high"]
LOADS = [(0.50, "light"), (0.25, "medium"), (0.10, "heavy")]
DATA_ROOT = Path("real_simu5g_multiseed_data")
OUT_DIR = Path("real_multiseed_baseline_results")

METHODS = {
    "No grouping": lambda s: mvp.cqi_kmeans_grouping(s, 1, SWITCH_BETA, KMEANS_N_INIT),
    "CQI k-means": lambda s: mvp.cqi_kmeans_grouping(s, KMAX, SWITCH_BETA, KMEANS_N_INIT),
    "Resource-cost k-means": lambda s: mvp.resource_cost_kmeans_grouping(s, KMAX, SWITCH_BETA, KMEANS_N_INIT),
    "Multi-feature k-means": lambda s: mvp.multi_feature_kmeans_grouping(
        s, KMAX, SWITCH_BETA, feature_mode="full", kmeans_n_init=KMEANS_N_INIT
    ),
    "CQI+resource-cost hybrid (paper method)": lambda s: mvp.cqi_resource_hybrid_kmeans_grouping(
        s, KMAX, SWITCH_BETA, KMEANS_N_INIT
    ),
    "Offline teacher": lambda s: mvp.offline_teacher_groups_multikey(s, KMAX, SWITCH_BETA),
}


def progress(msg: str) -> None:
    print(msg, flush=True)


def run_all() -> list[dict]:
    rows = []
    for dispersion in DISPERSIONS:
        for seed in SEEDS:
            seed_dir = DATA_ROOT / dispersion / seed
            radio_path = seed_dir / "raw_radio.csv.gz"
            mobility_path = seed_dir / "raw_mobility.csv.gz"
            for ratio, load_label in LOADS:
                scenarios = build_scenarios(ratio, radio_path=radio_path, mobility_path=mobility_path)
                for idx, scenario in enumerate(scenarios):
                    for name, fn in METHODS.items():
                        groups = fn(scenario)
                        result = mvp.allocate_and_evaluate(groups, scenario, SWITCH_BETA)
                        rows.append({
                            "dispersion": dispersion, "seed": seed, "load": load_label,
                            "scenario_index": idx, "method": name,
                            "utility": result.utility, "adr_kbps": result.adr_kbps,
                            "served_ratio": result.served_ratio,
                            "average_quality": result.average_quality,
                            "system_spectral_efficiency": result.system_spectral_efficiency,
                            "fairness": result.fairness,
                        })
            progress(f"  {dispersion}/{seed} done ({len(scenarios)} scenarios/load)")
    return rows


def summarize(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Two levels: per_seed (mean over the 15 snapshots in one run -- the
    independent unit) and across_seeds (mean/std over the 10 per-seed means,
    plus win/tie/loss vs CQI k-means counted in SEEDS, not snapshots)."""

    methods = list(METHODS.keys())
    keys = sorted({(r["dispersion"], r["load"], r["seed"]) for r in rows})
    per_seed = []
    for dispersion, load, seed in keys:
        cell = [r for r in rows if r["dispersion"] == dispersion and r["load"] == load and r["seed"] == seed]
        for method in methods:
            vals = [r["utility"] for r in cell if r["method"] == method]
            per_seed.append({
                "dispersion": dispersion, "load": load, "seed": seed, "method": method,
                "mean_utility": float(np.mean(vals)), "n_scenarios": len(vals),
            })

    across_seeds = []
    for dispersion in DISPERSIONS:
        for load_ratio, load in LOADS:
            cqi_by_seed = {
                r["seed"]: r["mean_utility"] for r in per_seed
                if r["dispersion"] == dispersion and r["load"] == load and r["method"] == "CQI k-means"
            }
            for method in methods:
                seed_means = {
                    r["seed"]: r["mean_utility"] for r in per_seed
                    if r["dispersion"] == dispersion and r["load"] == load and r["method"] == method
                }
                diffs = np.array([seed_means[s] - cqi_by_seed[s] for s in SEEDS])
                vals = np.array([seed_means[s] for s in SEEDS])
                across_seeds.append({
                    "dispersion": dispersion, "load": load, "method": method,
                    "mean_utility": float(vals.mean()), "std_utility": float(vals.std()),
                    "mean_diff_vs_cqi": float(diffs.mean()),
                    "seeds_win": int((diffs > 1e-9).sum()),
                    "seeds_tie": int((np.abs(diffs) <= 1e-9).sum()),
                    "seeds_loss": int((diffs < -1e-9).sum()),
                })
    return per_seed, across_seeds


def main() -> None:
    progress(f"Protocol: dispersions={DISPERSIONS}, seeds={len(SEEDS)}/dispersion, loads={[l for _, l in LOADS]}")
    rows = run_all()
    per_seed, across_seeds = summarize(rows)

    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "per_scenario_results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    with open(OUT_DIR / "per_seed_summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(per_seed[0].keys()))
        writer.writeheader()
        writer.writerows(per_seed)
    with open(OUT_DIR / "summary_across_seeds.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(across_seeds[0].keys()))
        writer.writeheader()
        writer.writerows(across_seeds)

    progress("\n=== Summary (utility, mean over 10 seeds; win/tie/loss counted in SEEDS vs CQI k-means) ===")
    for row in across_seeds:
        progress(
            f"  {row['dispersion']:5s} {row['load']:7s} {row['method']:24s} "
            f"mean={row['mean_utility']:+.4f} std={row['std_utility']:.4f} "
            f"diff_vs_cqi={row['mean_diff_vs_cqi']:+.4f} "
            f"win={row['seeds_win']} tie={row['seeds_tie']} loss={row['seeds_loss']} (/10 seeds)"
        )
    progress(f"\nWrote results to {OUT_DIR}/")


if __name__ == "__main__":
    main()
