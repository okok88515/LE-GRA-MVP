"""P3.6g focused temporal learner protocol on the P3.6e3 split-pressure trace."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import le_gra_mvp as mvp
import run_standard_matrix as matrix
from run_p3_6_coupled_learner import (
    _load_export_metadata,
    _write_csv,
    _subset_scenarios,
    build_explicit_split,
    evaluate_trace_methods,
    evaluate_trace_teacher_imitation,
    train_trace_model,
)


def _filter_time_window(
    scenarios: list[mvp.Scenario],
    metadata_rows: list[dict],
    *,
    start_s: float | None,
    end_s: float | None,
) -> tuple[list[mvp.Scenario], list[dict]]:
    kept_scenarios = []
    kept_metadata = []
    for scenario, metadata in zip(scenarios, metadata_rows):
        timestamp = float(metadata["timestamp_s"])
        if start_s is not None and timestamp < start_s:
            continue
        if end_s is not None and timestamp > end_s:
            continue
        kept_scenarios.append(scenario)
        kept_metadata.append(metadata)
    return kept_scenarios, kept_metadata


def _teacher_positive_gain_count(scenarios: list[mvp.Scenario], switch_beta: float, max_groups: int) -> int:
    count = 0
    for scenario in scenarios:
        teacher_groups = mvp.offline_teacher_groups(
            scenario,
            max_groups=min(max_groups, len(scenario.cqi_now)),
            switch_beta=switch_beta,
        )
        teacher_result = mvp.allocate_and_evaluate(teacher_groups, scenario, switch_beta)
        single_result = mvp.allocate_and_evaluate([list(range(len(scenario.cqi_now)))], scenario, switch_beta)
        if teacher_result.utility - single_result.utility > 1e-9:
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", type=Path, default=Path("p3_6e3_coupled_bundle/bundle"))
    parser.add_argument("--out-dir", type=Path, default=Path("p3_6g_temporal_learner"))
    parser.add_argument("--feature-mode", default="history_cost_quality")
    parser.add_argument("--focus-ue-ids", nargs="+", default=["0", "1", "2", "3"])
    parser.add_argument("--train-window-end", type=float, default=15.9)
    parser.add_argument("--test-window-start", type=float, default=16.0)
    parser.add_argument("--test-window-end", type=float, default=18.0)
    parser.add_argument("--max-groups", type=int, default=3)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--pair-sampling", default="random_balanced")
    parser.add_argument("--pairs-per-class", type=int, default=160)
    parser.add_argument("--kmeans-n-init", type=int, default=10)
    parser.add_argument("--seed", type=int, default=9)
    parser.add_argument("--min-users", type=int, default=2)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    export_metadata = _load_export_metadata(args.bundle_dir)

    focus_split = build_explicit_split(
        args.bundle_dir,
        test_ue_ids=args.focus_ue_ids,
        feature_mode=args.feature_mode,
        min_users=args.min_users,
    )
    background_train, background_metadata = _subset_scenarios(
        args.bundle_dir,
        set(focus_split["train_ue_ids"]),
        args.feature_mode,
        min_users=args.min_users,
    )
    focus_all, focus_metadata = _subset_scenarios(
        args.bundle_dir,
        set(focus_split["test_ue_ids"]),
        args.feature_mode,
        min_users=args.min_users,
    )
    focus_train, focus_train_metadata = _filter_time_window(
        focus_all,
        focus_metadata,
        start_s=None,
        end_s=args.train_window_end,
    )
    focus_test, focus_test_metadata = _filter_time_window(
        focus_all,
        focus_metadata,
        start_s=args.test_window_start,
        end_s=args.test_window_end,
    )

    train = background_train + focus_train
    train_metadata = background_metadata + focus_train_metadata
    test = focus_test
    test_metadata = focus_test_metadata
    if not train or not test:
        raise ValueError("Temporal protocol produced empty train or test split")

    mvp.set_seed(args.seed)
    label = "P3.6g temporal learner"
    matrix.progress(
        f"[{label}] background_train={len(background_train)} focus_train={len(focus_train)} "
        f"test={len(test)} focus_ues={focus_split['test_ue_ids']}"
    )
    model = train_trace_model(
        train,
        test,
        feature_mode=args.feature_mode,
        max_groups=args.max_groups,
        switch_beta=args.switch_beta,
        epochs=args.epochs,
        pair_sampling=args.pair_sampling,
        pairs_per_class=args.pairs_per_class,
        progress_label=label,
    )
    method_rows, grouping_cache = evaluate_trace_methods(
        test,
        model,
        max_groups=args.max_groups,
        switch_beta=args.switch_beta,
        kmeans_n_init=args.kmeans_n_init,
        progress_label=label,
    )
    for row in method_rows:
        row.update(
            {
                "dataset": "p3_6g_temporal_focus",
                "feature_mode": args.feature_mode,
                "max_groups": args.max_groups,
                "rb_budget_ratio": export_metadata["rb_budget_ratio"],
                "focus_ue_ids": "|".join(focus_split["test_ue_ids"]),
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
        feature_mode=args.feature_mode,
        scenario_mode="coupled_temporal_focus",
        load_level=f"coupled_trace_rb_{int(round(export_metadata['rb_budget_ratio'] * 100)):02d}_temporal_focus",
        rb_budget_ratio=export_metadata["rb_budget_ratio"],
        seed=args.seed,
        progress_label=label,
    )

    split_summary = {
        "bundle_dir": str(args.bundle_dir),
        "feature_mode": args.feature_mode,
        "max_groups": args.max_groups,
        "seed": args.seed,
        "min_users": args.min_users,
        "focus_ue_ids": focus_split["test_ue_ids"],
        "background_train_ue_ids": focus_split["train_ue_ids"],
        "background_train_scenarios": len(background_train),
        "focus_train_scenarios": len(focus_train),
        "focus_test_scenarios": len(focus_test),
        "focus_train_positive_gain_count": _teacher_positive_gain_count(
            focus_train, args.switch_beta, args.max_groups
        ),
        "focus_test_positive_gain_count": _teacher_positive_gain_count(
            focus_test, args.switch_beta, args.max_groups
        ),
        "train_window_end": args.train_window_end,
        "test_window_start": args.test_window_start,
        "test_window_end": args.test_window_end,
        "rb_budget_ratio": export_metadata["rb_budget_ratio"],
        "selected_epoch": model.selected_epoch,
        "selection_validation_loss": model.selection_validation_loss,
        "pair_sampling": model.pair_sampling,
    }
    (args.out_dir / "split_summary.json").write_text(
        json.dumps(split_summary, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_csv(args.out_dir / "train_scenarios.csv", train_metadata)
    _write_csv(args.out_dir / "test_scenarios.csv", test_metadata)
    _write_csv(args.out_dir / "main_comparison.csv", method_rows)
    _write_csv(args.out_dir / "teacher_imitation_diagnostics.csv", diagnostic_rows)

    print("P3.6g temporal learner summary:")
    print(json.dumps(split_summary, indent=2))
    print("\nMain comparison")
    for row in method_rows:
        print(
            f"  {row['method']}: utility={row['utility']:.4f}, "
            f"system_SE={row['system_spectral_efficiency']:.3f}, "
            f"served={row['served_ratio']:.3f}, quality={row['average_quality']:.3f}, "
            f"switching={row['avg_switching']:.3f}, groups={row['avg_groups']:.2f}"
        )


if __name__ == "__main__":
    main()
