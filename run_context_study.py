"""P2.6 bounded mixed-load study for decision-context features."""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from types import SimpleNamespace

import run_standard_matrix as matrix


DEFAULT_FEATURE_MODES = ["history_cost", "history_cost_context"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-scenarios", type=int, default=40)
    parser.add_argument("--test-scenarios", type=int, default=20)
    parser.add_argument("--users", type=int, default=24)
    parser.add_argument("--rbs", type=int, default=100)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--kmax", type=int, default=3)
    parser.add_argument("--seeds", nargs="+", type=int, default=[9, 17, 23])
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--kmeans-n-init", type=int, default=10)
    parser.add_argument(
        "--feature-modes",
        nargs="+",
        choices=[
            "history_cost",
            "history_cost_quality",
            "history_cost_load",
            "history_cost_context",
        ],
        default=DEFAULT_FEATURE_MODES,
    )
    parser.add_argument("--out-dir", type=Path, default=Path("p2_6_context_study"))
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    split_args = SimpleNamespace(
        users=args.users,
        rbs=args.rbs,
        train_scenarios=args.train_scenarios,
        test_scenarios=args.test_scenarios,
    )
    main_rows, diagnostic_rows = [], []
    total = len(args.feature_modes) * len(args.seeds)
    job = 0
    started = time.perf_counter()

    for feature_mode in args.feature_modes:
        for seed in args.seeds:
            job += 1
            label = f"P2.6 {job}/{total}: feature={feature_mode}, seed={seed}"
            matrix.progress(f"\n[{label}] Generating paired light/medium splits")
            light_train, light_test = matrix.generate_splits(
                split_args, "ambiguous", seed, "light"
            )
            medium_train, medium_test = matrix.generate_splits(
                split_args, "ambiguous", seed, "medium"
            )
            combined_train = light_train + medium_train
            combined_test = light_test + medium_test
            model = matrix.train_model(
                combined_train,
                combined_test,
                feature_mode=feature_mode,
                max_groups=args.kmax,
                switch_beta=args.switch_beta,
                epochs=args.epochs,
                validation_fraction=0.0,
                pair_sampling="random_balanced",
                pairs_per_class=160,
                progress_label=label,
            )

            for load, test in (("light", light_test), ("medium", medium_test)):
                eval_label = f"{label}, load={load}"
                method_rows, cache = matrix.evaluate_main_methods(
                    test,
                    model,
                    max_groups=args.kmax,
                    switch_beta=args.switch_beta,
                    kmeans_n_init=args.kmeans_n_init,
                    progress_label=eval_label,
                )
                for row in method_rows:
                    row.update({
                        "scenario_mode": "ambiguous",
                        "load_level": load,
                        "rb_budget_ratio": matrix.LOAD_RATIOS[load],
                        "kmax": args.kmax,
                        "seed": seed,
                        "feature_mode": feature_mode,
                        "training_loads": "light+medium",
                    })
                    main_rows.append(row)
                for row in matrix.evaluate_teacher_imitation(
                    test,
                    cache,
                    max_groups=args.kmax,
                    switch_beta=args.switch_beta,
                    feature_mode=feature_mode,
                    scenario_mode="ambiguous",
                    load_level=load,
                    seed=seed,
                    progress_label=eval_label,
                ):
                    row["training_loads"] = "light+medium"
                    diagnostic_rows.append(row)
            matrix.progress(
                f"[{label}] Complete ({time.perf_counter() - started:.1f}s elapsed)"
            )

    main_path = args.out_dir / "main_comparison_matrix.csv"
    diagnostics_path = args.out_dir / "teacher_imitation_diagnostics.csv"
    matrix.write_csv(main_path, main_rows)
    matrix.write_csv(diagnostics_path, diagnostic_rows)
    matrix.progress(f"Saved {main_path}")
    matrix.progress(f"Saved {diagnostics_path}")


if __name__ == "__main__":
    main()
