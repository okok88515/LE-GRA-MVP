"""Run the standard LE-GRA experiment matrix and feature ablations.

This script operationalizes the current research plan:

1. Fix the main comparison group.
2. Sweep the standard scenario/Kmax matrix.
3. Run the minimal feature ablation for LE-GRA.
"""

from __future__ import annotations

import argparse
import csv
import random
import time
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp


MAIN_METHODS = [
    "No grouping",
    "CQI k-means",
    "Resource-cost k-means",
    "Offline teacher",
    "LE-GRA MVP",
]

FEATURE_MODE_LABELS = {
    "history_only": "CQI/history only",
    "history_cost": "+ resource-cost",
    "full": "full feature",
}

LOAD_RATIOS = {
    "light": 0.50,
    "medium": 0.25,
    "heavy": 0.10,
}


def progress(message: str) -> None:
    """Print progress immediately, even when stdout is buffered."""

    print(message, flush=True)


def generate_splits(
    args, scenario_mode: str, seed: int, load_level: str
) -> tuple[list[mvp.Scenario], list[mvp.Scenario]]:
    mvp.set_seed(seed)
    dispersions = ["high", "mid", "low"]
    rb_budget_ratio = LOAD_RATIOS[load_level]
    train = [
        mvp.generate_scenario(
            args.users, args.rbs, random.choice(dispersions), scenario_mode,
            rb_budget_ratio=rb_budget_ratio,
        )
        for _ in range(args.train_scenarios)
    ]
    test = [
        mvp.generate_scenario(
            args.users, args.rbs, random.choice(dispersions), scenario_mode,
            rb_budget_ratio=rb_budget_ratio,
        )
        for _ in range(args.test_scenarios)
    ]
    return train, test


def train_model(
    train: list[mvp.Scenario],
    test: list[mvp.Scenario],
    feature_mode: str,
    max_groups: int,
    switch_beta: float,
    epochs: int,
    progress_label: str = "",
) -> mvp.MLPEncoder:
    started = time.perf_counter()
    prefix = f"[{progress_label}] " if progress_label else ""
    mvp.apply_feature_mode(train, test, feature_mode)
    mvp.normalize_features(train, test)
    progress(
        f"{prefix}Generating offline-teacher labels "
        f"(0/{len(train)}, feature={feature_mode}, Kmax={max_groups})"
    )
    teacher_groups = []
    for index, scenario in enumerate(train, start=1):
        teacher_groups.append(mvp.offline_teacher_groups(scenario, max_groups, switch_beta))
        progress(
            f"{prefix}Teacher labels {index}/{len(train)} "
            f"({time.perf_counter() - started:.1f}s elapsed)"
        )
    teacher_labels = [mvp.pairwise_labels(g, len(train[0].cqi_now)) for g in teacher_groups]

    model = mvp.MLPEncoder(
        input_dim=train[0].features.shape[1],
        hidden_dim=48,
        embedding_dim=8,
        lr=0.01,
    )
    progress(f"{prefix}Training model (0/{epochs} epochs)")
    for epoch in range(1, epochs + 1):
        order = list(range(len(train)))
        random.shuffle(order)
        losses = []
        for idx in order:
            losses.append(model.train_step(train[idx].features, teacher_labels[idx]))
        progress(
            f"{prefix}Epoch {epoch}/{epochs}, loss={np.mean(losses):.4f} "
            f"({time.perf_counter() - started:.1f}s elapsed)"
        )
    return model


def evaluate_main_methods(
    train: list[mvp.Scenario],
    test: list[mvp.Scenario],
    feature_mode: str,
    max_groups: int,
    switch_beta: float,
    epochs: int,
    progress_label: str,
) -> list[dict]:
    model = train_model(
        train, test, feature_mode, max_groups, switch_beta, epochs, progress_label
    )
    methods = mvp.default_methods(max_groups, switch_beta, model)
    rows = []
    for method_index, method_name in enumerate(MAIN_METHODS, start=1):
        progress(
            f"[{progress_label}] Evaluating {method_name} "
            f"({method_index}/{len(MAIN_METHODS)})"
        )
        result = mvp.evaluate_method(test, methods[method_name], switch_beta)
        rows.append(
            {
                "method": method_name,
                "utility": result.utility,
                "adr_kbps": result.adr_kbps,
                "used_spectral_efficiency": result.used_spectral_efficiency,
                "system_spectral_efficiency": result.system_spectral_efficiency,
                "served_ratio": result.served_ratio,
                "unserved_ratio": result.unserved_ratio,
                "average_quality": result.average_quality,
                "rb_utilization": result.rb_utilization,
                "avg_switching": result.avg_switching,
                "fairness": result.fairness,
                "avg_groups": result.groups,
            }
        )
    return rows


def run_main_matrix(args) -> list[dict]:
    rows = []
    total_jobs = (
        len(args.scenario_modes) * len(args.load_levels)
        * len(args.kmax_values) * len(args.seeds)
    )
    job = 0
    for scenario_mode in args.scenario_modes:
        for load_level in args.load_levels:
            for max_groups in args.kmax_values:
                for seed in args.seeds:
                    job += 1
                    label = (
                        f"Main {job}/{total_jobs}: scenario={scenario_mode}, "
                        f"load={load_level}, Kmax={max_groups}, seed={seed}"
                    )
                    progress(f"\n[{label}] Starting")
                    train, test = generate_splits(args, scenario_mode, seed, load_level)
                    for row in evaluate_main_methods(
                        train,
                        test,
                        feature_mode="full",
                        max_groups=max_groups,
                        switch_beta=args.switch_beta,
                        epochs=args.epochs,
                        progress_label=label,
                    ):
                        row.update(
                            {
                                "scenario_mode": scenario_mode,
                                "load_level": load_level,
                                "rb_budget_ratio": LOAD_RATIOS[load_level],
                                "kmax": max_groups,
                                "seed": seed,
                            }
                        )
                        rows.append(row)
    return rows


def run_ablation(args) -> list[dict]:
    rows = []
    total_jobs = (
        len(args.scenario_modes) * len(args.load_levels)
        * len(args.seeds) * len(args.feature_modes)
    )
    job = 0
    for scenario_mode in args.scenario_modes:
        for load_level in args.load_levels:
          for seed in args.seeds:
            for feature_mode in args.feature_modes:
                job += 1
                label = (
                    f"Ablation {job}/{total_jobs}: scenario={scenario_mode}, "
                    f"load={load_level}, feature={feature_mode}, seed={seed}"
                )
                progress(f"\n[{label}] Starting")
                train, test = generate_splits(args, scenario_mode, seed, load_level)
                model = train_model(
                    train,
                    test,
                    feature_mode=feature_mode,
                    max_groups=args.ablation_kmax,
                    switch_beta=args.switch_beta,
                    epochs=args.epochs,
                    progress_label=label,
                )
                progress(f"[{label}] Evaluating LE-GRA MVP")
                result = mvp.evaluate_method(
                    test,
                    lambda s, model=model: mvp.learned_grouping(
                        s, model, args.ablation_kmax, args.switch_beta
                    ),
                    args.switch_beta,
                )
                rows.append(
                    {
                        "scenario_mode": scenario_mode,
                        "load_level": load_level,
                        "rb_budget_ratio": LOAD_RATIOS[load_level],
                        "seed": seed,
                        "feature_mode": feature_mode,
                        "feature_label": FEATURE_MODE_LABELS[feature_mode],
                        "method": "LE-GRA MVP",
                        "utility": result.utility,
                        "adr_kbps": result.adr_kbps,
                        "used_spectral_efficiency": result.used_spectral_efficiency,
                        "system_spectral_efficiency": result.system_spectral_efficiency,
                        "served_ratio": result.served_ratio,
                        "unserved_ratio": result.unserved_ratio,
                        "average_quality": result.average_quality,
                        "rb_utilization": result.rb_utilization,
                        "avg_switching": result.avg_switching,
                        "fairness": result.fairness,
                        "avg_groups": result.groups,
                        "kmax": args.ablation_kmax,
                    }
                )
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-scenarios", type=int, default=120)
    parser.add_argument("--test-scenarios", type=int, default=40)
    parser.add_argument("--users", type=int, default=24)
    parser.add_argument("--rbs", type=int, default=100)
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--scenario-modes", nargs="+", default=["aligned", "ambiguous", "mixed"])
    parser.add_argument(
        "--load-levels",
        nargs="+",
        choices=list(LOAD_RATIOS),
        default=["light", "medium", "heavy"],
        help="Resource-pressure levels: light=0.50, medium=0.25, heavy=0.10.",
    )
    parser.add_argument("--kmax-values", nargs="+", type=int, default=[3, 4, 5, 6])
    parser.add_argument("--seeds", nargs="+", type=int, default=[9, 17, 23])
    parser.add_argument(
        "--feature-modes",
        nargs="+",
        default=["history_only", "history_cost", "full"],
    )
    parser.add_argument("--ablation-kmax", type=int, default=5)
    parser.add_argument("--out-dir", type=Path, default=Path("standard_matrix_results"))
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    progress("Starting LE-GRA standard experiment matrix")
    progress(
        f"Main jobs: {len(args.scenario_modes) * len(args.load_levels) * len(args.kmax_values) * len(args.seeds)}; "
        f"ablation jobs: {len(args.scenario_modes) * len(args.load_levels) * len(args.seeds) * len(args.feature_modes)}"
    )

    matrix_rows = run_main_matrix(args)
    progress("\nMain comparison matrix complete; starting feature ablation")
    ablation_rows = run_ablation(args)

    matrix_path = args.out_dir / "main_comparison_matrix.csv"
    ablation_path = args.out_dir / "feature_ablation.csv"
    write_csv(matrix_path, matrix_rows)
    write_csv(ablation_path, ablation_rows)

    print(f"Saved {matrix_path}")
    print(f"Saved {ablation_path}")

    metric_summary = {}
    for row in matrix_rows:
        key = (row["scenario_mode"], row["load_level"], row["kmax"], row["method"])
        summary = metric_summary.setdefault(
            key,
            {
                "utility": [],
                "used_spectral_efficiency": [],
                "system_spectral_efficiency": [],
                "served_ratio": [],
                "average_quality": [],
            },
        )
        for metric in summary:
            summary[metric].append(row[metric])

    print("\nMain comparison summary (mean utility, SE, service, and quality)")
    for scenario_mode in args.scenario_modes:
        for load_level in args.load_levels:
            for kmax in args.kmax_values:
                print(f"\nscenario_mode={scenario_mode}, load={load_level}, kmax={kmax}")
                for method_name in MAIN_METHODS:
                    values = metric_summary[(scenario_mode, load_level, kmax, method_name)]
                    print(
                        f"  {method_name}: utility={np.mean(values['utility']):.4f}, "
                        f"used_SE={np.mean(values['used_spectral_efficiency']):.3f}, "
                        f"system_SE={np.mean(values['system_spectral_efficiency']):.3f} bit/s/Hz, "
                        f"served={np.mean(values['served_ratio']):.3f}, "
                        f"quality={np.mean(values['average_quality']):.2f}"
                    )

    print("\nFeature ablation summary (mean utility)")
    for scenario_mode in args.scenario_modes:
        for load_level in args.load_levels:
            print(f"\nscenario_mode={scenario_mode}, load={load_level}, kmax={args.ablation_kmax}")
            for feature_mode in args.feature_modes:
                values = [
                    row["utility"]
                    for row in ablation_rows
                    if row["scenario_mode"] == scenario_mode
                    and row["load_level"] == load_level
                    and row["feature_mode"] == feature_mode
                ]
                print(f"  {FEATURE_MODE_LABELS[feature_mode]}: {np.mean(values):.4f}")


if __name__ == "__main__":
    main()
