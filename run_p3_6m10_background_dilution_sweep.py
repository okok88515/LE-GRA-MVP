"""P3.6m-10 background-dilution sweep with fixed exact support density."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path


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


def _row_by_method(rows: list[dict[str, str]], method: str) -> dict[str, str]:
    for row in rows:
        if row["method"] == method:
            return row
    raise ValueError(f"Missing method row: {method}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", type=Path, default=Path("p3_6m4b_threshold_nudge_bundle/bundle"))
    parser.add_argument("--out-dir", type=Path, default=Path("p3_6m10_background_dilution_sweep"))
    parser.add_argument("--feature-mode", default="history_cost_quality")
    parser.add_argument("--focus-ue-ids", nargs="+", default=["0", "1", "15", "2", "3", "4", "5"])
    parser.add_argument("--train-window-start", type=float, default=43.7)
    parser.add_argument("--train-window-end", type=float, default=43.8)
    parser.add_argument("--test-window-start", type=float, default=43.9)
    parser.add_argument("--test-window-end", type=float, default=43.9)
    parser.add_argument("--background-train-limits", nargs="+", type=int, default=[150, 100, 50, 20, 10, 5, 0])
    parser.add_argument("--background-train-repeat", type=int, default=1)
    parser.add_argument("--focus-train-repeat", type=int, default=2)
    parser.add_argument("--max-groups", type=int, default=3)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--pair-sampling", default="teacher_boundary")
    parser.add_argument("--pairs-per-class", type=int, default=160)
    parser.add_argument("--supervision-weight-mode", default="teacher_hard_group")
    parser.add_argument("--hard-positive-scale", type=float, default=2.5)
    parser.add_argument("--hard-negative-scale", type=float, default=1.5)
    parser.add_argument("--scenario-weight-mode", default="positive_multigroup_focus")
    parser.add_argument("--positive-gain-boost", type=int, default=4)
    parser.add_argument("--multigroup-boost", type=int, default=2)
    parser.add_argument("--prototype-weight", type=float, default=0.5)
    parser.add_argument("--prototype-margin", type=float, default=1.0)
    parser.add_argument("--membership-weight", type=float, default=1.0)
    parser.add_argument("--grouping-mode", default="membership_order")
    parser.add_argument("--kmeans-n-init", type=int, default=10)
    parser.add_argument("--seed", type=int, default=9)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "bundle_dir": str(args.bundle_dir),
        "focus_ue_ids": args.focus_ue_ids,
        "train_window_start": args.train_window_start,
        "train_window_end": args.train_window_end,
        "test_window_start": args.test_window_start,
        "test_window_end": args.test_window_end,
        "background_train_limits": args.background_train_limits,
        "background_train_repeat": args.background_train_repeat,
        "focus_train_repeat": args.focus_train_repeat,
        "seed": args.seed,
    }
    (args.out_dir / "sweep_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    summary_rows: list[dict] = []
    for limit in args.background_train_limits:
        run_name = f"background_limit_{limit:03d}"
        run_out_dir = args.out_dir / run_name
        command = [
            sys.executable,
            "run_p3_6g_temporal_learner.py",
            "--bundle-dir",
            str(args.bundle_dir),
            "--out-dir",
            str(run_out_dir),
            "--feature-mode",
            args.feature_mode,
            "--background-train-limit",
            str(limit),
            "--background-train-repeat",
            str(args.background_train_repeat),
            "--focus-train-repeat",
            str(args.focus_train_repeat),
            "--train-window-start",
            str(args.train_window_start),
            "--train-window-end",
            str(args.train_window_end),
            "--test-window-start",
            str(args.test_window_start),
            "--test-window-end",
            str(args.test_window_end),
            "--max-groups",
            str(args.max_groups),
            "--epochs",
            str(args.epochs),
            "--switch-beta",
            str(args.switch_beta),
            "--pair-sampling",
            args.pair_sampling,
            "--pairs-per-class",
            str(args.pairs_per_class),
            "--supervision-weight-mode",
            args.supervision_weight_mode,
            "--hard-positive-scale",
            str(args.hard_positive_scale),
            "--hard-negative-scale",
            str(args.hard_negative_scale),
            "--scenario-weight-mode",
            args.scenario_weight_mode,
            "--positive-gain-boost",
            str(args.positive_gain_boost),
            "--multigroup-boost",
            str(args.multigroup_boost),
            "--prototype-weight",
            str(args.prototype_weight),
            "--prototype-margin",
            str(args.prototype_margin),
            "--membership-weight",
            str(args.membership_weight),
            "--grouping-mode",
            args.grouping_mode,
            "--kmeans-n-init",
            str(args.kmeans_n_init),
            "--seed",
            str(args.seed),
            "--focus-ue-ids",
            *args.focus_ue_ids,
        ]
        print(f"[P3.6m-10] Running {run_name} ...", flush=True)
        subprocess.run(command, check=True)

        split_summary = json.loads((run_out_dir / "split_summary.json").read_text(encoding="utf-8"))
        main_rows = _read_csv(run_out_dir / "main_comparison.csv")
        diag_rows = _read_csv(run_out_dir / "teacher_imitation_diagnostics.csv")

        legra = _row_by_method(main_rows, "LE-GRA MVP")
        teacher = _row_by_method(main_rows, "Offline teacher")
        multif = _row_by_method(main_rows, "Multi-feature k-means")
        diag = _row_by_method(diag_rows, "LE-GRA MVP")

        summary_rows.append(
            {
                "background_train_limit": limit,
                "effective_background_train_scenarios": split_summary["effective_background_train_scenarios"],
                "effective_focus_train_scenarios": split_summary["effective_focus_train_scenarios"],
                "legra_utility": float(legra["utility"]),
                "teacher_utility": float(teacher["utility"]),
                "multifeature_utility": float(multif["utility"]),
                "legra_teacher_gap": float(teacher["utility"]) - float(legra["utility"]),
                "legra_vs_multifeature_gap": float(legra["utility"]) - float(multif["utility"]),
                "pairwise_accuracy": float(diag["pairwise_accuracy"]),
                "ari": float(diag["ari"]),
                "nmi": float(diag["nmi"]),
                "selected_epoch": split_summary["selected_epoch"],
                "selection_validation_loss": split_summary["selection_validation_loss"],
                "out_dir": str(run_out_dir),
            }
        )

    _write_csv(args.out_dir / "sweep_summary.csv", summary_rows)
    print("\n[P3.6m-10] Sweep summary")
    for row in summary_rows:
        print(
            f"  background_limit={row['background_train_limit']:>3}: "
            f"LE-GRA={row['legra_utility']:.6f}, "
            f"teacher_gap={row['legra_teacher_gap']:.6f}, "
            f"pairwise={row['pairwise_accuracy']:.3f}, "
            f"ARI={row['ari']:.3f}, NMI={row['nmi']:.3f}"
        )


if __name__ == "__main__":
    main()
