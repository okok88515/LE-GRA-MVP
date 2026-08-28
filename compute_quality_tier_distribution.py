"""Quality-tier distribution (what fraction of user-instances land at each
video quality level, or go unserved) for the same 6-method baseline
comparison, pooled over mid+high dispersion to match the established scope.

Reuses METHODS from run_real_multiseed_baseline_comparison.py and the same
temporal closed-loop primitives, but captures the raw per-user quality
assignment (`EvalResult.user_quality`) that the standard trajectory runner
discards after computing its aggregate metrics -- this is new data, not
reusable from the existing results CSVs.
"""

from __future__ import annotations

import csv
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp
import run_real_multiseed_baseline_comparison as baseline
import run_real_multiseed_temporal_closed_loop as temporal
from parse_real_simu5g_data import build_scenarios

N_TIERS = len(mvp.VIDEO_BITRATES_KBPS)  # 6 quality tiers, plus "unserved" (-1)


def run_seed_quality_counts(dispersion: str, seed: str) -> dict[str, np.ndarray]:
    """Return, per method, a length-(N_TIERS+1) count array: index 0 =
    unserved, index 1..N_TIERS = quality tiers 0..N_TIERS-1. Pooled across
    mid+high dispersion only (matching this project's established scope),
    so this function is only meaningfully called for dispersion in
    {'mid','high'}."""

    counts = {name: np.zeros(N_TIERS + 1, dtype=np.int64) for name in baseline.METHODS}
    seed_dir = temporal.DATA_ROOT / dispersion / seed
    radio_path = seed_dir / "raw_radio.csv.gz"
    mobility_path = seed_dir / "raw_mobility.csv.gz"

    for load_ratio, _load in temporal.LOADS:
        scenarios = build_scenarios(load_ratio, radio_path=radio_path, mobility_path=mobility_path)
        for method_name, method in baseline.METHODS.items():
            previous_quality = np.zeros(len(scenarios[0].cqi_now), dtype=int)
            for step, base_scenario in enumerate(scenarios):
                scenario = replace(base_scenario, previous_quality=previous_quality.copy())
                groups = method(scenario)
                result = mvp.allocate_and_evaluate(groups, scenario, temporal.SWITCH_BETA)
                assigned = result.user_quality
                if step > 0:  # exclude the shared warm-up snapshot, matching every other script
                    for q in assigned:
                        counts[method_name][int(q) + 1] += 1
                served = assigned >= 0
                previous_quality = previous_quality.copy()
                previous_quality[served] = assigned[served]
    return counts


def run_all(seeds: list[str]) -> dict[str, np.ndarray]:
    totals = {name: np.zeros(N_TIERS + 1, dtype=np.int64) for name in baseline.METHODS}
    jobs = [(dispersion, seed) for dispersion in ["mid", "high"] for seed in seeds]
    with ProcessPoolExecutor(max_workers=temporal.MAX_WORKERS) as executor:
        futures = {executor.submit(run_seed_quality_counts, d, s): (d, s) for d, s in jobs}
        for future in as_completed(futures):
            d, s = futures[future]
            result = future.result()
            for name in totals:
                totals[name] += result[name]
            temporal.progress(f"  {d}/{s} done")
    return totals


def main() -> None:
    seeds = baseline.parse_seed_spec("31-50")
    temporal.progress(f"Quality-tier distribution: {len(seeds)} seeds, mid+high dispersion, {len(baseline.METHODS)} methods")
    totals = run_all(seeds)

    out_path = Path("real_multiseed_baseline_comparison_results/quality_tier_distribution.csv")
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["method", "tier", "count", "fraction"])
        for name, counts in totals.items():
            total = counts.sum()
            for tier_idx, count in enumerate(counts):
                label = "unserved" if tier_idx == 0 else f"q{tier_idx - 1}"
                writer.writerow([name, label, int(count), float(count) / total])

    temporal.progress("\n=== Quality-tier distribution (mid+high pooled, fraction of user-instances) ===")
    for name, counts in totals.items():
        total = counts.sum()
        frac = counts / total
        parts = [f"unserved={frac[0]:.3f}"] + [f"q{i}={frac[i+1]:.3f}" for i in range(N_TIERS)]
        temporal.progress(f"  {name:28s} " + " ".join(parts))
    temporal.progress(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
