"""Run the five-scenario showcase benchmark suite.

The suite follows the scenario-design framework documented in
`scenario_design_framework_zh.html` and `benchmark_plan_zh.html`.
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp
from run_corridor_general_regime import scenario_audit_row, summarize_rows
from run_standard_matrix import evaluate_main_methods, progress, train_model


@dataclass(frozen=True)
class BenchmarkSpec:
    benchmark_id: str
    title: str
    cqi_dispersion: str
    rb_heterogeneity: str
    pressure: str
    dispersion: str
    scenario_mode: str
    rb_budget_ratio: float
    filtered: bool
    min_teacher_gain: float = 0.0
    min_cqi_gap: float = -1.0
    min_same_cqi_cost_std: float = 0.0
    min_cqi_span: int = 0
    max_cqi_span: int = 15


SHOWCASE_SPECS = [
    BenchmarkSpec(
        benchmark_id="bench_d3_h1_p2_cqi_easy",
        title="CQI-easy aligned medium-pressure showcase",
        cqi_dispersion="d3_widespread",
        rb_heterogeneity="h1_aligned",
        pressure="p2_medium",
        dispersion="high",
        scenario_mode="aligned",
        rb_budget_ratio=0.42,
        filtered=False,
    ),
    BenchmarkSpec(
        benchmark_id="bench_d2_h2_p2_main_general",
        title="Main general corridor showcase",
        cqi_dispersion="d2_midspread",
        rb_heterogeneity="h2_mild_heterogeneous",
        pressure="p2_medium",
        dispersion="mid",
        scenario_mode="corridor_general",
        rb_budget_ratio=0.42,
        filtered=True,
        min_teacher_gain=0.008,
        min_cqi_gap=0.004,
        min_same_cqi_cost_std=0.0035,
        min_cqi_span=3,
        max_cqi_span=7,
    ),
    BenchmarkSpec(
        benchmark_id="bench_d1_h3_p3_dense_hard",
        title="Dense-CQI hard stress showcase",
        cqi_dispersion="d1_dense",
        rb_heterogeneity="h3_strong_heterogeneous",
        pressure="p3_high",
        dispersion="low",
        scenario_mode="anti_cqi_hard",
        rb_budget_ratio=0.28,
        filtered=True,
        min_teacher_gain=0.014,
        min_cqi_gap=0.008,
        min_same_cqi_cost_std=0.004,
        min_cqi_span=0,
        max_cqi_span=3,
    ),
    BenchmarkSpec(
        benchmark_id="bench_d2_h3_p3_main_hard",
        title="Main hard corridor showcase",
        cqi_dispersion="d2_midspread",
        rb_heterogeneity="h3_strong_heterogeneous",
        pressure="p3_high",
        dispersion="mid",
        scenario_mode="corridor_general",
        rb_budget_ratio=0.34,
        filtered=True,
        min_teacher_gain=0.010,
        min_cqi_gap=0.005,
        min_same_cqi_cost_std=0.0035,
        min_cqi_span=3,
        max_cqi_span=7,
    ),
    BenchmarkSpec(
        benchmark_id="bench_d1_h1_p1_control_easy",
        title="Dense-CQI aligned low-pressure control",
        cqi_dispersion="d1_dense",
        rb_heterogeneity="h1_aligned",
        pressure="p1_low",
        dispersion="low",
        scenario_mode="aligned",
        rb_budget_ratio=0.68,
        filtered=False,
    ),
]


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


def benchmark_metadata(spec: BenchmarkSpec) -> dict:
    return {
        "benchmark_id": spec.benchmark_id,
        "benchmark_title": spec.title,
        "cqi_dispersion": spec.cqi_dispersion,
        "rb_heterogeneity": spec.rb_heterogeneity,
        "pressure": spec.pressure,
        "scenario_mode": spec.scenario_mode,
        "rb_budget_ratio": spec.rb_budget_ratio,
    }


def is_selected_candidate(row: dict, spec: BenchmarkSpec) -> bool:
    return (
        row["teacher_groups"] >= 2
        and row["teacher_gain_vs_no_grouping"] >= spec.min_teacher_gain
        and row["teacher_gain_vs_cqi"] >= spec.min_cqi_gap
        and row["max_same_cqi_cost_std"] >= spec.min_same_cqi_cost_std
        and row["cqi_span"] >= spec.min_cqi_span
        and row["cqi_span"] <= spec.max_cqi_span
    )


def score_candidate(row: dict) -> float:
    return float(
        1.8 * row["teacher_gain_vs_cqi"]
        + 0.8 * max(row["resource_gain_vs_cqi"], 0.0)
        + 0.8 * max(row["multifeature_gain_vs_cqi"], 0.0)
        + 0.5 * row["teacher_gain_vs_no_grouping"]
        + 0.3 * row["max_same_cqi_cost_std"]
    )


def generate_one_scenario(
    spec: BenchmarkSpec,
    *,
    users: int,
    rbs: int,
) -> mvp.Scenario:
    return mvp.generate_scenario(
        users,
        rbs,
        spec.dispersion,
        scenario_mode=spec.scenario_mode,
        rb_budget_ratio=spec.rb_budget_ratio,
    )


def build_scenarios(
    spec: BenchmarkSpec,
    *,
    target_count: int,
    seed: int,
    split_name: str,
    args,
) -> tuple[list[mvp.Scenario], list[dict]]:
    mvp.set_seed(seed)
    random.seed(seed)
    audit_rows: list[dict] = []

    if not spec.filtered:
        scenarios = [
            generate_one_scenario(spec, users=args.users, rbs=args.rbs)
            for _ in range(target_count)
        ]
        for index, scenario in enumerate(scenarios):
            row = scenario_audit_row(
                scenario,
                scenario_index=index,
                max_groups=args.max_groups,
                switch_beta=args.switch_beta,
                feature_mode=args.feature_mode,
            )
            row.update(benchmark_metadata(spec))
            row["split"] = split_name
            row["seed"] = seed
            row["accepted"] = 1
            row["selected"] = 1
            row["acceptance_score"] = score_candidate(row)
            audit_rows.append(row)
        return scenarios, audit_rows

    candidates: list[tuple[float, mvp.Scenario, dict]] = []
    max_attempts = max(target_count * args.max_attempt_multiplier, target_count)
    for attempt in range(1, max_attempts + 1):
        scenario = generate_one_scenario(spec, users=args.users, rbs=args.rbs)
        row = scenario_audit_row(
            scenario,
            scenario_index=attempt - 1,
            max_groups=args.max_groups,
            switch_beta=args.switch_beta,
            feature_mode=args.feature_mode,
        )
        row.update(benchmark_metadata(spec))
        row["split"] = split_name
        row["seed"] = seed
        row["accepted"] = int(is_selected_candidate(row, spec))
        row["acceptance_score"] = score_candidate(row)
        audit_rows.append(row)
        if row["accepted"]:
            candidates.append((row["acceptance_score"], scenario, row))
            progress(
                f"[{spec.benchmark_id}/{split_name}] candidate {len(candidates)} "
                f"after {attempt} tries: teacher-cqi={row['teacher_gain_vs_cqi']:.4f}, "
                f"resource-cqi={row['resource_gain_vs_cqi']:.4f}, cqi_span={row['cqi_span']}"
            )
            if len(candidates) >= target_count * args.target_buffer_multiplier:
                break

    if len(candidates) < target_count:
        raise RuntimeError(
            f"{spec.benchmark_id}/{split_name}: mined only "
            f"{len(candidates)} / {target_count} scenarios after {max_attempts} attempts."
        )

    candidates.sort(key=lambda item: item[0], reverse=True)
    selected = candidates[:target_count]
    selected_indices = {row["scenario_index"] for _, _, row in selected}
    for row in audit_rows:
        row["selected"] = int(row["scenario_index"] in selected_indices)
    return [scenario for _, scenario, _ in selected], audit_rows


def evaluate_teacher_imitation_rows(
    spec: BenchmarkSpec,
    test: list[mvp.Scenario],
    grouping_cache: dict[str, list[list[list[int]]]],
    *,
    max_groups: int,
    feature_mode: str,
    seed: int,
) -> list[dict]:
    rows = []
    for scenario_index, scenario in enumerate(test):
        teacher_groups = grouping_cache["Offline teacher"][scenario_index]
        teacher_ids = mvp.group_ids_from_groups(teacher_groups, len(scenario.cqi_now))
        for method_name in ["Multi-feature k-means", "LE-GRA MVP"]:
            predicted_groups = grouping_cache[method_name][scenario_index]
            predicted_ids = mvp.group_ids_from_groups(predicted_groups, len(scenario.cqi_now))
            rows.append(
                {
                    **benchmark_metadata(spec),
                    "seed": seed,
                    "test_index": scenario_index,
                    "kmax": max_groups,
                    "feature_mode": feature_mode,
                    "method": method_name,
                    "pairwise_accuracy": mvp.pairwise_same_group_accuracy(teacher_ids, predicted_ids),
                    "ari": mvp.adjusted_rand_index(teacher_ids, predicted_ids),
                    "nmi": mvp.normalized_mutual_information(teacher_ids, predicted_ids),
                    "teacher_groups": len(teacher_groups),
                    "predicted_groups": len(predicted_groups),
                }
            )
    return rows


def run_one_benchmark(spec: BenchmarkSpec, args) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    progress(f"\n[{spec.benchmark_id}] Starting {spec.title}")
    bench_dir = args.out_dir / spec.benchmark_id
    train, train_audit = build_scenarios(
        spec,
        target_count=args.train_scenarios,
        seed=args.seed,
        split_name="train",
        args=args,
    )
    test, test_audit = build_scenarios(
        spec,
        target_count=args.test_scenarios,
        seed=args.seed + 1000,
        split_name="test",
        args=args,
    )

    model = train_model(
        train,
        test,
        feature_mode=args.feature_mode,
        max_groups=args.max_groups,
        switch_beta=args.switch_beta,
        epochs=args.epochs,
        validation_fraction=args.validation_fraction,
        pair_sampling=args.pair_sampling,
        pairs_per_class=args.pairs_per_class,
        progress_label=spec.benchmark_id,
    )

    method_rows, grouping_cache = evaluate_main_methods(
        test,
        model,
        max_groups=args.max_groups,
        switch_beta=args.switch_beta,
        kmeans_n_init=args.kmeans_n_init,
        progress_label=spec.benchmark_id,
    )
    for row in method_rows:
        row.update(
            {
                **benchmark_metadata(spec),
                "kmax": args.max_groups,
                "seed": args.seed,
                "feature_mode": args.feature_mode,
                "train_scenarios": len(train),
                "test_scenarios": len(test),
            }
        )

    diagnostic_rows = evaluate_teacher_imitation_rows(
        spec,
        test,
        grouping_cache,
        max_groups=args.max_groups,
        feature_mode=args.feature_mode,
        seed=args.seed,
    )

    summary_rows = [
        {"split": "train", **benchmark_metadata(spec), **summarize_rows(train_audit)},
        {"split": "test", **benchmark_metadata(spec), **summarize_rows(test_audit)},
    ]
    audit_rows = train_audit + test_audit

    write_csv(bench_dir / "main_comparison.csv", method_rows)
    write_csv(bench_dir / "teacher_imitation_diagnostics.csv", diagnostic_rows)
    write_csv(bench_dir / "scenario_audit.csv", audit_rows)
    write_csv(bench_dir / "scenario_summary.csv", summary_rows)
    progress(f"[{spec.benchmark_id}] Saved outputs under {bench_dir}")
    return method_rows, diagnostic_rows, audit_rows, summary_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=Path("bench_results/showcase"))
    parser.add_argument(
        "--benchmarks",
        nargs="+",
        default=[spec.benchmark_id for spec in SHOWCASE_SPECS],
        choices=[spec.benchmark_id for spec in SHOWCASE_SPECS],
    )
    parser.add_argument("--train-scenarios", type=int, default=24)
    parser.add_argument("--test-scenarios", type=int, default=8)
    parser.add_argument("--users", type=int, default=12)
    parser.add_argument("--rbs", type=int, default=72)
    parser.add_argument("--max-groups", type=int, default=3)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--validation-fraction", type=float, default=0.15)
    parser.add_argument("--pair-sampling", default="random_balanced")
    parser.add_argument("--pairs-per-class", type=int, default=128)
    parser.add_argument("--feature-mode", default="history_cost_quality")
    parser.add_argument("--max-attempt-multiplier", type=int, default=80)
    parser.add_argument("--target-buffer-multiplier", type=int, default=3)
    parser.add_argument("--kmeans-n-init", type=int, default=10)
    parser.add_argument("--seed", type=int, default=31)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.train_scenarios <= 0 or args.test_scenarios <= 0:
        raise ValueError("--train-scenarios and --test-scenarios must be positive")
    if args.pairs_per_class <= 0:
        raise ValueError("--pairs-per-class must be positive")

    specs_by_id = {spec.benchmark_id: spec for spec in SHOWCASE_SPECS}
    selected_specs = [specs_by_id[benchmark_id] for benchmark_id in args.benchmarks]
    args.out_dir.mkdir(parents=True, exist_ok=True)

    all_method_rows: list[dict] = []
    all_diagnostic_rows: list[dict] = []
    all_audit_rows: list[dict] = []
    all_summary_rows: list[dict] = []
    for spec in selected_specs:
        method_rows, diagnostic_rows, audit_rows, summary_rows = run_one_benchmark(spec, args)
        all_method_rows.extend(method_rows)
        all_diagnostic_rows.extend(diagnostic_rows)
        all_audit_rows.extend(audit_rows)
        all_summary_rows.extend(summary_rows)

    write_csv(args.out_dir / "all_main_comparison.csv", all_method_rows)
    write_csv(args.out_dir / "all_teacher_imitation_diagnostics.csv", all_diagnostic_rows)
    write_csv(args.out_dir / "all_scenario_audit.csv", all_audit_rows)
    write_csv(args.out_dir / "all_scenario_summary.csv", all_summary_rows)

    progress("\nShowcase suite summary")
    for row in all_method_rows:
        progress(
            f"  {row['benchmark_id']} | {row['method']}: "
            f"utility={row['utility']:.4f}, adr={row['adr_kbps']:.1f}, "
            f"groups={row['avg_groups']:.2f}"
        )
    progress(f"Saved aggregate outputs under {args.out_dir}")


if __name__ == "__main__":
    main()
