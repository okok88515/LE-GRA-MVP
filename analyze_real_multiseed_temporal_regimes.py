"""Fit a small, grouped-CV regime map for strict switching-candidate wins.

This is an interpretability diagnostic, not a new production model.  All
loads and dispersions sharing the same simulator seed are held out together,
so adjacent snapshots and paired radio-power variants never leak across the
train/test boundary.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.tree import DecisionTreeClassifier, export_text


DATA_PATH = Path("real_multiseed_temporal_regime_results/per_transition_attribution.csv")
OUT_DIR = Path("real_multiseed_temporal_regime_results")
FEATURES = [
    "cqi_std",
    "cqi_temporal_delta",
    "cqi_history_volatility",
    "previous_quality_std",
    "previous_quality_cqi_mismatch",
    "cost_std_across_users",
    "cqi_cost_rank_disagreement",
    "previous_quality_rb_pressure",
]


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_model() -> DecisionTreeClassifier:
    return DecisionTreeClassifier(
        max_depth=3,
        min_samples_leaf=35,
        class_weight="balanced",
        random_state=20260825,
    )


def summarize_strict_event_paths(rows: list[dict]) -> list[dict]:
    lookup = {
        (row["dispersion"], row["load"], row["seed"], int(row["step"])): row
        for row in rows
    }
    events: list[dict] = []
    for row in rows:
        step = int(row["step"])
        if row["switching_strictly_best"] != "1" or step >= 14:
            continue
        key_prefix = (row["dispersion"], row["load"], row["seed"])
        previous = lookup.get(key_prefix + (step - 1,))
        following = lookup[key_prefix + (step + 1,)]
        before_gap = float(previous["diff_vs_2way_trajectory"]) if previous else 0.0
        current_gap = float(row["diff_vs_2way_trajectory"])
        next_gap = float(following["diff_vs_2way_trajectory"])
        events.append({
            "dispersion": row["dispersion"],
            "load": row["load"],
            "before_gap": before_gap,
            "current_gap": current_gap,
            "next_gap": next_gap,
            "immediate_jump": current_gap - before_gap,
            "next_retained": next_gap - before_gap,
            "gain_erased_next": int(next_gap < before_gap - 1e-9),
        })

    output: list[dict] = []
    for dispersion in ["mid", "high"]:
        for load in ["light", "medium", "heavy"]:
            cell = [
                event for event in events
                if event["dispersion"] == dispersion and event["load"] == load
            ]
            if not cell:
                continue
            output.append({
                "dispersion": dispersion,
                "load": load,
                "strict_events_with_next_step": len(cell),
                "gain_erased_next_count": sum(event["gain_erased_next"] for event in cell),
                "gain_erased_next_rate": float(np.mean([
                    event["gain_erased_next"] for event in cell
                ])),
                "mean_immediate_jump_vs_2way_path": float(np.mean([
                    event["immediate_jump"] for event in cell
                ])),
                "mean_next_retained_vs_pre_event_gap": float(np.mean([
                    event["next_retained"] for event in cell
                ])),
            })
    return output


def summarize_gain_concentration(rows: list[dict]) -> list[dict]:
    output: list[dict] = []
    for dispersion in ["mid", "high"]:
        for load in ["light", "medium", "heavy"]:
            cell = [
                row for row in rows
                if row["dispersion"] == dispersion
                and row["load"] == load
                and row["switching_strictly_best"] == "1"
            ]
            values = sorted(
                [float(row["switching_marginal_same_state"]) for row in cell],
                reverse=True,
            )
            if not values:
                continue
            total = float(sum(values))
            output.append({
                "dispersion": dispersion,
                "load": load,
                "strict_events": len(values),
                "seeds_with_strict_event": len({row["seed"] for row in cell}),
                "total_same_state_gain": total,
                "median_positive_gain": float(np.median(values)),
                "top1_gain_share": values[0] / total,
                "top3_gain_share": sum(values[:3]) / total,
            })
    return output


def main() -> None:
    with DATA_PATH.open(newline="", encoding="utf-8") as handle:
        rows = [
            row for row in csv.DictReader(handle)
            if row["is_warmup"] == "0" and row["dispersion"] in {"mid", "high"}
        ]

    path_summary = summarize_strict_event_paths(rows)
    concentration_summary = summarize_gain_concentration(rows)

    x = np.array([[float(row[feature]) for feature in FEATURES] for row in rows])
    y = np.array([int(row["switching_strictly_best"]) for row in rows])
    # seed_0001 is the same mobility trajectory across low/mid/high power and
    # across loads, so the numeric seed is the leakage-safe grouping unit.
    groups = np.array([row["seed"] for row in rows])

    probabilities = np.zeros(len(rows), dtype=float)
    splitter = LeaveOneGroupOut()
    for train, test in splitter.split(x, y, groups):
        model = build_model()
        model.fit(x[train], y[train])
        probabilities[test] = model.predict_proba(x[test])[:, 1]

    predictions = (probabilities >= 0.5).astype(int)
    summary = [{
        "n_transitions": len(rows),
        "positive_transitions": int(y.sum()),
        "positive_prevalence": float(y.mean()),
        "leave_one_seed_out_roc_auc": float(roc_auc_score(y, probabilities)),
        "leave_one_seed_out_average_precision": float(average_precision_score(y, probabilities)),
        "threshold": 0.5,
        "precision": float(precision_score(y, predictions, zero_division=0)),
        "recall": float(recall_score(y, predictions, zero_division=0)),
        "f1": float(f1_score(y, predictions, zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y, predictions)),
    }]

    final_model = build_model()
    final_model.fit(x, y)
    importance = sorted(
        [
            {"feature": feature, "importance": float(value)}
            for feature, value in zip(FEATURES, final_model.feature_importances_)
        ],
        key=lambda row: row["importance"],
        reverse=True,
    )
    rules = export_text(final_model, feature_names=FEATURES, decimals=4)

    write_csv(OUT_DIR / "regime_tree_cv_summary.csv", summary)
    write_csv(OUT_DIR / "regime_tree_feature_importance.csv", importance)
    write_csv(OUT_DIR / "strict_event_path_summary.csv", path_summary)
    write_csv(OUT_DIR / "switching_gain_concentration.csv", concentration_summary)
    (OUT_DIR / "regime_tree_rules.txt").write_text(rules, encoding="utf-8")

    print("=== Leave-one-seed-out regime tree ===")
    for key, value in summary[0].items():
        print(f"{key}: {value}")
    print("\n=== Full-data descriptive tree (depth <= 3) ===")
    print(rules)
    print("=== Feature importance ===")
    for row in importance:
        print(f"{row['feature']}: {row['importance']:.4f}")


if __name__ == "__main__":
    main()
