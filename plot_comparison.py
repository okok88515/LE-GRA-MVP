"""Run LE-GRA MVP once and save comparison figures."""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import le_gra_mvp as mvp


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-scenarios", type=int, default=60)
    parser.add_argument("--test-scenarios", type=int, default=24)
    parser.add_argument("--users", type=int, default=12)
    parser.add_argument("--rbs", type=int, default=70)
    parser.add_argument("--max-groups", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--scenario-mode", choices=["aligned", "ambiguous", "mixed"], default="mixed")
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--out-dir", type=Path, default=Path("."))
    args = parser.parse_args()

    mvp.set_seed(args.seed)
    dispersions = ["high", "mid", "low"]
    train = [
        mvp.generate_scenario(args.users, args.rbs, random.choice(dispersions), args.scenario_mode)
        for _ in range(args.train_scenarios)
    ]
    test = [
        mvp.generate_scenario(args.users, args.rbs, random.choice(dispersions), args.scenario_mode)
        for _ in range(args.test_scenarios)
    ]
    mvp.normalize_features(train, test)

    print("Generating offline-teacher pseudo-labels...")
    teacher_groups = [mvp.offline_teacher_groups(s, args.max_groups, args.switch_beta) for s in train]
    teacher_labels = [mvp.pairwise_labels(g, args.users) for g in teacher_groups]

    model = mvp.MLPEncoder(
        input_dim=train[0].features.shape[1],
        hidden_dim=48,
        embedding_dim=8,
        lr=0.01,
    )
    print("Training MLP embedding model...")
    for epoch in range(1, args.epochs + 1):
        order = list(range(len(train)))
        random.shuffle(order)
        losses = [model.train_step(train[idx].features, teacher_labels[idx]) for idx in order]
        print(f"epoch={epoch:02d} contrastive_loss={np.mean(losses):.4f}")

    methods = {
        "No grouping": lambda s: mvp.no_grouping(s),
        "CQI k-means": lambda s: mvp.cqi_kmeans_grouping(s, args.max_groups, args.switch_beta),
        "Resource-cost": lambda s: mvp.resource_cost_kmeans_grouping(s, args.max_groups, args.switch_beta),
        "Multi-feature": lambda s: mvp.multi_feature_kmeans_grouping(s, args.max_groups, args.switch_beta),
        "Teacher": lambda s: mvp.offline_teacher_groups(s, args.max_groups, args.switch_beta),
        "LE-GRA": lambda s: mvp.learned_grouping(s, model, args.max_groups, args.switch_beta),
    }

    rows = []
    for name, fn in methods.items():
        result = mvp.evaluate_method(test, fn, args.switch_beta)
        rows.append(
            {
                "method": name,
                "utility": result.utility,
                "adr_kbps": result.adr_kbps,
                "rb_utilization": result.rb_utilization,
                "avg_switching": result.avg_switching,
                "fairness": result.fairness,
                "avg_groups": result.groups,
            }
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "comparison_metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), dpi=160)
    metrics = [
        ("utility", "QoE Utility"),
        ("adr_kbps", "ADR (kbps)"),
        ("rb_utilization", "RB Utilization"),
        ("avg_switching", "Avg. Switching Penalty"),
    ]
    colors = ["#6b7280", "#2563eb", "#0891b2", "#7c3aed", "#16a34a", "#dc2626"]
    labels = [r["method"] for r in rows]
    x = np.arange(len(labels))
    for ax, (key, title) in zip(axes.ravel(), metrics):
        values = [r[key] for r in rows]
        ax.bar(x, values, color=colors)
        ax.set_title(title)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=25, ha="right")
        ax.grid(axis="y", alpha=0.25)
        for i, value in enumerate(values):
            ax.text(i, value, f"{value:.2f}", ha="center", va="bottom", fontsize=8)
    fig.suptitle(f"LE-GRA MVP Comparison ({args.scenario_mode} synthetic scenarios)")
    fig.tight_layout()
    png_path = args.out_dir / "comparison_bar_chart.png"
    fig.savefig(png_path, bbox_inches="tight")
    print(f"Saved {csv_path}")
    print(f"Saved {png_path}")


if __name__ == "__main__":
    main()
