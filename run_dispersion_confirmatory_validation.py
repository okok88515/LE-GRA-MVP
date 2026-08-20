"""Phase 4 confirmatory test: does resource-cost k-means's advantage (or
disadvantage) over CQI k-means depend on CQI *dispersion* (`generate_scenario`'s
"high"/"mid"/"low" cross-user CQI spread)?

Why this script exists
-----------------------
Phase 1 (`run_clean_resource_cost_validation.py`) found that pooled across all
5 scenario_modes and 3 load_levels, resource-cost k-means is NOT reliably
better than CQI k-means (not significant overall), but the per-cell breakdown
showed a clear sign flip: resource-cost was significantly WORSE in `aligned`
mode across all loads and in `ambiguous/heavy`, but significantly BETTER in
`ambiguous/light` and `corridor_general/heavy`. `dispersion` (high/mid/low
cross-user CQI spread) was never held fixed in that run -- it was drawn
randomly per scenario inside `generate_splits` -- so it was never tested as
its own controlled variable, only mean_speed / cqi_volatility /
speed_temporal_volatility were (see `exploratory_mobility_subgroups.csv`).

This matters because the user's own published k-GBRM paper reports
high/mid/low-*dispersed*-CQI as one of its own headline test conditions
(alongside cell radius), and the user's own experiment with something
CQI+resource-cost-like beat pure CQI there. That is not automatically in
conflict with the Phase 1 "not reliably better, pooled" finding -- it would
only be in conflict if resource-cost also lost or tied at whichever
dispersion level the user's own test happened to use. This script checks that
directly instead of guessing.

Pre-registered protocol
------------------------
- scenario_mode: {aligned, ambiguous} -- the two non-adversarial, physically
  motivated modes (anti_cqi_hard and corridor_general are deliberately
  excluded: they are adversarial/general-mobility stress tests, not standard
  "CQI-dispersion" conditions comparable to the paper's setup).
- dispersion: {low, mid, high} -- the controlled variable this script exists
  to test, held fixed per condition instead of drawn randomly.
- load_level: {light, medium, heavy} -- already known from Phase 1 to
  interact with the resource_cost_vs_cqi sign, kept as a second factor so a
  dispersion effect is not confounded with it.
- Kmax=3, seeds = the same 6 as Phase 1 (9, 17, 23, 31, 42, 58), 120 scenarios
  per (mode, dispersion, load, seed) cell.
- Methods scored: CQI k-means, Resource-cost k-means, Multi-feature k-means
  (multi-feature kept only as secondary context, not the primary question
  here).

Primary confirmatory test: for each of the 18 (mode, dispersion, load) cells,
the paired bootstrap mean of (resource_cost_utility - cqi_utility), Holm-
corrected across all 18 cells. This directly answers "at which dispersion
level(s), if any, does resource-cost k-means beat CQI k-means" -- the
question needed to reconcile Phase 1's pooled null with the user's own
paper's reported result.
"""

from __future__ import annotations

import argparse
import csv
import random
import time
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp
from run_standard_matrix import LOAD_RATIOS

DISPERSIONS = ["low", "mid", "high"]
MODES = ["aligned", "ambiguous"]
DEFAULT_SEEDS = [9, 17, 23, 31, 42, 58]

METHODS = {
    "CQI k-means": lambda s, kmax, beta, n_init: mvp.cqi_kmeans_grouping(s, kmax, beta, n_init),
    "Resource-cost k-means": lambda s, kmax, beta, n_init: mvp.resource_cost_kmeans_grouping(s, kmax, beta, n_init),
    "Multi-feature k-means": lambda s, kmax, beta, n_init: mvp.multi_feature_kmeans_grouping(
        s, kmax, beta, feature_mode="full", kmeans_n_init=n_init
    ),
}


def progress(message: str) -> None:
    print(message, flush=True)


def run_matrix(args) -> list[dict]:
    rows = []
    total_jobs = len(MODES) * len(DISPERSIONS) * len(args.load_levels) * len(args.seeds)
    job = 0
    started = time.perf_counter()
    for scenario_mode in MODES:
        for dispersion in DISPERSIONS:
            for load_level in args.load_levels:
                rb_budget_ratio = LOAD_RATIOS[load_level]
                for seed in args.seeds:
                    job += 1
                    progress(
                        f"job {job}/{total_jobs} mode={scenario_mode} dispersion={dispersion} "
                        f"load={load_level} seed={seed} ({time.perf_counter() - started:.1f}s elapsed)"
                    )
                    mvp.set_seed(seed)
                    random.seed(seed)
                    scenarios = [
                        mvp.generate_scenario(
                            args.users,
                            args.rbs,
                            dispersion,
                            scenario_mode,
                            rb_budget_ratio=rb_budget_ratio,
                        )
                        for _ in range(args.scenarios_per_condition)
                    ]
                    for scenario_index, scenario in enumerate(scenarios):
                        for method_name, method_fn in METHODS.items():
                            groups = method_fn(scenario, args.kmax, args.switch_beta, args.kmeans_n_init)
                            result = mvp.allocate_and_evaluate(groups, scenario, args.switch_beta)
                            rows.append(
                                {
                                    "scenario_mode": scenario_mode,
                                    "dispersion": dispersion,
                                    "load_level": load_level,
                                    "seed": seed,
                                    "scenario_index": scenario_index,
                                    "method": method_name,
                                    "utility": result.utility,
                                }
                            )
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def bootstrap_ci(diffs: np.ndarray, n_boot: int, rng: np.random.Generator) -> tuple[float, float, float, float]:
    if len(diffs) == 0:
        return float("nan"), float("nan"), float("nan"), float("nan")
    mean = float(diffs.mean())
    n = len(diffs)
    boot_means = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        boot_means[i] = diffs[rng.integers(0, n, size=n)].mean()
    lo, hi = np.percentile(boot_means, [2.5, 97.5])
    p_pos = float(np.mean(boot_means <= 0.0))
    p_neg = float(np.mean(boot_means >= 0.0))
    return mean, float(lo), float(hi), float(min(1.0, 2.0 * min(p_pos, p_neg)))


def holm_correction(p_values: list[float]) -> list[float]:
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    adjusted = [0.0] * len(p_values)
    running_max = 0.0
    for rank, idx in enumerate(order):
        adj = (len(p_values) - rank) * p_values[idx]
        running_max = max(running_max, adj)
        adjusted[idx] = min(1.0, running_max)
    return adjusted


def cell_table(
    rows: list[dict], method_a: str, method_b: str, n_boot: int, rng: np.random.Generator
) -> list[dict]:
    records = []
    p_values = []
    cells = [(m, d, l) for m in MODES for d in DISPERSIONS for l in sorted({r["load_level"] for r in rows})]
    for scenario_mode, dispersion, load_level in cells:
        cell_rows = [
            r
            for r in rows
            if r["scenario_mode"] == scenario_mode and r["dispersion"] == dispersion and r["load_level"] == load_level
        ]
        by_unit: dict[tuple, dict] = {}
        for row in cell_rows:
            unit = (row["seed"], row["scenario_index"])
            by_unit.setdefault(unit, {})[row["method"]] = row["utility"]
        diffs = np.array(
            [v[method_a] - v[method_b] for v in by_unit.values() if method_a in v and method_b in v],
            dtype=float,
        )
        mean, lo, hi, p = bootstrap_ci(diffs, n_boot, rng)
        win_rate = float(np.mean(diffs > 0)) if len(diffs) else float("nan")
        records.append(
            {
                "scenario_mode": scenario_mode,
                "dispersion": dispersion,
                "load_level": load_level,
                "mean_diff_a_minus_b": mean,
                "ci95_lo": lo,
                "ci95_hi": hi,
                "p_value_raw": p,
                "p_value_holm": None,
                "win_rate_a_over_b": win_rate,
                "n": len(diffs),
            }
        )
        p_values.append(p)
    adjusted = holm_correction(p_values)
    for record, adj in zip(records, adjusted):
        record["p_value_holm"] = adj
    return records


def print_cell_table(label: str, records: list[dict]) -> None:
    print(f"\n=== {label} (Holm-corrected across all 18 cells) ===")
    for r in records:
        sig = "significant" if r["p_value_holm"] < 0.05 else "not significant"
        print(
            f"mode={r['scenario_mode']:9s} dispersion={r['dispersion']:4s} load={r['load_level']:6s}: "
            f"mean(a-b)={r['mean_diff_a_minus_b']:+.5f} 95% CI=[{r['ci95_lo']:+.5f},{r['ci95_hi']:+.5f}] "
            f"holm_p={r['p_value_holm']:.4f} ({sig}) win_rate={r['win_rate_a_over_b']:.3f} n={r['n']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--users", type=int, default=24)
    parser.add_argument("--rbs", type=int, default=100)
    parser.add_argument("--kmax", type=int, default=3)
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--kmeans-n-init", type=int, default=10)
    parser.add_argument("--load-levels", nargs="+", choices=list(LOAD_RATIOS), default=["light", "medium", "heavy"])
    parser.add_argument("--scenarios-per-condition", type=int, default=120)
    parser.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--n-boot", type=int, default=10000)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    parser.add_argument("--out-dir", type=Path, default=Path("dispersion_confirmatory_validation_results"))
    args = parser.parse_args()

    started = time.perf_counter()
    progress(
        f"Pre-registered protocol: scenario_modes={MODES}, dispersions={DISPERSIONS}, "
        f"load_levels={args.load_levels}, kmax={args.kmax}, seeds={args.seeds}, "
        f"scenarios_per_condition={args.scenarios_per_condition}"
    )
    rows = run_matrix(args)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "per_scenario_results.csv", rows)

    rng = np.random.default_rng(args.bootstrap_seed)

    primary = cell_table(rows, "Resource-cost k-means", "CQI k-means", args.n_boot, rng)
    print_cell_table("PRIMARY: Resource-cost k-means minus CQI k-means, by (mode, dispersion, load)", primary)
    write_csv(args.out_dir / "primary_resource_cost_vs_cqi_by_dispersion.csv", primary)

    secondary = cell_table(rows, "Multi-feature k-means", "CQI k-means", args.n_boot, rng)
    print_cell_table(
        "SECONDARY CONTEXT: Multi-feature k-means minus CQI k-means, by (mode, dispersion, load)", secondary
    )
    write_csv(args.out_dir / "secondary_multifeature_vs_cqi_by_dispersion.csv", secondary)

    progress(f"Done in {time.perf_counter() - started:.1f}s. Wrote {args.out_dir}/")


if __name__ == "__main__":
    main()
