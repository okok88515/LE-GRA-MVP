"""Full power-set ablation over the three extra candidate families
{resource-cost, switching, regret-graph} combined with the CQI base,
each of the 7 non-empty combinations compared directly against CQI alone
-- requested to precisely attribute each family's isolated contribution
for interview presentation, rather than only contribution on top of the
paper's own CQI+cost union.

Reuses the same confirmatory seed range, temporal closed-loop protocol,
and shared primitives (`run_real_multiseed_temporal_closed_loop`) as
`run_real_multiseed_regret_confirmatory.py` -- no retuning, same fixed
method definitions imported from `le_gra_mvp.py`, just a fuller method set.

Usage:
    python run_real_multiseed_power_set_confirmatory.py --seeds 31-50
"""

from __future__ import annotations

import argparse
import csv
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp
import run_real_multiseed_temporal_closed_loop as temporal
from parse_real_simu5g_data import build_scenarios

METHODS = {
    "CQI": lambda s: mvp.cqi_kmeans_grouping(s, temporal.KMAX, temporal.SWITCH_BETA, temporal.KMEANS_N_INIT),
    "CQI+cost": lambda s: mvp.cqi_resource_hybrid_kmeans_grouping(s, temporal.KMAX, temporal.SWITCH_BETA, temporal.KMEANS_N_INIT),
    "CQI+switching": lambda s: mvp.cqi_switching_hybrid_kmeans_grouping(s, temporal.KMAX, temporal.SWITCH_BETA, temporal.KMEANS_N_INIT),
    "CQI+regret-graph": lambda s: mvp.cqi_regret_graph_hybrid_grouping(s, temporal.KMAX, temporal.SWITCH_BETA, temporal.KMEANS_N_INIT),
    "CQI+cost+switching": lambda s: mvp.cqi_cost_switching_hybrid_kmeans_grouping(s, temporal.KMAX, temporal.SWITCH_BETA, temporal.KMEANS_N_INIT),
    "CQI+cost+regret-graph": lambda s: mvp.cqi_cost_regret_graph_hybrid_grouping(s, temporal.KMAX, temporal.SWITCH_BETA, temporal.KMEANS_N_INIT),
    "CQI+switching+regret-graph": lambda s: mvp.cqi_switching_regret_graph_hybrid_grouping(s, temporal.KMAX, temporal.SWITCH_BETA, temporal.KMEANS_N_INIT),
    "CQI+cost+switching+regret-graph": lambda s: mvp.cqi_cost_switching_regret_graph_hybrid_grouping(s, temporal.KMAX, temporal.SWITCH_BETA, temporal.KMEANS_N_INIT),
}

REFERENCE = "CQI"


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
                temporal.run_method_trajectory(scenarios, method_name, method, dispersion, load, seed)
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
    """Pooled mid+high dispersion (the 6 non-saturated cells), matching
    the scope used for the isolated-attribution numbers already reported."""
    rng = np.random.default_rng(temporal.BOOTSTRAP_SEED + 20)
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
                "mean_utility": float(values.mean()),
                "mean_diff_vs_cqi": float(diffs.mean()),
                "diff_vs_cqi_ci95_low": ci_low, "diff_vs_cqi_ci95_high": ci_high,
                "seeds_win_vs_cqi": int((diffs > 1e-9).sum()),
                "seeds_tie_vs_cqi": int((np.abs(diffs) <= 1e-9).sum()),
                "seeds_loss_vs_cqi": int((diffs < -1e-9).sum()),
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
    parser.add_argument("--out-dir", type=Path, default=Path("real_multiseed_power_set_confirmatory_results"))
    args = parser.parse_args()
    seeds = parse_seed_spec(args.seeds)

    temporal.progress(
        f"Power-set ablation: {len(seeds)} confirmatory seeds ({seeds[0]}..{seeds[-1]}), "
        f"{len(METHODS)} methods (all 7 non-empty subsets of {{cost,switching,regret-graph}} + CQI + CQI alone)"
    )
    rows = run_all(seeds)
    per_seed = summarize_per_seed(rows, seeds)
    pooled = summarize_pooled(per_seed, seeds)

    args.out_dir.mkdir(exist_ok=True)
    write_csv(args.out_dir / "per_transition_results.csv", rows)
    write_csv(args.out_dir / "comparison_per_seed.csv", per_seed)
    write_csv(args.out_dir / "pooled_summary.csv", pooled)

    temporal.progress("\n=== Pooled mid+high dispersion (6 non-saturated cells), all methods vs CQI alone ===")
    for row in pooled:
        if row["scope"] != "mid_high_6_cells":
            continue
        temporal.progress(
            f"  {row['method']:36s} u={row['mean_utility']:+.5f} "
            f"dCQI={row['mean_diff_vs_cqi']:+.5f} CI=[{row['diff_vs_cqi_ci95_low']:+.5f},{row['diff_vs_cqi_ci95_high']:+.5f}] "
            f"WTL={row['seeds_win_vs_cqi']}/{row['seeds_tie_vs_cqi']}/{row['seeds_loss_vs_cqi']}"
        )
    temporal.progress(f"\nWrote results to {args.out_dir}/")


if __name__ == "__main__":
    main()
