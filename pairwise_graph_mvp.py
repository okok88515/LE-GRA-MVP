"""Pairwise probability + graph clustering MVP.

This script is the next step after `le_gra_mvp.py`.

Instead of:
    user features -> embedding -> k-means

it trains a pairwise classifier:
    user_i, user_j -> P(same MBS group)

Then it builds a graph where edges connect user pairs whose same-group
probability is above a threshold. Connected components become MBS groups.
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import le_gra_mvp as mvp


class PairwiseClassifier:
    def __init__(self, input_dim: int, hidden_dim: int = 64, lr: float = 0.01):
        self.lr = lr
        self.w1 = np.random.normal(0, 0.08, size=(input_dim, hidden_dim))
        self.b1 = np.zeros(hidden_dim)
        self.w2 = np.random.normal(0, 0.08, size=(hidden_dim, 1))
        self.b2 = np.zeros(1)

    def forward(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        h_pre = x @ self.w1 + self.b1
        h = np.maximum(0, h_pre)
        logit = h @ self.w2 + self.b2
        prob = 1.0 / (1.0 + np.exp(-np.clip(logit, -30, 30)))
        return h, prob

    def train_batch(self, x: np.ndarray, y: np.ndarray) -> float:
        h, prob = self.forward(x)
        y = y.reshape(-1, 1)
        eps = 1e-8
        loss = -np.mean(y * np.log(prob + eps) + (1.0 - y) * np.log(1.0 - prob + eps))

        dlogit = (prob - y) / len(x)
        dw2 = h.T @ dlogit
        db2 = dlogit.sum(axis=0)
        dh = dlogit @ self.w2.T
        dh[h <= 0] = 0
        dw1 = x.T @ dh
        db1 = dh.sum(axis=0)

        self.w2 -= self.lr * dw2
        self.b2 -= self.lr * db2
        self.w1 -= self.lr * dw1
        self.b1 -= self.lr * db1
        return float(loss)

    def predict(self, x: np.ndarray) -> np.ndarray:
        _, prob = self.forward(x)
        return prob.ravel()


def make_pair_features(features: np.ndarray, i: int, j: int) -> np.ndarray:
    xi = features[i]
    xj = features[j]
    return np.concatenate([np.abs(xi - xj), xi * xj, (xi + xj) * 0.5])


def scenario_pair_dataset(
    scenario: mvp.Scenario,
    labels: np.ndarray,
    max_pos: int = 180,
    max_neg: int = 180,
) -> tuple[np.ndarray, np.ndarray]:
    pos = []
    neg = []
    n = len(scenario.features)
    for i in range(n):
        for j in range(i + 1, n):
            if labels[i, j] > 0.5:
                pos.append((i, j))
            else:
                neg.append((i, j))
    random.shuffle(pos)
    random.shuffle(neg)
    pairs = pos[:max_pos] + neg[:max_neg]
    random.shuffle(pairs)
    x = np.stack([make_pair_features(scenario.features, i, j) for i, j in pairs]).astype(np.float32)
    y = np.array([labels[i, j] for i, j in pairs], dtype=np.float32)
    return x, y


def probability_matrix(model: PairwiseClassifier, scenario: mvp.Scenario) -> np.ndarray:
    n = len(scenario.features)
    p = np.eye(n, dtype=float)
    pair_features = []
    pair_indices = []
    for i in range(n):
        for j in range(i + 1, n):
            pair_features.append(make_pair_features(scenario.features, i, j))
            pair_indices.append((i, j))
    probs = model.predict(np.stack(pair_features).astype(np.float32))
    for (i, j), value in zip(pair_indices, probs):
        p[i, j] = value
        p[j, i] = value
    return p


def graph_groups_from_prob(p: np.ndarray, threshold: float) -> list[list[int]]:
    n = len(p)
    seen = np.zeros(n, dtype=bool)
    groups = []
    for start in range(n):
        if seen[start]:
            continue
        stack = [start]
        seen[start] = True
        group = []
        while stack:
            node = stack.pop()
            group.append(node)
            neighbors = np.where((p[node] >= threshold) & (~seen))[0]
            for nb in neighbors:
                seen[nb] = True
                stack.append(int(nb))
        groups.append(group)
    return groups


def pairwise_graph_grouping(
    model: PairwiseClassifier,
    scenario: mvp.Scenario,
    thresholds: list[float],
    max_groups: int,
    switch_beta: float,
) -> list[list[int]]:
    p = probability_matrix(model, scenario)
    best_groups = [list(range(len(scenario.cqi_now)))]
    best_utility = -1e9
    for threshold in thresholds:
        groups = graph_groups_from_prob(p, threshold)
        if len(groups) > max_groups:
            continue
        result = mvp.allocate_and_evaluate(groups, scenario, switch_beta)
        if result.utility > best_utility:
            best_utility = result.utility
            best_groups = groups
    return best_groups


def evaluate_method(scenarios, grouping_fn, switch_beta):
    results = [mvp.allocate_and_evaluate(grouping_fn(s), s, switch_beta) for s in scenarios]
    return {
        "utility": float(np.mean([r.utility for r in results])),
        "adr_kbps": float(np.mean([r.adr_kbps for r in results])),
        "rb_utilization": float(np.mean([r.rb_utilization for r in results])),
        "avg_switching": float(np.mean([r.avg_switching for r in results])),
        "fairness": float(np.mean([r.fairness for r in results])),
        "avg_groups": float(np.mean([r.groups for r in results])),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-scenarios", type=int, default=100)
    parser.add_argument("--test-scenarios", type=int, default=40)
    parser.add_argument("--users", type=int, default=12)
    parser.add_argument("--rbs", type=int, default=70)
    parser.add_argument("--max-groups", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--scenario-mode", choices=["aligned", "ambiguous", "mixed"], default="ambiguous")
    parser.add_argument("--seed", type=int, default=23)
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

    print("Generating offline-teacher pairwise labels...")
    teacher_groups = [mvp.offline_teacher_groups(s, args.max_groups, args.switch_beta) for s in train]
    teacher_labels = [mvp.pairwise_labels(g, args.users) for g in teacher_groups]

    pair_dim = len(make_pair_features(train[0].features, 0, 1))
    model = PairwiseClassifier(input_dim=pair_dim, hidden_dim=64, lr=0.01)

    print("Training pairwise same-group classifier...")
    for epoch in range(1, args.epochs + 1):
        order = list(range(len(train)))
        random.shuffle(order)
        losses = []
        for idx in order:
            x, y = scenario_pair_dataset(train[idx], teacher_labels[idx])
            losses.append(model.train_batch(x, y))
        print(f"epoch={epoch:02d} bce_loss={np.mean(losses):.4f}")

    thresholds = [0.35, 0.45, 0.55, 0.65, 0.75, 0.85]
    methods = {
        "No grouping": lambda s: mvp.no_grouping(s),
        "CQI k-means": lambda s: mvp.cqi_kmeans_grouping(s, args.max_groups, args.switch_beta),
        "Resource-cost": lambda s: mvp.resource_cost_kmeans_grouping(s, args.max_groups, args.switch_beta),
        "Teacher": lambda s: mvp.offline_teacher_groups(s, args.max_groups, args.switch_beta),
        "Pairwise graph": lambda s: pairwise_graph_grouping(
            model, s, thresholds, args.max_groups, args.switch_beta
        ),
    }

    rows = []
    for name, fn in methods.items():
        row = {"method": name}
        row.update(evaluate_method(test, fn, args.switch_beta))
        rows.append(row)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "pairwise_graph_metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    labels = [r["method"] for r in rows]
    x = np.arange(len(labels))
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), dpi=160)
    metrics = [
        ("utility", "QoE Utility"),
        ("adr_kbps", "ADR (kbps)"),
        ("rb_utilization", "RB Utilization"),
        ("avg_switching", "Avg. Switching"),
    ]
    colors = ["#6b7280", "#2563eb", "#0891b2", "#16a34a", "#dc2626"]
    for ax, (key, title) in zip(axes.ravel(), metrics):
        values = [r[key] for r in rows]
        ax.bar(x, values, color=colors)
        ax.set_title(title)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=25, ha="right")
        ax.grid(axis="y", alpha=0.25)
        for i, value in enumerate(values):
            ax.text(i, value, f"{value:.2f}", ha="center", va="bottom", fontsize=8)
    fig.suptitle(f"Pairwise Graph Grouping MVP ({args.scenario_mode} scenarios)")
    fig.tight_layout()
    png_path = args.out_dir / "pairwise_graph_chart.png"
    fig.savefig(png_path, bbox_inches="tight")

    print(f"Saved {csv_path}")
    print(f"Saved {png_path}")
    print("\nSummary")
    for row in rows:
        print(
            f"{row['method']}: utility={row['utility']:.4f}, "
            f"ADR={row['adr_kbps']:.1f}, RB={row['rb_utilization']:.3f}, "
            f"switch={row['avg_switching']:.3f}, groups={row['avg_groups']:.2f}"
        )


if __name__ == "__main__":
    main()
