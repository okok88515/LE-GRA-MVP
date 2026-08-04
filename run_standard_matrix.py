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


def generate_splits(args, scenario_mode: str, seed: int) -> tuple[list[mvp.Scenario], list[mvp.Scenario]]:
    mvp.set_seed(seed)
    dispersions = ["high", "mid", "low"]
    train = [
        mvp.generate_scenario(args.users, args.rbs, random.choice(dispersions), scenario_mode)
        for _ in range(args.train_scenarios)
    ]
    test = [
        mvp.generate_scenario(args.users, args.rbs, random.choice(dispersions), scenario_mode)
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
) -> mvp.MLPEncoder:
    mvp.apply_feature_mode(train, test, feature_mode)
    mvp.normalize_features(train, test)
    teacher_groups = [mvp.offline_teacher_groups(s, max_groups, switch_beta) for s in train]
    teacher_labels = [mvp.pairwise_labels(g, len(train[0].cqi_now)) for g in teacher_groups]

    model = mvp.MLPEncoder(
        input_dim=train[0].features.shape[1],
        hidden_dim=48,
        embedding_dim=8,
        lr=0.01,
    )
    for _ in range(epochs):
        order = list(range(len(train)))
        random.shuffle(order)
        for idx in order:
            model.train_step(train[idx].features, teacher_labels[idx])
    return model


def evaluate_main_methods(
    train: list[mvp.Scenario],
    test: list[mvp.Scenario],
    feature_mode: str,
    max_groups: int,
    switch_beta: float,
    epochs: int,
) -> list[dict]:
    model = train_model(train, test, feature_mode, max_groups, switch_beta, epochs)
    methods = mvp.default_methods(max_groups, switch_beta, model)
    rows = []
    for method_name in MAIN_METHODS:
        result = mvp.evaluate_method(test, methods[method_name], switch_beta)
        rows.append(
            {
                "method": method_name,
                "utility": result.utility,
                "adr_kbps": result.adr_kbps,
                "rb_utilization": result.rb_utilization,
                "avg_switching": result.avg_switching,
                "fairness": result.fairness,
                "avg_groups": result.groups,
            }
        )
    return rows


def run_main_matrix(args) -> list[dict]:
    rows = []
    for scenario_mode in args.scenario_modes:
        for max_groups in args.kmax_values:
            for seed in args.seeds:
                train, test = generate_splits(args, scenario_mode, seed)
                for row in evaluate_main_methods(
                    train,
                    test,
                    feature_mode="full",
                    max_groups=max_groups,
                    switch_beta=args.switch_beta,
                    epochs=args.epochs,
                ):
                    row.update(
                        {
                            "scenario_mode": scenario_mode,
                            "kmax": max_groups,
                            "seed": seed,
                        }
                    )
                    rows.append(row)
    return rows


def run_ablation(args) -> list[dict]:
    rows = []
    for scenario_mode in args.scenario_modes:
        for seed in args.seeds:
            for feature_mode in args.feature_modes:
                train, test = generate_splits(args, scenario_mode, seed)
                model = train_model(
                    train,
                    test,
                    feature_mode=feature_mode,
                    max_groups=args.ablation_kmax,
                    switch_beta=args.switch_beta,
                    epochs=args.epochs,
                )
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
                        "seed": seed,
                        "feature_mode": feature_mode,
                        "feature_label": FEATURE_MODE_LABELS[feature_mode],
                        "method": "LE-GRA MVP",
                        "utility": result.utility,
                        "adr_kbps": result.adr_kbps,
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

    matrix_rows = run_main_matrix(args)
    ablation_rows = run_ablation(args)

    matrix_path = args.out_dir / "main_comparison_matrix.csv"
    ablation_path = args.out_dir / "feature_ablation.csv"
    write_csv(matrix_path, matrix_rows)
    write_csv(ablation_path, ablation_rows)

    print(f"Saved {matrix_path}")
    print(f"Saved {ablation_path}")

    utility_summary = {}
    for row in matrix_rows:
        key = (row["scenario_mode"], row["kmax"], row["method"])
        utility_summary.setdefault(key, []).append(row["utility"])

    print("\nMain comparison summary (mean utility)")
    for scenario_mode in args.scenario_modes:
        for kmax in args.kmax_values:
            print(f"\nscenario_mode={scenario_mode}, kmax={kmax}")
            for method_name in MAIN_METHODS:
                values = utility_summary[(scenario_mode, kmax, method_name)]
                print(f"  {method_name}: {np.mean(values):.4f}")

    print("\nFeature ablation summary (mean utility)")
    for scenario_mode in args.scenario_modes:
        print(f"\nscenario_mode={scenario_mode}, kmax={args.ablation_kmax}")
        for feature_mode in args.feature_modes:
            values = [
                row["utility"]
                for row in ablation_rows
                if row["scenario_mode"] == scenario_mode and row["feature_mode"] == feature_mode
            ]
            print(f"  {FEATURE_MODE_LABELS[feature_mode]}: {np.mean(values):.4f}")


if __name__ == "__main__":
    main()
