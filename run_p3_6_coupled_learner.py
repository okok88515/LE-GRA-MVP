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
    for index, scenario in enumerate(train, start=1):
        groups = mvp.offline_teacher_groups(scenario, max_groups, switch_beta)
        teacher_groups.append(groups)
        teacher_labels.append(mvp.pairwise_labels(groups, len(scenario.cqi_now)))
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
    matrix.progress(f"{prefix}Training model (0/{epochs} epochs)")
    for epoch in range(1, epochs + 1):
        order = list(range(len(train)))
        matrix.random.shuffle(order)
        losses = []
        epoch_pair_stats = []
        for idx in order:
            losses.append(model.train_step(
                train[idx].features,
                teacher_labels[idx],
                pair_sampling=pair_sampling,
                max_pairs_per_class=pairs_per_class,
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
            model.training_pair_stats = pair_stats
            stats_msg = (
                f"pairs=+{pair_stats['positive_pairs']:.1f}/-{pair_stats['negative_pairs']:.1f}, "
                f"active_neg={pair_stats['active_negative_ratio']:.3f}, "
                f"neg_dist={pair_stats['mean_selected_negative_distance']:.3f}"
            )
        else:
            stats_msg = "pairs=empty"
        matrix.progress(
            f"{prefix}Epoch {epoch}/{epochs}, train_loss={loss:.4f}, "
            f"best_epoch={best_epoch} {stats_msg} "
            f"({matrix.time.perf_counter() - started:.1f}s elapsed)"
        )
    model.set_state(best_state)
    model.selected_epoch = best_epoch
    model.selection_validation_loss = best_loss
    model.pair_sampling = pair_sampling
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
            "train_positive_pairs": model.training_pair_stats.get("positive_pairs", float("nan")),
            "train_negative_pairs": model.training_pair_stats.get("negative_pairs", float("nan")),
            "train_active_negative_ratio": model.training_pair_stats.get("active_negative_ratio", float("nan")),
            "train_mean_negative_distance": model.training_pair_stats.get("mean_selected_negative_distance", float("nan")),
        })
    return rows, grouping_cache


def evaluate_trace_teacher_imitation(
    test: list[mvp.Scenario],
    grouping_cache: dict[str, list[list[list[int]]]],
    *,
    max_groups: int,
    feature_mode: str,
    scenario_mode: str,
    load_level: str,
    rb_budget_ratio: float,
    seed: int,
    progress_label: str,
) -> list[dict]:
    """Compare trace predictions against teacher partitions without synthetic load keys."""

    rows = []
    for scenario_idx, scenario in enumerate(test):
        matrix.progress(
            f"[{progress_label}] Teacher-imitation diagnostics "
            f"{scenario_idx + 1}/{len(test)}"
        )
        teacher_groups = grouping_cache["Offline teacher"][scenario_idx]
        for method_name in ["Multi-feature k-means", "LE-GRA MVP"]:
            predicted_groups = grouping_cache[method_name][scenario_idx]
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
