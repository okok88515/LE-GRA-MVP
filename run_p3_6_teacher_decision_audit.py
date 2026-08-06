"""Audit offline-teacher decision diversity on the P3.6 coupled trace."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp
from run_p3_6_coupled_learner import (
    build_explicit_split,
    _load_export_metadata,
    _read_csv,
    _subset_scenarios,
    choose_trajectory_split,
)


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _mean_quality_to_bucket(value: float) -> str:
    if value < 2.0:
        return "low(<2)"
    if value < 3.0:
        return "mid[2,3)"
    if value < 4.0:
        return "high[3,4)"
    return "very_high(>=4)"


def _rb_ratio_to_bucket(value: float) -> str:
    if value < 0.45:
        return "tight(<0.45)"
    if value < 0.60:
        return "mid[0.45,0.60)"
    return "loose(>=0.60)"


def _range_to_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value == 1:
        return "1"
    if value == 2:
        return "2"
    return "3+"


def _summarize_slice(
    rows: list[dict],
    key_name: str,
    value_name: str,
) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[str(row[key_name])].append(row)
    summary = []
    for key in sorted(grouped):
        group_rows = grouped[key]
        gains = [float(row["teacher_gain_vs_single"]) for row in group_rows]
        summary.append(
            {
                value_name: key,
                "scenario_count": len(group_rows),
                "multi_group_count": sum(int(row["teacher_group_count"]) > 1 for row in group_rows),
                "multi_group_ratio": (
                    sum(int(row["teacher_group_count"]) > 1 for row in group_rows) / len(group_rows)
                ),
                "mean_teacher_group_count": np.mean(
                    [int(row["teacher_group_count"]) for row in group_rows]
                ),
                "mean_teacher_gain_vs_single": np.mean(gains),
                "max_teacher_gain_vs_single": np.max(gains),
            }
        )
    return summary


def _scenario_row(
    metadata: dict,
    scenario: mvp.Scenario,
    teacher_groups: list[list[int]],
    switch_beta: float,
    split_name: str,
) -> dict:
    teacher_result = mvp.allocate_and_evaluate(teacher_groups, scenario, switch_beta)
    single_result = mvp.allocate_and_evaluate([list(range(len(scenario.cqi_now)))], scenario, switch_beta)
    cqi_values = scenario.cqi_now.astype(int)
    quality_values = scenario.previous_quality.astype(int)
    user_cost = mvp.user_resource_cost_vector(scenario.rb_rates)
    mean_cost = user_cost.mean(axis=1)
    sorted_group_sizes = sorted((len(group) for group in teacher_groups), reverse=True)
    return {
        "split_name": split_name,
        "scenario_id": metadata["scenario_id"],
        "timestamp_s": metadata["timestamp_s"],
        "serving_gnb": metadata["serving_gnb"],
        "ue_ids": metadata["ue_ids"],
        "user_count": int(metadata["user_count"]),
        "rb_available": int(scenario.rb_available),
        "total_rbs": int(scenario.rb_rates.shape[1]),
        "rb_budget_ratio_snapshot": float(scenario.rb_available / scenario.rb_rates.shape[1]),
        "cqi_min": int(cqi_values.min()),
        "cqi_max": int(cqi_values.max()),
        "cqi_range": int(cqi_values.max() - cqi_values.min()),
        "cqi_mean": float(np.mean(cqi_values)),
        "previous_quality_min": int(quality_values.min()),
        "previous_quality_max": int(quality_values.max()),
        "previous_quality_range": int(quality_values.max() - quality_values.min()),
        "previous_quality_mean": float(np.mean(quality_values)),
        "distance_mean_m": float(np.mean(scenario.distance)),
        "distance_range_m": float(np.max(scenario.distance) - np.min(scenario.distance)),
        "mean_resource_cost": float(np.mean(mean_cost)),
        "resource_cost_range": float(np.max(mean_cost) - np.min(mean_cost)),
        "teacher_group_count": len(teacher_groups),
        "teacher_group_sizes": "|".join(str(size) for size in sorted_group_sizes),
        "teacher_groups": json.dumps([sorted(group) for group in teacher_groups]),
        "teacher_utility": float(teacher_result.utility),
        "single_group_utility": float(single_result.utility),
        "teacher_gain_vs_single": float(teacher_result.utility - single_result.utility),
        "teacher_avg_quality": float(teacher_result.average_quality),
        "single_avg_quality": float(single_result.average_quality),
        "teacher_switching": float(teacher_result.avg_switching),
        "single_switching": float(single_result.avg_switching),
        "teacher_rb_utilization": float(teacher_result.rb_utilization),
        "single_rb_utilization": float(single_result.rb_utilization),
    }


def _build_summary(rows: list[dict], split_name: str) -> list[dict]:
    gains = np.asarray([float(row["teacher_gain_vs_single"]) for row in rows], dtype=float)
    group_counts = np.asarray([int(row["teacher_group_count"]) for row in rows], dtype=int)
    multi_group = group_counts > 1
    return [
        {"metric": "split_name", "value": split_name},
        {"metric": "scenario_count", "value": len(rows)},
        {"metric": "multi_group_count", "value": int(np.sum(multi_group))},
        {"metric": "multi_group_ratio", "value": float(np.mean(multi_group)) if len(rows) else 0.0},
        {"metric": "mean_teacher_group_count", "value": float(np.mean(group_counts)) if len(rows) else 0.0},
        {"metric": "max_teacher_group_count", "value": int(np.max(group_counts)) if len(rows) else 0},
        {"metric": "mean_teacher_gain_vs_single", "value": float(np.mean(gains)) if len(rows) else 0.0},
        {"metric": "max_teacher_gain_vs_single", "value": float(np.max(gains)) if len(rows) else 0.0},
        {
            "metric": "positive_gain_count",
            "value": int(np.sum(gains > 1e-9)),
        },
        {
            "metric": "positive_gain_ratio",
            "value": float(np.mean(gains > 1e-9)) if len(rows) else 0.0,
        },
    ]


def _run_split_audit(
    bundle_dir: Path,
    scenarios: list[mvp.Scenario],
    metadata_rows: list[dict],
    *,
    switch_beta: float,
    split_name: str,
    out_dir: Path,
) -> None:
    rows = []
    for metadata, scenario in zip(metadata_rows, scenarios):
        teacher_groups = mvp.offline_teacher_groups(scenario, max_groups=len(scenario.cqi_now), switch_beta=switch_beta)
        rows.append(_scenario_row(metadata, scenario, teacher_groups, switch_beta, split_name))

    split_dir = out_dir / split_name
    split_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(split_dir / "scenario_teacher_decisions.csv", rows)
    _write_csv(split_dir / "summary.csv", _build_summary(rows, split_name))
    _write_csv(split_dir / "by_user_count.csv", _summarize_slice(rows, "user_count", "user_count"))

    enriched = []
    for row in rows:
        enriched_row = dict(row)
        enriched_row["rb_budget_bucket"] = _rb_ratio_to_bucket(float(row["rb_budget_ratio_snapshot"]))
        enriched_row["quality_mean_bucket"] = _mean_quality_to_bucket(float(row["previous_quality_mean"]))
        enriched_row["quality_range_bucket"] = _range_to_bucket(int(row["previous_quality_range"]))
        enriched_row["cqi_range_bucket"] = _range_to_bucket(int(row["cqi_range"]))
        enriched.append(enriched_row)
    _write_csv(split_dir / "by_serving_gnb.csv", _summarize_slice(enriched, "serving_gnb", "serving_gnb"))
    _write_csv(split_dir / "by_rb_budget_bucket.csv", _summarize_slice(enriched, "rb_budget_bucket", "rb_budget_bucket"))
    _write_csv(split_dir / "by_quality_mean_bucket.csv", _summarize_slice(enriched, "quality_mean_bucket", "quality_mean_bucket"))
    _write_csv(split_dir / "by_quality_range_bucket.csv", _summarize_slice(enriched, "quality_range_bucket", "quality_range_bucket"))
    _write_csv(split_dir / "by_cqi_range_bucket.csv", _summarize_slice(enriched, "cqi_range_bucket", "cqi_range_bucket"))

    top_gain = sorted(rows, key=lambda row: float(row["teacher_gain_vs_single"]), reverse=True)[:20]
    _write_csv(split_dir / "top_teacher_gain_scenarios.csv", top_gain)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", type=Path, default=Path("p3_6_coupled_bundle/bundle"))
    parser.add_argument("--out-dir", type=Path, default=Path("p3_6_teacher_audit"))
    parser.add_argument("--feature-mode", default="history_cost_quality")
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--test-ue-count", type=int, default=3)
    parser.add_argument("--test-ue-ids", nargs="*", default=None)
    parser.add_argument("--min-users", type=int, default=2)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    export_metadata = _load_export_metadata(args.bundle_dir)
    all_users = _read_csv(args.bundle_dir / "users.csv")
    all_ue_ids = sorted({row["ue_id"] for row in all_users})
    if args.test_ue_ids:
        split = build_explicit_split(
            args.bundle_dir,
            test_ue_ids=args.test_ue_ids,
            feature_mode=args.feature_mode,
            min_users=args.min_users,
        )
    else:
        split = choose_trajectory_split(
            args.bundle_dir,
            test_ue_count=args.test_ue_count,
            feature_mode=args.feature_mode,
            min_users=args.min_users,
        )

    full_scenarios, full_metadata = _subset_scenarios(
        args.bundle_dir,
        set(all_ue_ids),
        args.feature_mode,
        min_users=args.min_users,
    )
    test_scenarios, test_metadata = _subset_scenarios(
        args.bundle_dir,
        set(split["test_ue_ids"]),
        args.feature_mode,
        min_users=args.min_users,
    )

    _run_split_audit(
        args.bundle_dir,
        full_scenarios,
        full_metadata,
        switch_beta=args.switch_beta,
        split_name="full_bundle",
        out_dir=args.out_dir,
    )
    _run_split_audit(
        args.bundle_dir,
        test_scenarios,
        test_metadata,
        switch_beta=args.switch_beta,
        split_name="learner_test_split",
        out_dir=args.out_dir,
    )

    run_metadata = {
        "bundle_dir": str(args.bundle_dir),
        "feature_mode": args.feature_mode,
        "switch_beta": args.switch_beta,
        "min_users": args.min_users,
        "export_rb_budget_ratio": export_metadata["rb_budget_ratio"],
        "trajectory_split_test_ue_ids": split["test_ue_ids"],
        "trajectory_split_train_ue_ids": split["train_ue_ids"],
    }
    (args.out_dir / "run_metadata.json").write_text(
        json.dumps(run_metadata, indent=2) + "\n",
        encoding="utf-8",
    )

    print("P3.6 teacher-decision audit complete")
    print(json.dumps(run_metadata, indent=2))


if __name__ == "__main__":
    main()
