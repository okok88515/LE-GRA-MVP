"""Family-preserving temporal learner evaluation on a focused coupled bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import le_gra_mvp as mvp
from run_p3_6_coupled_learner import (
    _load_export_metadata,
    _read_csv,
    _write_csv,
    _scenario_from_rows,
    evaluate_trace_methods,
    evaluate_trace_teacher_imitation,
    train_trace_model,
)


def _select_family_rows(
    bundle_dir: Path,
    *,
    feature_mode: str,
    serving_gnb: str,
    ue_ids_signature: str,
) -> tuple[list[mvp.Scenario], list[dict]]:
    scenario_rows = _read_csv(bundle_dir / "scenarios.csv")
    user_rows = _read_csv(bundle_dir / "users.csv")
    rb_rows = _read_csv(bundle_dir / "rb_rates.csv")
    users_by_scenario: dict[str, list[dict[str, str]]] = {}
    for row in user_rows:
        users_by_scenario.setdefault(row["scenario_id"], []).append(row)
    rbs_by_scenario: dict[str, list[dict[str, str]]] = {}
    for row in rb_rows:
        rbs_by_scenario.setdefault(row["scenario_id"], []).append(row)

    selected_scenarios: list[mvp.Scenario] = []
    selected_metadata: list[dict] = []
    for scenario_row in scenario_rows:
        if scenario_row["serving_gnb"] != serving_gnb:
            continue
        current_users = sorted(
            users_by_scenario.get(scenario_row["scenario_id"], []),
            key=lambda row: int(row["user_index"]),
        )
        if "|".join(row["ue_id"] for row in current_users) != ue_ids_signature:
            continue
        current_rbs = sorted(
            rbs_by_scenario.get(scenario_row["scenario_id"], []),
            key=lambda row: (int(row["user_index"]), int(row["rb_index"])),
        )
        selected_scenarios.append(
            _scenario_from_rows(scenario_row, current_users, current_rbs, feature_mode)
        )
        selected_metadata.append(
            {
                "scenario_id": scenario_row["scenario_id"],
                "timestamp_s": scenario_row["timestamp_s"],
                "serving_gnb": scenario_row["serving_gnb"],
                "user_count": len(current_users),
                "ue_ids": ue_ids_signature,
            }
        )
    return selected_scenarios, selected_metadata


def _filter_window(
    scenarios: list[mvp.Scenario],
    metadata_rows: list[dict],
    *,
    start_s: float | None,
    end_s: float | None,
) -> tuple[list[mvp.Scenario], list[dict]]:
    kept_scenarios = []
    kept_metadata = []
    for scenario, metadata in zip(scenarios, metadata_rows):
        ts = float(metadata["timestamp_s"])
        if start_s is not None and ts < start_s:
            continue
        if end_s is not None and ts > end_s:
            continue
        kept_scenarios.append(scenario)
        kept_metadata.append(metadata)
    return kept_scenarios, kept_metadata


def _teacher_positive_gain_count(
    scenarios: list[mvp.Scenario],
    *,
    max_groups: int,
    switch_beta: float,
) -> int:
    count = 0
    for scenario in scenarios:
        groups = mvp.offline_teacher_groups(
            scenario,
            max_groups=min(max_groups, len(scenario.cqi_now)),
            switch_beta=switch_beta,
        )
        teacher_eval = mvp.allocate_and_evaluate(groups, scenario, switch_beta)
        single_eval = mvp.allocate_and_evaluate(
            [list(range(len(scenario.cqi_now)))],
            scenario,
            switch_beta,
        )
        if teacher_eval.utility - single_eval.utility > 1e-9:
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--serving-gnb", required=True)
    parser.add_argument("--ue-ids", required=True, help="Exact family signature, e.g. 1|2|3|4|5|6")
    parser.add_argument("--train-window-start", type=float, default=None)
    parser.add_argument("--train-window-end", type=float, default=None)
    parser.add_argument("--test-window-start", type=float, default=None)
    parser.add_argument("--test-window-end", type=float, default=None)
    parser.add_argument("--feature-mode", default="history_cost_quality")
    parser.add_argument("--max-groups", type=int, default=3)
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--pair-sampling", default="random_balanced")
    parser.add_argument("--pairs-per-class", type=int, default=64)
    parser.add_argument("--seed", type=int, default=9)
    parser.add_argument("--kmeans-n-init", type=int, default=10)
    parser.add_argument("--grouping-mode", default="kmeans_embedding")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    mvp.set_seed(args.seed)
    export_metadata = _load_export_metadata(args.bundle_dir)
    family_scenarios, family_metadata = _select_family_rows(
        args.bundle_dir,
        feature_mode=args.feature_mode,
        serving_gnb=args.serving_gnb,
        ue_ids_signature=args.ue_ids,
    )
    train, train_metadata = _filter_window(
        family_scenarios,
        family_metadata,
        start_s=args.train_window_start,
        end_s=args.train_window_end,
    )
    test, test_metadata = _filter_window(
        family_scenarios,
        family_metadata,
        start_s=args.test_window_start,
        end_s=args.test_window_end,
    )
    if not train or not test:
        raise ValueError("Family temporal split produced empty train or test set")

    model = train_trace_model(
        train,
        test,
        feature_mode=args.feature_mode,
        max_groups=args.max_groups,
        switch_beta=args.switch_beta,
        epochs=args.epochs,
        pair_sampling=args.pair_sampling,
        pairs_per_class=args.pairs_per_class,
        supervision_weight_mode="uniform",
        hard_positive_scale=2.5,
        hard_negative_scale=1.5,
        scenario_weight_mode="uniform",
        positive_gain_boost=4,
        multigroup_boost=2,
        prototype_weight=0.0,
        prototype_margin=1.0,
        membership_weight=0.0,
        candidate_membership_weight=0.0,
        candidate_top_k=2,
        candidate_secondary_scale=2.0,
        frontier_contrast_weight=0.0,
        frontier_negative_top_k=2,
        frontier_margin=0.25,
        focus_support_indices=None,
        focus_only_warmup_epochs=0,
        grouping_mode=args.grouping_mode,
        progress_label="Focused family temporal learner",
    )
    method_rows, grouping_cache = evaluate_trace_methods(
        test,
        model,
        max_groups=args.max_groups,
        switch_beta=args.switch_beta,
        kmeans_n_init=args.kmeans_n_init,
        progress_label="Focused family temporal learner",
    )
    for row in method_rows:
        row.update(
            {
                "dataset": "focused_family_temporal",
                "feature_mode": args.feature_mode,
                "rb_budget_ratio": export_metadata["rb_budget_ratio"],
                "serving_gnb": args.serving_gnb,
                "ue_ids": args.ue_ids,
                "train_window_start": args.train_window_start,
                "train_window_end": args.train_window_end,
                "test_window_start": args.test_window_start,
                "test_window_end": args.test_window_end,
                "seed": args.seed,
            }
        )
    diagnostic_rows = evaluate_trace_teacher_imitation(
        test,
        grouping_cache,
        max_groups=args.max_groups,
        switch_beta=args.switch_beta,
        metadata_rows=test_metadata,
        feature_mode=args.feature_mode,
        scenario_mode="focused_family_temporal",
        load_level=f"focused_family_rb_{int(round(export_metadata['rb_budget_ratio'] * 100)):02d}",
        rb_budget_ratio=export_metadata["rb_budget_ratio"],
        seed=args.seed,
        progress_label="Focused family temporal learner",
    )
    summary = {
        "bundle_dir": str(args.bundle_dir),
        "serving_gnb": args.serving_gnb,
        "ue_ids": args.ue_ids,
        "feature_mode": args.feature_mode,
        "train_scenarios": len(train),
        "test_scenarios": len(test),
        "train_positive_gain_count": _teacher_positive_gain_count(
            train,
            max_groups=args.max_groups,
            switch_beta=args.switch_beta,
        ),
        "test_positive_gain_count": _teacher_positive_gain_count(
            test,
            max_groups=args.max_groups,
            switch_beta=args.switch_beta,
        ),
        "train_window_start": args.train_window_start,
        "train_window_end": args.train_window_end,
        "test_window_start": args.test_window_start,
        "test_window_end": args.test_window_end,
        "rb_budget_ratio": export_metadata["rb_budget_ratio"],
        "selected_epoch": model.selected_epoch,
        "selection_validation_loss": model.selection_validation_loss,
        "grouping_mode": args.grouping_mode,
    }
    (args.out_dir / "split_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_csv(args.out_dir / "train_scenarios.csv", train_metadata)
    _write_csv(args.out_dir / "test_scenarios.csv", test_metadata)
    _write_csv(args.out_dir / "main_comparison.csv", method_rows)
    _write_csv(args.out_dir / "teacher_imitation_diagnostics.csv", diagnostic_rows)

    print("Focused family temporal learner summary:")
    print(json.dumps(summary, indent=2))
    print("\nMain comparison")
    for row in method_rows:
        print(
            f"  {row['method']}: utility={float(row['utility']):.4f}, "
            f"system_SE={float(row['system_spectral_efficiency']):.3f}, "
            f"quality={float(row['average_quality']):.3f}, "
            f"switching={float(row['avg_switching']):.3f}, "
            f"groups={float(row['avg_groups']):.2f}"
        )


if __name__ == "__main__":
    main()
