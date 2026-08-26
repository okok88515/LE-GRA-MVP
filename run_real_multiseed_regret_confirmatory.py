"""Confirmatory evaluation of research direction 2's finding
(`REAL_SIMU5G_REGRET_GRAPH_TEMPORAL_DIRECTION.md`) on an independent seed
set never used to discover or characterize it.

Direction 2's exploratory result (seeds 1..10) found that
`CQI+cost+regret-graph 3-way union` (no switching family) matches or beats
the shipped `CQI+cost+switching 3-way union` headline under the real
temporal closed loop, with a clear head-to-head win at all three
high-dispersion cells. This does not retune anything -- it only re-evaluates
the same fixed method set (imported, not duplicated, from
`run_real_multiseed_regret_temporal_direction.py`) on a fresh seed range.

Seeds 1..30 are all already "used": 1..10 for both direction 1 and
direction 2's exploratory passes, 11..30 for the switching-gate
confirmatory pass. This defaults to seeds 31..50, the next untouched block.

Usage:
    python run_real_multiseed_regret_confirmatory.py --seeds 31-50
"""

from __future__ import annotations

import argparse
import csv
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

import run_real_multiseed_regret_temporal_direction as direction2
import run_real_multiseed_temporal_closed_loop as temporal
from parse_real_simu5g_data import build_scenarios

REFERENCES = [
    ("CQI k-means", "cqi"),
    ("CQI+cost+switching 3-way union", "3way"),
]


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
        for method_name, method in direction2.METHODS.items():
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
            temporal.progress(f"  {dispersion}/{seed} confirmatory done")
    return rows


def summarize_per_seed(rows: list[dict], seeds: list[str]) -> list[dict]:
    evaluated = [row for row in rows if not row["is_warmup"]]
    result: list[dict] = []
    for dispersion in temporal.DISPERSIONS:
        for _, load in temporal.LOADS:
            for seed in seeds:
                for method in direction2.METHODS:
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


def summarize_across_seeds(per_seed: list[dict], seeds: list[str]) -> list[dict]:
    rng = np.random.default_rng(temporal.BOOTSTRAP_SEED + 11)
    summaries: list[dict] = []
    for dispersion in temporal.DISPERSIONS:
        for _, load in temporal.LOADS:
            cell = [row for row in per_seed if row["dispersion"] == dispersion and row["load"] == load]
            by_method = {
                method: {row["seed"]: row for row in cell if row["method"] == method}
                for method in direction2.METHODS
            }
            for method in direction2.METHODS:
                utilities = np.array([by_method[method][seed]["mean_utility"] for seed in seeds])
                summary: dict[str, object] = {
                    "dispersion": dispersion, "load": load, "method": method,
                    "mean_utility": float(utilities.mean()),
                }
                for reference, suffix in REFERENCES:
                    diffs = np.array([
                        by_method[method][seed]["mean_utility"] - by_method[reference][seed]["mean_utility"]
                        for seed in seeds
                    ])
                    ci_low, ci_high = temporal.bootstrap_mean_ci(diffs, rng)
                    summary.update({
                        f"mean_diff_vs_{suffix}": float(diffs.mean()),
                        f"diff_vs_{suffix}_ci95_low": ci_low,
                        f"diff_vs_{suffix}_ci95_high": ci_high,
                        f"seeds_win_vs_{suffix}": int((diffs > 1e-9).sum()),
                        f"seeds_tie_vs_{suffix}": int((np.abs(diffs) <= 1e-9).sum()),
                        f"seeds_loss_vs_{suffix}": int((diffs < -1e-9).sum()),
                    })
                summaries.append(summary)
    return summaries


def summarize_pooled(per_seed: list[dict], seeds: list[str]) -> list[dict]:
    rng = np.random.default_rng(temporal.BOOTSTRAP_SEED + 12)
    outputs: list[dict] = []
    scopes = {"all_9_cells": set(temporal.DISPERSIONS), "high_only_3_cells": {"high"}}
    for scope, allowed in scopes.items():
        by_method_seed: dict[str, dict[str, float]] = {}
        for method in direction2.METHODS:
            by_method_seed[method] = {}
            for seed in seeds:
                selected = [
                    row for row in per_seed
                    if row["method"] == method and row["seed"] == seed and row["dispersion"] in allowed
                ]
                by_method_seed[method][seed] = float(np.mean([row["mean_utility"] for row in selected]))
        for method in direction2.METHODS:
            values = np.array([by_method_seed[method][seed] for seed in seeds])
            row: dict[str, object] = {"scope": scope, "method": method, "mean_utility": float(values.mean())}
            for reference, suffix in REFERENCES:
                diffs = np.array([by_method_seed[method][seed] - by_method_seed[reference][seed] for seed in seeds])
                ci_low, ci_high = temporal.bootstrap_mean_ci(diffs, rng)
                row.update({
                    f"mean_diff_vs_{suffix}": float(diffs.mean()),
                    f"diff_vs_{suffix}_ci95_low": ci_low,
                    f"diff_vs_{suffix}_ci95_high": ci_high,
                    f"seeds_win_vs_{suffix}": int((diffs > 1e-9).sum()),
                    f"seeds_tie_vs_{suffix}": int((np.abs(diffs) <= 1e-9).sum()),
                    f"seeds_loss_vs_{suffix}": int((diffs < -1e-9).sum()),
                })
            outputs.append(row)
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
    parser.add_argument("--out-dir", type=Path, default=Path("real_multiseed_regret_confirmatory_results"))
    args = parser.parse_args()
    seeds = parse_seed_spec(args.seeds)

    temporal.progress(
        f"Direction 2 confirmatory run: {len(seeds)} independent seeds ({seeds[0]}..{seeds[-1]}), "
        f"never used for direction 1, direction 2 exploratory, or the switching-gate confirmatory pass"
    )
    rows = run_all(seeds)
    per_seed = summarize_per_seed(rows, seeds)
    across_seeds = summarize_across_seeds(per_seed, seeds)
    pooled = summarize_pooled(per_seed, seeds)

    args.out_dir.mkdir(exist_ok=True)
    write_csv(args.out_dir / "per_transition_results.csv", rows)
    write_csv(args.out_dir / "comparison_per_seed.csv", per_seed)
    write_csv(args.out_dir / "comparison_across_seeds.csv", across_seeds)
    write_csv(args.out_dir / "pooled_summary.csv", pooled)

    temporal.progress("\n=== Confirmatory: regret-graph 3-way vs switching 3-way headline (high-only pooled) ===")
    for row in pooled:
        if row["scope"] != "high_only_3_cells":
            continue
        temporal.progress(
            f"  {row['method']:48s} u={row['mean_utility']:+.6f} "
            f"dCQI={row['mean_diff_vs_cqi']:+.6f} CI=[{row['diff_vs_cqi_ci95_low']:+.6f},{row['diff_vs_cqi_ci95_high']:+.6f}] "
            f"d3way={row['mean_diff_vs_3way']:+.6f} CI=[{row['diff_vs_3way_ci95_low']:+.6f},{row['diff_vs_3way_ci95_high']:+.6f}]"
        )
    temporal.progress("\n=== Confirmatory: per dispersion x load, vs switching 3-way headline ===")
    for row in across_seeds:
        if row["method"] not in ("CQI+cost+regret-graph 3-way union", "CQI+cost+switching+regret-graph 4-way union"):
            continue
        temporal.progress(
            f"  {row['dispersion']:4s} {row['load']:6s} {row['method']:44s} "
            f"d3way={row['mean_diff_vs_3way']:+.5f} "
            f"CI=[{row['diff_vs_3way_ci95_low']:+.5f},{row['diff_vs_3way_ci95_high']:+.5f}] "
            f"WTL={row['seeds_win_vs_3way']}/{row['seeds_tie_vs_3way']}/{row['seeds_loss_vs_3way']}"
        )
    temporal.progress(f"\nWrote confirmatory results to {args.out_dir}/")


if __name__ == "__main__":
    main()
