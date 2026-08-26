"""Research direction 3 (`POST_CQI_RESEARCH_ROADMAP_ZH.md`): does a CAUSAL
CQI-trend feature -- slope, volatility, downside deviation, all computed
only from the 5-step history already in every real Simu5G scenario, never
looking past `cqi_now` -- carry information CQI k-means misses? Two users at
the same current CQI can have opposite trajectories (`[4,5,6,7,8]` vs
`[12,11,10,9,8]`); snapshot CQI k-means treats them as identical.

Step 1 of the roadmap's direction-3 plan ("causal hand-crafted trend
baseline") -- NOT the later next-step predictor or multi-step teacher
objective, which are separate, more involved follow-ups. This is
snapshot-level, non-temporal evaluation (`previous_quality` reset to 0 each
snapshot), matching direction 1's own first pass, since the trend features
here are per-snapshot causal features, not a temporal-closed-loop question.

This script was written ahead of running it, while a direction-2
confirmatory Simu5G generation batch was using this machine's WSL/CPU
budget. That confirmatory pass (seeds 31..50) has since completed and made
an important correction: the regret-graph-only 3-way does NOT safely
replace switching (real losses at mid dispersion in the larger sample), but
the 4-way union (switching + regret-graph together) strictly dominates the
previous switching-only headline with zero seed-level losses. This script's
reference method was updated accordingly -- trend features are tested on
top of the confirmatory-validated 4-way, not the superseded regret-only
3-way (see `REAL_SIMU5G_REGRET_GRAPH_TEMPORAL_DIRECTION.md`'s "Decision
(revised after confirmatory validation)" section).

Exploratory only: uses seeds 1..10. Seeds 11..30 were already used for the
switching-gate confirmatory pass and seeds 31..50 for direction 2's
confirmatory pass -- per the roadmap's own rule, none of seeds 1..50 can be
claimed as an untouched confirmatory set for direction 3 once this
exploratory pass has looked at seeds 1..10.
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
OUT_DIR = Path("real_multiseed_trend_direction_results")

METHODS = {
    "CQI k-means": lambda s: mvp.cqi_kmeans_grouping(s, KMAX, SWITCH_BETA, KMEANS_N_INIT),
    "Trend-slope k-means": lambda s: mvp.cqi_trend_slope_kmeans_grouping(s, KMAX, SWITCH_BETA, KMEANS_N_INIT),
    "Trend-volatility k-means": lambda s: mvp.cqi_trend_volatility_kmeans_grouping(s, KMAX, SWITCH_BETA, KMEANS_N_INIT),
    "Trend-downside-deviation k-means": lambda s: mvp.cqi_trend_downside_deviation_kmeans_grouping(
        s, KMAX, SWITCH_BETA, KMEANS_N_INIT
    ),
    "Trend-only union (CQI+slope+volatility+downside)": lambda s: mvp.cqi_trend_hybrid_kmeans_grouping(
        s, KMAX, SWITCH_BETA, KMEANS_N_INIT
    ),
    "CQI+cost+regret-graph 3-way union (ablation, no switching)": lambda s: mvp.cqi_cost_regret_graph_hybrid_grouping(
        s, KMAX, SWITCH_BETA, KMEANS_N_INIT
    ),
    "CQI+cost+switching+regret-graph 4-way union (confirmatory-validated base)": lambda s: mvp.cqi_cost_switching_regret_graph_hybrid_grouping(
        s, KMAX, SWITCH_BETA, KMEANS_N_INIT
    ),
    "CQI+cost+regret-graph+trend union (ablation, no switching)": lambda s: mvp.cqi_cost_regret_trend_hybrid_grouping(
        s, KMAX, SWITCH_BETA, KMEANS_N_INIT
    ),
    "CQI+cost+switching+regret-graph+trend union": lambda s: mvp.cqi_cost_switching_regret_trend_hybrid_grouping(
        s, KMAX, SWITCH_BETA, KMEANS_N_INIT
    ),
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
            reference_by_seed = {
                r["seed"]: r["mean_utility"] for r in per_seed
                if r["dispersion"] == dispersion and r["load"] == load
                and r["method"] == "CQI+cost+switching+regret-graph 4-way union (confirmatory-validated base)"
            }
            for method in methods:
                by_seed = {
                    r["seed"]: r["mean_utility"] for r in per_seed
                    if r["dispersion"] == dispersion and r["load"] == load and r["method"] == method
                }
                diffs_cqi = np.array([by_seed[seed] - cqi_by_seed[seed] for seed in SEEDS])
                diffs_ref = np.array([by_seed[seed] - reference_by_seed[seed] for seed in SEEDS])
                utilities = np.array([by_seed[seed] for seed in SEEDS])
                across_seeds.append({
                    "dispersion": dispersion, "load": load, "method": method,
                    "mean_utility": float(utilities.mean()),
                    "std_utility_across_seeds": float(utilities.std()),
                    "mean_diff_vs_cqi": float(diffs_cqi.mean()),
                    "seeds_win_vs_cqi": int((diffs_cqi > 1e-9).sum()),
                    "seeds_tie_vs_cqi": int((np.abs(diffs_cqi) <= 1e-9).sum()),
                    "seeds_loss_vs_cqi": int((diffs_cqi < -1e-9).sum()),
                    "mean_diff_vs_base4way": float(diffs_ref.mean()),
                    "seeds_win_vs_base4way": int((diffs_ref > 1e-9).sum()),
                    "seeds_tie_vs_base4way": int((np.abs(diffs_ref) <= 1e-9).sum()),
                    "seeds_loss_vs_base4way": int((diffs_ref < -1e-9).sum()),
                })
    return per_seed, across_seeds


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    progress(
        "Direction 3 exploratory: causal CQI-trend features (slope/volatility/"
        "downside deviation) vs CQI k-means and the confirmatory-validated base "
        "(CQI+cost+switching+regret-graph 4-way), real Simu5G seeds 1..10, "
        "snapshot-level (non-temporal, previous_quality=0 each snapshot)"
    )
    rows = run_all()
    per_seed, across_seeds = summarize(rows)

    OUT_DIR.mkdir(exist_ok=True)
    write_csv(OUT_DIR / "per_scenario_results.csv", rows)
    write_csv(OUT_DIR / "per_seed_summary.csv", per_seed)
    write_csv(OUT_DIR / "summary_across_seeds.csv", across_seeds)

    progress("\n=== Mean utility & diff vs CQI k-means / confirmatory-validated base, by dispersion x load x method (10 seeds) ===")
    for dispersion in DISPERSIONS:
        for _, load in LOADS:
            for row in across_seeds:
                if row["dispersion"] != dispersion or row["load"] != load:
                    continue
                progress(
                    f"  {dispersion:4s} {load:6s} {row['method']:60s} "
                    f"u={row['mean_utility']:+.4f} dCQI={row['mean_diff_vs_cqi']:+.4f} "
                    f"dRegret3way={row['mean_diff_vs_base4way']:+.4f} "
                    f"WTL(base4way)={row['seeds_win_vs_base4way']}/{row['seeds_tie_vs_base4way']}/{row['seeds_loss_vs_base4way']} "
                    f"(/10 seeds)"
                )
    progress(f"\nWrote results to {OUT_DIR}/")


if __name__ == "__main__":
    main()
