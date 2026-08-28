"""Closed-loop temporal grouping evaluation on the real 10-seed Simu5G data.

Unlike the snapshot baseline, each method owns a separate playback-quality
state.  The exact allocation selected at time t becomes previous_quality at
time t+1 for that same method.  The first usable snapshot is a common warm-up
from quality zero and is excluded from the primary statistics; the remaining
14 transitions per run are the evaluated trajectory.

Unserved users retain their last delivered quality in the state.  This keeps
previous_quality in its declared 0..5 range and models a player that has not
received a new representation rather than inventing a seventh quality level.

The independent statistical unit is the simulator seed/trajectory.  All
reported across-seed comparisons first average the 14 evaluated transitions
inside one run, then use the ten seed-level paired differences.  Confidence
intervals are deterministic percentile bootstrap intervals over seeds.
"""

from __future__ import annotations

import csv
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from typing import Callable

import numpy as np

import le_gra_mvp as mvp
from parse_real_simu5g_data import build_scenarios


KMAX = 3
SWITCH_BETA = 0.5
KMEANS_N_INIT = 10
BOOTSTRAP_REPS = 20_000
BOOTSTRAP_SEED = 20260825
MAX_WORKERS = 4

SEEDS = [f"seed_{i:04d}" for i in range(1, 11)]
DISPERSIONS = ["low", "mid", "high"]
LOADS = [(0.50, "light"), (0.25, "medium"), (0.10, "heavy")]
DATA_ROOT = Path("real_simu5g_multiseed_data")
OUT_DIR = Path("real_multiseed_temporal_closed_loop_results")

Method = Callable[[mvp.Scenario], list[list[int]]]
METHODS: dict[str, Method] = {
    "CQI k-means": lambda s: mvp.cqi_kmeans_grouping(s, KMAX, SWITCH_BETA, KMEANS_N_INIT),
    "CQI+cost 2-way union": lambda s: mvp.cqi_resource_hybrid_kmeans_grouping(
        s, KMAX, SWITCH_BETA, KMEANS_N_INIT
    ),
    "CQI+cost+switching 3-way union": lambda s: mvp.cqi_cost_switching_hybrid_kmeans_grouping(
        s, KMAX, SWITCH_BETA, KMEANS_N_INIT
    ),
}

METRICS = [
    "utility",
    "adr_kbps",
    "served_ratio",
    "average_quality",
    "system_spectral_efficiency",
    "fairness",
    "avg_switching",
    "quality_switch_rate",
    "quality_change_levels",
    "pairwise_group_churn",
    "groups",
]


def progress(message: str) -> None:
    print(message, flush=True)


def pairwise_group_churn(
    previous_groups: list[list[int]] | None,
    current_groups: list[list[int]],
    n_users: int,
) -> float:
    """Label-invariant fraction of UE pairs whose co-membership changed."""

    if previous_groups is None or n_users < 2:
        return 0.0

    def labels(groups: list[list[int]]) -> np.ndarray:
        result = np.full(n_users, -1, dtype=int)
        for group_id, group in enumerate(groups):
            result[group] = group_id
        if np.any(result < 0):
            raise ValueError("grouping does not cover every user")
        return result

    old = labels(previous_groups)
    new = labels(current_groups)
    upper = np.triu_indices(n_users, k=1)
    old_same = old[upper[0]] == old[upper[1]]
    new_same = new[upper[0]] == new[upper[1]]
    return float(np.mean(old_same != new_same))


def run_method_trajectory(
    scenarios: list[mvp.Scenario],
    method_name: str,
    method: Method,
    dispersion: str,
    load: str,
    seed: str,
    value_fn=None,
) -> list[dict]:
    """`value_fn` is forwarded to `allocate_and_evaluate` for the final
    quality-assignment/scoring step (default None -> `group_quality_value`);
    pass `mvp.group_adr_value` to score trajectories by raw ADR instead,
    matching the original published paper's objective (see
    `run_real_multiseed_baseline_comparison_adr.py`). This does not affect
    how `method` itself decides groupings -- only how the resulting
    grouping is scored and how quality tiers get allocated under the RB
    budget."""

    if len(scenarios) < 2:
        raise ValueError(f"{dispersion}/{seed}/{load} needs at least two snapshots")

    previous_quality = np.zeros(len(scenarios[0].cqi_now), dtype=int)
    previous_groups: list[list[int]] | None = None
    rows: list[dict] = []

    for step, base_scenario in enumerate(scenarios):
        scenario = replace(base_scenario, previous_quality=previous_quality.copy())
        groups = method(scenario)
        result = mvp.allocate_and_evaluate(groups, scenario, SWITCH_BETA, value_fn=value_fn)
        if result.user_quality is None:
            raise RuntimeError("allocator did not return its per-user quality assignment")

        assigned = result.user_quality
        served = assigned >= 0
        quality_delta = np.zeros(len(assigned), dtype=float)
        quality_delta[served] = np.abs(assigned[served] - previous_quality[served])

        rows.append({
            "dispersion": dispersion,
            "load": load,
            "seed": seed,
            "step": step,
            "is_warmup": int(step == 0),
            "method": method_name,
            "utility": result.utility,
            "adr_kbps": result.adr_kbps,
            "served_ratio": result.served_ratio,
            "average_quality": result.average_quality,
            "system_spectral_efficiency": result.system_spectral_efficiency,
            "fairness": result.fairness,
            "avg_switching": result.avg_switching,
            "quality_switch_rate": float(np.mean(served & (assigned != previous_quality))),
            "quality_change_levels": float(quality_delta.mean()),
            "pairwise_group_churn": pairwise_group_churn(previous_groups, groups, len(assigned)),
            "groups": result.groups,
        })

        # No newly delivered representation means the player retains its last
        # quality state.  Served users advance to the actual DP assignment.
        previous_quality = previous_quality.copy()
        previous_quality[served] = assigned[served]
        previous_groups = [list(group) for group in groups]

    return rows


def run_seed(dispersion: str, seed: str) -> list[dict]:
    rows: list[dict] = []
    seed_dir = DATA_ROOT / dispersion / seed
    radio_path = seed_dir / "raw_radio.csv.gz"
    mobility_path = seed_dir / "raw_mobility.csv.gz"
    for load_ratio, load in LOADS:
        scenarios = build_scenarios(
            load_ratio,
            radio_path=radio_path,
            mobility_path=mobility_path,
        )
        for method_name, method in METHODS.items():
            rows.extend(
                run_method_trajectory(
                    scenarios, method_name, method, dispersion, load, seed
                )
            )
    return rows


def run_all() -> list[dict]:
    rows: list[dict] = []
    jobs = [(dispersion, seed) for dispersion in DISPERSIONS for seed in SEEDS]
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(run_seed, dispersion, seed): (dispersion, seed)
            for dispersion, seed in jobs
        }
        for future in as_completed(futures):
            dispersion, seed = futures[future]
            rows.extend(future.result())
            progress(f"  {dispersion}/{seed} done")

    dispersion_order = {value: index for index, value in enumerate(DISPERSIONS)}
    load_order = {value: index for index, (_, value) in enumerate(LOADS)}
    method_order = {value: index for index, value in enumerate(METHODS)}
    rows.sort(key=lambda row: (
        dispersion_order[row["dispersion"]],
        row["seed"],
        load_order[row["load"]],
        row["step"],
        method_order[row["method"]],
    ))
    return rows


def bootstrap_mean_ci(values: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    if len(values) == 0:
        return float("nan"), float("nan")
    sample_indices = rng.integers(0, len(values), size=(BOOTSTRAP_REPS, len(values)))
    means = values[sample_indices].mean(axis=1)
    low, high = np.quantile(means, [0.025, 0.975])
    return float(low), float(high)


def summarize(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    # The warm-up determines each method's initial playback state but is not
    # part of the reported trajectory metrics.
    evaluated = [row for row in rows if not row["is_warmup"]]
    per_seed: list[dict] = []
    for dispersion in DISPERSIONS:
        for load_ratio, load in LOADS:
            for seed in SEEDS:
                for method in METHODS:
                    cell = [
                        row for row in evaluated
                        if row["dispersion"] == dispersion
                        and row["load"] == load
                        and row["seed"] == seed
                        and row["method"] == method
                    ]
                    if len(cell) != 14:
                        raise ValueError(
                            f"expected 14 post-warmup transitions for "
                            f"{dispersion}/{load}/{seed}/{method}, got {len(cell)}"
                        )
                    summary = {
                        "dispersion": dispersion,
                        "load": load,
                        "seed": seed,
                        "method": method,
                        "n_transitions": len(cell),
                    }
                    for metric in METRICS:
                        summary[f"mean_{metric}"] = float(np.mean([row[metric] for row in cell]))
                    per_seed.append(summary)

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    across_seeds: list[dict] = []
    for dispersion in DISPERSIONS:
        for load_ratio, load in LOADS:
            by_method = {
                method: {
                    row["seed"]: row
                    for row in per_seed
                    if row["dispersion"] == dispersion
                    and row["load"] == load
                    and row["method"] == method
                }
                for method in METHODS
            }
            for method in METHODS:
                seed_rows = by_method[method]
                utilities = np.array([seed_rows[seed]["mean_utility"] for seed in SEEDS])
                cqi_diffs = np.array([
                    seed_rows[seed]["mean_utility"]
                    - by_method["CQI k-means"][seed]["mean_utility"]
                    for seed in SEEDS
                ])
                two_way_diffs = np.array([
                    seed_rows[seed]["mean_utility"]
                    - by_method["CQI+cost 2-way union"][seed]["mean_utility"]
                    for seed in SEEDS
                ])
                cqi_ci = bootstrap_mean_ci(cqi_diffs, rng)
                two_way_ci = bootstrap_mean_ci(two_way_diffs, rng)
                summary = {
                    "dispersion": dispersion,
                    "load": load,
                    "method": method,
                    "mean_utility": float(utilities.mean()),
                    "std_utility_across_seeds": float(utilities.std()),
                    "mean_diff_vs_cqi": float(cqi_diffs.mean()),
                    "diff_vs_cqi_ci95_low": cqi_ci[0],
                    "diff_vs_cqi_ci95_high": cqi_ci[1],
                    "seeds_win_vs_cqi": int((cqi_diffs > 1e-9).sum()),
                    "seeds_tie_vs_cqi": int((np.abs(cqi_diffs) <= 1e-9).sum()),
                    "seeds_loss_vs_cqi": int((cqi_diffs < -1e-9).sum()),
                    "mean_diff_vs_2way": float(two_way_diffs.mean()),
                    "diff_vs_2way_ci95_low": two_way_ci[0],
                    "diff_vs_2way_ci95_high": two_way_ci[1],
                    "seeds_win_vs_2way": int((two_way_diffs > 1e-9).sum()),
                    "seeds_tie_vs_2way": int((np.abs(two_way_diffs) <= 1e-9).sum()),
                    "seeds_loss_vs_2way": int((two_way_diffs < -1e-9).sum()),
                }
                for metric in METRICS[1:]:
                    summary[f"mean_{metric}"] = float(np.mean([
                        seed_rows[seed][f"mean_{metric}"] for seed in SEEDS
                    ]))
                across_seeds.append(summary)
    return per_seed, across_seeds


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    progress(
        "Closed-loop protocol: 10 seeds/dispersion, 15 snapshots/run "
        "(1 warm-up + 14 evaluated transitions), method-owned quality state"
    )
    rows = run_all()
    per_seed, across_seeds = summarize(rows)

    OUT_DIR.mkdir(exist_ok=True)
    write_csv(OUT_DIR / "per_transition_results.csv", rows)
    write_csv(OUT_DIR / "per_seed_summary.csv", per_seed)
    write_csv(OUT_DIR / "summary_across_seeds.csv", across_seeds)

    progress("\n=== Closed-loop utility summary (seed is the independent unit) ===")
    for row in across_seeds:
        if row["method"] not in {
            "CQI k-means",
            "CQI+cost 2-way union",
            "CQI+cost+switching 3-way union",
        }:
            continue
        progress(
            f"  {row['dispersion']:4s} {row['load']:6s} {row['method']:36s} "
            f"u={row['mean_utility']:+.5f} "
            f"dCQI={row['mean_diff_vs_cqi']:+.5f} "
            f"CI=[{row['diff_vs_cqi_ci95_low']:+.5f},{row['diff_vs_cqi_ci95_high']:+.5f}] "
            f"WTL={row['seeds_win_vs_cqi']}/{row['seeds_tie_vs_cqi']}/{row['seeds_loss_vs_cqi']} "
            f"switch={row['mean_avg_switching']:.4f} "
            f"churn={row['mean_pairwise_group_churn']:.4f}"
        )
    progress(f"\nWrote results to {OUT_DIR}/")


if __name__ == "__main__":
    main()
