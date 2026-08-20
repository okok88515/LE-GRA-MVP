"""Pre-registered, non-searched validation of resource-cost / multi-feature
k-means against CQI k-means, no grouping, offline teacher, and LE-GRA.

Why this script exists
-----------------------
Every headline number in `SESSION_HANDOFF.md` from the `p3_6*` era comes from
scenario bundles that were hand-edited per user, or from a search script that
tried hundreds of variants and kept whichever one produced the largest
`teacher - resource-cost` (or similar) gap, or from a train/test split point
that was chosen after looking at which split made the result look best. None
of that is a valid estimate of how these methods compare in general -- it is
the argmax of a search, not a held-out result.

This script deliberately does none of that:

- Scenarios come only from `mvp.generate_scenario`, the repo's existing
  stochastic generator. No per-user field is ever hand-edited.
- Every generated scenario is scored. Nothing is filtered by outcome (no
  `min_teacher_gain` / `min_cqi_gap` / etc. thresholds).
- Train/test scenarios are independent random draws (`generate_splits`,
  reused verbatim from `run_standard_matrix.py`). No split point is chosen
  after looking at results.
- The full protocol (scenario modes, load levels, Kmax, seeds, scenario
  counts, LE-GRA hyperparameters) is fixed by the CLI defaults below *before*
  running. If you rerun this after seeing a result you don't like, changing
  only the numbers until it looks better, you have recreated the exact
  problem this script exists to avoid. Run it once per question; report what
  comes out, including negative or mixed results.

Protocol defaults (see README.md / SESSION_HANDOFF.md for provenance):

- scenario_modes: aligned, ambiguous, mixed, anti_cqi_hard, corridor_general
  -- all five built-in generative modes, not a favorable subset.
- load_levels: light (0.50), medium (0.25), heavy (0.10) -- the repo's
  standard reproducible pressure levels.
- Kmax: 3 -- matches the historical `medium_matrix_results_v2_after_grad_fix`
  reference run, and keeps the exact teacher DP search (which is
  combinatorial in Kmax: roughly sum_{k=1..Kmax} C(n_users-1, k-1) DP calls
  per training scenario) tractable at a large seed/scenario count. Kmax
  sensitivity (4, 5, 6) is a separate, explicitly-labeled follow-up, not the
  headline.
- seeds: 9, 17, 23, 31, 42, 58 -- the first three are the historical
  standard-matrix seeds; three more were added for statistical power, fixed
  before running.
- LE-GRA hyperparameters: repo defaults (feature_mode=history_cost, epochs=6,
  pair_sampling=random_balanced, pairs_per_class=160, kmeans_n_init=10). Not
  tuned here; LE-GRA is included only as a sanity check that it stays behind
  resource-cost, matching the project's decision to de-prioritize it.

Output
------
`--out-dir` gets two files:

- `per_scenario_results.csv`: long format, one row per
  (scenario_mode, load_level, seed, test_index, method) with utility and
  other metrics. This is the raw evidence; every downstream statistic in
  `summary_stats.csv` / stdout is computed from this file alone.
- `summary_stats.csv`: for each scenario_mode/load_level cell (and a pooled
  "overall" row), mean utility per method plus paired bootstrap comparisons
  for the method pairs that matter for the resource-cost/multi-feature
  thesis: Resource-cost vs CQI, Multi-feature vs CQI, Resource-cost vs
  Multi-feature, Offline teacher vs Resource-cost (the remaining headroom),
  LE-GRA vs Resource-cost (sanity check). The "overall" row's p-values are
  Holm-corrected across those 5 comparisons; per-cell p-values are not
  corrected and are exploratory/diagnostic only.
"""

from __future__ import annotations

import argparse
import csv
import random
import time
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp
from run_standard_matrix import LOAD_RATIOS, progress, train_model

SPEED_VOLATILITY_LEVELS = ["low", "mid", "high"]


def generate_splits(args, scenario_mode: str, seed: int, load_level: str) -> tuple[list, list]:
    """Like `run_standard_matrix.generate_splits`, plus a random per-scenario
    `speed_volatility` draw (analogous to the existing random `dispersion`
    draw) so scenarios naturally vary in accel/decel behavior. This is a
    local copy, not an edit to `run_standard_matrix.py`, so other scripts
    that import the original keep their exact historical RNG behavior."""

    mvp.set_seed(seed)
    dispersions = ["high", "mid", "low"]
    rb_budget_ratio = LOAD_RATIOS[load_level]
    train = [
        mvp.generate_scenario(
            args.users, args.rbs, random.choice(dispersions), scenario_mode,
            rb_budget_ratio=rb_budget_ratio,
            speed_volatility=random.choice(SPEED_VOLATILITY_LEVELS),
        )
        for _ in range(args.train_scenarios)
    ]
    test = [
        mvp.generate_scenario(
            args.users, args.rbs, random.choice(dispersions), scenario_mode,
            rb_budget_ratio=rb_budget_ratio,
            speed_volatility=random.choice(SPEED_VOLATILITY_LEVELS),
        )
        for _ in range(args.test_scenarios)
    ]
    return train, test

MAIN_METHODS = [
    "No grouping",
    "CQI k-means",
    "Resource-cost k-means",
    "Multi-feature k-means",
    "Offline teacher",
    "LE-GRA MVP",
]

# (label, method_a, method_b) -- reported as "a minus b".
HEADLINE_COMPARISONS = [
    ("resource_cost_vs_cqi", "Resource-cost k-means", "CQI k-means"),
    ("multifeature_vs_cqi", "Multi-feature k-means", "CQI k-means"),
    ("resource_cost_vs_multifeature", "Resource-cost k-means", "Multi-feature k-means"),
    ("teacher_vs_resource_cost", "Offline teacher", "Resource-cost k-means"),
    ("legra_vs_resource_cost", "LE-GRA MVP", "Resource-cost k-means"),
]

DEFAULT_SCENARIO_MODES = ["aligned", "ambiguous", "mixed", "anti_cqi_hard", "corridor_general"]
DEFAULT_SEEDS = [9, 17, 23, 31, 42, 58]


def evaluate_per_scenario(
    test: list[mvp.Scenario],
    model: mvp.MLPEncoder,
    max_groups: int,
    switch_beta: float,
    kmeans_n_init: int,
    tags: dict,
    progress_label: str,
) -> list[dict]:
    """Score every method on every test scenario individually (no aggregation).

    Unlike `run_standard_matrix.evaluate_main_methods`, this keeps one row per
    (method, test scenario) so downstream analysis can pair scenarios across
    methods and bootstrap the paired difference, instead of only comparing
    already-averaged means.
    """

    methods = mvp.default_methods(
        max_groups,
        switch_beta,
        model,
        include_multifeature_baseline=True,
        multifeature_feature_mode="full",
        kmeans_n_init=kmeans_n_init,
    )
    # Scenario-level covariates for exploratory (not pre-registered) subgroup
    # analysis, e.g. "does multi-feature's mobility/history signal help more
    # under fast movement or fast-changing CQI?" These are read directly off
    # each generated scenario, never hand-set, and logged for every scenario
    # regardless of outcome -- see `stratified_subgroup_report` docstring for
    # how they must and must not be used.
    mean_speed = [float(np.mean(scenario.speed)) for scenario in test]
    cqi_volatility = [float(np.mean(np.std(scenario.cqi_history, axis=1))) for scenario in test]
    # Per-user temporal accel/decel fluctuation (std across the 5-step speed
    # history), averaged across users -- distinct from `mean_speed`, which is
    # just the current speed level. Requires `speed_history`; scenarios from
    # sources that never populated it (see `Scenario.speed_history`) would
    # crash here, but every path used by this script goes through
    # `mvp.generate_scenario`, which always fills it in.
    speed_temporal_volatility = [
        float(np.mean(np.std(scenario.speed_history, axis=1))) for scenario in test
    ]

    rows = []
    for method_index, method_name in enumerate(MAIN_METHODS, start=1):
        progress(f"[{progress_label}] Scoring {method_name} ({method_index}/{len(MAIN_METHODS)})")
        for test_index, scenario in enumerate(test):
            groups = methods[method_name](scenario)
            result = mvp.allocate_and_evaluate(groups, scenario, switch_beta)
            rows.append(
                {
                    **tags,
                    "method": method_name,
                    "test_index": test_index,
                    "utility": result.utility,
                    "adr_kbps": result.adr_kbps,
                    "served_ratio": result.served_ratio,
                    "average_quality": result.average_quality,
                    "system_spectral_efficiency": result.system_spectral_efficiency,
                    "groups": result.groups,
                    "mean_speed": mean_speed[test_index],
                    "cqi_volatility": cqi_volatility[test_index],
                    "speed_temporal_volatility": speed_temporal_volatility[test_index],
                }
            )
    return rows


def run_matrix(args) -> list[dict]:
    all_rows: list[dict] = []
    total_jobs = len(args.scenario_modes) * len(args.load_levels) * len(args.seeds)
    job = 0
    started = time.perf_counter()
    for scenario_mode in args.scenario_modes:
        for load_level in args.load_levels:
            for seed in args.seeds:
                job += 1
                label = f"job {job}/{total_jobs} mode={scenario_mode} load={load_level} seed={seed}"
                progress(f"{label} ({time.perf_counter() - started:.1f}s elapsed)")
                mvp.set_seed(seed)
                random.seed(seed)
                train, test = generate_splits(args, scenario_mode, seed, load_level)
                mvp.apply_feature_mode(train, test, args.feature_mode)
                mvp.normalize_features(train, test)
                model = train_model(
                    train,
                    test,
                    feature_mode=args.feature_mode,
                    max_groups=args.kmax,
                    switch_beta=args.switch_beta,
                    epochs=args.epochs,
                    validation_fraction=0.0,
                    pair_sampling=args.pair_sampling,
                    pairs_per_class=args.pairs_per_class,
                    progress_label=label,
                )
                rows = evaluate_per_scenario(
                    test,
                    model,
                    max_groups=args.kmax,
                    switch_beta=args.switch_beta,
                    kmeans_n_init=args.kmeans_n_init,
                    tags={
                        "scenario_mode": scenario_mode,
                        "load_level": load_level,
                        "seed": seed,
                        "kmax": args.kmax,
                    },
                    progress_label=label,
                )
                all_rows.extend(rows)
    return all_rows


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


def paired_utility_matrix(rows: list[dict], method_a: str, method_b: str) -> np.ndarray:
    """Return per-unit (seed, test_index) utility_a - utility_b, matched exactly."""

    by_unit: dict[tuple, dict[str, float]] = {}
    for row in rows:
        unit = (row["scenario_mode"], row["load_level"], row["seed"], row["test_index"])
        by_unit.setdefault(unit, {})[row["method"]] = row["utility"]
    diffs = []
    for values in by_unit.values():
        if method_a in values and method_b in values:
            diffs.append(values[method_a] - values[method_b])
    return np.array(diffs, dtype=float)


def bootstrap_ci(diffs: np.ndarray, n_boot: int, rng: np.random.Generator) -> tuple[float, float, float, float]:
    """Percentile bootstrap on the mean of `diffs`. Returns (mean, lo95, hi95, two_sided_p)."""

    if len(diffs) == 0:
        return float("nan"), float("nan"), float("nan"), float("nan")
    mean = float(diffs.mean())
    n = len(diffs)
    boot_means = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        sample = diffs[rng.integers(0, n, size=n)]
        boot_means[i] = sample.mean()
    lo, hi = np.percentile(boot_means, [2.5, 97.5])
    p_pos = float(np.mean(boot_means <= 0.0))
    p_neg = float(np.mean(boot_means >= 0.0))
    p_two_sided = float(min(1.0, 2.0 * min(p_pos, p_neg)))
    return mean, float(lo), float(hi), p_two_sided


def paired_utility_and_covariates(
    rows: list[dict], method_a: str, method_b: str, covariate_names: list[str]
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Like `paired_utility_matrix`, but also returns each unit's requested
    scenario-level covariates, aligned index-for-index with the diffs."""

    by_unit: dict[tuple, dict] = {}
    for row in rows:
        unit = (row["scenario_mode"], row["load_level"], row["seed"], row["test_index"])
        entry = by_unit.setdefault(unit, {})
        entry[row["method"]] = row["utility"]
        for name in covariate_names:
            entry[name] = row[name]
    diffs = []
    covariates: dict[str, list] = {name: [] for name in covariate_names}
    for values in by_unit.values():
        if method_a in values and method_b in values:
            diffs.append(values[method_a] - values[method_b])
            for name in covariate_names:
                covariates[name].append(values[name])
    diffs_arr = np.array(diffs, dtype=float)
    covariate_arrs = {name: np.array(values, dtype=float) for name, values in covariates.items()}
    return diffs_arr, covariate_arrs


EXPLORATORY_COMPARISONS = [
    ("resource_cost_vs_cqi", "Resource-cost k-means", "CQI k-means"),
    ("multifeature_vs_cqi", "Multi-feature k-means", "CQI k-means"),
    ("resource_cost_vs_multifeature", "Resource-cost k-means", "Multi-feature k-means"),
]
EXPLORATORY_COVARIATES = ["mean_speed", "cqi_volatility", "speed_temporal_volatility"]


def exploratory_subgroup_report(rows: list[dict], n_boot: int, seed: int) -> list[dict]:
    """Hypothesis-generating only: does the resource-cost/multi-feature/CQI

    ranking change under fast movement, fast-changing CQI, or frequent
    accel/decel (stop-and-go traffic)? This splits the *same* pooled data
    used for the pre-registered headline by a median split on each
    scenario-level covariate -- it does not draw a new sample and does not
    filter any scenario out. Both halves of every split are always reported.
    Nothing here is Holm-combined with the confirmatory headline family in
    `summarize()`; it gets its own, separate Holm correction across its own
    tests (covariates x 2 strata x comparisons) so it is internally honest
    but not mixed with the pre-registered claim.

    A pattern found here is a hypothesis for a *future*, freshly pre-registered
    confirmatory run (e.g. a dedicated `mobility_level` or `speed_volatility`
    sweep analogous to `load_levels`), not evidence to put in a paper by
    itself.
    """

    rng = np.random.default_rng(seed)
    records = []
    p_values = []
    for label, method_a, method_b in EXPLORATORY_COMPARISONS:
        diffs, covariate_values = paired_utility_and_covariates(
            rows, method_a, method_b, EXPLORATORY_COVARIATES
        )
        for covariate_name in EXPLORATORY_COVARIATES:
            values = covariate_values[covariate_name]
            median = float(np.median(values))
            for stratum_name, mask in (
                ("low", values <= median),
                ("high", values > median),
            ):
                stratum_diffs = diffs[mask]
                mean_diff, lo, hi, p_value = bootstrap_ci(stratum_diffs, n_boot, rng)
                win_rate = float(np.mean(stratum_diffs > 0)) if len(stratum_diffs) else float("nan")
                records.append(
                    {
                        "comparison": label,
                        "method_a": method_a,
                        "method_b": method_b,
                        "covariate": covariate_name,
                        "stratum": stratum_name,
                        "stratum_median_split": median,
                        "mean_diff_a_minus_b": mean_diff,
                        "ci95_lo": lo,
                        "ci95_hi": hi,
                        "p_value_raw": p_value,
                        "p_value_holm": None,
                        "win_rate_a_over_b": win_rate,
                        "n_paired_units": len(stratum_diffs),
                    }
                )
                p_values.append(p_value)
    adjusted = holm_correction(p_values)
    for record, adj in zip(records, adjusted):
        record["p_value_holm"] = adj
    return records


def print_exploratory_summary(records: list[dict]) -> None:
    print(
        "\n=== EXPLORATORY subgroup analysis "
        "(mean_speed / cqi_volatility / speed_temporal_volatility) "
        "-- hypothesis-generating only, NOT a paper claim ==="
    )
    for r in records:
        sig = "significant" if r["p_value_holm"] < 0.05 else "not significant"
        print(
            f"{r['comparison']} | {r['covariate']}={r['stratum']} (split@{r['stratum_median_split']:.3f}): "
            f"mean(a-b)={r['mean_diff_a_minus_b']:.5f} "
            f"95% CI=[{r['ci95_lo']:.5f}, {r['ci95_hi']:.5f}] "
            f"holm_p={r['p_value_holm']:.4f} ({sig}) "
            f"win_rate={r['win_rate_a_over_b']:.3f} n={r['n_paired_units']}"
        )
    print(
        "If any 'high' stratum row looks materially different from its 'low' "
        "counterpart, treat it as a hypothesis for a fresh, pre-registered "
        "mobility-level sweep -- not as a result to report as-is."
    )


def holm_correction(p_values: list[float]) -> list[float]:
    """Holm step-down correction. Returns adjusted p-values in the input order."""

    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    adjusted = [0.0] * len(p_values)
    running_max = 0.0
    for rank, idx in enumerate(order):
        adj = (len(p_values) - rank) * p_values[idx]
        running_max = max(running_max, adj)
        adjusted[idx] = min(1.0, running_max)
    return adjusted


def summarize(rows: list[dict], n_boot: int, seed: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    summary_rows = []

    def cell_rows(scenario_mode, load_level):
        if scenario_mode is None and load_level is None:
            return rows
        return [r for r in rows if r["scenario_mode"] == scenario_mode and r["load_level"] == load_level]

    cells = [(m, l) for m in sorted({r["scenario_mode"] for r in rows}) for l in sorted({r["load_level"] for r in rows})]
    cells.append((None, None))  # pooled "overall" row group

    for scenario_mode, load_level in cells:
        cell = cell_rows(scenario_mode, load_level)
        if not cell:
            continue
        mean_utility = {}
        for method in MAIN_METHODS:
            values = [r["utility"] for r in cell if r["method"] == method]
            if values:
                mean_utility[method] = float(np.mean(values))

        is_overall = scenario_mode is None
        cell_p_values = []
        cell_records = []
        for label, method_a, method_b in HEADLINE_COMPARISONS:
            diffs = paired_utility_matrix(cell, method_a, method_b)
            mean_diff, lo, hi, p_value = bootstrap_ci(diffs, n_boot, rng)
            win_rate = float(np.mean(diffs > 0)) if len(diffs) else float("nan")
            tie_rate = float(np.mean(diffs == 0)) if len(diffs) else float("nan")
            record = {
                "scenario_mode": "ALL" if is_overall else scenario_mode,
                "load_level": "ALL" if is_overall else load_level,
                "comparison": label,
                "method_a": method_a,
                "method_b": method_b,
                "mean_utility_a": mean_utility.get(method_a, float("nan")),
                "mean_utility_b": mean_utility.get(method_b, float("nan")),
                "mean_diff_a_minus_b": mean_diff,
                "ci95_lo": lo,
                "ci95_hi": hi,
                "p_value_raw": p_value,
                "p_value_holm": None,
                "win_rate_a_over_b": win_rate,
                "tie_rate": tie_rate,
                "n_paired_units": len(diffs),
            }
            cell_records.append(record)
            cell_p_values.append(p_value)

        if is_overall:
            adjusted = holm_correction(cell_p_values)
            for record, adj in zip(cell_records, adjusted):
                record["p_value_holm"] = adj

        summary_rows.extend(cell_records)

    return summary_rows


def print_summary(summary_rows: list[dict]) -> None:
    overall = [r for r in summary_rows if r["scenario_mode"] == "ALL"]
    print("\n=== Pooled ('ALL' modes/loads) headline comparisons, Holm-corrected ===")
    for r in overall:
        sig = "significant" if r["p_value_holm"] < 0.05 else "not significant"
        print(
            f"{r['comparison']}: mean(a-b)={r['mean_diff_a_minus_b']:.5f} "
            f"95% CI=[{r['ci95_lo']:.5f}, {r['ci95_hi']:.5f}] "
            f"holm_p={r['p_value_holm']:.4f} ({sig}) "
            f"win_rate={r['win_rate_a_over_b']:.3f} n={r['n_paired_units']}"
        )
    print("\nPer-cell breakdowns (exploratory, not multiple-comparison corrected) are in summary_stats.csv.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--train-scenarios", type=int, default=60)
    parser.add_argument("--test-scenarios", type=int, default=30)
    parser.add_argument("--users", type=int, default=24)
    parser.add_argument("--rbs", type=int, default=100)
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--kmax", type=int, default=3, help="Fixed Kmax for the headline run; see module docstring.")
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--kmeans-n-init", type=int, default=10)
    parser.add_argument("--pair-sampling", choices=["random_balanced", "hard_negative"], default="random_balanced")
    parser.add_argument("--pairs-per-class", type=int, default=160)
    parser.add_argument("--feature-mode", default="history_cost")
    parser.add_argument("--scenario-modes", nargs="+", default=DEFAULT_SCENARIO_MODES)
    parser.add_argument("--load-levels", nargs="+", choices=list(LOAD_RATIOS), default=["light", "medium", "heavy"])
    parser.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--n-boot", type=int, default=10000)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    parser.add_argument("--out-dir", type=Path, default=Path("clean_resource_cost_validation_results"))
    args = parser.parse_args()

    started = time.perf_counter()
    progress(
        f"Pre-registered protocol: modes={args.scenario_modes}, loads={args.load_levels}, "
        f"kmax={args.kmax}, seeds={args.seeds}, train={args.train_scenarios}, test={args.test_scenarios}"
    )
    rows = run_matrix(args)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "per_scenario_results.csv", rows)
    summary_rows = summarize(rows, n_boot=args.n_boot, seed=args.bootstrap_seed)
    write_csv(args.out_dir / "summary_stats.csv", summary_rows)
    print_summary(summary_rows)

    exploratory_rows = exploratory_subgroup_report(rows, n_boot=args.n_boot, seed=args.bootstrap_seed + 1)
    write_csv(args.out_dir / "exploratory_mobility_subgroups.csv", exploratory_rows)
    print_exploratory_summary(exploratory_rows)

    progress(f"Done in {time.perf_counter() - started:.1f}s. Wrote {args.out_dir}/")


if __name__ == "__main__":
    main()
