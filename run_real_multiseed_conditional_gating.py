"""Closed-loop conditional gating for the switching candidate family.

The robust CQI+resource-cost 2-way union is the fallback.  On each decision
state, the best switching-aware candidate is admitted only when its exact-DP
utility exceeds the best 2-way candidate by more than a margin ``eta``.

Candidate eta values are evaluated as genuinely separate closed-loop paths.
The deployment eta is then selected with leave-one-seed-out cross-validation:
the same seed number is held out jointly across every dispersion and load, and
one global eta is chosen from the other nine seeds.  This prevents per-cell
threshold tuning and keeps the held-out trajectory out of model selection.
"""

from __future__ import annotations

import csv
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp
from parse_real_simu5g_data import build_scenarios
import run_real_multiseed_temporal_closed_loop as temporal
import run_real_multiseed_temporal_regime_analysis as regime


OUT_DIR = Path("real_multiseed_conditional_gating_results")
BASELINE_PATH = temporal.OUT_DIR / "per_transition_results.csv"
ETA_VALUES = [0.0, 0.005, 0.010, 0.020, 0.030, 0.050, float("inf")]
TIE_TOLERANCE = 1e-12

BASELINE_METHODS = [
    "CQI k-means",
    "CQI+cost 2-way union",
    "CQI+cost+switching 3-way union",
]
CV_METHOD = "Conditional switching gate (LOSO)"
COMPARISON_METHODS = BASELINE_METHODS + [CV_METHOD]

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


def eta_label(eta: float) -> str:
    if np.isinf(eta):
        return "eta_inf"
    return f"eta_{eta:.3f}"


def _best_candidate(
    scenario: mvp.Scenario,
    candidates: list[list[list[int]]],
    cache: dict[tuple[tuple[int, ...], ...], mvp.EvalResult],
) -> tuple[list[list[int]], mvp.EvalResult]:
    best_groups = candidates[0]
    best_result: mvp.EvalResult | None = None
    for groups in candidates:
        signature = regime.grouping_signature(groups)
        if signature not in cache:
            cache[signature] = mvp.allocate_and_evaluate(
                groups, scenario, temporal.SWITCH_BETA
            )
        result = cache[signature]
        # Strict improvement matches best_candidate_groups and preserves the
        # original CQI -> cost -> switching candidate order on utility ties.
        if best_result is None or result.utility > best_result.utility:
            best_groups = groups
            best_result = result
    if best_result is None:
        raise RuntimeError("candidate family was empty")
    return best_groups, best_result


def select_gated_candidate(
    scenario: mvp.Scenario,
    eta: float,
) -> tuple[list[list[int]], mvp.EvalResult, dict[str, float | int | str]]:
    families, _ = regime.candidate_families(scenario)
    cache: dict[tuple[tuple[int, ...], ...], mvp.EvalResult] = {}
    two_way_groups, two_way_result = _best_candidate(
        scenario, families["cqi"] + families["cost"], cache
    )
    switching_groups, switching_result = _best_candidate(
        scenario, families["switching"], cache
    )
    margin = switching_result.utility - two_way_result.utility
    admit_switching = bool(margin > eta)
    if admit_switching:
        groups, result, source = switching_groups, switching_result, "switching"
    else:
        groups, result, source = two_way_groups, two_way_result, "two_way"
    return groups, result, {
        "best_2way_candidate_utility": two_way_result.utility,
        "best_switching_candidate_utility": switching_result.utility,
        "switching_margin": margin,
        "switching_admitted": int(admit_switching),
        "selected_source": source,
        "unique_candidate_count": len(cache),
    }


def run_threshold_trajectory(
    scenarios: list[mvp.Scenario],
    dispersion: str,
    load: str,
    seed: str,
    eta: float,
) -> list[dict]:
    previous_quality = np.zeros(len(scenarios[0].cqi_now), dtype=int)
    previous_groups: list[list[int]] | None = None
    rows: list[dict] = []

    for step, base_scenario in enumerate(scenarios):
        scenario = replace(base_scenario, previous_quality=previous_quality.copy())
        groups, result, gate = select_gated_candidate(scenario, eta)
        if result.user_quality is None:
            raise RuntimeError("allocator did not return per-user quality")
        assigned = result.user_quality
        served = assigned >= 0
        quality_delta = np.zeros(len(assigned), dtype=float)
        quality_delta[served] = np.abs(assigned[served] - previous_quality[served])

        row: dict[str, object] = {
            "dispersion": dispersion,
            "load": load,
            "seed": seed,
            "step": step,
            "is_warmup": int(step == 0),
            "eta": eta,
            "eta_label": eta_label(eta),
            "utility": result.utility,
            "adr_kbps": result.adr_kbps,
            "served_ratio": result.served_ratio,
            "average_quality": result.average_quality,
            "system_spectral_efficiency": result.system_spectral_efficiency,
            "fairness": result.fairness,
            "avg_switching": result.avg_switching,
            "quality_switch_rate": float(np.mean(served & (assigned != previous_quality))),
            "quality_change_levels": float(quality_delta.mean()),
            "pairwise_group_churn": temporal.pairwise_group_churn(
                previous_groups, groups, len(assigned)
            ),
            "groups": result.groups,
        }
        row.update(gate)
        rows.append(row)

        previous_quality = previous_quality.copy()
        previous_quality[served] = assigned[served]
        previous_groups = [list(group) for group in groups]

    return rows


def run_seed(dispersion: str, seed: str) -> list[dict]:
    rows: list[dict] = []
    seed_dir = temporal.DATA_ROOT / dispersion / seed
    for load_ratio, load in temporal.LOADS:
        scenarios = build_scenarios(
            load_ratio,
            radio_path=seed_dir / "raw_radio.csv.gz",
            mobility_path=seed_dir / "raw_mobility.csv.gz",
        )
        for eta in ETA_VALUES:
            rows.extend(
                run_threshold_trajectory(scenarios, dispersion, load, seed, eta)
            )
    return rows


def run_all() -> list[dict]:
    rows: list[dict] = []
    jobs = [
        (dispersion, seed)
        for dispersion in temporal.DISPERSIONS
        for seed in temporal.SEEDS
    ]
    with ProcessPoolExecutor(max_workers=temporal.MAX_WORKERS) as executor:
        futures = {
            executor.submit(run_seed, dispersion, seed): (dispersion, seed)
            for dispersion, seed in jobs
        }
        for future in as_completed(futures):
            dispersion, seed = futures[future]
            rows.extend(future.result())
            temporal.progress(f"  {dispersion}/{seed} gated sweep done")

    dispersion_order = {
        value: index for index, value in enumerate(temporal.DISPERSIONS)
    }
    load_order = {
        value: index for index, (_, value) in enumerate(temporal.LOADS)
    }
    eta_order = {eta_label(value): index for index, value in enumerate(ETA_VALUES)}
    rows.sort(key=lambda row: (
        dispersion_order[row["dispersion"]],
        row["seed"],
        load_order[row["load"]],
        eta_order[row["eta_label"]],
        row["step"],
    ))
    return rows


def read_baseline_rows() -> list[dict]:
    if not BASELINE_PATH.exists():
        raise FileNotFoundError(
            f"missing {BASELINE_PATH}; run the temporal closed-loop experiment first"
        )
    numeric_fields = set(METRICS) - {"groups"}
    numeric_fields.update({"step", "is_warmup"})
    rows: list[dict] = []
    with BASELINE_PATH.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            row: dict[str, object] = dict(raw)
            for field in numeric_fields:
                row[field] = float(raw[field])
            row["step"] = int(float(raw["step"]))
            row["is_warmup"] = int(float(raw["is_warmup"]))
            rows.append(row)
    return rows


def validate_endpoints(rows: list[dict], baselines: list[dict]) -> list[dict]:
    lookup = {
        (row["dispersion"], row["load"], row["seed"], row["step"], row["method"]): row
        for row in baselines
    }
    checks = [
        (eta_label(0.0), "CQI+cost+switching 3-way union"),
        (eta_label(float("inf")), "CQI+cost 2-way union"),
    ]
    validation: list[dict] = []
    for label, method in checks:
        gated = [row for row in rows if row["eta_label"] == label]
        errors = []
        for row in gated:
            baseline = lookup[(
                row["dispersion"], row["load"], row["seed"], row["step"], method
            )]
            errors.append(abs(float(row["utility"]) - float(baseline["utility"])))
        validation.append({
            "eta_label": label,
            "expected_method": method,
            "n_rows": len(errors),
            "max_abs_utility_error": max(errors),
            "passed": int(max(errors) <= 1e-12),
        })
    if not all(row["passed"] for row in validation):
        raise AssertionError(f"gating endpoint validation failed: {validation}")
    return validation


def choose_loso_thresholds(rows: list[dict]) -> list[dict]:
    evaluated = [row for row in rows if not row["is_warmup"]]
    cv_scores: list[dict] = []
    for held_out_seed in temporal.SEEDS:
        scores: list[tuple[float, float]] = []
        for eta in ETA_VALUES:
            values = [
                float(row["utility"])
                for row in evaluated
                if row["seed"] != held_out_seed and row["eta_label"] == eta_label(eta)
            ]
            expected = 9 * 9 * 14
            if len(values) != expected:
                raise ValueError(
                    f"expected {expected} training transitions for {held_out_seed}/{eta}, "
                    f"got {len(values)}"
                )
            scores.append((eta, float(np.mean(values))))
        best_score = max(score for _, score in scores)
        tied = [eta for eta, score in scores if best_score - score <= TIE_TOLERANCE]
        selected_eta = max(tied)
        for eta, score in scores:
            cv_scores.append({
                "held_out_seed": held_out_seed,
                "eta": eta,
                "eta_label": eta_label(eta),
                "training_mean_utility": score,
                "training_regret_from_best": best_score - score,
                "selected": int(eta == selected_eta),
            })
    return cv_scores


def build_cv_rows(rows: list[dict], cv_scores: list[dict]) -> list[dict]:
    selected = {
        row["held_out_seed"]: row["eta_label"]
        for row in cv_scores
        if row["selected"]
    }
    if set(selected) != set(temporal.SEEDS):
        raise ValueError("each held-out seed must have exactly one selected eta")
    cv_rows: list[dict] = []
    for source in rows:
        if source["eta_label"] != selected[source["seed"]]:
            continue
        row = dict(source)
        row["method"] = CV_METHOD
        row["selected_eta_label"] = source["eta_label"]
        cv_rows.append(row)
    expected = len(temporal.DISPERSIONS) * len(temporal.SEEDS) * len(temporal.LOADS) * 15
    if len(cv_rows) != expected:
        raise ValueError(f"expected {expected} CV rows, got {len(cv_rows)}")
    return cv_rows


def summarize_per_seed(rows: list[dict], methods: list[str]) -> list[dict]:
    evaluated = [row for row in rows if not row["is_warmup"]]
    result: list[dict] = []
    for dispersion in temporal.DISPERSIONS:
        for _, load in temporal.LOADS:
            for seed in temporal.SEEDS:
                for method in methods:
                    cell = [
                        row for row in evaluated
                        if row["dispersion"] == dispersion
                        and row["load"] == load
                        and row["seed"] == seed
                        and row["method"] == method
                    ]
                    if len(cell) != 14:
                        raise ValueError(
                            f"expected 14 rows for {dispersion}/{load}/{seed}/{method}, "
                            f"got {len(cell)}"
                        )
                    summary: dict[str, object] = {
                        "dispersion": dispersion,
                        "load": load,
                        "seed": seed,
                        "method": method,
                        "n_transitions": len(cell),
                    }
                    for metric in METRICS:
                        summary[f"mean_{metric}"] = float(np.mean([
                            float(row[metric]) for row in cell
                        ]))
                    if method == CV_METHOD:
                        summary["selected_eta_label"] = cell[0]["selected_eta_label"]
                        summary["switching_admission_rate"] = float(np.mean([
                            float(row["switching_admitted"]) for row in cell
                        ]))
                    else:
                        summary["selected_eta_label"] = ""
                        summary["switching_admission_rate"] = float("nan")
                    result.append(summary)
    return result


def summarize_across_seeds(per_seed: list[dict]) -> list[dict]:
    rng = np.random.default_rng(temporal.BOOTSTRAP_SEED + 1)
    summaries: list[dict] = []
    for dispersion in temporal.DISPERSIONS:
        for _, load in temporal.LOADS:
            cell = [
                row for row in per_seed
                if row["dispersion"] == dispersion and row["load"] == load
            ]
            by_method = {
                method: {row["seed"]: row for row in cell if row["method"] == method}
                for method in COMPARISON_METHODS
            }
            for method in COMPARISON_METHODS:
                utilities = np.array([
                    by_method[method][seed]["mean_utility"] for seed in temporal.SEEDS
                ])
                summary: dict[str, object] = {
                    "dispersion": dispersion,
                    "load": load,
                    "method": method,
                    "mean_utility": float(utilities.mean()),
                    "std_utility_across_seeds": float(utilities.std()),
                }
                for reference, suffix in [
                    ("CQI k-means", "cqi"),
                    ("CQI+cost 2-way union", "2way"),
                    ("CQI+cost+switching 3-way union", "3way"),
                ]:
                    diffs = np.array([
                        by_method[method][seed]["mean_utility"]
                        - by_method[reference][seed]["mean_utility"]
                        for seed in temporal.SEEDS
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
                for metric in METRICS[1:]:
                    summary[f"mean_{metric}"] = float(np.mean([
                        by_method[method][seed][f"mean_{metric}"]
                        for seed in temporal.SEEDS
                    ]))
                summary["mean_switching_admission_rate"] = (
                    float(np.nanmean([
                        by_method[method][seed]["switching_admission_rate"]
                        for seed in temporal.SEEDS
                    ]))
                    if method == CV_METHOD else float("nan")
                )
                summaries.append(summary)
    return summaries


def summarize_pooled(per_seed: list[dict]) -> list[dict]:
    rng = np.random.default_rng(temporal.BOOTSTRAP_SEED + 2)
    outputs: list[dict] = []
    scopes = {
        "all_9_cells": set(temporal.DISPERSIONS),
        "mid_high_6_cells": {"mid", "high"},
    }
    for scope, allowed_dispersions in scopes.items():
        by_method_seed: dict[str, dict[str, float]] = {}
        for method in COMPARISON_METHODS:
            by_method_seed[method] = {}
            for seed in temporal.SEEDS:
                selected = [
                    row for row in per_seed
                    if row["method"] == method
                    and row["seed"] == seed
                    and row["dispersion"] in allowed_dispersions
                ]
                by_method_seed[method][seed] = float(np.mean([
                    row["mean_utility"] for row in selected
                ]))
        for method in COMPARISON_METHODS:
            values = np.array([
                by_method_seed[method][seed] for seed in temporal.SEEDS
            ])
            row: dict[str, object] = {
                "scope": scope,
                "method": method,
                "mean_utility": float(values.mean()),
            }
            for reference, suffix in [
                ("CQI k-means", "cqi"),
                ("CQI+cost 2-way union", "2way"),
                ("CQI+cost+switching 3-way union", "3way"),
            ]:
                diffs = np.array([
                    by_method_seed[method][seed] - by_method_seed[reference][seed]
                    for seed in temporal.SEEDS
                ])
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
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    temporal.progress(
        "Conditional switching gate: fixed eta closed-loop sweep, then global "
        "leave-one-seed-out eta selection across all dispersions and loads"
    )
    fixed_rows = run_all()
    baselines = read_baseline_rows()
    validation = validate_endpoints(fixed_rows, baselines)
    cv_scores = choose_loso_thresholds(fixed_rows)
    cv_rows = build_cv_rows(fixed_rows, cv_scores)

    comparison_rows = [
        row for row in baselines if row["method"] in BASELINE_METHODS
    ] + cv_rows
    per_seed = summarize_per_seed(comparison_rows, COMPARISON_METHODS)
    across_seeds = summarize_across_seeds(per_seed)
    pooled = summarize_pooled(per_seed)

    OUT_DIR.mkdir(exist_ok=True)
    write_csv(OUT_DIR / "fixed_eta_per_transition.csv", fixed_rows)
    write_csv(OUT_DIR / "endpoint_validation.csv", validation)
    write_csv(OUT_DIR / "loso_eta_selection.csv", cv_scores)
    write_csv(OUT_DIR / "cv_gated_per_transition.csv", cv_rows)
    write_csv(OUT_DIR / "comparison_per_seed.csv", per_seed)
    write_csv(OUT_DIR / "comparison_across_seeds.csv", across_seeds)
    write_csv(OUT_DIR / "pooled_summary.csv", pooled)

    temporal.progress("\n=== LOSO-selected eta by held-out seed ===")
    for row in cv_scores:
        if row["selected"]:
            temporal.progress(
                f"  {row['held_out_seed']}: {row['eta_label']} "
                f"(training utility={row['training_mean_utility']:+.6f})"
            )

    temporal.progress("\n=== Conditional gate vs 2-way / always-on 3-way ===")
    for row in across_seeds:
        if row["method"] != CV_METHOD:
            continue
        temporal.progress(
            f"  {row['dispersion']:4s} {row['load']:6s} "
            f"u={row['mean_utility']:+.6f} "
            f"d2={row['mean_diff_vs_2way']:+.6f} "
            f"CI2=[{row['diff_vs_2way_ci95_low']:+.6f},"
            f"{row['diff_vs_2way_ci95_high']:+.6f}] "
            f"d3={row['mean_diff_vs_3way']:+.6f} "
            f"CI3=[{row['diff_vs_3way_ci95_low']:+.6f},"
            f"{row['diff_vs_3way_ci95_high']:+.6f}] "
            f"gate={row['mean_switching_admission_rate']:.3f}"
        )
    temporal.progress(f"\nWrote results to {OUT_DIR}/")


if __name__ == "__main__":
    main()
