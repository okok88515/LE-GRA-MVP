"""P3.6g focused temporal learner protocol on the P3.6e3 split-pressure trace."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import le_gra_mvp as mvp
import numpy as np
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


def _teacher_weak_group_audit(
    scenarios: list[mvp.Scenario],
    metadata_rows: list[dict],
    switch_beta: float,
    max_groups: int,
) -> list[dict]:
    rows = []
    for scenario, metadata in zip(scenarios, metadata_rows):
        teacher_groups = mvp.offline_teacher_groups(
            scenario,
            max_groups=min(max_groups, len(scenario.cqi_now)),
            switch_beta=switch_beta,
        )
        teacher_result = mvp.allocate_and_evaluate(teacher_groups, scenario, switch_beta)
        single_result = mvp.allocate_and_evaluate(
            [list(range(len(scenario.cqi_now)))],
            scenario,
            switch_beta,
        )
        ue_ids = metadata["ue_ids"].split("|")
        ordered = mvp.teacher_group_difficulty_order(scenario, teacher_groups)
        hard_group = teacher_groups[ordered[0]] if ordered else []
        rows.append(
            {
                "split": metadata.get("split", ""),
                "scenario_id": metadata["scenario_id"],
                "timestamp_s": metadata["timestamp_s"],
                "serving_gnb": metadata["serving_gnb"],
                "ue_ids": metadata["ue_ids"],
                "teacher_group_count": len(teacher_groups),
                "teacher_groups": json.dumps(
                    [[ue_ids[idx] for idx in group] for group in teacher_groups],
                    ensure_ascii=False,
                ),
                "hard_group_signature": "|".join(sorted(ue_ids[idx] for idx in hard_group)),
                "teacher_gain_vs_single": teacher_result.utility - single_result.utility,
            }
        )
    return rows


def _weak_group_prediction_audit(
    scenarios: list[mvp.Scenario],
    metadata_rows: list[dict],
    model: mvp.MLPEncoder,
    switch_beta: float,
    max_groups: int,
    *,
    split_name: str,
    candidate_top_k: int,
    candidate_secondary_scale: float,
) -> list[dict]:
    rows = []
    for scenario, metadata in zip(scenarios, metadata_rows):
        teacher_groups = mvp.offline_teacher_groups(
            scenario,
            max_groups=min(max_groups, len(scenario.cqi_now)),
            switch_beta=switch_beta,
        )
        ue_ids = metadata["ue_ids"].split("|")
        hard_target = mvp.hardest_group_membership(scenario, teacher_groups)
        candidate_target, candidate_target_weights = (
            mvp.candidate_conditioned_membership_targets(
                scenario,
                teacher_groups,
                top_k=candidate_top_k,
                secondary_scale=candidate_secondary_scale,
            )
        )
        weak_scores = model.weak_group_scores(scenario.features)
        ranking = np.argsort(-weak_scores)
        predicted_top_k = ranking[:candidate_top_k].tolist()
        teacher_hard_members = np.where(hard_target > 0.5)[0].tolist()
        teacher_candidates = np.where(candidate_target > 0.5)[0].tolist()
        teacher_secondary_idx = teacher_candidates[1] if len(teacher_candidates) >= 2 else None
        predicted_secondary_rank = None
        if teacher_secondary_idx is not None:
            predicted_secondary_rank = int(np.where(ranking == teacher_secondary_idx)[0][0]) + 1
        rows.append(
            {
                "split": split_name,
                "scenario_id": metadata["scenario_id"],
                "timestamp_s": metadata["timestamp_s"],
                "serving_gnb": metadata["serving_gnb"],
                "ue_ids": metadata["ue_ids"],
                "teacher_hard_group_signature": "|".join(
                    sorted(ue_ids[idx] for idx in teacher_hard_members)
                ),
                "teacher_candidate_signature": "|".join(
                    ue_ids[idx] for idx in teacher_candidates
                ),
                "predicted_topk_signature": "|".join(
                    ue_ids[idx] for idx in predicted_top_k
                ),
                "teacher_secondary_ue": (
                    ue_ids[teacher_secondary_idx] if teacher_secondary_idx is not None else ""
                ),
                "predicted_secondary_rank": (
                    predicted_secondary_rank if predicted_secondary_rank is not None else ""
                ),
                "predicted_top1_ue": ue_ids[ranking[0]] if len(ranking) >= 1 else "",
                "predicted_top2_ue": ue_ids[ranking[1]] if len(ranking) >= 2 else "",
                "predicted_top1_score": float(weak_scores[ranking[0]]) if len(ranking) >= 1 else float("nan"),
                "predicted_top2_score": float(weak_scores[ranking[1]]) if len(ranking) >= 2 else float("nan"),
                "teacher_candidate_hit_count": sum(idx in predicted_top_k for idx in teacher_candidates),
                "teacher_secondary_in_predicted_topk": int(
                    teacher_secondary_idx in predicted_top_k if teacher_secondary_idx is not None else 0
                ),
                "teacher_secondary_weight": (
                    float(candidate_target_weights[teacher_secondary_idx])
                    if teacher_secondary_idx is not None
                    else float("nan")
                ),
            }
        )
    return rows


def _repeat_examples(
    scenarios: list[mvp.Scenario],
    metadata_rows: list[dict],
    repeat: int,
) -> tuple[list[mvp.Scenario], list[dict]]:
    repeated_scenarios: list[mvp.Scenario] = []
    repeated_metadata: list[dict] = []
    for _ in range(repeat):
        repeated_scenarios.extend(copy.deepcopy(scenarios))
        repeated_metadata.extend(dict(row) for row in metadata_rows)
    return repeated_scenarios, repeated_metadata


def _repeat_selected_examples(
    scenarios: list[mvp.Scenario],
    metadata_rows: list[dict],
    selected_indices: list[int],
    repeat: int,
) -> tuple[list[mvp.Scenario], list[dict]]:
    if repeat < 1:
        raise ValueError("repeat must be >= 1")
    repeated_scenarios: list[mvp.Scenario] = []
    repeated_metadata: list[dict] = []
    for _ in range(repeat):
        for idx in selected_indices:
            repeated_scenarios.append(copy.deepcopy(scenarios[idx]))
            repeated_metadata.append(dict(metadata_rows[idx]))
    return repeated_scenarios, repeated_metadata


def _limit_examples(
    scenarios: list[mvp.Scenario],
    metadata_rows: list[dict],
    limit: int | None,
) -> tuple[list[mvp.Scenario], list[dict]]:
    if limit is None or limit >= len(scenarios):
        return scenarios, metadata_rows
    if limit < 0:
        raise ValueError("background-train-limit must be >= 0")
    if limit == 0:
        return [], []
    if limit == 1:
        return [scenarios[len(scenarios) // 2]], [metadata_rows[len(metadata_rows) // 2]]
    selected_indices = []
    for slot in range(limit):
        index = round(slot * (len(scenarios) - 1) / (limit - 1))
        if index not in selected_indices:
            selected_indices.append(index)
    while len(selected_indices) < limit:
        for index in range(len(scenarios)):
            if index not in selected_indices:
                selected_indices.append(index)
                if len(selected_indices) >= limit:
                    break
    selected_indices.sort()
    return [scenarios[idx] for idx in selected_indices], [metadata_rows[idx] for idx in selected_indices]


def _filter_explicit_timestamps(
    scenarios: list[mvp.Scenario],
    metadata_rows: list[dict],
    timestamps: list[float],
) -> tuple[list[mvp.Scenario], list[dict]]:
    allowed = {round(float(ts), 6) for ts in timestamps}
    kept_scenarios = []
    kept_metadata = []
    for scenario, metadata in zip(scenarios, metadata_rows):
        timestamp = round(float(metadata["timestamp_s"]), 6)
        if timestamp not in allowed:
            continue
        kept_scenarios.append(scenario)
        kept_metadata.append(metadata)
    return kept_scenarios, kept_metadata


def _select_boundary_support_indices(
    scenarios: list[mvp.Scenario],
    metadata_rows: list[dict],
    *,
    boundary_start_s: float | None,
    positive_only: bool,
    switch_beta: float,
    max_groups: int,
) -> list[int]:
    selected = []
    for idx, (scenario, metadata) in enumerate(zip(scenarios, metadata_rows)):
        timestamp = float(metadata["timestamp_s"])
        if boundary_start_s is not None and timestamp < boundary_start_s:
            continue
        if positive_only:
            teacher_groups = mvp.offline_teacher_groups(
                scenario,
                max_groups=min(max_groups, len(scenario.cqi_now)),
                switch_beta=switch_beta,
            )
            teacher_result = mvp.allocate_and_evaluate(teacher_groups, scenario, switch_beta)
            single_result = mvp.allocate_and_evaluate(
                [list(range(len(scenario.cqi_now)))],
                scenario,
                switch_beta,
            )
            if teacher_result.utility - single_result.utility <= 1e-9:
                continue
        selected.append(idx)
    return selected


def _score_restart_candidate(
    model: mvp.MLPEncoder,
    support_scenarios: list[mvp.Scenario],
    *,
    max_groups: int,
    switch_beta: float,
    kmeans_n_init: int,
    feature_mode: str,
    rb_budget_ratio: float,
    progress_label: str,
) -> tuple[dict, dict[str, list[list[list[int]]]]]:
    def _safe_mean(values: list[float]) -> float:
        if not values:
            return float("nan")
        arr = np.asarray(values, dtype=float)
        if np.all(np.isnan(arr)):
            return float("nan")
        return float(np.nanmean(arr))

    method_rows, grouping_cache = evaluate_trace_methods(
        support_scenarios,
        model,
        max_groups=max_groups,
        switch_beta=switch_beta,
        kmeans_n_init=kmeans_n_init,
        progress_label=progress_label,
    )
    diagnostic_rows = evaluate_trace_teacher_imitation(
        support_scenarios,
        grouping_cache,
        max_groups=max_groups,
        switch_beta=switch_beta,
        feature_mode=feature_mode,
        scenario_mode="coupled_temporal_support",
        load_level=f"coupled_trace_rb_{int(round(rb_budget_ratio * 100)):02d}_temporal_support",
        rb_budget_ratio=rb_budget_ratio,
        seed=getattr(model, "seed", -1),
        progress_label=progress_label,
    )
    learner_row = next(row for row in method_rows if row["method"] == "LE-GRA MVP")
    teacher_row = next(row for row in method_rows if row["method"] == "Offline teacher")
    learner_diag_rows = [row for row in diagnostic_rows if row["method"] == "LE-GRA MVP"]
    mean_pairwise = sum(row["pairwise_accuracy"] for row in learner_diag_rows) / len(learner_diag_rows)
    mean_ari = sum(row["ari"] for row in learner_diag_rows) / len(learner_diag_rows)
    mean_nmi = sum(row["nmi"] for row in learner_diag_rows) / len(learner_diag_rows)
    mean_utility = float(learner_row["utility"])
    teacher_utility = float(teacher_row["utility"])
    contrastive_losses = []
    weak_bces = []
    weak_margin_mins = []
    weak_margin_means = []
    proto_sep_margins = []
    for scenario in support_scenarios:
        teacher_groups = mvp.offline_teacher_groups(
            scenario,
            max_groups=min(max_groups, len(scenario.cqi_now)),
            switch_beta=switch_beta,
        )
        same_group = mvp.pairwise_labels(teacher_groups, len(scenario.cqi_now))
        hard_target = mvp.hardest_group_membership(scenario, teacher_groups)
        contrastive_losses.append(
            model.contrastive_loss(scenario.features, same_group, margin=1.0)
        )
        weak_scores = model.weak_group_scores(scenario.features)
        probs = np.clip(weak_scores, 1e-6, 1.0 - 1e-6)
        weak_bces.append(
            float(
                -np.mean(
                    hard_target * np.log(probs)
                    + (1.0 - hard_target) * np.log(1.0 - probs)
                )
            )
        )
        hard_idx = np.where(hard_target > 0.5)[0]
        other_idx = np.where(hard_target <= 0.5)[0]
        if len(hard_idx) == 0 or len(other_idx) == 0:
            weak_margin_mins.append(float("nan"))
            weak_margin_means.append(float("nan"))
            proto_sep_margins.append(float("nan"))
        else:
            weak_margin_mins.append(
                float(np.min(weak_scores[hard_idx]) - np.max(weak_scores[other_idx]))
            )
            weak_margin_means.append(
                float(np.mean(weak_scores[hard_idx]) - np.mean(weak_scores[other_idx]))
            )
            embeddings = model.embed(scenario.features)
            prototype_center = embeddings[hard_idx].mean(axis=0)
            hard_dists = np.linalg.norm(embeddings[hard_idx] - prototype_center, axis=1)
            other_dists = np.linalg.norm(embeddings[other_idx] - prototype_center, axis=1)
            proto_sep_margins.append(float(np.min(other_dists) - np.max(hard_dists)))
    return {
        "support_pairwise_accuracy": mean_pairwise,
        "support_ari": mean_ari,
        "support_nmi": mean_nmi,
        "support_utility": mean_utility,
        "support_teacher_utility": teacher_utility,
        "support_utility_gap": mean_utility - teacher_utility,
        "support_contrastive_loss": _safe_mean(contrastive_losses),
        "support_weak_bce": _safe_mean(weak_bces),
        "support_weak_margin_min": _safe_mean(weak_margin_mins),
        "support_weak_margin_mean": _safe_mean(weak_margin_means),
        "support_proto_sep_margin": _safe_mean(proto_sep_margins),
    }, grouping_cache


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", type=Path, default=Path("p3_6e3_coupled_bundle/bundle"))
    parser.add_argument("--out-dir", type=Path, default=Path("p3_6g_temporal_learner"))
    parser.add_argument("--feature-mode", default="history_cost_quality")
    parser.add_argument(
        "--joint-supervision-mode",
        choices=["none", "m4b_minimal_joint_v1", "m4b_localized_hard_negative_v1"],
        default="none",
    )
    parser.add_argument("--focus-ue-ids", nargs="+", default=["0", "1", "2", "3"])
    parser.add_argument("--background-train-limit", type=int, default=None)
    parser.add_argument("--background-train-repeat", type=int, default=1)
    parser.add_argument("--focus-train-repeat", type=int, default=1)
    parser.add_argument("--boundary-support-start", type=float, default=None)
    parser.add_argument("--boundary-support-repeat", type=int, default=1)
    parser.add_argument("--boundary-support-positive-only", action="store_true")
    parser.add_argument("--train-window-start", type=float, default=None)
    parser.add_argument("--train-window-end", type=float, default=15.9)
    parser.add_argument("--train-include-timestamps", nargs="*", type=float, default=None)
    parser.add_argument("--test-window-start", type=float, default=16.0)
    parser.add_argument("--test-window-end", type=float, default=18.0)
    parser.add_argument("--test-include-timestamps", nargs="*", type=float, default=None)
    parser.add_argument("--max-groups", type=int, default=3)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--pair-sampling", default="random_balanced")
    parser.add_argument("--pairs-per-class", type=int, default=160)
    parser.add_argument("--supervision-weight-mode", default="uniform")
    parser.add_argument("--hard-positive-scale", type=float, default=2.5)
    parser.add_argument("--hard-negative-scale", type=float, default=1.5)
    parser.add_argument("--scenario-weight-mode", default="uniform")
    parser.add_argument("--positive-gain-boost", type=int, default=4)
    parser.add_argument("--multigroup-boost", type=int, default=2)
    parser.add_argument("--prototype-weight", type=float, default=0.0)
    parser.add_argument("--prototype-margin", type=float, default=1.0)
    parser.add_argument("--membership-weight", type=float, default=0.0)
    parser.add_argument("--candidate-membership-weight", type=float, default=0.0)
    parser.add_argument("--candidate-top-k", type=int, default=2)
    parser.add_argument("--candidate-secondary-scale", type=float, default=2.0)
    parser.add_argument("--frontier-contrast-weight", type=float, default=0.0)
    parser.add_argument("--frontier-negative-top-k", type=int, default=2)
    parser.add_argument("--frontier-margin", type=float, default=0.25)
    parser.add_argument("--focus-only-warmup-epochs", type=int, default=0)
    parser.add_argument("--grouping-mode", default="kmeans_embedding")
    parser.add_argument("--kmeans-n-init", type=int, default=10)
    parser.add_argument("--restart-seeds", nargs="*", type=int, default=None)
    parser.add_argument(
        "--restart-selection-mode",
        choices=("support_imitation", "margin_aware"),
        default="support_imitation",
    )
    parser.add_argument("--seed", type=int, default=9)
    parser.add_argument("--min-users", type=int, default=2)
    args = parser.parse_args()

    if args.joint_supervision_mode == "m4b_minimal_joint_v1":
        args.pair_sampling = "teacher_boundary"
        args.supervision_weight_mode = "teacher_candidate_boundary"
        args.candidate_top_k = 2
        args.candidate_membership_weight = max(args.candidate_membership_weight, 4.0)
        args.candidate_secondary_scale = max(args.candidate_secondary_scale, 4.0)
        args.boundary_support_repeat = max(args.boundary_support_repeat, 16)
        args.boundary_support_positive_only = True
        if args.boundary_support_start is None:
            args.boundary_support_start = 43.4
    elif args.joint_supervision_mode == "m4b_localized_hard_negative_v1":
        args.pair_sampling = "teacher_boundary"
        args.supervision_weight_mode = "teacher_candidate_boundary"
        args.candidate_top_k = 2
        args.candidate_membership_weight = max(args.candidate_membership_weight, 4.0)
        args.candidate_secondary_scale = max(args.candidate_secondary_scale, 4.0)
        args.frontier_contrast_weight = max(args.frontier_contrast_weight, 6.0)
        args.frontier_negative_top_k = max(args.frontier_negative_top_k, 2)
        args.frontier_margin = max(args.frontier_margin, 0.25)
        args.boundary_support_repeat = max(args.boundary_support_repeat, 16)
        args.boundary_support_positive_only = True
        if args.boundary_support_start is None:
            args.boundary_support_start = 43.4

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
    background_train, background_metadata = _limit_examples(
        background_train,
        background_metadata,
        args.background_train_limit,
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
        start_s=args.train_window_start,
        end_s=args.train_window_end,
    )
    focus_test, focus_test_metadata = _filter_time_window(
        focus_all,
        focus_metadata,
        start_s=args.test_window_start,
        end_s=args.test_window_end,
    )
    if args.train_include_timestamps:
        focus_train, focus_train_metadata = _filter_explicit_timestamps(
            focus_train,
            focus_train_metadata,
            args.train_include_timestamps,
        )
    if args.test_include_timestamps:
        focus_test, focus_test_metadata = _filter_explicit_timestamps(
            focus_test,
            focus_test_metadata,
            args.test_include_timestamps,
        )

    if args.background_train_repeat < 1 or args.focus_train_repeat < 1:
        raise ValueError("background-train-repeat and focus-train-repeat must be >= 1")
    if args.boundary_support_repeat < 1:
        raise ValueError("boundary-support-repeat must be >= 1")

    repeated_background_train, repeated_background_metadata = _repeat_examples(
        background_train,
        background_metadata,
        args.background_train_repeat,
    )
    repeated_focus_train, repeated_focus_metadata = _repeat_examples(
        focus_train,
        focus_train_metadata,
        args.focus_train_repeat,
    )
    boundary_support_indices = _select_boundary_support_indices(
        focus_train,
        focus_train_metadata,
        boundary_start_s=args.boundary_support_start,
        positive_only=args.boundary_support_positive_only,
        switch_beta=args.switch_beta,
        max_groups=args.max_groups,
    )
    repeated_boundary_train: list[mvp.Scenario] = []
    repeated_boundary_metadata: list[dict] = []
    if boundary_support_indices and args.boundary_support_repeat > 1:
        repeated_boundary_train, repeated_boundary_metadata = _repeat_selected_examples(
            focus_train,
            focus_train_metadata,
            boundary_support_indices,
            args.boundary_support_repeat - 1,
        )
    train = repeated_background_train + repeated_focus_train
    train_metadata = repeated_background_metadata + repeated_focus_metadata
    if repeated_boundary_train:
        train.extend(repeated_boundary_train)
        train_metadata.extend(repeated_boundary_metadata)
    focus_support_indices = list(range(len(repeated_background_train), len(train)))
    support_eval_scenarios = train[
        len(repeated_background_train):
        len(repeated_background_train) + len(focus_train)
    ]
    test = focus_test
    test_metadata = focus_test_metadata
    if not train or not test:
        raise ValueError("Temporal protocol produced empty train or test split")

    label = "P3.6g temporal learner"
    matrix.progress(
        f"[{label}] background_train={len(background_train)} focus_train={len(focus_train)} "
        f"test={len(test)} focus_ues={focus_split['test_ue_ids']}"
    )
    restart_seeds = args.restart_seeds if args.restart_seeds else [args.seed]
    candidate_rows = []
    selected_support_metrics = None
    best_score = None
    best_seed = None
    model = None
    for candidate_seed in restart_seeds:
        mvp.set_seed(candidate_seed)
        candidate_label = f"{label} [seed={candidate_seed}]"
        candidate_model = train_trace_model(
            train,
            test,
            feature_mode=args.feature_mode,
            max_groups=args.max_groups,
            switch_beta=args.switch_beta,
            epochs=args.epochs,
            pair_sampling=args.pair_sampling,
            pairs_per_class=args.pairs_per_class,
            supervision_weight_mode=args.supervision_weight_mode,
            hard_positive_scale=args.hard_positive_scale,
            hard_negative_scale=args.hard_negative_scale,
            scenario_weight_mode=args.scenario_weight_mode,
            positive_gain_boost=args.positive_gain_boost,
            multigroup_boost=args.multigroup_boost,
            prototype_weight=args.prototype_weight,
            prototype_margin=args.prototype_margin,
            membership_weight=args.membership_weight,
            candidate_membership_weight=args.candidate_membership_weight,
            candidate_top_k=args.candidate_top_k,
            candidate_secondary_scale=args.candidate_secondary_scale,
            frontier_contrast_weight=args.frontier_contrast_weight,
            frontier_negative_top_k=args.frontier_negative_top_k,
            frontier_margin=args.frontier_margin,
            focus_support_indices=focus_support_indices,
            focus_only_warmup_epochs=args.focus_only_warmup_epochs,
            grouping_mode=args.grouping_mode,
            progress_label=candidate_label,
        )
        candidate_model.seed = candidate_seed
        support_metrics, _ = _score_restart_candidate(
            candidate_model,
            support_eval_scenarios,
            max_groups=args.max_groups,
            switch_beta=args.switch_beta,
            kmeans_n_init=args.kmeans_n_init,
            feature_mode=args.feature_mode,
            rb_budget_ratio=export_metadata["rb_budget_ratio"],
            progress_label=candidate_label,
        )
        if args.restart_selection_mode == "margin_aware":
            score = (
                support_metrics["support_weak_margin_min"],
                support_metrics["support_weak_margin_mean"],
                support_metrics["support_proto_sep_margin"],
                support_metrics["support_pairwise_accuracy"],
                support_metrics["support_ari"],
                support_metrics["support_nmi"],
                support_metrics["support_utility"],
                -abs(support_metrics["support_utility_gap"]),
                -candidate_model.selection_validation_loss,
            )
        else:
            score = (
                support_metrics["support_pairwise_accuracy"],
                support_metrics["support_ari"],
                support_metrics["support_nmi"],
                support_metrics["support_utility"],
                -abs(support_metrics["support_utility_gap"]),
                -candidate_model.selection_validation_loss,
            )
        candidate_rows.append(
            {
                "candidate_seed": candidate_seed,
                "selected": 0,
                "restart_selection_mode": args.restart_selection_mode,
                **support_metrics,
                "selected_epoch": candidate_model.selected_epoch,
                "selection_validation_loss": candidate_model.selection_validation_loss,
            }
        )
        matrix.progress(
            f"[{label}] restart seed={candidate_seed} support_pairwise="
            f"{support_metrics['support_pairwise_accuracy']:.3f} support_ari="
            f"{support_metrics['support_ari']:.3f} support_nmi="
            f"{support_metrics['support_nmi']:.3f} support_gap="
            f"{support_metrics['support_utility_gap']:.6f}"
        )
        if best_score is None or score > best_score:
            best_score = score
            best_seed = candidate_seed
            model = candidate_model
            selected_support_metrics = support_metrics
    if model is None:
        raise ValueError("No restart candidate produced a trained model")
    for row in candidate_rows:
        if row["candidate_seed"] == best_seed:
            row["selected"] = 1
            break
    mvp.set_seed(best_seed)
    model.seed = best_seed
    matrix.progress(f"[{label}] selected restart seed={best_seed} score={best_score}")
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
                "restart_selection_mode": args.restart_selection_mode,
                "max_groups": args.max_groups,
                "rb_budget_ratio": export_metadata["rb_budget_ratio"],
                "focus_ue_ids": "|".join(focus_split["test_ue_ids"]),
                "train_window_end": args.train_window_end,
                "test_window_start": args.test_window_start,
                "test_window_end": args.test_window_end,
                "seed": args.seed,
                "selected_restart_seed": best_seed,
            }
        )
    diagnostic_rows = evaluate_trace_teacher_imitation(
        test,
        grouping_cache,
        max_groups=args.max_groups,
        switch_beta=args.switch_beta,
        metadata_rows=focus_test_metadata,
        feature_mode=args.feature_mode,
        scenario_mode="coupled_temporal_focus",
        load_level=f"coupled_trace_rb_{int(round(export_metadata['rb_budget_ratio'] * 100)):02d}_temporal_focus",
        rb_budget_ratio=export_metadata["rb_budget_ratio"],
        seed=best_seed,
        progress_label=label,
    )

    split_summary = {
        "bundle_dir": str(args.bundle_dir),
        "joint_supervision_mode": args.joint_supervision_mode,
        "feature_mode": args.feature_mode,
        "restart_selection_mode": args.restart_selection_mode,
        "max_groups": args.max_groups,
        "seed": args.seed,
        "restart_seeds": restart_seeds,
        "selected_restart_seed": best_seed,
        "min_users": args.min_users,
        "focus_ue_ids": focus_split["test_ue_ids"],
        "background_train_ue_ids": focus_split["train_ue_ids"],
        "background_train_scenarios": len(background_train),
        "background_train_limit": args.background_train_limit,
        "focus_train_scenarios": len(focus_train),
        "focus_test_scenarios": len(focus_test),
        "background_train_repeat": args.background_train_repeat,
        "focus_train_repeat": args.focus_train_repeat,
        "boundary_support_start": args.boundary_support_start,
        "boundary_support_repeat": args.boundary_support_repeat,
        "boundary_support_positive_only": args.boundary_support_positive_only,
        "boundary_support_selected_scenarios": len(boundary_support_indices),
        "effective_background_train_scenarios": len(background_train) * args.background_train_repeat,
        "effective_focus_train_scenarios": len(focus_train) * args.focus_train_repeat,
        "effective_boundary_support_scenarios": len(repeated_boundary_train),
        "effective_train_scenarios": len(train),
        "focus_train_positive_gain_count": _teacher_positive_gain_count(
            focus_train, args.switch_beta, args.max_groups
        ),
        "focus_test_positive_gain_count": _teacher_positive_gain_count(
            focus_test, args.switch_beta, args.max_groups
        ),
        "train_window_start": args.train_window_start,
        "train_window_end": args.train_window_end,
        "train_include_timestamps": args.train_include_timestamps,
        "test_window_start": args.test_window_start,
        "test_window_end": args.test_window_end,
        "test_include_timestamps": args.test_include_timestamps,
        "rb_budget_ratio": export_metadata["rb_budget_ratio"],
        "selected_epoch": model.selected_epoch,
        "selection_validation_loss": model.selection_validation_loss,
        "support_selection_pairwise_accuracy": selected_support_metrics["support_pairwise_accuracy"],
        "support_selection_ari": selected_support_metrics["support_ari"],
        "support_selection_nmi": selected_support_metrics["support_nmi"],
        "support_selection_utility": selected_support_metrics["support_utility"],
        "support_selection_teacher_utility": selected_support_metrics["support_teacher_utility"],
        "support_selection_utility_gap": selected_support_metrics["support_utility_gap"],
        "pair_sampling": model.pair_sampling,
        "supervision_weight_mode": getattr(model, "supervision_weight_mode", "uniform"),
        "hard_positive_scale": getattr(model, "hard_positive_scale", 1.0),
        "hard_negative_scale": getattr(model, "hard_negative_scale", 1.0),
        "scenario_weight_mode": getattr(model, "scenario_weight_mode", "uniform"),
        "positive_gain_boost": getattr(model, "positive_gain_boost", 1),
        "multigroup_boost": getattr(model, "multigroup_boost", 1),
        "prototype_weight": getattr(model, "prototype_weight", 0.0),
        "prototype_margin": getattr(model, "prototype_margin", 1.0),
        "membership_weight": getattr(model, "membership_weight", 0.0),
        "candidate_membership_weight": getattr(model, "candidate_membership_weight", 0.0),
        "candidate_top_k": getattr(model, "candidate_top_k", 0),
        "candidate_secondary_scale": getattr(model, "candidate_secondary_scale", 0.0),
        "frontier_contrast_weight": getattr(model, "frontier_contrast_weight", 0.0),
        "frontier_negative_top_k": getattr(model, "frontier_negative_top_k", 0),
        "frontier_margin": getattr(model, "frontier_margin", 0.0),
        "focus_only_warmup_epochs": getattr(model, "focus_only_warmup_epochs", 0),
        "grouping_mode": getattr(model, "grouping_mode", "kmeans_embedding"),
    }
    (args.out_dir / "split_summary.json").write_text(
        json.dumps(split_summary, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_csv(args.out_dir / "train_scenarios.csv", train_metadata)
    _write_csv(args.out_dir / "test_scenarios.csv", test_metadata)
    _write_csv(args.out_dir / "main_comparison.csv", method_rows)
    _write_csv(args.out_dir / "teacher_imitation_diagnostics.csv", diagnostic_rows)
    _write_csv(args.out_dir / "restart_candidates.csv", candidate_rows)
    _write_csv(
        args.out_dir / "teacher_group_evidence_audit.csv",
        _teacher_weak_group_audit(
            focus_train,
            [{**row, "split": "focus_train"} for row in focus_train_metadata],
            args.switch_beta,
            args.max_groups,
        )
        + _teacher_weak_group_audit(
            focus_test,
            [{**row, "split": "focus_test"} for row in focus_test_metadata],
            args.switch_beta,
            args.max_groups,
        ),
    )
    _write_csv(
        args.out_dir / "weak_group_prediction_audit.csv",
        _weak_group_prediction_audit(
            focus_train,
            [{**row, "split": "focus_train"} for row in focus_train_metadata],
            model,
            args.switch_beta,
            args.max_groups,
            split_name="focus_train",
            candidate_top_k=args.candidate_top_k,
            candidate_secondary_scale=args.candidate_secondary_scale,
        )
        + _weak_group_prediction_audit(
            focus_test,
            [{**row, "split": "focus_test"} for row in focus_test_metadata],
            model,
            args.switch_beta,
            args.max_groups,
            split_name="focus_test",
            candidate_top_k=args.candidate_top_k,
            candidate_secondary_scale=args.candidate_secondary_scale,
        ),
    )

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
