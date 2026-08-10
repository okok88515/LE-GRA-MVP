"""Targeted local search for harder `n3` dual-weak corridors.

This search is intentionally small and structured:
- source family: `3|4|5|6 @ gnb_2`
- target idea: convert the easy `ue5` singleton regime into a harder corridor
  where `ue4` becomes history-side weak enough to matter, but not so weak in
  instantaneous cost that `resource-cost` trivially matches the teacher.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BASE_BUNDLE = "p3_6n3_isolate_ue5_bundle"


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _save_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run(command: list[str]) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.returncode, completed.stdout + completed.stderr


def _variant_spec(
    *,
    name: str,
    ue4_prevq: int,
    ue4_cqi: float,
    ue4_rb: float,
    ue5_prevq: int,
    ue5_cqi: float,
    ue5_rb: float,
    ue6_cqi: float,
    ue6_rb: float,
) -> dict:
    return {
        "name": name,
        "base_bundle": BASE_BUNDLE,
        "out_dir": f"{name}_bundle",
        "intent": "Automated n3 dual-weak search variant.",
        "family": {
            "serving_gnb": "gnb_2",
            "target_ue_ids": "3|4|5|6",
            "window_start_s": 27.2,
            "window_end_s": 28.8,
        },
        "windows": [
            {
                "start_s": 27.2,
                "end_s": 28.8,
                "ue_rules": {
                    "3": {
                        "previous_quality": 4,
                        "history_offsets": [0.0, 0.0, 0.0, 0.0],
                        "rb_scale": 1.0,
                    },
                    "4": {
                        "previous_quality": ue4_prevq,
                        "cqi_now_raw": ue4_cqi,
                        "history_offsets": [1.4, 1.0, 0.6, 0.2],
                        "rb_scale": ue4_rb,
                    },
                    "5": {
                        "previous_quality": ue5_prevq,
                        "cqi_now_raw": ue5_cqi,
                        "history_offsets": [1.5, 1.1, 0.8, 0.4],
                        "rb_scale": ue5_rb,
                    },
                    "6": {
                        "previous_quality": 4,
                        "cqi_now_raw": ue6_cqi,
                        "history_offsets": [0.2, 0.1, 0.0, 0.0],
                        "rb_scale": ue6_rb,
                    },
                },
            }
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=Path("n3_dualweak_variant_search"))
    parser.add_argument("--epochs", type=int, default=120)
    args = parser.parse_args()

    out_dir = (ROOT / args.out_dir).resolve() if not args.out_dir.is_absolute() else args.out_dir.resolve()
    specs_dir = out_dir / "specs"
    runs_dir = out_dir / "runs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    leaderboard_path = out_dir / "leaderboard.csv"
    existing_rows: list[dict[str, str]] = _read_csv(leaderboard_path) if leaderboard_path.exists() else []
    existing_by_name = {row["variant_name"]: row for row in existing_rows if "variant_name" in row}
    leaderboard: list[dict] = list(existing_rows)
    combos = list(
        itertools.product(
            [1, 2],              # ue4_prevq
            [11.3, 11.6, 11.9],  # ue4_cqi
            [0.78, 0.84, 0.90],  # ue4_rb
            [0, 1],              # ue5_prevq
            [9.6, 10.0],         # ue5_cqi
            [0.78, 0.84],        # ue5_rb
            [13.0, 13.4],        # ue6_cqi
            [0.94, 1.0],         # ue6_rb
        )
    )

    for index, combo in enumerate(combos, start=1):
        ue4_prevq, ue4_cqi, ue4_rb, ue5_prevq, ue5_cqi, ue5_rb, ue6_cqi, ue6_rb = combo
        variant_name = (
            f"p3_6r5s_{index:03d}_"
            f"u4p{ue4_prevq}_u4c{str(ue4_cqi).replace('.','')}_u4r{str(ue4_rb).replace('.','')}_"
            f"u5p{ue5_prevq}_u5c{str(ue5_cqi).replace('.','')}_u5r{str(ue5_rb).replace('.','')}_"
            f"u6c{str(ue6_cqi).replace('.','')}_u6r{str(ue6_rb).replace('.','')}"
        )
        spec = _variant_spec(
            name=variant_name,
            ue4_prevq=ue4_prevq,
            ue4_cqi=ue4_cqi,
            ue4_rb=ue4_rb,
            ue5_prevq=ue5_prevq,
            ue5_cqi=ue5_cqi,
            ue5_rb=ue5_rb,
            ue6_cqi=ue6_cqi,
            ue6_rb=ue6_rb,
        )
        spec_path = specs_dir / f"{variant_name}.json"
        _save_json(spec_path, spec)
        if variant_name in existing_by_name and existing_by_name[variant_name].get("status") == "ok":
            continue

        build_code, build_log = _run(
            [sys.executable, str(ROOT / "build_family_window_transform_bundle.py"), "--spec", str(spec_path)]
        )
        (runs_dir / f"{variant_name}_build.log").write_text(build_log, encoding="utf-8")
        if build_code != 0:
            leaderboard.append({"variant_name": variant_name, "status": f"build_failed_{build_code}"})
            _write_csv(leaderboard_path, leaderboard)
            continue

        eval_dir = runs_dir / variant_name
        eval_dir.mkdir(parents=True, exist_ok=True)
        eval_code, eval_log = _run(
            [
                sys.executable,
                str(ROOT / "run_focused_family_temporal_learner.py"),
                "--bundle-dir",
                str(ROOT / spec["out_dir"] / "bundle"),
                "--out-dir",
                str(eval_dir),
                "--serving-gnb",
                "gnb_2",
                "--ue-ids",
                "3|4|5|6",
                "--train-window-start",
                "27.2",
                "--train-window-end",
                "27.9",
                "--test-window-start",
                "28.0",
                "--test-window-end",
                "28.8",
                "--feature-mode",
                "history_cost_quality",
                "--epochs",
                str(args.epochs),
            ]
        )
        (eval_dir / "run.log").write_text(eval_log, encoding="utf-8")
        if eval_code != 0:
            leaderboard.append({"variant_name": variant_name, "status": f"eval_failed_{eval_code}"})
            _write_csv(leaderboard_path, leaderboard)
            continue

        summary = json.loads((eval_dir / "split_summary.json").read_text(encoding="utf-8"))
        comparison_rows = {row["method"]: row for row in _read_csv(eval_dir / "main_comparison.csv")}
        teacher = float(comparison_rows["Offline teacher"]["utility"])
        resource = float(comparison_rows["Resource-cost k-means"]["utility"])
        legra = float(comparison_rows["LE-GRA MVP"]["utility"])
        cqi = float(comparison_rows["CQI k-means"]["utility"])
        leaderboard.append(
            {
                "variant_name": variant_name,
                "status": "ok",
                "train_positive_gain_count": summary["train_positive_gain_count"],
                "test_positive_gain_count": summary["test_positive_gain_count"],
                "teacher_utility": teacher,
                "resource_cost_utility": resource,
                "legra_utility": legra,
                "cqi_utility": cqi,
                "teacher_minus_resource_cost": teacher - resource,
                "teacher_minus_legra": teacher - legra,
                "teacher_minus_cqi": teacher - cqi,
                "bundle_dir": spec["out_dir"],
                "spec_path": str(spec_path),
            }
        )
        _write_csv(leaderboard_path, leaderboard)

    def _sort_key(row: dict) -> tuple:
        if row.get("status") != "ok":
            return (-999.0, -999.0, -999.0)
        return (
            float(row["teacher_minus_resource_cost"]),
            min(int(row["train_positive_gain_count"]), int(row["test_positive_gain_count"])),
            float(row["teacher_utility"]),
        )

    leaderboard.sort(key=_sort_key, reverse=True)
    _write_csv(leaderboard_path, leaderboard)
    print(f"variant_count={len(leaderboard)}")
    for row in leaderboard[:12]:
        print(row)


if __name__ == "__main__":
    main()
