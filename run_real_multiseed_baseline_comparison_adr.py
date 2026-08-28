"""Robustness check: re-run the same 6-method baseline comparison scored by
raw ADR (`mvp.group_adr_value` -- unserved = 0, no switching penalty) instead
of this project's own extended log-utility (`mvp.group_quality_value` --
unserved = -2, switching penalty). This matches the objective the user's
originally published paper actually used, and tests whether the qualitative
ranking (published method beats Method A/B; candidate-union beats published)
is robust to which QoE objective is used, or whether it flips.

Same confirmatory seed range and temporal closed-loop protocol as
run_real_multiseed_baseline_comparison.py -- only the scoring objective
(value_fn) changes, threaded through every DP call: candidate selection
(where applicable) AND the final per-trajectory quality assignment.

Usage:
    python run_real_multiseed_baseline_comparison_adr.py --seeds 31-50
"""

from __future__ import annotations

import argparse
import csv
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

import baseline_prior_methods as bp
import le_gra_mvp as mvp
import run_real_multiseed_temporal_closed_loop as temporal
from parse_real_simu5g_data import build_scenarios

VALUE_FN = mvp.group_adr_value


def _candidate_union_final_adr(s: mvp.Scenario) -> list[list[int]]:
    """Same candidate generation as `cqi_cost_regret_graph_hybrid_grouping`,
    but selecting by raw ADR instead of the default log-utility."""
    cqi_rep = s.cqi_now.reshape(-1, 1).astype(float)
    cost_rep = mvp.user_resource_cost_vector(s.rb_rates)
    affinity = mvp.pairwise_exact_regret_matrix(s, temporal.SWITCH_BETA)
    candidates = (
        mvp.kmeans_candidate_groups(cqi_rep, temporal.KMAX, kmeans_n_init=temporal.KMEANS_N_INIT, kmeans_seed=0)
        + mvp.kmeans_candidate_groups(cost_rep, temporal.KMAX, kmeans_n_init=temporal.KMEANS_N_INIT, kmeans_seed=0)
        + mvp.graph_candidate_groups(affinity, temporal.KMAX, kmeans_n_init=temporal.KMEANS_N_INIT)
    )
    return mvp.best_candidate_groups(s, candidates, temporal.SWITCH_BETA, value_fn=VALUE_FN)


METHODS = {
    "NoGrouping_single_group": lambda s: bp.no_grouping_single_group(s),
    "MethodA_proxy_kmeans": lambda s: bp.cqi_min_weighted_kmeans_grouping(
        s, temporal.KMAX, kmeans_n_init=temporal.KMEANS_N_INIT
    ),
    "MethodB_cutpoint_stddev": lambda s: bp.sorted_cutpoint_stddev_threshold_grouping(
        s, temporal.KMAX, temporal.SWITCH_BETA, value_fn=VALUE_FN
    ),
    "CQI_kmeans_published": lambda s: mvp.best_kmeans_groups(
        s, s.cqi_now.reshape(-1, 1).astype(float), temporal.KMAX, temporal.SWITCH_BETA,
        kmeans_n_init=temporal.KMEANS_N_INIT, value_fn=VALUE_FN,
    ),
    "Candidate_union_final": _candidate_union_final_adr,
    "OptimalCutpoint_upperbound": lambda s: bp.optimal_sorted_cutpoint_partition(
        s, temporal.SWITCH_BETA, value_fn=VALUE_FN
    )[0],
}

REFERENCE = "CQI_kmeans_published"


def parse_seed_spec(spec: str) -> list[str]:
    seeds: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", maxsplit=1)
            start, end = int(start_text), int(end_text)
            if end < start:
                raise ValueError(f"descending seed range is invalid: {part}")
            seeds.update(range(start, end + 1))
        else:
            seeds.add(int(part))
    if not seeds or min(seeds) < 0:
        raise ValueError("at least one non-negative seed is required")
    return [f"seed_{value:04d}" for value in sorted(seeds)]


def run_seed(dispersion: str, seed: str) -> list[dict]:
    rows: list[dict] = []
    seed_dir = temporal.DATA_ROOT / dispersion / seed
    radio_path = seed_dir / "raw_radio.csv.gz"
    mobility_path = seed_dir / "raw_mobility.csv.gz"
    for load_ratio, load in temporal.LOADS:
        scenarios = build_scenarios(load_ratio, radio_path=radio_path, mobility_path=mobility_path)
        for method_name, method in METHODS.items():
            rows.extend(
                temporal.run_method_trajectory(
                    scenarios, method_name, method, dispersion, load, seed, value_fn=VALUE_FN
                )
            )
    return rows


def run_all(seeds: list[str]) -> list[dict]:
    rows: list[dict] = []
    jobs = [(dispersion, seed) for dispersion in temporal.DISPERSIONS for seed in seeds]
    with ProcessPoolExecutor(max_workers=temporal.MAX_WORKERS) as executor:
        futures = {executor.submit(run_seed, dispersion, seed): (dispersion, seed) for dispersion, seed in jobs}
        for future in as_completed(futures):
            dispersion, seed = futures[future]
            rows.extend(future.result())
            temporal.progress(f"  {dispersion}/{seed} done")
    return rows


def summarize_per_seed(rows: list[dict], seeds: list[str]) -> list[dict]:
    evaluated = [row for row in rows if not row["is_warmup"]]
    result: list[dict] = []
    for dispersion in temporal.DISPERSIONS:
        for _, load in temporal.LOADS:
            for seed in seeds:
                for method in METHODS:
                    cell = [
                        row for row in evaluated
                        if row["dispersion"] == dispersion and row["load"] == load
                        and row["seed"] == seed and row["method"] == method
                    ]
                    if len(cell) != 14:
                        raise ValueError(f"expected 14 rows for {dispersion}/{load}/{seed}/{method}, got {len(cell)}")
                    result.append({
                        "dispersion": dispersion, "load": load, "seed": seed, "method": method,
                        "mean_utility": float(np.mean([row["utility"] for row in cell])),
                    })
    return result


def summarize_pooled(per_seed: list[dict], seeds: list[str]) -> list[dict]:
    rng = np.random.default_rng(temporal.BOOTSTRAP_SEED + 40)
    outputs: list[dict] = []
    scopes = {
        "mid_high_6_cells": {"mid", "high"},
        "high_only_3_cells": {"high"},
        "all_9_cells": {"low", "mid", "high"},
    }
    for scope, allowed in scopes.items():
        by_method_seed: dict[str, dict[str, float]] = {}
        for method in METHODS:
            by_method_seed[method] = {}
            for seed in seeds:
                selected = [
                    row for row in per_seed
                    if row["method"] == method and row["seed"] == seed and row["dispersion"] in allowed
                ]
                by_method_seed[method][seed] = float(np.mean([row["mean_utility"] for row in selected]))
        for method in METHODS:
            values = np.array([by_method_seed[method][seed] for seed in seeds])
            diffs = np.array([by_method_seed[method][seed] - by_method_seed[REFERENCE][seed] for seed in seeds])
            ci_low, ci_high = temporal.bootstrap_mean_ci(diffs, rng)
            outputs.append({
                "scope": scope, "method": method,
                "mean_adr_utility": float(values.mean()),
                "mean_diff_vs_published": float(diffs.mean()),
                "diff_vs_published_ci95_low": ci_low, "diff_vs_published_ci95_high": ci_high,
                "seeds_win_vs_published": int((diffs > 1e-9).sum()),
                "seeds_tie_vs_published": int((np.abs(diffs) <= 1e-9).sum()),
                "seeds_loss_vs_published": int((diffs < -1e-9).sum()),
            })
    return outputs


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path}")
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, restval="")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", default="31-50", help="Confirmatory seed spec, e.g. 31-50")
    parser.add_argument("--out-dir", type=Path, default=Path("real_multiseed_baseline_comparison_adr_results"))
    args = parser.parse_args()
    seeds = parse_seed_spec(args.seeds)

    temporal.progress(
        f"ADR-objective robustness check: {len(seeds)} confirmatory seeds ({seeds[0]}..{seeds[-1]}), "
        f"{len(METHODS)} methods, scored by raw ADR (group_adr_value) not the extended log-utility"
    )
    rows = run_all(seeds)
    per_seed = summarize_per_seed(rows, seeds)
    pooled = summarize_pooled(per_seed, seeds)

    args.out_dir.mkdir(exist_ok=True)
    write_csv(args.out_dir / "per_transition_results.csv", rows)
    write_csv(args.out_dir / "comparison_per_seed.csv", per_seed)
    write_csv(args.out_dir / "pooled_summary.csv", pooled)

    temporal.progress("\n=== Pooled mid+high dispersion (6 non-saturated cells), ADR objective, vs published CQI k-means ===")
    for row in pooled:
        if row["scope"] != "mid_high_6_cells":
            continue
        temporal.progress(
            f"  {row['method']:28s} adr_utility={row['mean_adr_utility']:+9.2f} "
            f"dPublished={row['mean_diff_vs_published']:+9.2f} CI=[{row['diff_vs_published_ci95_low']:+9.2f},{row['diff_vs_published_ci95_high']:+9.2f}] "
            f"WTL={row['seeds_win_vs_published']}/{row['seeds_tie_vs_published']}/{row['seeds_loss_vs_published']}"
        )
    temporal.progress(f"\nWrote results to {args.out_dir}/")


if __name__ == "__main__":
    main()
