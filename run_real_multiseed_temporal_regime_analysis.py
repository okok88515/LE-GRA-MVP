"""Attribute the real closed-loop 3-way result to its candidate sources.

For every transition on the final 3-way method's own state trajectory, this
runner builds the CQI, resource-cost, and switching-aware candidate families
separately.  It records each family's best exact-DP utility and the strict
marginal value of adding switching to the same-state CQI+cost pool.

The output also contains pre-decision regime features.  These features are
descriptive inputs only; no post-allocation metric is used to define a regime.
"""

from __future__ import annotations

import csv
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp
import run_real_multiseed_temporal_closed_loop as temporal
from parse_real_simu5g_data import build_scenarios


OUT_DIR = Path("real_multiseed_temporal_regime_results")
SOURCE_ORDER = ["cqi", "cost", "switching"]
TOLERANCE = 1e-9


def grouping_signature(groups: list[list[int]]) -> tuple[tuple[int, ...], ...]:
    return tuple(sorted(tuple(sorted(group)) for group in groups))


def average_ranks(values: np.ndarray) -> np.ndarray:
    """Return deterministic average ranks for ties, using ranks 0..n-1."""

    values = np.asarray(values, dtype=float)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and values[order[end]] == values[order[start]]:
            end += 1
        ranks[order[start:end]] = (start + end - 1) / 2.0
        start = end
    return ranks


def rank_alignment(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman correlation of tie-aware ranks; zero if either is constant."""

    ra = average_ranks(a)
    rb = average_ranks(b)
    if np.std(ra) <= 1e-12 or np.std(rb) <= 1e-12:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


def candidate_families(scenario: mvp.Scenario) -> tuple[dict[str, list[list[list[int]]]], np.ndarray]:
    cqi_rep = scenario.cqi_now.reshape(-1, 1).astype(float)
    cost_rep = mvp.user_resource_cost_vector(scenario.rb_rates)
    switching = np.column_stack([
        cqi_rep,
        scenario.previous_quality.reshape(-1, 1).astype(float),
    ])
    switching_rep = (
        (switching - switching.mean(axis=0)) / (switching.std(axis=0) + 1e-6)
    ).astype(np.float32)
    kwargs = {
        "kmeans_n_init": temporal.KMEANS_N_INIT,
        "kmeans_seed": 0,
    }
    return {
        "cqi": mvp.kmeans_candidate_groups(cqi_rep, temporal.KMAX, **kwargs),
        "cost": mvp.kmeans_candidate_groups(cost_rep, temporal.KMAX, **kwargs),
        "switching": mvp.kmeans_candidate_groups(switching_rep, temporal.KMAX, **kwargs),
    }, cost_rep


def select_with_attribution(
    scenario: mvp.Scenario,
) -> tuple[list[list[int]], mvp.EvalResult, dict[str, object], np.ndarray]:
    families, cost_rep = candidate_families(scenario)
    cache: dict[tuple[tuple[int, ...], ...], mvp.EvalResult] = {}
    groups_by_signature: dict[tuple[tuple[int, ...], ...], list[list[int]]] = {}
    sources_by_signature: dict[tuple[tuple[int, ...], ...], list[str]] = {}
    ordered_unique_signatures: list[tuple[tuple[int, ...], ...]] = []
    best_by_source: dict[str, float] = {}

    for source in SOURCE_ORDER:
        source_best = -1e9
        for groups in families[source]:
            signature = grouping_signature(groups)
            if signature not in cache:
                cache[signature] = mvp.allocate_and_evaluate(
                    groups, scenario, temporal.SWITCH_BETA
                )
                groups_by_signature[signature] = groups
                sources_by_signature[signature] = []
                ordered_unique_signatures.append(signature)
            if source not in sources_by_signature[signature]:
                sources_by_signature[signature].append(source)
            source_best = max(source_best, cache[signature].utility)
        best_by_source[source] = source_best

    # Preserve the production function's strict-improvement tie behavior and
    # source order: CQI candidates first, then cost, then switching.
    selected_signature = ordered_unique_signatures[0]
    selected_utility = -1e9
    for signature in ordered_unique_signatures:
        utility = cache[signature].utility
        if utility > selected_utility:
            selected_utility = utility
            selected_signature = signature

    result = cache[selected_signature]
    best_same_state_2way = max(best_by_source["cqi"], best_by_source["cost"])
    best_sources = [
        source for source in SOURCE_ORDER
        if abs(best_by_source[source] - selected_utility) <= TOLERANCE
    ]
    attribution: dict[str, object] = {
        "best_cqi_candidate_utility": best_by_source["cqi"],
        "best_cost_candidate_utility": best_by_source["cost"],
        "best_switching_candidate_utility": best_by_source["switching"],
        "best_same_state_2way_utility": best_same_state_2way,
        "switching_marginal_same_state": selected_utility - best_same_state_2way,
        "switching_strictly_best": int(
            best_by_source["switching"] > best_same_state_2way + TOLERANCE
        ),
        "best_sources": "|".join(best_sources),
        "selected_group_sources": "|".join(sources_by_signature[selected_signature]),
        "selected_primary_source": sources_by_signature[selected_signature][0],
        "selected_k": len(groups_by_signature[selected_signature]),
        "unique_candidate_count": len(cache),
    }
    return groups_by_signature[selected_signature], result, attribution, cost_rep


def regime_features(scenario: mvp.Scenario, cost_rep: np.ndarray) -> dict[str, float]:
    cqi = scenario.cqi_now.astype(float)
    previous = scenario.previous_quality.astype(float)
    mean_cost = cost_rep.mean(axis=1)
    cqi_history = scenario.cqi_history.astype(float)

    previous_cost = cost_rep[
        np.arange(len(previous)),
        np.clip(previous.astype(int), 0, cost_rep.shape[1] - 1),
    ]
    aligned_quality_proxy = np.clip(np.rint(cqi / 3.0), 0, len(mvp.VIDEO_BITRATES_KBPS) - 1)
    return {
        "cqi_mean": float(cqi.mean()),
        "cqi_std": float(cqi.std()),
        "cqi_iqr": float(np.quantile(cqi, 0.75) - np.quantile(cqi, 0.25)),
        "cqi_range": float(np.ptp(cqi)),
        "cqi_saturation_ratio": float(np.mean(cqi >= 14)),
        "cqi_temporal_delta": float(np.mean(np.abs(cqi_history[:, -1] - cqi_history[:, -2]))),
        "cqi_history_volatility": float(np.mean(np.std(cqi_history, axis=1))),
        "previous_quality_mean": float(previous.mean()),
        "previous_quality_std": float(previous.std()),
        "previous_quality_range": float(np.ptp(previous)),
        "previous_quality_cqi_mismatch": float(np.mean(np.abs(previous - aligned_quality_proxy))),
        "cost_mean": float(mean_cost.mean()),
        "cost_std_across_users": float(mean_cost.std()),
        "cqi_cost_rank_alignment": rank_alignment(cqi, -mean_cost),
        "cqi_cost_rank_disagreement": float((1.0 - rank_alignment(cqi, -mean_cost)) / 2.0),
        "previous_quality_rb_pressure": float(previous_cost.sum() / scenario.rb_available),
        "rb_available": float(scenario.rb_available),
    }


def run_seed(dispersion: str, seed: str) -> list[dict]:
    rows: list[dict] = []
    seed_dir = temporal.DATA_ROOT / dispersion / seed
    for load_ratio, load in temporal.LOADS:
        scenarios = build_scenarios(
            load_ratio,
            radio_path=seed_dir / "raw_radio.csv.gz",
            mobility_path=seed_dir / "raw_mobility.csv.gz",
        )
        previous_quality = np.zeros(len(scenarios[0].cqi_now), dtype=int)
        previous_groups: list[list[int]] | None = None
        for step, base_scenario in enumerate(scenarios):
            scenario = replace(base_scenario, previous_quality=previous_quality.copy())
            groups, result, attribution, cost_rep = select_with_attribution(scenario)
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
                "utility": result.utility,
                "adr_kbps": result.adr_kbps,
                "served_ratio": result.served_ratio,
                "average_quality": result.average_quality,
                "fairness": result.fairness,
                "avg_switching": result.avg_switching,
                "quality_switch_rate": float(np.mean(served & (assigned != previous_quality))),
                "quality_change_levels": float(quality_delta.mean()),
                "pairwise_group_churn": temporal.pairwise_group_churn(
                    previous_groups, groups, len(assigned)
                ),
            }
            row.update(regime_features(scenario, cost_rep))
            row.update(attribution)
            rows.append(row)

            previous_quality = previous_quality.copy()
            previous_quality[served] = assigned[served]
            previous_groups = [list(group) for group in groups]
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
            temporal.progress(f"  {dispersion}/{seed} attributed")
    dispersion_order = {value: index for index, value in enumerate(temporal.DISPERSIONS)}
    load_order = {value: index for index, (_, value) in enumerate(temporal.LOADS)}
    rows.sort(key=lambda row: (
        dispersion_order[row["dispersion"]],
        row["seed"],
        load_order[row["load"]],
        row["step"],
    ))
    return rows


def attach_trajectory_comparisons(rows: list[dict]) -> float:
    path = temporal.OUT_DIR / "per_transition_results.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        baseline_rows = list(csv.DictReader(handle))
    lookup = {
        (row["dispersion"], row["load"], row["seed"], int(row["step"]), row["method"]): float(row["utility"])
        for row in baseline_rows
    }
    max_reproduction_error = 0.0
    for row in rows:
        key = (row["dispersion"], row["load"], row["seed"], int(row["step"]))
        cqi = lookup[key + ("CQI k-means",)]
        two_way = lookup[key + ("CQI+cost 2-way union",)]
        expected_three_way = lookup[key + ("CQI+cost+switching 3-way union",)]
        row["diff_vs_cqi_trajectory"] = float(row["utility"]) - cqi
        row["diff_vs_2way_trajectory"] = float(row["utility"]) - two_way
        max_reproduction_error = max(
            max_reproduction_error,
            abs(float(row["utility"]) - expected_three_way),
        )
    return max_reproduction_error


def summarize_cells(rows: list[dict]) -> list[dict]:
    evaluated = [row for row in rows if not row["is_warmup"]]
    output: list[dict] = []
    for dispersion in temporal.DISPERSIONS:
        for _, load in temporal.LOADS:
            cell = [
                row for row in evaluated
                if row["dispersion"] == dispersion and row["load"] == load
            ]
            strict = [row for row in cell if row["switching_strictly_best"]]
            output.append({
                "dispersion": dispersion,
                "load": load,
                "n_transitions": len(cell),
                "switching_strict_win_count": len(strict),
                "switching_strict_win_rate": len(strict) / len(cell),
                "mean_switching_marginal_same_state": float(np.mean([
                    row["switching_marginal_same_state"] for row in cell
                ])),
                "mean_positive_switching_marginal": (
                    float(np.mean([row["switching_marginal_same_state"] for row in strict]))
                    if strict else 0.0
                ),
                "mean_diff_vs_cqi_trajectory": float(np.mean([
                    row["diff_vs_cqi_trajectory"] for row in cell
                ])),
                "mean_diff_vs_2way_trajectory": float(np.mean([
                    row["diff_vs_2way_trajectory"] for row in cell
                ])),
            })
    return output


def summarize_feature_quartiles(rows: list[dict]) -> list[dict]:
    evaluated = [
        row for row in rows
        if not row["is_warmup"] and row["dispersion"] in {"mid", "high"}
    ]
    feature_names = [
        "cqi_std",
        "cqi_temporal_delta",
        "cqi_history_volatility",
        "previous_quality_std",
        "previous_quality_cqi_mismatch",
        "cost_std_across_users",
        "cqi_cost_rank_disagreement",
        "previous_quality_rb_pressure",
    ]
    output: list[dict] = []
    for feature in feature_names:
        values = np.array([float(row[feature]) for row in evaluated])
        edges = np.quantile(values, [0.0, 0.25, 0.5, 0.75, 1.0])
        for quartile in range(4):
            low, high = edges[quartile], edges[quartile + 1]
            if quartile < 3:
                cell = [row for row in evaluated if low <= float(row[feature]) < high]
            else:
                cell = [row for row in evaluated if low <= float(row[feature]) <= high]
            if not cell:
                continue
            strict = [row for row in cell if row["switching_strictly_best"]]
            output.append({
                "feature": feature,
                "quartile": quartile + 1,
                "feature_low": float(low),
                "feature_high": float(high),
                "n_transitions": len(cell),
                "switching_strict_win_rate": len(strict) / len(cell),
                "mean_switching_marginal_same_state": float(np.mean([
                    row["switching_marginal_same_state"] for row in cell
                ])),
                "mean_diff_vs_2way_trajectory": float(np.mean([
                    row["diff_vs_2way_trajectory"] for row in cell
                ])),
            })
    return output


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    temporal.progress("Attributing final 3-way candidate sources on real closed-loop trajectories")
    rows = run_all()
    reproduction_error = attach_trajectory_comparisons(rows)
    if reproduction_error > 1e-12:
        raise RuntimeError(f"3-way reproduction mismatch: {reproduction_error}")

    cell_summary = summarize_cells(rows)
    quartile_summary = summarize_feature_quartiles(rows)
    OUT_DIR.mkdir(exist_ok=True)
    write_csv(OUT_DIR / "per_transition_attribution.csv", rows)
    write_csv(OUT_DIR / "cell_summary.csv", cell_summary)
    write_csv(OUT_DIR / "feature_quartile_summary.csv", quartile_summary)

    temporal.progress("\n=== Switching candidate strict same-state contribution ===")
    for row in cell_summary:
        temporal.progress(
            f"  {row['dispersion']:4s} {row['load']:6s} "
            f"strict={row['switching_strict_win_count']:3d}/{row['n_transitions']} "
            f"rate={row['switching_strict_win_rate']:.3f} "
            f"mean_marginal={row['mean_switching_marginal_same_state']:+.6f} "
            f"trajectory_d2way={row['mean_diff_vs_2way_trajectory']:+.6f}"
        )
    temporal.progress(f"Reproduction max error: {reproduction_error:.3g}")
    temporal.progress(f"Wrote results to {OUT_DIR}/")


if __name__ == "__main__":
    main()
