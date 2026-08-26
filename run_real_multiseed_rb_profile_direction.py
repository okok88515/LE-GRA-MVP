"""Research direction 1 (`POST_CQI_RESEARCH_ROADMAP_ZH.md`): does keeping the
full per-band RB-rate profile -- or a pairwise RB-profile-compatibility graph
built from it -- beat CQI k-means, on the SAME real Simu5G snapshots used
throughout this project's real-data track?

This is the first go/no-go check named in the roadmap's execution order:
compare full-profile k-means against a pairwise overlap graph and a
pairwise exact-utility-regret graph, using the exact same 25-band input,
to isolate "is the frequency-selectivity information itself useful" from
"does a fancier clustering algorithm help." Non-temporal snapshot
evaluation (`previous_quality` reset to 0 each snapshot) -- deliberately
NOT the closed-loop protocol from `run_real_multiseed_temporal_closed_loop.py`,
to keep this pass about the frequency axis only, not entangled with the
switching/temporal axis (a separate, already-explored direction).

Exploratory only: uses seeds 1..10. Seeds 11..30 were already used to
confirm the eta=.020 switching gate (see `REAL_SIMU5G_CONDITIONAL_GATING.md`)
and per the roadmap's own rule cannot also be claimed as an untouched
confirmatory set for this direction.
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
OUT_DIR = Path("real_multiseed_rb_profile_direction_results")

METHODS = {
    "CQI k-means": lambda s: mvp.cqi_kmeans_grouping(s, KMAX, SWITCH_BETA, KMEANS_N_INIT),
    "Resource-cost k-means": lambda s: mvp.resource_cost_kmeans_grouping(s, KMAX, SWITCH_BETA, KMEANS_N_INIT),
    "Full RB-profile k-means": lambda s: mvp.full_rb_profile_kmeans_grouping(s, KMAX, SWITCH_BETA, KMEANS_N_INIT),
    "Block RB-profile k-means (5 blocks)": lambda s: mvp.block_rb_profile_kmeans_grouping(
        s, KMAX, SWITCH_BETA, 5, KMEANS_N_INIT
    ),
    "Overlap graph (simple similarity)": lambda s: mvp.overlap_graph_grouping(s, KMAX, SWITCH_BETA, KMEANS_N_INIT),
    "Exact-regret graph (utility-aware)": lambda s: mvp.exact_regret_graph_grouping(s, KMAX, SWITCH_BETA, KMEANS_N_INIT),
    "CQI+cost 2-way union (paper method)": lambda s: mvp.cqi_resource_hybrid_kmeans_grouping(s, KMAX, SWITCH_BETA, KMEANS_N_INIT),
    "CQI+cost+regret-graph 3-way union": lambda s: mvp.cqi_cost_regret_graph_hybrid_grouping(s, KMAX, SWITCH_BETA, KMEANS_N_INIT),
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
            for method in methods:
                by_seed = {
                    r["seed"]: r["mean_utility"] for r in per_seed
                    if r["dispersion"] == dispersion and r["load"] == load and r["method"] == method
                }
                diffs = np.array([by_seed[seed] - cqi_by_seed[seed] for seed in SEEDS])
                utilities = np.array([by_seed[seed] for seed in SEEDS])
                across_seeds.append({
                    "dispersion": dispersion, "load": load, "method": method,
                    "mean_utility": float(utilities.mean()),
                    "std_utility_across_seeds": float(utilities.std()),
                    "mean_diff_vs_cqi": float(diffs.mean()),
                    "seeds_win_vs_cqi": int((diffs > 1e-9).sum()),
                    "seeds_tie_vs_cqi": int((np.abs(diffs) <= 1e-9).sum()),
                    "seeds_loss_vs_cqi": int((diffs < -1e-9).sum()),
                })
    return per_seed, across_seeds


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    progress(
        "Direction 1 exploratory: full RB-profile / block-profile / overlap graph / "
        "exact-regret graph vs CQI+cost k-means, real Simu5G seeds 1..10, snapshot-level "
        "(non-temporal, previous_quality=0 each snapshot)"
    )
    rows = run_all()
    per_seed, across_seeds = summarize(rows)

    OUT_DIR.mkdir(exist_ok=True)
    write_csv(OUT_DIR / "per_scenario_results.csv", rows)
    write_csv(OUT_DIR / "per_seed_summary.csv", per_seed)
    write_csv(OUT_DIR / "summary_across_seeds.csv", across_seeds)

    progress("\n=== Mean utility & diff vs CQI k-means, by dispersion x load x method (10 seeds) ===")
    for dispersion in DISPERSIONS:
        for _, load in LOADS:
            for row in across_seeds:
                if row["dispersion"] != dispersion or row["load"] != load:
                    continue
                progress(
                    f"  {dispersion:4s} {load:6s} {row['method']:36s} "
                    f"u={row['mean_utility']:+.4f} dCQI={row['mean_diff_vs_cqi']:+.4f} "
                    f"WTL={row['seeds_win_vs_cqi']}/{row['seeds_tie_vs_cqi']}/{row['seeds_loss_vs_cqi']} (/10 seeds)"
                )
    progress(f"\nWrote results to {OUT_DIR}/")


if __name__ == "__main__":
    main()
