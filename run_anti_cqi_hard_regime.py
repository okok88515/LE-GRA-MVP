"""Mine and evaluate anti-CQI hard scenarios where grouping quality matters."""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp
from run_standard_matrix import (
    evaluate_main_methods,
    progress,
    train_model,
)


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


def scenario_audit_row(
    scenario: mvp.Scenario,
    *,
    scenario_index: int,
    max_groups: int,
    switch_beta: float,
    feature_mode: str,
) -> dict:
    no_groups = mvp.no_grouping(scenario)
    cqi_groups = mvp.cqi_kmeans_grouping(scenario, max_groups, switch_beta, 10)
    resource_groups = mvp.resource_cost_kmeans_grouping(scenario, max_groups, switch_beta, 10)
    multifeature_groups = mvp.multi_feature_kmeans_grouping(
        scenario,
        max_groups,
        switch_beta,
        feature_mode="full",
        kmeans_n_init=10,
    )
    teacher_groups = mvp.offline_teacher_groups(scenario, max_groups, switch_beta)

    no_eval = mvp.allocate_and_evaluate(no_groups, scenario, switch_beta)
    cqi_eval = mvp.allocate_and_evaluate(cqi_groups, scenario, switch_beta)
    resource_eval = mvp.allocate_and_evaluate(resource_groups, scenario, switch_beta)
    multifeature_eval = mvp.allocate_and_evaluate(multifeature_groups, scenario, switch_beta)
    teacher_eval = mvp.allocate_and_evaluate(teacher_groups, scenario, switch_beta)

    cost_vec = mvp.user_resource_cost_vector(scenario.rb_rates) / scenario.rb_rates.shape[1]
    mean_user_cost = cost_vec.mean(axis=1)
    within_cqi_std = 0.0
    for cqi_value in np.unique(scenario.cqi_now):
        mask = scenario.cqi_now == cqi_value
        if np.sum(mask) >= 2:
            within_cqi_std = max(within_cqi_std, float(np.std(mean_user_cost[mask])))

    teacher_ids = mvp.group_ids_from_groups(teacher_groups, len(scenario.cqi_now))
    cqi_ids = mvp.group_ids_from_groups(cqi_groups, len(scenario.cqi_now))
    resource_ids = mvp.group_ids_from_groups(resource_groups, len(scenario.cqi_now))
    multi_ids = mvp.group_ids_from_groups(multifeature_groups, len(scenario.cqi_now))

    return {
        "scenario_index": scenario_index,
        "feature_mode": feature_mode,
        "users": len(scenario.cqi_now),
        "rbs": scenario.rb_rates.shape[1],
        "rb_budget_ratio": scenario.rb_available / scenario.rb_rates.shape[1],
        "cqi_min": int(np.min(scenario.cqi_now)),
        "cqi_max": int(np.max(scenario.cqi_now)),
        "cqi_span": int(np.max(scenario.cqi_now) - np.min(scenario.cqi_now)),
        "mean_cost_std": float(np.std(mean_user_cost)),
        "max_same_cqi_cost_std": within_cqi_std,
        "teacher_groups": len(teacher_groups),
        "cqi_groups": len(cqi_groups),
        "resource_groups": len(resource_groups),
        "multifeature_groups": len(multifeature_groups),
        "teacher_gain_vs_no_grouping": teacher_eval.utility - no_eval.utility,
        "teacher_gain_vs_cqi": teacher_eval.utility - cqi_eval.utility,
        "resource_gain_vs_cqi": resource_eval.utility - cqi_eval.utility,
        "multifeature_gain_vs_cqi": multifeature_eval.utility - cqi_eval.utility,
        "resource_gap_vs_teacher": teacher_eval.utility - resource_eval.utility,
        "multifeature_gap_vs_teacher": teacher_eval.utility - multifeature_eval.utility,
        "cqi_pairwise_vs_teacher": mvp.pairwise_same_group_accuracy(teacher_ids, cqi_ids),
        "resource_pairwise_vs_teacher": mvp.pairwise_same_group_accuracy(teacher_ids, resource_ids),
        "multifeature_pairwise_vs_teacher": mvp.pairwise_same_group_accuracy(teacher_ids, multi_ids),
        "teacher_utility": teacher_eval.utility,
        "cqi_utility": cqi_eval.utility,
        "resource_utility": resource_eval.utility,
        "multifeature_utility": multifeature_eval.utility,
        "no_grouping_utility": no_eval.utility,
    }


def is_hard_enough(row: dict, args) -> bool:
    return (
        row["teacher_groups"] >= 2
        and row["cqi_span"] <= args.max_cqi_span
        and row["teacher_gain_vs_no_grouping"] >= args.min_teacher_gain
        and row["teacher_gain_vs_cqi"] >= args.min_cqi_gap
        and row["resource_gain_vs_cqi"] >= args.min_resource_gap
    )


def acceptance_score(row: dict) -> float:
    return float(
        2.0 * row["teacher_gain_vs_cqi"]
        + 1.0 * max(row["resource_gain_vs_cqi"], 0.0)
        + 0.75 * max(row["multifeature_gain_vs_cqi"], 0.0)
        + 0.50 * row["teacher_gain_vs_no_grouping"]
        + 0.25 * row["max_same_cqi_cost_std"]
    )


def mine_scenarios(
    *,
    target_count: int,
    seed: int,
    args,
    split_name: str,
) -> tuple[list[mvp.Scenario], list[dict]]:
    mvp.set_seed(seed)
    random.seed(seed)
    audit_rows: list[dict] = []
    candidates: list[tuple[float, mvp.Scenario, dict]] = []
    attempts = 0
    max_attempts = max(target_count * args.max_attempt_multiplier, target_count)
    while attempts < max_attempts:
        attempts += 1
        scenario = mvp.generate_scenario(
            args.users,
            args.rbs,
            "mid",
            scenario_mode="anti_cqi_hard",
            rb_budget_ratio=args.rb_budget_ratio,
        )
        row = scenario_audit_row(
            scenario,
            scenario_index=attempts - 1,
            max_groups=args.max_groups,
            switch_beta=args.switch_beta,
            feature_mode=args.feature_mode,
        )
        row["split"] = split_name
        row["seed"] = seed
        row["accepted"] = int(is_hard_enough(row, args))
        row["acceptance_score"] = acceptance_score(row)
        audit_rows.append(row)
        if row["accepted"]:
            candidates.append((row["acceptance_score"], scenario, row))
            progress(
                f"[{split_name}] hard candidate {len(candidates)} after {attempts} tries: "
                f"teacher-cqi gap={row['teacher_gain_vs_cqi']:.4f}, "
                f"resource-cqi gap={row['resource_gain_vs_cqi']:.4f}, "
                f"cqi_span={row['cqi_span']}"
            )
            if len(candidates) >= target_count * args.target_buffer_multiplier:
                break
    if len(candidates) < target_count:
        raise RuntimeError(
            f"Only mined {len(candidates)} / {target_count} {split_name} hard scenarios "
            f"after {attempts} attempts. Loosen thresholds or increase max_attempt_multiplier."
        )
    candidates.sort(key=lambda item: item[0], reverse=True)
    selected = candidates[:target_count]
    kept = [scenario for _, scenario, _ in selected]
    selected_indices = {row["scenario_index"] for _, _, row in selected}
    for row in audit_rows:
        row["selected"] = int(row["scenario_index"] in selected_indices and row["split"] == split_name)
    progress(
        f"[{split_name}] selected top {len(kept)} / {len(candidates)} hard candidates "
        f"(best score={selected[0][0]:.4f}, cutoff={selected[-1][0]:.4f})"
    )
    return kept, audit_rows


def summarize_rows(rows: list[dict]) -> dict[str, float]:
    selected = [row for row in rows if row.get("selected", 0)]
    accepted = [row for row in rows if row.get("accepted", 0)]
    source = selected if selected else accepted if accepted else rows
    return {
        "count": float(len(source)),
        "mean_teacher_gain_vs_cqi": float(np.mean([row["teacher_gain_vs_cqi"] for row in source])),
        "mean_resource_gain_vs_cqi": float(np.mean([row["resource_gain_vs_cqi"] for row in source])),
        "mean_multifeature_gain_vs_cqi": float(np.mean([row["multifeature_gain_vs_cqi"] for row in source])),
        "mean_cqi_span": float(np.mean([row["cqi_span"] for row in source])),
        "mean_same_cqi_cost_std": float(np.mean([row["max_same_cqi_cost_std"] for row in source])),
    }


def evaluate_teacher_imitation_rows(
    test: list[mvp.Scenario],
    grouping_cache: dict[str, list[list[list[int]]]],
    *,
    max_groups: int,
    feature_mode: str,
    seed: int,
    rb_budget_ratio: float,
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
                    "scenario_mode": "anti_cqi_hard",
                    "load_level": "focused",
                    "rb_budget_ratio": rb_budget_ratio,
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=Path("anti_cqi_hard_regime"))
    parser.add_argument("--train-scenarios", type=int, default=96)
    parser.add_argument("--test-scenarios", type=int, default=32)
    parser.add_argument("--users", type=int, default=12)
    parser.add_argument("--rbs", type=int, default=72)
    parser.add_argument("--max-groups", type=int, default=3)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--validation-fraction", type=float, default=0.15)
    parser.add_argument("--pair-sampling", default="random_balanced")
    parser.add_argument("--pairs-per-class", type=int, default=160)
    parser.add_argument("--feature-mode", default="history_cost_quality")
    parser.add_argument("--rb-budget-ratio", type=float, default=0.24)
    parser.add_argument("--min-teacher-gain", type=float, default=0.018)
    parser.add_argument("--min-cqi-gap", type=float, default=0.010)
    parser.add_argument("--min-resource-gap", type=float, default=0.0)
    parser.add_argument("--max-cqi-span", type=int, default=2)
    parser.add_argument("--max-attempt-multiplier", type=int, default=80)
    parser.add_argument("--target-buffer-multiplier", type=int, default=4)
    parser.add_argument("--kmeans-n-init", type=int, default=10)
    parser.add_argument("--seed", type=int, default=9)
    args = parser.parse_args()

    if not 0.0 < args.rb_budget_ratio <= 1.0:
        parser.error("--rb-budget-ratio must be in the interval (0, 1]")
    if args.pairs_per_class <= 0:
        parser.error("--pairs-per-class must be positive")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    progress("Mining anti-CQI hard train/test scenarios")
    train, train_audit = mine_scenarios(
        target_count=args.train_scenarios,
        seed=args.seed,
        args=args,
        split_name="train",
    )
    test, test_audit = mine_scenarios(
        target_count=args.test_scenarios,
        seed=args.seed + 1000,
        args=args,
        split_name="test",
    )

    progress("Training LE-GRA on mined anti-CQI hard scenarios")
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
        progress_label="anti_cqi_hard",
    )

    progress("Evaluating methods on mined anti-CQI hard test set")
    method_rows, grouping_cache = evaluate_main_methods(
        test,
        model,
        max_groups=args.max_groups,
        switch_beta=args.switch_beta,
        kmeans_n_init=args.kmeans_n_init,
        progress_label="anti_cqi_hard",
    )
    for row in method_rows:
        row.update(
            {
                "scenario_mode": "anti_cqi_hard",
                "load_level": "focused",
                "rb_budget_ratio": args.rb_budget_ratio,
                "kmax": args.max_groups,
                "seed": args.seed,
                "feature_mode": args.feature_mode,
                "train_scenarios": len(train),
                "test_scenarios": len(test),
            }
        )
    diagnostic_rows = evaluate_teacher_imitation_rows(
        test,
        grouping_cache,
        max_groups=args.max_groups,
        feature_mode=args.feature_mode,
        seed=args.seed,
        rb_budget_ratio=args.rb_budget_ratio,
    )

    train_summary = summarize_rows(train_audit)
    test_summary = summarize_rows(test_audit)
    summary_rows = [
        {
            "split": "train",
            **train_summary,
        },
        {
            "split": "test",
            **test_summary,
        },
    ]

    write_csv(args.out_dir / "main_comparison.csv", method_rows)
    write_csv(args.out_dir / "teacher_imitation_diagnostics.csv", diagnostic_rows)
    write_csv(args.out_dir / "scenario_audit.csv", train_audit + test_audit)
    write_csv(args.out_dir / "scenario_summary.csv", summary_rows)

    progress(f"Saved {args.out_dir / 'main_comparison.csv'}")
    progress(f"Saved {args.out_dir / 'teacher_imitation_diagnostics.csv'}")
    progress(f"Saved {args.out_dir / 'scenario_audit.csv'}")
    progress(f"Saved {args.out_dir / 'scenario_summary.csv'}")

    progress("Main comparison summary")
    for row in method_rows:
        progress(
            f"  {row['method']}: utility={row['utility']:.4f}, "
            f"adr={row['adr_kbps']:.1f}, rb_utilization={row['rb_utilization']:.4f}, "
            f"switching={row['avg_switching']:.4f}, fairness={row['fairness']:.4f}"
        )


if __name__ == "__main__":
    main()
