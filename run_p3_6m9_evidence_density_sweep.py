"""P3.6m-9 evidence-density sweep on the dual-weak focused regime."""

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


def _single_row_by_method(rows: list[dict[str, str]], method: str) -> dict[str, str]:
    for row in rows:
        if row["method"] == method:
            return row
    raise ValueError(f"Missing method row: {method}")


def _single_row_by_method_diag(rows: list[dict[str, str]], method: str) -> dict[str, str]:
    for row in rows:
        if row["method"] == method:
            return row
    raise ValueError(f"Missing diagnostic row: {method}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", type=Path, default=Path("p3_6m4b_threshold_nudge_bundle/bundle"))
    parser.add_argument("--out-dir", type=Path, default=Path("p3_6m9_evidence_density_sweep"))
    parser.add_argument("--feature-mode", default="history_cost_quality")
    parser.add_argument("--focus-ue-ids", nargs="+", default=["0", "1", "15", "2", "3", "4", "5"])
    parser.add_argument("--train-window-start", type=float, default=43.7)
    parser.add_argument("--train-window-end", type=float, default=43.8)
    parser.add_argument("--test-window-start", type=float, default=43.9)
    parser.add_argument("--test-window-end", type=float, default=43.9)
    parser.add_argument("--background-train-repeat", type=int, default=1)
    parser.add_argument("--focus-train-repeats", nargs="+", type=int, default=[1, 2, 4, 8, 16, 40, 80])
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

    summary_rows: list[dict] = []
    sweep_manifest = {
        "bundle_dir": str(args.bundle_dir),
        "focus_ue_ids": args.focus_ue_ids,
        "train_window_start": args.train_window_start,
        "train_window_end": args.train_window_end,
        "test_window_start": args.test_window_start,
        "test_window_end": args.test_window_end,
        "background_train_repeat": args.background_train_repeat,
        "focus_train_repeats": args.focus_train_repeats,
        "seed": args.seed,
    }
    (args.out_dir / "sweep_manifest.json").write_text(
        json.dumps(sweep_manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    for repeat in args.focus_train_repeats:
        run_name = f"focus_repeat_{repeat:03d}"
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
            "--background-train-repeat",
            str(args.background_train_repeat),
            "--focus-train-repeat",
            str(repeat),
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
        print(f"[P3.6m-9] Running {run_name} ...", flush=True)
        subprocess.run(command, check=True)

        split_summary = json.loads((run_out_dir / "split_summary.json").read_text(encoding="utf-8"))
        main_rows = _read_csv(run_out_dir / "main_comparison.csv")
        diag_rows = _read_csv(run_out_dir / "teacher_imitation_diagnostics.csv")
        evidence_rows = _read_csv(run_out_dir / "teacher_group_evidence_audit.csv")

        teacher_row = _single_row_by_method(main_rows, "Offline teacher")
        legra_row = _single_row_by_method(main_rows, "LE-GRA MVP")
        multif_row = _single_row_by_method(main_rows, "Multi-feature k-means")
        legra_diag = _single_row_by_method_diag(diag_rows, "LE-GRA MVP")

        focus_train_rows = [row for row in evidence_rows if row["split"] == "focus_train"]
        focus_test_rows = [row for row in evidence_rows if row["split"] == "focus_test"]
        exact_train_count = sum(row["hard_group_signature"] == "15|4" for row in focus_train_rows)
        exact_test_count = sum(row["hard_group_signature"] == "15|4" for row in focus_test_rows)

        summary_rows.append(
            {
                "focus_train_repeat": repeat,
                "focus_train_scenarios": split_summary["focus_train_scenarios"],
                "focus_test_scenarios": split_summary["focus_test_scenarios"],
                "effective_focus_train_scenarios": split_summary["effective_focus_train_scenarios"],
                "effective_background_train_scenarios": split_summary["effective_background_train_scenarios"],
                "exact_dualweak_train_slices": exact_train_count,
                "exact_dualweak_test_slices": exact_test_count,
                "legra_utility": float(legra_row["utility"]),
                "teacher_utility": float(teacher_row["utility"]),
                "multifeature_utility": float(multif_row["utility"]),
                "legra_teacher_gap": float(teacher_row["utility"]) - float(legra_row["utility"]),
                "legra_vs_multifeature_gap": float(legra_row["utility"]) - float(multif_row["utility"]),
                "pairwise_accuracy": float(legra_diag["pairwise_accuracy"]),
                "ari": float(legra_diag["ari"]),
                "nmi": float(legra_diag["nmi"]),
                "selected_epoch": split_summary["selected_epoch"],
                "selection_validation_loss": split_summary["selection_validation_loss"],
                "out_dir": str(run_out_dir),
            }
        )

    _write_csv(args.out_dir / "sweep_summary.csv", summary_rows)
    print("\n[P3.6m-9] Sweep summary")
    for row in summary_rows:
        print(
            f"  repeat={row['focus_train_repeat']:>3}: "
            f"LE-GRA={row['legra_utility']:.6f}, "
            f"teacher_gap={row['legra_teacher_gap']:.6f}, "
            f"pairwise={row['pairwise_accuracy']:.3f}, "
            f"ARI={row['ari']:.3f}, NMI={row['nmi']:.3f}"
        )


if __name__ == "__main__":
    main()
