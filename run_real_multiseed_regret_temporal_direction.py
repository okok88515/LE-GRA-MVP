"""Research direction 2 (`POST_CQI_RESEARCH_ROADMAP_ZH.md`): does the exact-
utility-regret graph built for direction 1 (`REAL_SIMU5G_RB_PROFILE_DIRECTION.md`)
also capture switching-state value once evaluated under the real temporal
closed loop, where `previous_quality` genuinely diverges across users --
instead of building a separate switching-only regret metric first?

`pairwise_exact_regret_matrix`'s regret formula already includes the
switching penalty (`group_quality_value` uses `scenario.previous_quality`
like everything else in `le_gra_mvp.py`); direction 1's snapshot-level
evaluation just never exercised that term (previous_quality was reset to 0
for everyone). This reuses `run_real_multiseed_temporal_closed_loop.py`'s
validated closed-loop machinery (imported, not copied) with a new METHODS
dict, writing to a separate output directory -- the original module's own
results/output are untouched.

Exploratory only: seeds 1..10. Seeds 11..30 are already "used" by the
switching-gate confirmatory work.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

import le_gra_mvp as mvp
import run_real_multiseed_temporal_closed_loop as temporal
from parse_real_simu5g_data import build_scenarios
from pathlib import Path

OUT_DIR = Path("real_multiseed_regret_temporal_direction_results")

METHODS: dict[str, temporal.Method] = {
    "CQI k-means": lambda s: mvp.cqi_kmeans_grouping(s, temporal.KMAX, temporal.SWITCH_BETA, temporal.KMEANS_N_INIT),
    "CQI+cost 2-way union": lambda s: mvp.cqi_resource_hybrid_kmeans_grouping(
        s, temporal.KMAX, temporal.SWITCH_BETA, temporal.KMEANS_N_INIT
    ),
    "CQI+cost+switching 3-way union": lambda s: mvp.cqi_cost_switching_hybrid_kmeans_grouping(
        s, temporal.KMAX, temporal.SWITCH_BETA, temporal.KMEANS_N_INIT
    ),
    "CQI+cost+regret-graph 3-way union": lambda s: mvp.cqi_cost_regret_graph_hybrid_grouping(
        s, temporal.KMAX, temporal.SWITCH_BETA, temporal.KMEANS_N_INIT
    ),
    "CQI+cost+switching+regret-graph 4-way union": lambda s: mvp.cqi_cost_switching_regret_graph_hybrid_grouping(
        s, temporal.KMAX, temporal.SWITCH_BETA, temporal.KMEANS_N_INIT
    ),
}


def run_seed(dispersion: str, seed: str) -> list[dict]:
    rows: list[dict] = []
    seed_dir = temporal.DATA_ROOT / dispersion / seed
    radio_path = seed_dir / "raw_radio.csv.gz"
    mobility_path = seed_dir / "raw_mobility.csv.gz"
    for load_ratio, load in temporal.LOADS:
        scenarios = build_scenarios(load_ratio, radio_path=radio_path, mobility_path=mobility_path)
        for method_name, method in METHODS.items():
            rows.extend(
                temporal.run_method_trajectory(scenarios, method_name, method, dispersion, load, seed)
            )
    return rows


def run_all() -> list[dict]:
    rows: list[dict] = []
    jobs = [(dispersion, seed) for dispersion in temporal.DISPERSIONS for seed in temporal.SEEDS]
    with ProcessPoolExecutor(max_workers=temporal.MAX_WORKERS) as executor:
        futures = {executor.submit(run_seed, dispersion, seed): (dispersion, seed) for dispersion, seed in jobs}
        for future in as_completed(futures):
            dispersion, seed = futures[future]
            rows.extend(future.result())
            temporal.progress(f"  {dispersion}/{seed} done")
    return rows


def summarize(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    evaluated = [row for row in rows if not row["is_warmup"]]
    per_seed: list[dict] = []
    for dispersion in temporal.DISPERSIONS:
        for load_ratio, load in temporal.LOADS:
            for seed in temporal.SEEDS:
                for method in METHODS:
                    cell = [
                        row for row in evaluated
                        if row["dispersion"] == dispersion and row["load"] == load
                        and row["seed"] == seed and row["method"] == method
                    ]
                    if len(cell) != 14:
                        raise ValueError(f"expected 14 transitions for {dispersion}/{load}/{seed}/{method}, got {len(cell)}")
                    per_seed.append({
                        "dispersion": dispersion, "load": load, "seed": seed, "method": method,
                        "mean_utility": float(np.mean([row["utility"] for row in cell])),
                    })

    rng = np.random.default_rng(temporal.BOOTSTRAP_SEED + 10)
    across_seeds: list[dict] = []
    for dispersion in temporal.DISPERSIONS:
        for load_ratio, load in temporal.LOADS:
            by_method = {
                method: {row["seed"]: row for row in per_seed if row["dispersion"] == dispersion and row["load"] == load and row["method"] == method}
                for method in METHODS
            }
            for method in METHODS:
                seed_rows = by_method[method]
                utilities = np.array([seed_rows[seed]["mean_utility"] for seed in temporal.SEEDS])
                cqi_diffs = np.array([seed_rows[seed]["mean_utility"] - by_method["CQI k-means"][seed]["mean_utility"] for seed in temporal.SEEDS])
                three_way_diffs = np.array([seed_rows[seed]["mean_utility"] - by_method["CQI+cost+switching 3-way union"][seed]["mean_utility"] for seed in temporal.SEEDS])
                cqi_ci = temporal.bootstrap_mean_ci(cqi_diffs, rng)
                three_way_ci = temporal.bootstrap_mean_ci(three_way_diffs, rng)
                across_seeds.append({
                    "dispersion": dispersion, "load": load, "method": method,
                    "mean_utility": float(utilities.mean()),
                    "mean_diff_vs_cqi": float(cqi_diffs.mean()),
                    "diff_vs_cqi_ci95_low": cqi_ci[0], "diff_vs_cqi_ci95_high": cqi_ci[1],
                    "seeds_win_vs_cqi": int((cqi_diffs > 1e-9).sum()),
                    "seeds_tie_vs_cqi": int((np.abs(cqi_diffs) <= 1e-9).sum()),
                    "seeds_loss_vs_cqi": int((cqi_diffs < -1e-9).sum()),
                    "mean_diff_vs_switching3way": float(three_way_diffs.mean()),
                    "diff_vs_switching3way_ci95_low": three_way_ci[0],
                    "diff_vs_switching3way_ci95_high": three_way_ci[1],
                    "seeds_win_vs_switching3way": int((three_way_diffs > 1e-9).sum()),
                    "seeds_tie_vs_switching3way": int((np.abs(three_way_diffs) <= 1e-9).sum()),
                    "seeds_loss_vs_switching3way": int((three_way_diffs < -1e-9).sum()),
                })
    return per_seed, across_seeds


def write_csv(path, rows: list[dict]) -> None:
    import csv
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    temporal.progress(
        "Direction 2 exploratory (temporal closed loop): does the regret graph "
        "capture switching-state value once previous_quality genuinely diverges? "
        "Seeds 1..10, real Simu5G, method-owned previous_quality state."
    )
    rows = run_all()
    per_seed, across_seeds = summarize(rows)

    OUT_DIR.mkdir(exist_ok=True)
    write_csv(OUT_DIR / "per_transition_results.csv", rows)
    write_csv(OUT_DIR / "per_seed_summary.csv", per_seed)
    write_csv(OUT_DIR / "summary_across_seeds.csv", across_seeds)

    temporal.progress("\n=== Closed-loop utility, vs CQI and vs the existing switching 3-way headline ===")
    for row in across_seeds:
        temporal.progress(
            f"  {row['dispersion']:4s} {row['load']:6s} {row['method']:44s} "
            f"u={row['mean_utility']:+.5f} "
            f"dCQI={row['mean_diff_vs_cqi']:+.5f} CI=[{row['diff_vs_cqi_ci95_low']:+.5f},{row['diff_vs_cqi_ci95_high']:+.5f}] "
            f"d3way={row['mean_diff_vs_switching3way']:+.5f} CI=[{row['diff_vs_switching3way_ci95_low']:+.5f},{row['diff_vs_switching3way_ci95_high']:+.5f}] "
            f"WTL3way={row['seeds_win_vs_switching3way']}/{row['seeds_tie_vs_switching3way']}/{row['seeds_loss_vs_switching3way']}"
        )
    temporal.progress(f"\nWrote results to {OUT_DIR}/")


if __name__ == "__main__":
    main()
