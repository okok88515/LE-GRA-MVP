"""Batch-run family-preserving temporal evaluations from mined corridors."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _segment_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row["bundle_name"],
        row["serving_gnb"],
        row["ue_ids"],
        row["start_time_s"],
        row["end_time_s"],
    )


def _find_bundle_root(bundle_name: str) -> Path | None:
    candidates = []
    for path in ROOT.glob(f"{bundle_name}*"):
        if not path.is_dir():
            continue
        if not (path / "bundle" / "scenarios.csv").exists():
            continue
        name = path.name.lower()
        if any(token in name for token in ["teacher_audit", "focus_mining", "learner", "baseline", "focused_teacher_subset"]):
            continue
        score = 0
        if "bundle" in name:
            score += 3
        if "focused" in name:
            score -= 3
        if "audit" in name:
            score -= 5
        score -= len(path.name) / 1000.0
        candidates.append((score, path))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _select_segments(
    positive_segments: list[dict[str, str]],
    candidate_slices: list[dict[str, str]],
    *,
    top_k: int,
    diversity_mode: str,
) -> list[dict[str, str]]:
    best_slice_by_segment: dict[tuple[str, str, str, str, str], dict[str, str]] = {}
    for row in candidate_slices:
        key = (
            row["bundle_name"],
            row["serving_gnb"],
            row["ue_ids"],
            row["segment_start_s"],
            row["segment_end_s"],
        )
        current = best_slice_by_segment.get(key)
        score = (
            int(row["balance_score"]),
            min(int(row["train_positive_gain_count"]), int(row["test_positive_gain_count"])),
            min(float(row["train_mean_gain_vs_single"]), float(row["test_mean_gain_vs_single"])),
        )
        if current is None:
            best_slice_by_segment[key] = row | {"_score": score}
            continue
        if score > current["_score"]:
            best_slice_by_segment[key] = row | {"_score": score}

    selected = []
    seen_family_signature: set[tuple[str, ...]] = set()
    for row in positive_segments:
        key = _segment_key(row)
        if key not in best_slice_by_segment:
            continue
        if diversity_mode == "family_signature":
            family_signature = (row["serving_gnb"], row["ue_ids"])
        elif diversity_mode == "bundle_family":
            family_signature = (row["bundle_name"], row["serving_gnb"], row["ue_ids"])
        else:
            raise ValueError(f"Unsupported diversity_mode: {diversity_mode}")
        if family_signature in seen_family_signature:
            continue
        selected.append(row | best_slice_by_segment[key])
        seen_family_signature.add(family_signature)
        if len(selected) >= top_k:
            break
    return selected


def _run_one(
    *,
    bundle_dir: Path,
    out_dir: Path,
    serving_gnb: str,
    ue_ids: str,
    train_start: float,
    train_end: float,
    test_start: float,
    test_end: float,
    feature_mode: str,
    epochs: int,
) -> tuple[int, str]:
    command = [
        sys.executable,
        str(ROOT / "run_focused_family_temporal_learner.py"),
        "--bundle-dir",
        str(bundle_dir / "bundle"),
        "--out-dir",
        str(out_dir),
        "--serving-gnb",
        serving_gnb,
        "--ue-ids",
        ue_ids,
        "--train-window-start",
        str(train_start),
        "--train-window-end",
        str(train_end),
        "--test-window-start",
        str(test_start),
        "--test-window-end",
        str(test_end),
        "--feature-mode",
        feature_mode,
        "--epochs",
        str(epochs),
    ]
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.returncode, completed.stdout + completed.stderr


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mining-dir", type=Path, default=Path("family_corridor_mining_global"))
    parser.add_argument("--out-dir", type=Path, default=Path("family_corridor_batch_runs"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--feature-modes", nargs="*", default=["history_cost_quality", "history_cost_radio"])
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument(
        "--diversity-mode",
        choices=["bundle_family", "family_signature"],
        default="bundle_family",
    )
    args = parser.parse_args()

    mining_dir = (ROOT / args.mining_dir).resolve() if not args.mining_dir.is_absolute() else args.mining_dir.resolve()
    out_dir = (ROOT / args.out_dir).resolve() if not args.out_dir.is_absolute() else args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    positive_segments = _read_csv(mining_dir / "positive_segments.csv")
    candidate_slices = _read_csv(mining_dir / "candidate_temporal_slices.csv")
    selected_segments = _select_segments(
        positive_segments,
        candidate_slices,
        top_k=args.top_k,
        diversity_mode=args.diversity_mode,
    )

    run_rows: list[dict] = []
    failed_rows: list[dict] = []

    for index, segment in enumerate(selected_segments, start=1):
        bundle_root = _find_bundle_root(segment["bundle_name"])
        if bundle_root is None:
            failed_rows.append(
                {
                    "bundle_name": segment["bundle_name"],
                    "serving_gnb": segment["serving_gnb"],
                    "ue_ids": segment["ue_ids"],
                    "reason": "bundle_root_not_found",
                }
            )
            continue
        split_s = float(segment["suggested_split_s"])
        train_start = float(segment["segment_start_s"])
        train_end = round(split_s - 0.1, 6)
        test_start = split_s
        test_end = float(segment["segment_end_s"])
        for feature_mode in args.feature_modes:
            run_name = f"{index:02d}_{segment['bundle_name']}_{segment['segment_id']}_{feature_mode}"
            run_dir = out_dir / run_name
            returncode, output = _run_one(
                bundle_dir=bundle_root,
                out_dir=run_dir,
                serving_gnb=segment["serving_gnb"],
                ue_ids=segment["ue_ids"],
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                feature_mode=feature_mode,
                epochs=args.epochs,
            )
            (run_dir / "run.log").write_text(output, encoding="utf-8")
            if returncode != 0:
                failed_rows.append(
                    {
                        "run_name": run_name,
                        "bundle_name": segment["bundle_name"],
                        "bundle_root": str(bundle_root),
                        "serving_gnb": segment["serving_gnb"],
                        "ue_ids": segment["ue_ids"],
                        "feature_mode": feature_mode,
                        "reason": f"returncode_{returncode}",
                    }
                )
                continue
            summary = json.loads((run_dir / "split_summary.json").read_text(encoding="utf-8"))
            comparison_rows = _read_csv(run_dir / "main_comparison.csv")
            by_method = {row["method"]: row for row in comparison_rows}
            run_rows.append(
                {
                    "run_name": run_name,
                    "bundle_name": segment["bundle_name"],
                    "bundle_root": str(bundle_root),
                    "serving_gnb": segment["serving_gnb"],
                    "ue_ids": segment["ue_ids"],
                    "feature_mode": feature_mode,
                    "segment_start_s": train_start,
                    "segment_end_s": test_end,
                    "suggested_split_s": split_s,
                    "train_scenarios": summary["train_scenarios"],
                    "test_scenarios": summary["test_scenarios"],
                    "train_positive_gain_count": summary["train_positive_gain_count"],
                    "test_positive_gain_count": summary["test_positive_gain_count"],
                    "teacher_utility": float(by_method["Offline teacher"]["utility"]),
                    "legra_utility": float(by_method["LE-GRA MVP"]["utility"]),
                    "resource_cost_utility": float(by_method["Resource-cost k-means"]["utility"]),
                    "cqi_utility": float(by_method["CQI k-means"]["utility"]),
                    "multifeature_utility": float(by_method["Multi-feature k-means"]["utility"]),
                    "no_grouping_utility": float(by_method["No grouping"]["utility"]),
                    "teacher_minus_resource_cost": float(by_method["Offline teacher"]["utility"]) - float(by_method["Resource-cost k-means"]["utility"]),
                    "teacher_minus_cqi": float(by_method["Offline teacher"]["utility"]) - float(by_method["CQI k-means"]["utility"]),
                    "teacher_minus_multifeature": float(by_method["Offline teacher"]["utility"]) - float(by_method["Multi-feature k-means"]["utility"]),
                    "teacher_minus_legra": float(by_method["Offline teacher"]["utility"]) - float(by_method["LE-GRA MVP"]["utility"]),
                }
            )

    run_rows.sort(
        key=lambda row: (
            row["teacher_minus_resource_cost"],
            row["teacher_minus_cqi"],
            row["teacher_minus_multifeature"],
            -abs(row["teacher_minus_legra"]),
        ),
        reverse=True,
    )
    _write_csv(out_dir / "leaderboard.csv", run_rows)
    _write_csv(out_dir / "failed_runs.csv", failed_rows)

    summary_lines = [
        f"selected_segment_count={len(selected_segments)}",
        f"completed_run_count={len(run_rows)}",
        f"failed_run_count={len(failed_rows)}",
        f"diversity_mode={args.diversity_mode}",
    ]
    if run_rows:
        best = run_rows[0]
        summary_lines.extend(
            [
                f"top_run_name={best['run_name']}",
                f"top_bundle_name={best['bundle_name']}",
                f"top_feature_mode={best['feature_mode']}",
                f"top_teacher_minus_resource_cost={best['teacher_minus_resource_cost']}",
                f"top_teacher_minus_legra={best['teacher_minus_legra']}",
            ]
        )
    (out_dir / "summary.txt").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print("Family corridor batch complete")
    for line in summary_lines:
        print(f"  {line}")


if __name__ == "__main__":
    main()
