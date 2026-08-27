"""Research direction 4 follow-up (`POST_CQI_RESEARCH_ROADMAP_ZH.md`,
`REAL_SIMU5G_SCALE_PILOT.md`): do the method-family findings already
validated on the original 24-vehicle real Simu5G data replicate on the new
N=40 scale-pilot data (800x800m network, 50 vehicles requested, gNBs at
(400,160)/(400,640))?

Snapshot-level (non-temporal, `previous_quality` reset to 0 each snapshot),
matching direction 1's own methodology -- the scale-pilot data was only
validated for snapshot-level use so far (5-consecutive-second usable
windows exist, but no temporal closed-loop trajectory work has been done
here yet). Tests the key validated families in order of the project's own
history: CQI alone, the paper's 2-way union, the once-shipped 3-way
switching headline, direction 1's regret-graph 3-way, and direction 2's
confirmatory-validated 4-way union (the current best-evidenced method at
the original 24-vehicle scale).

Exploratory only: uses seeds 1..10, the only seeds this scale has ever
had generated. Per the project's own rule, any future confirmatory claim
at this scale needs its own fresh, untouched seed range.
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
DATA_ROOT = Path("real_simu5g_scale_pilot_multiseed_data")
OUT_DIR = Path("real_multiseed_scale_pilot_comparison_results")
N_USERS = 40
GNB_POS = {1: (400.0, 160.0), 2: (400.0, 640.0)}

METHODS = {
    "CQI k-means": lambda s: mvp.cqi_kmeans_grouping(s, KMAX, SWITCH_BETA, KMEANS_N_INIT),
    "CQI+cost 2-way union (paper method)": lambda s: mvp.cqi_resource_hybrid_kmeans_grouping(
        s, KMAX, SWITCH_BETA, KMEANS_N_INIT
    ),
    "CQI+cost+switching 3-way union (former headline)": lambda s: mvp.cqi_cost_switching_hybrid_kmeans_grouping(
        s, KMAX, SWITCH_BETA, KMEANS_N_INIT
    ),
    "CQI+cost+regret-graph 3-way union": lambda s: mvp.cqi_cost_regret_graph_hybrid_grouping(
        s, KMAX, SWITCH_BETA, KMEANS_N_INIT
    ),
    "CQI+cost+switching+regret-graph 4-way union (confirmatory-validated best)": lambda s: mvp.cqi_cost_switching_regret_graph_hybrid_grouping(
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
                scenarios = build_scenarios(
                    ratio, radio_path=radio_path, mobility_path=mobility_path,
                    n_users=N_USERS, gnb_pos=GNB_POS,
                )
                for idx, scenario in enumerate(scenarios):
                    for name, fn in METHODS.items():
                        groups = fn(scenario)
                        result = mvp.allocate_and_evaluate(groups, scenario, SWITCH_BETA)
                        rows.append({
                            "dispersion": dispersion, "seed": seed, "load": load_label,
                            "scenario_index": idx, "n_scenarios_this_run": len(scenarios),
                            "method": name,
                            "utility": result.utility, "adr_kbps": result.adr_kbps,
                            "served_ratio": result.served_ratio,
                            "average_quality": result.average_quality,
                            "system_spectral_efficiency": result.system_spectral_efficiency,
                            "fairness": result.fairness,
                        })
            progress(f"  {dispersion}/{seed} done")
    return rows


def summarize(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    methods = list(METHODS.keys())
    keys = sorted({(r["dispersion"], r["load"], r["seed"]) for r in rows})
    per_seed = []
    for dispersion, load, seed in keys:
        cell = [r for r in rows if r["dispersion"] == dispersion and r["load"] == load and r["seed"] == seed]
        for method in methods:
            vals = [r["utility"] for r in cell if r["method"] == method]
            if not vals:
                continue
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
            headline_by_seed = {
                r["seed"]: r["mean_utility"] for r in per_seed
                if r["dispersion"] == dispersion and r["load"] == load
                and r["method"] == "CQI+cost+switching+regret-graph 4-way union (confirmatory-validated best)"
            }
            valid_seeds = [s for s in SEEDS if s in cqi_by_seed and s in headline_by_seed]
            for method in methods:
                by_seed = {
                    r["seed"]: r["mean_utility"] for r in per_seed
                    if r["dispersion"] == dispersion and r["load"] == load and r["method"] == method
                }
                seeds_here = [s for s in valid_seeds if s in by_seed]
                if not seeds_here:
                    continue
                diffs_cqi = np.array([by_seed[s] - cqi_by_seed[s] for s in seeds_here])
                diffs_headline = np.array([by_seed[s] - headline_by_seed[s] for s in seeds_here])
                utilities = np.array([by_seed[s] for s in seeds_here])
                across_seeds.append({
                    "dispersion": dispersion, "load": load, "method": method,
                    "n_seeds": len(seeds_here),
                    "mean_utility": float(utilities.mean()),
                    "mean_diff_vs_cqi": float(diffs_cqi.mean()),
                    "seeds_win_vs_cqi": int((diffs_cqi > 1e-9).sum()),
                    "seeds_tie_vs_cqi": int((np.abs(diffs_cqi) <= 1e-9).sum()),
                    "seeds_loss_vs_cqi": int((diffs_cqi < -1e-9).sum()),
                    "mean_diff_vs_headline": float(diffs_headline.mean()),
                    "seeds_win_vs_headline": int((diffs_headline > 1e-9).sum()),
                    "seeds_tie_vs_headline": int((np.abs(diffs_headline) <= 1e-9).sum()),
                    "seeds_loss_vs_headline": int((diffs_headline < -1e-9).sum()),
                })
    return per_seed, across_seeds


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    progress(
        "Direction 4 follow-up: do the validated method-family findings replicate "
        "at N=40 scale-pilot? real Simu5G seeds 1..10, snapshot-level "
        "(non-temporal, previous_quality=0 each snapshot)"
    )
    rows = run_all()
    per_seed, across_seeds = summarize(rows)

    OUT_DIR.mkdir(exist_ok=True)
    write_csv(OUT_DIR / "per_scenario_results.csv", rows)
    write_csv(OUT_DIR / "per_seed_summary.csv", per_seed)
    write_csv(OUT_DIR / "summary_across_seeds.csv", across_seeds)

    progress("\n=== Mean utility & diff vs CQI k-means / 4-way headline, by dispersion x load x method ===")
    for dispersion in DISPERSIONS:
        for _, load in LOADS:
            for row in across_seeds:
                if row["dispersion"] != dispersion or row["load"] != load:
                    continue
                progress(
                    f"  {dispersion:4s} {load:6s} {row['method']:68s} "
                    f"n={row['n_seeds']:2d} u={row['mean_utility']:+.4f} "
                    f"dCQI={row['mean_diff_vs_cqi']:+.4f} WTL={row['seeds_win_vs_cqi']}/{row['seeds_tie_vs_cqi']}/{row['seeds_loss_vs_cqi']} "
                    f"dHeadline={row['mean_diff_vs_headline']:+.4f} WTL={row['seeds_win_vs_headline']}/{row['seeds_tie_vs_headline']}/{row['seeds_loss_vs_headline']}"
                )
    progress(f"\nWrote results to {OUT_DIR}/")


if __name__ == "__main__":
    main()
