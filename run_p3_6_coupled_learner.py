"""First-round LE-GRA learner study on the P3.6 coupled trace bundle."""

from __future__ import annotations

import argparse
import csv
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp
import run_standard_matrix as matrix
from trace_io import HISTORY_COLUMNS


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _load_export_metadata(bundle_dir: Path) -> dict:
    metadata_path = bundle_dir.parent / "radio" / "export_metadata.json"
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def _scenario_from_rows(
    metadata: dict[str, str],
    user_rows: list[dict[str, str]],
    rb_rows: list[dict[str, str]],
    feature_mode: str,
) -> mvp.Scenario:
    user_rows = sorted(user_rows, key=lambda row: int(row["user_index"]))
    n_users = len(user_rows)
    total_rbs = int(metadata["total_rbs"])
    rates = np.full((n_users, total_rbs), np.nan, dtype=float)
    ue_index = {row["ue_id"]: idx for idx, row in enumerate(user_rows)}
    for row in rb_rows:
        rates[ue_index[row["ue_id"]], int(row["rb_index"])] = float(row["rate_kbps"])
    if np.isnan(rates).any():
        raise ValueError(f"Missing RB rates in scenario {metadata['scenario_id']}")
    scenario = mvp.Scenario(
        features=np.empty((n_users, 0), dtype=np.float32),
        cqi_history=np.asarray(
            [[float(row[name]) for name in HISTORY_COLUMNS] for row in user_rows],
            dtype=float,
        ),
        cqi_now=np.asarray([int(row["cqi_now"]) for row in user_rows], dtype=int),
        rb_rates=rates,
        rb_available=int(metadata["rb_available"]),
        previous_quality=np.asarray(
            [int(row["previous_quality"]) for row in user_rows],
            dtype=int,
        ),
        distance=np.asarray([float(row["distance_m"]) for row in user_rows], dtype=float),
        speed=np.asarray([float(row["speed_mps"]) for row in user_rows], dtype=float),
        direction_to_gnb=np.asarray(
            [float(row["direction_to_gnb"]) for row in user_rows],
            dtype=float,
        ),
        dispersion=metadata.get("dispersion", "") or "trace",
    )
    scenario.features = mvp.build_feature_matrix(scenario, feature_mode)
    return scenario


def _subset_scenarios(
    bundle_dir: Path,
    ue_ids: set[str],
    feature_mode: str,
    *,
    min_users: int,
) -> tuple[list[mvp.Scenario], list[dict]]:
    scenarios = _read_csv(bundle_dir / "scenarios.csv")
    users = _read_csv(bundle_dir / "users.csv")
    rb_rows = _read_csv(bundle_dir / "rb_rates.csv")
    users_by_scenario: dict[str, list[dict[str, str]]] = defaultdict(list)
    rb_by_scenario_user: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in users:
        if row["ue_id"] in ue_ids:
            users_by_scenario[row["scenario_id"]].append(row)
    for row in rb_rows:
        if row["ue_id"] in ue_ids:
            rb_by_scenario_user[(row["scenario_id"], row["ue_id"])].append(row)

    subset_scenarios: list[mvp.Scenario] = []
    subset_metadata: list[dict] = []
    for metadata in scenarios:
        scenario_id = metadata["scenario_id"]
        kept_users = sorted(users_by_scenario.get(scenario_id, []), key=lambda row: row["ue_id"])
        if len(kept_users) < min_users:
            continue
        remapped_users = []
        remapped_rbs = []
        for user_index, row in enumerate(kept_users):
            remapped = dict(row)
            remapped["user_index"] = str(user_index)
            remapped_users.append(remapped)
            for rb_row in sorted(
                rb_by_scenario_user[(scenario_id, row["ue_id"])],
                key=lambda item: int(item["rb_index"]),
            ):
                remapped_rb = dict(rb_row)
                remapped_rb["user_index"] = str(user_index)
                remapped_rbs.append(remapped_rb)
        subset_scenarios.append(
            _scenario_from_rows(metadata, remapped_users, remapped_rbs, feature_mode)
        )
        subset_metadata.append(
            {
                "scenario_id": scenario_id,
                "timestamp_s": metadata["timestamp_s"],
                "serving_gnb": metadata["serving_gnb"],
                "user_count": len(remapped_users),
                "ue_ids": "|".join(row["ue_id"] for row in remapped_users),
            }
        )
    return subset_scenarios, subset_metadata


def _count_multi_user_scenarios(metadata_rows: list[dict]) -> int:
    return sum(int(row["user_count"]) >= 2 for row in metadata_rows)


def choose_trajectory_split(
    bundle_dir: Path,
    *,
    test_ue_count: int,
    feature_mode: str,
    min_users: int,
) -> dict:
    users = _read_csv(bundle_dir / "users.csv")
    all_ue_ids = sorted({row["ue_id"] for row in users})
    if not 0 < test_ue_count < len(all_ue_ids):
        raise ValueError("test_ue_count must be between 1 and total_ues-1")

    best: dict | None = None
    for test_ids_tuple in itertools.combinations(all_ue_ids, test_ue_count):
        test_ids = set(test_ids_tuple)
        train_ids = [ue for ue in all_ue_ids if ue not in test_ids]
        train_scenarios, train_metadata = _subset_scenarios(
            bundle_dir, set(train_ids), feature_mode, min_users=min_users
        )
        test_scenarios, test_metadata = _subset_scenarios(
            bundle_dir, test_ids, feature_mode, min_users=min_users
        )
        if not train_scenarios or not test_scenarios:
            continue
        score = (
            _count_multi_user_scenarios(test_metadata),
            len(test_metadata),
            _count_multi_user_scenarios(train_metadata),
            len(train_metadata),
        )
        candidate = {
            "score": score,
            "train_ue_ids": train_ids,
            "test_ue_ids": sorted(test_ids),
            "train_scenarios": len(train_scenarios),
            "test_scenarios": len(test_scenarios),
            "train_multi_ue_scenarios": _count_multi_user_scenarios(train_metadata),
            "test_multi_ue_scenarios": _count_multi_user_scenarios(test_metadata),
        }
        if best is None or candidate["score"] > best["score"]:
            best = candidate
    if best is None:
        raise ValueError("No valid trajectory-aware split found")
    return best


def build_explicit_split(
    bundle_dir: Path,
    *,
    test_ue_ids: list[str],
    feature_mode: str,
    min_users: int,
) -> dict:
    users = _read_csv(bundle_dir / "users.csv")
    all_ue_ids = sorted({row["ue_id"] for row in users})
    test_set = set(test_ue_ids)
    if not test_set:
        raise ValueError("test_ue_ids must not be empty")
    missing = sorted(test_set.difference(all_ue_ids))
    if missing:
        raise ValueError(f"Unknown test UE IDs: {missing}")
    train_ids = [ue for ue in all_ue_ids if ue not in test_set]
    if not train_ids:
        raise ValueError("Explicit split leaves no train UEs")
    train_scenarios, train_metadata = _subset_scenarios(
        bundle_dir, set(train_ids), feature_mode, min_users=min_users
    )
    test_scenarios, test_metadata = _subset_scenarios(
        bundle_dir, test_set, feature_mode, min_users=min_users
    )
    if not train_scenarios or not test_scenarios:
        raise ValueError("Explicit split does not produce both train and test scenarios")
    return {
        "score": (
            _count_multi_user_scenarios(test_metadata),
            len(test_metadata),
            _count_multi_user_scenarios(train_metadata),
            len(train_metadata),
        ),
        "train_ue_ids": train_ids,
        "test_ue_ids": sorted(test_set),
        "train_scenarios": len(train_scenarios),
        "test_scenarios": len(test_scenarios),
        "train_multi_ue_scenarios": _count_multi_user_scenarios(train_metadata),
        "test_multi_ue_scenarios": _count_multi_user_scenarios(test_metadata),
    }


def train_trace_model(
    train: list[mvp.Scenario],
    test: list[mvp.Scenario],
    *,
    feature_mode: str,
    max_groups: int,
    switch_beta: float,
    epochs: int,
    pair_sampling: str,
    pairs_per_class: int,
    supervision_weight_mode: str,
    hard_positive_scale: float,
    hard_negative_scale: float,
    scenario_weight_mode: str,
    positive_gain_boost: int,
    multigroup_boost: int,
    prototype_weight: float,
    prototype_margin: float,
    membership_weight: float,
    candidate_membership_weight: float,
    candidate_top_k: int,
    candidate_secondary_scale: float,
    frontier_contrast_weight: float,
    frontier_negative_top_k: int,
    frontier_margin: float,
    focus_support_indices: list[int] | None,
    focus_only_warmup_epochs: int,
    grouping_mode: str,
    progress_label: str,
) -> mvp.MLPEncoder:
    started = matrix.time.perf_counter()
    prefix = f"[{progress_label}] "
    mvp.apply_feature_mode(train, test, feature_mode)
    mvp.normalize_features(train, test)
    matrix.progress(
        f"{prefix}Generating offline-teacher labels "
        f"(0/{len(train)}, feature={feature_mode}, Kmax={max_groups})"
    )
    teacher_groups = []
    teacher_labels = []
    teacher_pair_weights = []
    teacher_hard_group_targets = []
    teacher_candidate_targets = []
    teacher_candidate_target_weights = []
    teacher_frontier_positive_weights = []
    teacher_frontier_negative_weights = []
    scenario_repeat_factors = []
    for index, scenario in enumerate(train, start=1):
        groups = mvp.offline_teacher_groups(scenario, max_groups, switch_beta)
        teacher_groups.append(groups)
        teacher_labels.append(mvp.pairwise_labels(groups, len(scenario.cqi_now)))
        teacher_pair_weights.append(
            mvp.pairwise_supervision_weights(
                scenario,
                groups,
                mode=supervision_weight_mode,
                hard_positive_scale=hard_positive_scale,
                hard_negative_scale=hard_negative_scale,
            )
        )
        teacher_hard_group_targets.append(
            mvp.hardest_group_membership(scenario, groups)
        )
        candidate_target, candidate_target_weights = mvp.candidate_conditioned_membership_targets(
            scenario,
            groups,
            top_k=candidate_top_k,
            secondary_scale=candidate_secondary_scale,
        )
        teacher_candidate_targets.append(candidate_target)
        teacher_candidate_target_weights.append(candidate_target_weights)
        frontier_positive_weights, frontier_negative_weights = mvp.candidate_frontier_contrast_targets(
            scenario,
            groups,
            candidate_top_k=candidate_top_k,
            negative_top_k=frontier_negative_top_k,
            secondary_scale=candidate_secondary_scale,
            negative_scale=1.0,
        )
        teacher_frontier_positive_weights.append(frontier_positive_weights)
        teacher_frontier_negative_weights.append(frontier_negative_weights)
        teacher_result = mvp.allocate_and_evaluate(groups, scenario, switch_beta)
        single_result = mvp.allocate_and_evaluate(
            [list(range(len(scenario.cqi_now)))],
            scenario,
            switch_beta,
        )
        repeat_factor = 1
        if scenario_weight_mode == "positive_multigroup_focus":
            if len(groups) > 1:
                repeat_factor = max(repeat_factor, multigroup_boost)
            if teacher_result.utility - single_result.utility > 1e-9:
                repeat_factor = max(repeat_factor, positive_gain_boost)
        elif scenario_weight_mode != "uniform":
            raise ValueError(f"Unsupported scenario_weight_mode: {scenario_weight_mode}")
        scenario_repeat_factors.append(repeat_factor)
        matrix.progress(
            f"{prefix}Teacher labels {index}/{len(train)} "
            f"({matrix.time.perf_counter() - started:.1f}s elapsed)"
        )

    model = mvp.MLPEncoder(
        input_dim=train[0].features.shape[1],
        hidden_dim=48,
        embedding_dim=8,
        lr=0.01,
    )
    best_state = model.get_state()
    best_loss = float("inf")
    best_epoch = 0
    train_schedule = [
        idx
        for idx, repeat_factor in enumerate(scenario_repeat_factors)
        for _ in range(repeat_factor)
    ]
    focus_support_index_set = set(focus_support_indices or [])
    focus_train_schedule = [
        idx
        for idx in train_schedule
        if idx in focus_support_index_set
    ]
    matrix.progress(f"{prefix}Training model (0/{epochs} epochs)")
    for epoch in range(1, epochs + 1):
        if focus_only_warmup_epochs > 0 and epoch <= focus_only_warmup_epochs:
            order = list(focus_train_schedule)
        else:
            order = list(train_schedule)
        matrix.random.shuffle(order)
        losses = []
        epoch_pair_stats = []
        for idx in order:
            losses.append(model.train_step(
                train[idx].features,
                teacher_labels[idx],
                pair_weights=teacher_pair_weights[idx],
                hard_group_target=teacher_hard_group_targets[idx],
                candidate_target=teacher_candidate_targets[idx],
                candidate_target_weights=teacher_candidate_target_weights[idx],
                frontier_positive_weights=teacher_frontier_positive_weights[idx],
                frontier_negative_weights=teacher_frontier_negative_weights[idx],
                pair_sampling=pair_sampling,
                max_pairs_per_class=pairs_per_class,
                prototype_margin=prototype_margin,
                prototype_weight=prototype_weight,
                membership_weight=membership_weight,
                candidate_membership_weight=candidate_membership_weight,
                frontier_contrast_weight=frontier_contrast_weight,
                frontier_margin=frontier_margin,
            ))
            epoch_pair_stats.append(model.last_pair_stats.copy())
        loss = float(np.mean(losses)) if losses else 0.0
        if loss < best_loss:
            best_loss = loss
            best_epoch = epoch
            best_state = model.get_state()
        if epoch_pair_stats:
            pair_stats = {
                key: float(np.nanmean([stats[key] for stats in epoch_pair_stats]))
                for key in epoch_pair_stats[0]
            }
            pair_stats["schedule_examples"] = float(len(order))
            pair_stats["boosted_scenarios"] = float(
                sum(1 for factor in scenario_repeat_factors if factor > 1)
            )
            pair_stats["warmup_epoch"] = float(
                focus_only_warmup_epochs > 0 and epoch <= focus_only_warmup_epochs
            )
            model.training_pair_stats = pair_stats
            stats_msg = (
                f"pairs=+{pair_stats['positive_pairs']:.1f}/-{pair_stats['negative_pairs']:.1f}, "
                f"priority_neg={pair_stats['priority_negative_pairs']:.2f}, "
                f"active_neg={pair_stats['active_negative_ratio']:.3f}, "
                f"neg_dist={pair_stats['mean_selected_negative_distance']:.3f}"
            )
        else:
            stats_msg = "pairs=empty"
        if focus_only_warmup_epochs > 0 and epoch <= focus_only_warmup_epochs:
            stats_msg += f", warmup_focus_only=1"
        matrix.progress(
            f"{prefix}Epoch {epoch}/{epochs}, train_loss={loss:.4f}, "
            f"best_epoch={best_epoch} {stats_msg} "
            f"({matrix.time.perf_counter() - started:.1f}s elapsed)"
        )
    model.set_state(best_state)
    model.selected_epoch = best_epoch
    model.selection_validation_loss = best_loss
    model.pair_sampling = pair_sampling
    model.supervision_weight_mode = supervision_weight_mode
    model.hard_positive_scale = hard_positive_scale
    model.hard_negative_scale = hard_negative_scale
    model.scenario_weight_mode = scenario_weight_mode
    model.positive_gain_boost = positive_gain_boost
    model.multigroup_boost = multigroup_boost
    model.prototype_weight = prototype_weight
    model.prototype_margin = prototype_margin
    model.membership_weight = membership_weight
    model.candidate_membership_weight = candidate_membership_weight
    model.candidate_top_k = candidate_top_k
    model.candidate_secondary_scale = candidate_secondary_scale
    model.frontier_contrast_weight = frontier_contrast_weight
    model.frontier_negative_top_k = frontier_negative_top_k
    model.frontier_margin = frontier_margin
    model.focus_only_warmup_epochs = focus_only_warmup_epochs
    model.grouping_mode = grouping_mode
    matrix.progress(
        f"{prefix}Restored best epoch {best_epoch} "
        f"(training_loss={best_loss:.4f})"
    )
    return model


def _scenario_kmax(scenario: mvp.Scenario, configured_kmax: int) -> int:
    return max(1, min(configured_kmax, len(scenario.cqi_now)))


def trace_methods(
    model: mvp.MLPEncoder,
    *,
    max_groups: int,
    switch_beta: float,
    kmeans_n_init: int,
) -> dict[str, callable]:
    return {
        "No grouping": lambda s: mvp.no_grouping(s),
        "CQI k-means": lambda s: mvp.cqi_kmeans_grouping(
            s, _scenario_kmax(s, max_groups), switch_beta, kmeans_n_init
        ),
        "Resource-cost k-means": lambda s: mvp.resource_cost_kmeans_grouping(
            s, _scenario_kmax(s, max_groups), switch_beta, kmeans_n_init
        ),
        "Multi-feature k-means": lambda s: mvp.multi_feature_kmeans_grouping(
            s, _scenario_kmax(s, max_groups), switch_beta, "full", kmeans_n_init
        ),
        "Offline teacher": lambda s: mvp.offline_teacher_groups(
            s, _scenario_kmax(s, max_groups), switch_beta
        ),
        "LE-GRA MVP": lambda s: mvp.learned_grouping(
            s, model, _scenario_kmax(s, max_groups), switch_beta, kmeans_n_init
        ),
    }


def evaluate_trace_methods(
    test: list[mvp.Scenario],
    model: mvp.MLPEncoder,
    *,
    max_groups: int,
    switch_beta: float,
    kmeans_n_init: int,
    progress_label: str,
) -> tuple[list[dict], dict[str, list[list[list[int]]]]]:
    methods = trace_methods(
        model,
        max_groups=max_groups,
        switch_beta=switch_beta,
        kmeans_n_init=kmeans_n_init,
    )
    rows = []
    grouping_cache: dict[str, list[list[list[int]]]] = {}
    method_names = [
        "No grouping",
        "CQI k-means",
        "Resource-cost k-means",
        "Multi-feature k-means",
        "Offline teacher",
        "LE-GRA MVP",
    ]
    for method_index, method_name in enumerate(method_names, start=1):
        matrix.progress(
            f"[{progress_label}] Evaluating {method_name} "
            f"({method_index}/{len(method_names)})"
        )
        method_groupings = [methods[method_name](scenario) for scenario in test]
        grouping_cache[method_name] = method_groupings
        result = mvp.aggregate_eval_results([
            mvp.allocate_and_evaluate(groups, scenario, switch_beta)
            for scenario, groups in zip(test, method_groupings)
        ])
        rows.append({
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
            "selected_epoch": model.selected_epoch,
            "selection_validation_loss": model.selection_validation_loss,
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
            "grouping_mode": getattr(model, "grouping_mode", "kmeans_embedding"),
            "train_positive_pairs": model.training_pair_stats.get("positive_pairs", float("nan")),
            "train_negative_pairs": model.training_pair_stats.get("negative_pairs", float("nan")),
            "train_active_negative_ratio": model.training_pair_stats.get("active_negative_ratio", float("nan")),
            "train_mean_negative_distance": model.training_pair_stats.get("mean_selected_negative_distance", float("nan")),
            "train_mean_positive_weight": model.training_pair_stats.get("mean_positive_weight", float("nan")),
            "train_mean_negative_weight": model.training_pair_stats.get("mean_negative_weight", float("nan")),
            "train_hard_group_positive_pairs": model.training_pair_stats.get("hard_group_positive_pairs", float("nan")),
            "train_hard_group_negative_pairs": model.training_pair_stats.get("hard_group_negative_pairs", float("nan")),
            "train_priority_positive_pairs": model.training_pair_stats.get("priority_positive_pairs", float("nan")),
            "train_priority_negative_pairs": model.training_pair_stats.get("priority_negative_pairs", float("nan")),
            "train_schedule_examples": model.training_pair_stats.get("schedule_examples", float("nan")),
            "train_boosted_scenarios": model.training_pair_stats.get("boosted_scenarios", float("nan")),
            "train_prototype_positive_terms": model.training_pair_stats.get("prototype_positive_terms", float("nan")),
            "train_prototype_negative_terms": model.training_pair_stats.get("prototype_negative_terms", float("nan")),
            "train_membership_terms": model.training_pair_stats.get("membership_terms", float("nan")),
            "train_candidate_membership_terms": model.training_pair_stats.get("candidate_membership_terms", float("nan")),
            "train_candidate_membership_weight": model.training_pair_stats.get("candidate_membership_weight", float("nan")),
            "train_candidate_secondary_weight_mean": model.training_pair_stats.get("candidate_secondary_weight_mean", float("nan")),
            "train_frontier_contrast_terms": model.training_pair_stats.get("frontier_contrast_terms", float("nan")),
            "train_frontier_contrast_weight": model.training_pair_stats.get("frontier_contrast_weight", float("nan")),
            "train_frontier_margin": model.training_pair_stats.get("frontier_margin", float("nan")),
            "train_frontier_positive_count": model.training_pair_stats.get("frontier_positive_count", float("nan")),
            "train_frontier_negative_count": model.training_pair_stats.get("frontier_negative_count", float("nan")),
            "train_mean_weak_score": model.training_pair_stats.get("mean_weak_score", float("nan")),
        })
    return rows, grouping_cache


def evaluate_trace_teacher_imitation(
    test: list[mvp.Scenario],
    grouping_cache: dict[str, list[list[list[int]]]],
    *,
    max_groups: int,
    switch_beta: float,
    metadata_rows: list[dict] | None = None,
    feature_mode: str,
    scenario_mode: str,
    load_level: str,
    rb_budget_ratio: float,
    seed: int,
    progress_label: str,
) -> list[dict]:
    """Compare trace predictions against teacher partitions without synthetic load keys."""

    def _group_signature(
        groups: list[list[int]],
        scenario: mvp.Scenario,
        metadata: dict | None,
    ) -> str:
        if metadata is not None and metadata.get("ue_ids"):
            labels = metadata["ue_ids"].split("|")
        else:
            labels = [str(idx) for idx in range(len(scenario.cqi_now))]
        parts = []
        for group in groups:
            ue_ids = sorted(labels[idx] for idx in group)
            parts.append("|".join(ue_ids))
        return " / ".join(parts)

    rows = []
    for scenario_idx, scenario in enumerate(test):
        metadata = metadata_rows[scenario_idx] if metadata_rows is not None else None
        matrix.progress(
            f"[{progress_label}] Teacher-imitation diagnostics "
            f"{scenario_idx + 1}/{len(test)}"
        )
        teacher_groups = grouping_cache["Offline teacher"][scenario_idx]
        teacher_eval = mvp.allocate_and_evaluate(teacher_groups, scenario, switch_beta)
        for method_name in ["Multi-feature k-means", "LE-GRA MVP"]:
            predicted_groups = grouping_cache[method_name][scenario_idx]
            predicted_eval = mvp.allocate_and_evaluate(predicted_groups, scenario, switch_beta)
            row = {
                "scenario_mode": scenario_mode,
                "load_level": load_level,
                "rb_budget_ratio": rb_budget_ratio,
                "seed": seed,
                "test_index": scenario_idx,
                "kmax": min(max_groups, len(scenario.cqi_now)),
                "feature_mode": feature_mode,
                "method": method_name,
                "pairwise_accuracy": mvp.pairwise_same_group_accuracy(
                    mvp.group_ids_from_groups(teacher_groups, len(scenario.cqi_now)),
                    mvp.group_ids_from_groups(predicted_groups, len(scenario.cqi_now)),
                ),
                "ari": mvp.adjusted_rand_index(
                    mvp.group_ids_from_groups(teacher_groups, len(scenario.cqi_now)),
                    mvp.group_ids_from_groups(predicted_groups, len(scenario.cqi_now)),
                ),
                "nmi": mvp.normalized_mutual_information(
                    mvp.group_ids_from_groups(teacher_groups, len(scenario.cqi_now)),
                    mvp.group_ids_from_groups(predicted_groups, len(scenario.cqi_now)),
                ),
                "teacher_groups": len(teacher_groups),
                "predicted_groups": len(predicted_groups),
                "teacher_group_signature": _group_signature(teacher_groups, scenario, metadata),
                "predicted_group_signature": _group_signature(predicted_groups, scenario, metadata),
                "teacher_group_json": json.dumps(teacher_groups),
                "predicted_group_json": json.dumps(predicted_groups),
                "teacher_utility": teacher_eval.utility,
                "predicted_utility": predicted_eval.utility,
                "utility_gap_vs_teacher": predicted_eval.utility - teacher_eval.utility,
            }
            rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", type=Path, default=Path("p3_6_coupled_bundle/bundle"))
    parser.add_argument("--out-dir", type=Path, default=Path("p3_6_coupled_learner"))
    parser.add_argument("--feature-mode", default="history_cost_quality")
    parser.add_argument("--max-groups", type=int, default=3)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--validation-fraction", type=float, default=0.0)
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
    parser.add_argument("--grouping-mode", default="kmeans_embedding")
    parser.add_argument("--kmeans-n-init", type=int, default=10)
    parser.add_argument("--test-ue-count", type=int, default=3)
    parser.add_argument("--test-ue-ids", nargs="*", default=None)
    parser.add_argument("--min-users", type=int, default=2)
    parser.add_argument("--seed", type=int, default=9)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    export_metadata = _load_export_metadata(args.bundle_dir)
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
    train, train_metadata = _subset_scenarios(
        args.bundle_dir,
        set(split["train_ue_ids"]),
        args.feature_mode,
        min_users=args.min_users,
    )
    test, test_metadata = _subset_scenarios(
        args.bundle_dir,
        set(split["test_ue_ids"]),
        args.feature_mode,
        min_users=args.min_users,
    )

    mvp.set_seed(args.seed)
    label = "P3.6 coupled learner"
    matrix.progress(
        f"[{label}] train_ues={split['train_ue_ids']} "
        f"test_ues={split['test_ue_ids']} train_scenarios={len(train)} "
        f"test_scenarios={len(test)}"
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
        focus_support_indices=None,
        focus_only_warmup_epochs=0,
        grouping_mode=args.grouping_mode,
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
                "dataset": "p3_6_coupled_trace",
                "feature_mode": args.feature_mode,
                "max_groups": args.max_groups,
                "rb_budget_ratio": export_metadata["rb_budget_ratio"],
                "test_ue_ids": "|".join(split["test_ue_ids"]),
                "train_ue_ids": "|".join(split["train_ue_ids"]),
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
        scenario_mode="coupled_trace",
        load_level="coupled_trace_rb_0.50",
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
        "train_ue_ids": split["train_ue_ids"],
        "test_ue_ids": split["test_ue_ids"],
        "train_scenarios": len(train),
        "test_scenarios": len(test),
        "train_multi_ue_scenarios": split["train_multi_ue_scenarios"],
        "test_multi_ue_scenarios": split["test_multi_ue_scenarios"],
        "rb_budget_ratio": export_metadata["rb_budget_ratio"],
        "selected_epoch": model.selected_epoch,
        "selection_validation_loss": model.selection_validation_loss,
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

    print("P3.6 coupled learner summary:")
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
