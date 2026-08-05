"""Run the standard LE-GRA experiment matrix and feature ablations.

This script operationalizes the current research plan:

1. Fix the main comparison group.
2. Sweep the standard scenario/Kmax matrix.
3. Run the minimal feature ablation for LE-GRA.
"""

from __future__ import annotations

import argparse
import csv
import random
import time
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp


MAIN_METHODS = [
    "No grouping",
    "CQI k-means",
    "Resource-cost k-means",
    "Multi-feature k-means",
    "Offline teacher",
    "LE-GRA MVP",
]

FEATURE_MODE_LABELS = {
    "history_only": "CQI/history only",
    "history_cost": "+ resource-cost",
    "history_cost_quality": "+ resource-cost + previous quality",
    "history_cost_load": "+ resource-cost + load context",
    "history_cost_context": "+ resource-cost + decision context",
    "full": "full feature",
    "full_context": "full feature + decision context",
}

LOAD_RATIOS = {
    "light": 0.50,
    "medium": 0.25,
    "heavy": 0.10,
}


def progress(message: str) -> None:
    """Print progress immediately, even when stdout is buffered."""

    print(message, flush=True)


def generate_splits(
    args, scenario_mode: str, seed: int, load_level: str
) -> tuple[list[mvp.Scenario], list[mvp.Scenario]]:
    mvp.set_seed(seed)
    dispersions = ["high", "mid", "low"]
    rb_budget_ratio = LOAD_RATIOS[load_level]
    train = [
        mvp.generate_scenario(
            args.users, args.rbs, random.choice(dispersions), scenario_mode,
            rb_budget_ratio=rb_budget_ratio,
        )
        for _ in range(args.train_scenarios)
    ]
    test = [
        mvp.generate_scenario(
            args.users, args.rbs, random.choice(dispersions), scenario_mode,
            rb_budget_ratio=rb_budget_ratio,
        )
        for _ in range(args.test_scenarios)
    ]
    return train, test


def train_model(
    train: list[mvp.Scenario],
    test: list[mvp.Scenario],
    feature_mode: str,
    max_groups: int,
    switch_beta: float,
    epochs: int,
    validation_fraction: float,
    pair_sampling: str,
    pairs_per_class: int,
    progress_label: str = "",
) -> mvp.MLPEncoder:
    started = time.perf_counter()
    prefix = f"[{progress_label}] " if progress_label else ""
    if not 0.0 <= validation_fraction < 1.0:
        raise ValueError("validation_fraction must be in the interval [0, 1)")

    validation_count = 0
    if validation_fraction > 0.0 and len(train) >= 3:
        validation_count = max(1, int(round(len(train) * validation_fraction)))
        validation_count = min(validation_count, len(train) - 1)
    fit = train[:-validation_count] if validation_count else train
    validation = train[-validation_count:] if validation_count else []

    mvp.apply_feature_mode(fit, validation + test, feature_mode)
    mvp.normalize_features(fit, validation + test)
    progress(
        f"{prefix}Generating offline-teacher labels "
        f"(0/{len(train)}, fit={len(fit)}, validation={len(validation)}, "
        f"feature={feature_mode}, Kmax={max_groups})"
    )
    teacher_groups = []
    for index, scenario in enumerate(train, start=1):
        teacher_groups.append(mvp.offline_teacher_groups(scenario, max_groups, switch_beta))
        progress(
            f"{prefix}Teacher labels {index}/{len(train)} "
            f"({time.perf_counter() - started:.1f}s elapsed)"
        )
    teacher_labels = [mvp.pairwise_labels(g, len(train[0].cqi_now)) for g in teacher_groups]

    model = mvp.MLPEncoder(
        input_dim=train[0].features.shape[1],
        hidden_dim=48,
        embedding_dim=8,
        lr=0.01,
    )
    initial_state = model.get_state()
    fit_labels = teacher_labels[:len(fit)]
    validation_labels = teacher_labels[len(fit):]
    best_state = model.get_state()
    best_validation_loss = float("inf")
    best_epoch = 0
    progress(f"{prefix}Training model (0/{epochs} epochs)")
    for epoch in range(1, epochs + 1):
        order = list(range(len(fit)))
        random.shuffle(order)
        losses = []
        epoch_pair_stats = []
        for idx in order:
            losses.append(model.train_step(
                fit[idx].features,
                fit_labels[idx],
                pair_sampling=pair_sampling,
                max_pairs_per_class=pairs_per_class,
            ))
            epoch_pair_stats.append(model.last_pair_stats.copy())
        validation_loss = (
            float(np.mean([
                model.contrastive_loss(scenario.features, labels)
                for scenario, labels in zip(validation, validation_labels)
            ]))
            if validation else float(np.mean(losses))
        )
        if validation_loss < best_validation_loss:
            best_validation_loss = validation_loss
            best_epoch = epoch
            best_state = model.get_state()
        pair_stats = {
            key: float(np.nanmean([stats[key] for stats in epoch_pair_stats]))
            for key in epoch_pair_stats[0]
        }
        model.training_pair_stats = pair_stats
        progress(
            f"{prefix}Epoch {epoch}/{epochs}, train_loss={np.mean(losses):.4f}, "
            f"validation_loss={validation_loss:.4f}, best_epoch={best_epoch} "
            f"pairs=+{pair_stats['positive_pairs']:.1f}/-{pair_stats['negative_pairs']:.1f}, "
            f"active_neg={pair_stats['active_negative_ratio']:.3f}, "
            f"neg_dist={pair_stats['mean_selected_negative_distance']:.3f} "
            f"({time.perf_counter() - started:.1f}s elapsed)"
        )
    if validation:
        # Standard select-then-refit workflow: validation chooses the epoch,
        # then the model is reset and trained on every training scenario for
        # that many epochs. This avoids permanently discarding validation data.
        mvp.apply_feature_mode(train, test, feature_mode)
        mvp.normalize_features(train, test)
        model.set_state(initial_state)
        progress(
            f"{prefix}Refitting on all {len(train)} training scenarios for "
            f"{best_epoch} selected epochs"
        )
        for refit_epoch in range(1, best_epoch + 1):
            order = list(range(len(train)))
            random.shuffle(order)
            refit_losses = [
                model.train_step(
                    train[idx].features,
                    teacher_labels[idx],
                    pair_sampling=pair_sampling,
                    max_pairs_per_class=pairs_per_class,
                )
                for idx in order
            ]
            progress(
                f"{prefix}Refit epoch {refit_epoch}/{best_epoch}, "
                f"loss={np.mean(refit_losses):.4f}"
            )
    else:
        model.set_state(best_state)
        progress(
            f"{prefix}Restored best epoch {best_epoch} "
            f"(training_loss={best_validation_loss:.4f})"
        )
    model.selected_epoch = best_epoch
    model.selection_validation_loss = best_validation_loss
    model.pair_sampling = pair_sampling
    return model


def diagnostic_row(
    scenario: mvp.Scenario,
    teacher_groups: list[list[int]],
    predicted_groups: list[list[int]],
    method: str,
    scenario_mode: str,
    load_level: str,
    seed: int,
    test_index: int,
    kmax: int,
    feature_mode: str,
) -> dict:
    """Summarize how closely a predicted grouping matches the teacher."""

    n_users = len(scenario.cqi_now)
    teacher_ids = mvp.group_ids_from_groups(teacher_groups, n_users)
    predicted_ids = mvp.group_ids_from_groups(predicted_groups, n_users)
    return {
        "scenario_mode": scenario_mode,
        "load_level": load_level,
        "rb_budget_ratio": LOAD_RATIOS[load_level],
        "seed": seed,
        "test_index": test_index,
        "kmax": kmax,
        "feature_mode": feature_mode,
        "method": method,
        "pairwise_accuracy": mvp.pairwise_same_group_accuracy(teacher_ids, predicted_ids),
        "ari": mvp.adjusted_rand_index(teacher_ids, predicted_ids),
        "nmi": mvp.normalized_mutual_information(teacher_ids, predicted_ids),
        "teacher_groups": len(teacher_groups),
        "predicted_groups": len(predicted_groups),
    }


def evaluate_main_methods(
    test: list[mvp.Scenario],
    model: mvp.MLPEncoder,
    max_groups: int,
    switch_beta: float,
    kmeans_n_init: int,
    progress_label: str,
) -> tuple[list[dict], dict[str, list[list[list[int]]]]]:
    methods = mvp.default_methods(
        max_groups,
        switch_beta,
        model,
        include_multifeature_baseline=True,
        multifeature_feature_mode="full",
        kmeans_n_init=kmeans_n_init,
    )
    rows = []
    grouping_cache: dict[str, list[list[list[int]]]] = {}
    for method_index, method_name in enumerate(MAIN_METHODS, start=1):
        progress(
            f"[{progress_label}] Evaluating {method_name} "
            f"({method_index}/{len(MAIN_METHODS)})"
        )
        method_groupings = [methods[method_name](scenario) for scenario in test]
        grouping_cache[method_name] = method_groupings
        result = mvp.aggregate_eval_results([
            mvp.allocate_and_evaluate(groups, scenario, switch_beta)
            for scenario, groups in zip(test, method_groupings)
        ])
        rows.append(
            {
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
            }
        )
    return rows, grouping_cache


def evaluate_teacher_imitation(
    test: list[mvp.Scenario],
    grouping_cache: dict[str, list[list[list[int]]]],
    max_groups: int,
    switch_beta: float,
    feature_mode: str,
    scenario_mode: str,
    load_level: str,
    seed: int,
    progress_label: str,
) -> list[dict]:
    """Compare cached student/baseline groupings against cached teacher partitions."""

    rows = []
    for scenario_idx, scenario in enumerate(test):
        progress(
            f"[{progress_label}] Teacher-imitation diagnostics "
            f"{scenario_idx + 1}/{len(test)}"
        )
        teacher_groups = grouping_cache["Offline teacher"][scenario_idx]
        for method_name in ["Multi-feature k-means", "LE-GRA MVP"]:
            predicted_groups = grouping_cache[method_name][scenario_idx]
            rows.append(
                diagnostic_row(
                    scenario,
                    teacher_groups,
                    predicted_groups,
                    method=method_name,
                    scenario_mode=scenario_mode,
                    load_level=load_level,
                    seed=seed,
                    test_index=scenario_idx,
                    kmax=max_groups,
                    feature_mode=feature_mode,
                )
            )
    return rows


def run_main_matrix(args) -> tuple[list[dict], list[dict]]:
    rows = []
    diagnostic_rows = []
    total_jobs = (
        len(args.scenario_modes) * len(args.load_levels)
        * len(args.kmax_values) * len(args.seeds)
    )
    job = 0
    for scenario_mode in args.scenario_modes:
        for load_level in args.load_levels:
            for max_groups in args.kmax_values:
                for seed in args.seeds:
                    job += 1
                    label = (
                        f"Main {job}/{total_jobs}: scenario={scenario_mode}, "
                        f"load={load_level}, Kmax={max_groups}, seed={seed}"
                    )
                    progress(f"\n[{label}] Starting")
                    train, test = generate_splits(args, scenario_mode, seed, load_level)
                    model = train_model(
                        train,
                        test,
                        feature_mode=args.main_feature_mode,
                        max_groups=max_groups,
                        switch_beta=args.switch_beta,
                        epochs=args.epochs,
                        validation_fraction=args.validation_fraction,
                        pair_sampling=args.pair_sampling,
                        pairs_per_class=args.pairs_per_class,
                        progress_label=label,
                    )
                    method_rows, grouping_cache = evaluate_main_methods(
                        test,
                        model,
                        max_groups=max_groups,
                        switch_beta=args.switch_beta,
                        kmeans_n_init=args.kmeans_n_init,
                        progress_label=label,
                    )
                    for row in method_rows:
                        row.update(
                            {
                                "scenario_mode": scenario_mode,
                                "load_level": load_level,
                                "rb_budget_ratio": LOAD_RATIOS[load_level],
                                "kmax": max_groups,
                                "seed": seed,
                            }
                        )
                        rows.append(row)
                    diagnostic_rows.extend(
                        evaluate_teacher_imitation(
                            test,
                            grouping_cache,
                            max_groups=max_groups,
                            switch_beta=args.switch_beta,
                            feature_mode=args.main_feature_mode,
                            scenario_mode=scenario_mode,
                            load_level=load_level,
                            seed=seed,
                            progress_label=label,
                        )
                    )
    return rows, diagnostic_rows


def run_ablation(args) -> list[dict]:
    rows = []
    total_jobs = (
        len(args.scenario_modes) * len(args.load_levels)
        * len(args.seeds) * len(args.feature_modes)
    )
    job = 0
    for scenario_mode in args.scenario_modes:
        for load_level in args.load_levels:
          for seed in args.seeds:
            for feature_mode in args.feature_modes:
                job += 1
                label = (
                    f"Ablation {job}/{total_jobs}: scenario={scenario_mode}, "
                    f"load={load_level}, feature={feature_mode}, seed={seed}"
                )
                progress(f"\n[{label}] Starting")
                train, test = generate_splits(args, scenario_mode, seed, load_level)
                model = train_model(
                    train,
                    test,
                    feature_mode=feature_mode,
                    max_groups=args.ablation_kmax,
                    switch_beta=args.switch_beta,
                    epochs=args.epochs,
                    validation_fraction=args.validation_fraction,
                    pair_sampling=args.pair_sampling,
                    pairs_per_class=args.pairs_per_class,
                    progress_label=label,
                )
                progress(f"[{label}] Evaluating LE-GRA MVP")
                result = mvp.evaluate_method(
                    test,
                    lambda s, model=model: mvp.learned_grouping(
                        s, model, args.ablation_kmax, args.switch_beta,
                        args.kmeans_n_init,
                    ),
                    args.switch_beta,
                )
                rows.append(
                    {
                        "scenario_mode": scenario_mode,
                        "load_level": load_level,
                        "rb_budget_ratio": LOAD_RATIOS[load_level],
                        "seed": seed,
                        "feature_mode": feature_mode,
                        "feature_label": FEATURE_MODE_LABELS[feature_mode],
                        "method": "LE-GRA MVP",
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
                        "kmax": args.ablation_kmax,
                        "selected_epoch": model.selected_epoch,
                        "selection_validation_loss": model.selection_validation_loss,
                    }
                )
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-scenarios", type=int, default=120)
    parser.add_argument("--test-scenarios", type=int, default=40)
    parser.add_argument("--users", type=int, default=24)
    parser.add_argument("--rbs", type=int, default=100)
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument(
        "--validation-fraction",
        type=float,
        default=0.0,
        help=(
            "Experimental fraction held out for best-epoch selection. "
            "Default 0 keeps the established full-training baseline."
        ),
    )
    parser.add_argument(
        "--pair-sampling",
        choices=["random_balanced", "hard_negative"],
        default="random_balanced",
        help="Negative-pair selection strategy for contrastive training.",
    )
    parser.add_argument(
        "--pairs-per-class",
        type=int,
        default=160,
        help="Maximum positive and negative pairs used per scenario update.",
    )
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument(
        "--kmeans-n-init",
        type=int,
        default=10,
        help="Deterministic k-means initializations per candidate k.",
    )
    parser.add_argument("--scenario-modes", nargs="+", default=["aligned", "ambiguous", "mixed"])
    parser.add_argument(
        "--load-levels",
        nargs="+",
        choices=list(LOAD_RATIOS),
        default=["light", "medium", "heavy"],
        help="Resource-pressure levels: light=0.50, medium=0.25, heavy=0.10.",
    )
    parser.add_argument("--kmax-values", nargs="+", type=int, default=[3, 4, 5, 6])
    parser.add_argument("--seeds", nargs="+", type=int, default=[9, 17, 23])
    parser.add_argument(
        "--feature-modes",
        nargs="+",
        default=["history_only", "history_cost", "full"],
    )
    parser.add_argument(
        "--main-feature-mode",
        choices=["history_only", "history_cost", "history_cost_quality", "history_cost_load", "history_cost_context", "full", "full_context"],
        default="history_cost",
        help="Feature mode used by LE-GRA in the main comparison matrix.",
    )
    parser.add_argument(
        "--skip-ablation",
        action="store_true",
        help="Skip feature ablation when running a focused learner study.",
    )
    parser.add_argument("--ablation-kmax", type=int, default=5)
    parser.add_argument("--out-dir", type=Path, default=Path("standard_matrix_results"))
    args = parser.parse_args()

    if args.pairs_per_class <= 0:
        parser.error("--pairs-per-class must be positive")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    progress("Starting LE-GRA standard experiment matrix")
    ablation_jobs = (
        0 if args.skip_ablation else
        len(args.scenario_modes) * len(args.load_levels)
        * len(args.seeds) * len(args.feature_modes)
    )
    progress(
        f"Main jobs: {len(args.scenario_modes) * len(args.load_levels) * len(args.kmax_values) * len(args.seeds)}; "
        f"ablation jobs: {ablation_jobs}"
    )

    matrix_rows, diagnostic_rows = run_main_matrix(args)
    if args.skip_ablation:
        progress("\nMain comparison matrix complete; feature ablation skipped")
        ablation_rows = []
    else:
        progress("\nMain comparison matrix complete; starting feature ablation")
        ablation_rows = run_ablation(args)

    matrix_path = args.out_dir / "main_comparison_matrix.csv"
    ablation_path = args.out_dir / "feature_ablation.csv"
    diagnostic_path = args.out_dir / "teacher_imitation_diagnostics.csv"
    write_csv(matrix_path, matrix_rows)
    write_csv(ablation_path, ablation_rows)
    write_csv(diagnostic_path, diagnostic_rows)

    print(f"Saved {matrix_path}")
    if ablation_rows:
        print(f"Saved {ablation_path}")
    print(f"Saved {diagnostic_path}")

    metric_summary = {}
    for row in matrix_rows:
        key = (row["scenario_mode"], row["load_level"], row["kmax"], row["method"])
        summary = metric_summary.setdefault(
            key,
            {
                "utility": [],
                "used_spectral_efficiency": [],
                "system_spectral_efficiency": [],
                "served_ratio": [],
                "average_quality": [],
            },
        )
        for metric in summary:
            summary[metric].append(row[metric])

    print("\nMain comparison summary (mean utility, SE, service, and quality)")
    for scenario_mode in args.scenario_modes:
        for load_level in args.load_levels:
            for kmax in args.kmax_values:
                print(f"\nscenario_mode={scenario_mode}, load={load_level}, kmax={kmax}")
                for method_name in MAIN_METHODS:
                    values = metric_summary[(scenario_mode, load_level, kmax, method_name)]
                    print(
                        f"  {method_name}: utility={np.mean(values['utility']):.4f}, "
                        f"used_SE={np.mean(values['used_spectral_efficiency']):.3f}, "
                        f"system_SE={np.mean(values['system_spectral_efficiency']):.3f} bit/s/Hz, "
                        f"served={np.mean(values['served_ratio']):.3f}, "
                        f"quality={np.mean(values['average_quality']):.2f}"
                    )

    if ablation_rows:
        print("\nFeature ablation summary (mean utility)")
        for scenario_mode in args.scenario_modes:
            for load_level in args.load_levels:
                print(f"\nscenario_mode={scenario_mode}, load={load_level}, kmax={args.ablation_kmax}")
                for feature_mode in args.feature_modes:
                    values = [
                        row["utility"]
                        for row in ablation_rows
                        if row["scenario_mode"] == scenario_mode
                        and row["load_level"] == load_level
                        and row["feature_mode"] == feature_mode
                    ]
                    print(f"  {FEATURE_MODE_LABELS[feature_mode]}: {np.mean(values):.4f}")

    print("\nTeacher-imitation diagnostics summary")
    for scenario_mode in args.scenario_modes:
        for load_level in args.load_levels:
            for method_name in ["Multi-feature k-means", "LE-GRA MVP"]:
                subset = [
                    row for row in diagnostic_rows
                    if row["scenario_mode"] == scenario_mode
                    and row["load_level"] == load_level
                    and row["method"] == method_name
                ]
                if not subset:
                    continue
                print(
                    f"  scenario={scenario_mode}, load={load_level}, method={method_name}: "
                    f"pairwise_acc={np.mean([r['pairwise_accuracy'] for r in subset]):.4f}, "
                    f"ARI={np.mean([r['ari'] for r in subset]):.4f}, "
                    f"NMI={np.mean([r['nmi'] for r in subset]):.4f}"
                )


if __name__ == "__main__":
    main()
