"""Phase 2 confirmatory test of the Phase 1 exploratory hypothesis: does
multi-feature k-means's advantage over resource-cost k-means (and CQI
k-means) grow with CQI temporal volatility?

Why this script exists
-----------------------
Phase 1 (`run_clean_resource_cost_validation.py`) found, via a POST-HOC
median split of already-collected data, that multi-feature's edge over
resource-cost grows with mean_speed and cqi_volatility (but shrinks with
speed-history accel/decel volatility -- the opposite of that particular
sub-hypothesis). That was explicitly hypothesis-generating, not
confirmatory -- reporting it as evidence would repeat the exact mistake
this whole audit exists to prevent.

This script originally also planned to manipulate vehicle speed as a
second controlled variable, but a smoke test plus the user's own reasoning
ruled that out *before* running anything at scale, for a principled reason,
not because the smoke result was unwelcome:

1. Mechanistically, `multi_feature_kmeans_grouping` z-score-normalizes every
   feature *within each scenario* before clustering (le_gra_mvp.py, around
   `multi_feature_kmeans_grouping`). Shifting every user's speed by the same
   level (e.g. 20-35 -> 65-90 km/h) leaves the *relative* structure across
   users unchanged, so it normalizes away completely -- confirmed directly:
   the exact same grouping came out at low/mid/high speed level for an
   otherwise-identical scenario.
2. More fundamentally (the user's point): speed's only physically plausible
   channel-relevant effect is *mediated through* the rate of distance change
   to the serving cell, which is exactly what drives CQI temporal
   volatility. Once CQI volatility is already a controlled variable, speed
   is a redundant, causally upstream variable with no independent
   information left to contribute.

So this script tests only `cqi_temporal_volatility` (see
`le_gra_mvp.generate_scenario`) as a controlled independent variable, the
same way `load_levels` already controls resource pressure. No scenario is
hand-edited; no scenario is filtered by outcome; the protocol below is fixed
before running and is not to be re-tuned after seeing results.

Pre-registered protocol
------------------------
- scenario_mode: ambiguous only (fixed -- the one mode motivated by real
  OFDMA frequency-selective-fading physics rather than by search; see
  project memory `review-le-gra-methodology`).
- load_level: medium only (fixed -- a deliberate middle ground so this
  isn't confounded with the load-dependent sign flip Phase 1 found for
  resource_cost_vs_cqi).
- Kmax: 3 (matches Phase 1).
- speed_level: left at each mode's own default range (not manipulated, per
  the reasoning above).
- cqi_temporal_volatility: {low, mid, high}.
- seeds: the same 6 seeds as Phase 1 (9, 17, 23, 31, 42, 58).
- scenarios per (condition, seed): 180 -- 3x the original 60, since dropping
  the speed_level cross frees up the same total scenario budget (3240) to
  concentrate on the one variable with a plausible causal path.
- Methods scored: CQI k-means, Resource-cost k-means, Multi-feature
  k-means only. Offline teacher and LE-GRA are intentionally out of scope
  for this specific hypothesis and are skipped to avoid paying for the
  expensive teacher-label DP search / MLP training this script has no use
  for.

Primary confirmatory test: an OLS regression of
  (multifeature_utility - resource_cost_utility)
on standardized cqi_temporal_volatility (coded low=-1, mid=0, high=+1),
with a percentile-bootstrap CI on the coefficient (unit = one generated
scenario). A positive, CI-excludes-zero coefficient supports "the gap grows
with CQI volatility"; this is the one result this script is registered to
report as a confirmatory claim.

Secondary diagnostic: the raw 3-level cell table (Holm-corrected within its
own family, for both multifeature_vs_resource_cost and multifeature_vs_cqi)
-- for transparency and to catch non-monotonic patterns a linear regression
would miss, not as an additional claim.
"""

from __future__ import annotations

import argparse
import csv
import random
import time
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp

LEVELS = ["low", "mid", "high"]
LEVEL_NUMERIC = {"low": -1.0, "mid": 0.0, "high": 1.0}
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
    total_jobs = len(LEVELS) * len(args.seeds)
    job = 0
    started = time.perf_counter()
    for cqi_volatility in LEVELS:
        for seed in args.seeds:
            job += 1
            progress(
                f"job {job}/{total_jobs} cqi_temporal_volatility={cqi_volatility} seed={seed} "
                f"({time.perf_counter() - started:.1f}s elapsed)"
            )
            mvp.set_seed(seed)
            random.seed(seed)
            scenarios = [
                mvp.generate_scenario(
                    args.users,
                    args.rbs,
                    random.choice(["low", "mid", "high"]),
                    "ambiguous",
                    rb_budget_ratio=args.rb_budget_ratio,
                    cqi_temporal_volatility=cqi_volatility,
                )
                for _ in range(args.scenarios_per_condition)
            ]
            for scenario_index, scenario in enumerate(scenarios):
                for method_name, method_fn in METHODS.items():
                    groups = method_fn(scenario, args.kmax, args.switch_beta, args.kmeans_n_init)
                    result = mvp.allocate_and_evaluate(groups, scenario, args.switch_beta)
                    rows.append(
                        {
                            "cqi_temporal_volatility": cqi_volatility,
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


def paired_diff_with_factor(rows: list[dict], method_a: str, method_b: str) -> tuple[np.ndarray, np.ndarray]:
    """Return (diff, cqi_numeric) arrays, one entry per unique
    (cqi_temporal_volatility, seed, scenario_index) unit."""

    by_unit: dict[tuple, dict] = {}
    for row in rows:
        unit = (row["cqi_temporal_volatility"], row["seed"], row["scenario_index"])
        entry = by_unit.setdefault(unit, {"cqi_temporal_volatility": row["cqi_temporal_volatility"]})
        entry[row["method"]] = row["utility"]
    diffs, cqi_numeric = [], []
    for values in by_unit.values():
        if method_a in values and method_b in values:
            diffs.append(values[method_a] - values[method_b])
            cqi_numeric.append(LEVEL_NUMERIC[values["cqi_temporal_volatility"]])
    return np.array(diffs, dtype=float), np.array(cqi_numeric, dtype=float)


def fit_ols(y: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Fit y ~ 1 + x by least squares. Returns [intercept, slope]."""

    design = np.column_stack([np.ones_like(y), x])
    coefs, *_ = np.linalg.lstsq(design, y, rcond=None)
    return coefs


def bootstrap_ols_ci(y: np.ndarray, x: np.ndarray, n_boot: int, rng: np.random.Generator) -> list[dict]:
    point = fit_ols(y, x)
    n = len(y)
    boot_coefs = np.empty((n_boot, 2), dtype=float)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        boot_coefs[i] = fit_ols(y[idx], x[idx])
    names = ["intercept", "cqi_temporal_volatility_coef"]
    records = []
    for j, name in enumerate(names):
        lo, hi = np.percentile(boot_coefs[:, j], [2.5, 97.5])
        p_pos = float(np.mean(boot_coefs[:, j] <= 0.0))
        p_neg = float(np.mean(boot_coefs[:, j] >= 0.0))
        p_two_sided = float(min(1.0, 2.0 * min(p_pos, p_neg)))
        records.append(
            {
                "coefficient": name,
                "point_estimate": float(point[j]),
                "ci95_lo": float(lo),
                "ci95_hi": float(hi),
                "p_value": p_two_sided,
            }
        )
    return records


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


def cell_table(rows: list[dict], method_a: str, method_b: str, n_boot: int, rng: np.random.Generator) -> list[dict]:
    records = []
    p_values = []
    for cqi_volatility in LEVELS:
        cell_rows = [r for r in rows if r["cqi_temporal_volatility"] == cqi_volatility]
        by_unit: dict[tuple, dict] = {}
        for row in cell_rows:
            unit = (row["seed"], row["scenario_index"])
            by_unit.setdefault(unit, {})[row["method"]] = row["utility"]
        diffs = np.array(
            [v[method_a] - v[method_b] for v in by_unit.values() if method_a in v and method_b in v],
            dtype=float,
        )
        mean, lo, hi, p = bootstrap_ci(diffs, n_boot, rng)
        records.append(
            {
                "cqi_temporal_volatility": cqi_volatility,
                "mean_diff_a_minus_b": mean,
                "ci95_lo": lo,
                "ci95_hi": hi,
                "p_value_raw": p,
                "p_value_holm": None,
                "n": len(diffs),
            }
        )
        p_values.append(p)
    adjusted = holm_correction(p_values)
    for record, adj in zip(records, adjusted):
        record["p_value_holm"] = adj
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--users", type=int, default=24)
    parser.add_argument("--rbs", type=int, default=100)
    parser.add_argument("--kmax", type=int, default=3)
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--kmeans-n-init", type=int, default=10)
    parser.add_argument("--rb-budget-ratio", type=float, default=0.25, help="medium load, matches Phase 1")
    parser.add_argument("--scenarios-per-condition", type=int, default=180)
    parser.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--n-boot", type=int, default=10000)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    parser.add_argument("--out-dir", type=Path, default=Path("mobility_confirmatory_validation_results"))
    args = parser.parse_args()

    started = time.perf_counter()
    progress(
        f"Pre-registered protocol: scenario_mode=ambiguous, load=medium, kmax={args.kmax}, "
        f"cqi_temporal_volatility=low/mid/high (speed_level not manipulated -- mediated by CQI "
        f"volatility, see module docstring), seeds={args.seeds}, "
        f"scenarios_per_condition={args.scenarios_per_condition}"
    )
    rows = run_matrix(args)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "per_scenario_results.csv", rows)

    rng = np.random.default_rng(args.bootstrap_seed)

    print("\n=== PRIMARY confirmatory test: OLS trend of (multifeature - resource_cost) on CQI temporal volatility ===")
    diffs, cqi_numeric = paired_diff_with_factor(rows, "Multi-feature k-means", "Resource-cost k-means")
    primary_records = bootstrap_ols_ci(diffs, cqi_numeric, args.n_boot, rng)
    for r in primary_records:
        sig = "significant" if r["p_value"] < 0.05 else "not significant"
        print(f"{r['coefficient']}: point={r['point_estimate']:+.5f} 95% CI=[{r['ci95_lo']:+.5f},{r['ci95_hi']:+.5f}] p={r['p_value']:.4f} ({sig})")
    write_csv(args.out_dir / "primary_ols_multifeature_vs_resource_cost.csv", primary_records)

    print("\n=== Secondary context: same OLS trend test for multifeature vs CQI, and resource_cost vs CQI ===")
    secondary_all = []
    for label, a, b in [("multifeature_vs_cqi", "Multi-feature k-means", "CQI k-means"),
                         ("resource_cost_vs_cqi", "Resource-cost k-means", "CQI k-means")]:
        d, cq = paired_diff_with_factor(rows, a, b)
        recs = bootstrap_ols_ci(d, cq, args.n_boot, rng)
        for r in recs:
            r["comparison"] = label
            sig = "significant" if r["p_value"] < 0.05 else "not significant"
            print(f"{label} | {r['coefficient']}: point={r['point_estimate']:+.5f} 95% CI=[{r['ci95_lo']:+.5f},{r['ci95_hi']:+.5f}] p={r['p_value']:.4f} ({sig})")
        secondary_all.extend(recs)
    write_csv(args.out_dir / "secondary_ols_context.csv", secondary_all)

    print("\n=== Diagnostic (Holm-corrected within family, NOT a separate claim): 3-level cell table ===")
    diagnostic_all = []
    for label, a, b in [("multifeature_vs_resource_cost", "Multi-feature k-means", "Resource-cost k-means"),
                         ("multifeature_vs_cqi", "Multi-feature k-means", "CQI k-means")]:
        cells = cell_table(rows, a, b, args.n_boot, rng)
        for c in cells:
            c["comparison"] = label
            sig = "significant" if c["p_value_holm"] < 0.05 else "not significant"
            print(
                f"{label} | cqi_vol={c['cqi_temporal_volatility']:4s}: "
                f"mean={c['mean_diff_a_minus_b']:+.5f} CI=[{c['ci95_lo']:+.5f},{c['ci95_hi']:+.5f}] "
                f"holm_p={c['p_value_holm']:.4f} ({sig}) n={c['n']}"
            )
        diagnostic_all.extend(cells)
    write_csv(args.out_dir / "diagnostic_cell_table.csv", diagnostic_all)

    progress(f"Done in {time.perf_counter() - started:.1f}s. Wrote {args.out_dir}/")


if __name__ == "__main__":
    main()
