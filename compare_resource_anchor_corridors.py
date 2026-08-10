"""Compare baseline vs resource-anchor LE-GRA on focused corridors."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


CORRIDORS = [
    {
        "name": "q10_main",
        "bundle_dir": ROOT / "p3_6q10_six_user_transition_extension_bundle" / "bundle",
        "serving_gnb": "gnb_2",
        "ue_ids": "1|2|3|4|5|6",
        "train_start": 27.3,
        "train_end": 27.7,
        "test_start": 27.8,
        "test_end": 28.2,
    },
    {
        "name": "r8_boundary",
        "bundle_dir": ROOT / "p3_6r8_q10_temporal_decoy_flicker_bundle" / "bundle",
        "serving_gnb": "gnb_2",
        "ue_ids": "1|2|3|4|5|6",
        "train_start": 27.7,
        "train_end": 28.0,
        "test_start": 28.1,
        "test_end": 28.2,
    },
    {
        "name": "n3_long",
        "bundle_dir": ROOT / "p3_6n3_isolate_ue5_bundle" / "bundle",
        "serving_gnb": "gnb_2",
        "ue_ids": "3|4|5|6",
        "train_start": 25.8,
        "train_end": 27.8,
        "test_start": 27.9,
        "test_end": 29.9,
    },
    {
        "name": "i2_m4b",
        "bundle_dir": ROOT / "p3_6i2_coupled_bundle" / "bundle",
        "serving_gnb": "gnb_1",
        "ue_ids": "0|1|15|2|3|4|5",
        "train_start": 43.7,
        "train_end": 43.7,
        "test_start": 43.8,
        "test_end": 43.9,
    },
]


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


def _run_one(corridor: dict, grouping_mode: str, out_dir: Path) -> tuple[int, str]:
    command = [
        sys.executable,
        str(ROOT / "run_focused_family_temporal_learner.py"),
        "--bundle-dir",
        str(corridor["bundle_dir"]),
        "--out-dir",
        str(out_dir),
        "--serving-gnb",
        corridor["serving_gnb"],
        "--ue-ids",
        corridor["ue_ids"],
        "--train-window-start",
        str(corridor["train_start"]),
        "--train-window-end",
        str(corridor["train_end"]),
        "--test-window-start",
        str(corridor["test_start"]),
        "--test-window-end",
        str(corridor["test_end"]),
        "--feature-mode",
        "history_cost_quality",
        "--epochs",
        "120",
        "--grouping-mode",
        grouping_mode,
    ]
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.returncode, completed.stdout + completed.stderr


def _extract_summary(run_dir: Path) -> dict:
    summary = json.loads((run_dir / "split_summary.json").read_text(encoding="utf-8"))
    rows = _read_csv(run_dir / "main_comparison.csv")
    by_method = {row["method"]: row for row in rows}
    return {
        "teacher": float(by_method["Offline teacher"]["utility"]),
        "resource": float(by_method["Resource-cost k-means"]["utility"]),
        "legra": float(by_method["LE-GRA MVP"]["utility"]),
        "cqi": float(by_method["CQI k-means"]["utility"]),
        "multifeature": float(by_method["Multi-feature k-means"]["utility"]),
        "grouping_mode": summary["grouping_mode"],
    }


def main() -> None:
    out_root = ROOT / "_tmp_resource_anchor_corridor_compare"
    out_root.mkdir(parents=True, exist_ok=True)

    result_rows: list[dict] = []
    for corridor in CORRIDORS:
        baseline_dir = out_root / f"{corridor['name']}_baseline"
        anchor_dir = out_root / f"{corridor['name']}_resource_anchor"
        for run_dir, grouping_mode in [
            (baseline_dir, "kmeans_embedding"),
            (anchor_dir, "resource_anchor_hybrid"),
        ]:
            run_dir.mkdir(parents=True, exist_ok=True)
            returncode, output = _run_one(corridor, grouping_mode, run_dir)
            (run_dir / "run.log").write_text(output, encoding="utf-8")
            if returncode != 0:
                raise RuntimeError(
                    f"{corridor['name']} failed under {grouping_mode}; see {run_dir / 'run.log'}"
                )
        baseline = _extract_summary(baseline_dir)
        anchor = _extract_summary(anchor_dir)
        result_rows.append(
            {
                "corridor": corridor["name"],
                "serving_gnb": corridor["serving_gnb"],
                "ue_ids": corridor["ue_ids"],
                "train_window": f"{corridor['train_start']:.1f}~{corridor['train_end']:.1f}",
                "test_window": f"{corridor['test_start']:.1f}~{corridor['test_end']:.1f}",
                "teacher": baseline["teacher"],
                "resource": baseline["resource"],
                "baseline_legra": baseline["legra"],
                "anchor_legra": anchor["legra"],
                "cqi": baseline["cqi"],
                "multifeature": baseline["multifeature"],
                "teacher_minus_resource": baseline["teacher"] - baseline["resource"],
                "baseline_gap": baseline["teacher"] - baseline["legra"],
                "anchor_gap": anchor["teacher"] - anchor["legra"],
                "anchor_gain_over_baseline": anchor["legra"] - baseline["legra"],
            }
        )

    result_rows.sort(
        key=lambda row: (
            row["anchor_gain_over_baseline"],
            row["teacher_minus_resource"],
        ),
        reverse=True,
    )
    _write_csv(out_root / "leaderboard.csv", result_rows)
    for row in result_rows:
        print(row)


if __name__ == "__main__":
    main()
