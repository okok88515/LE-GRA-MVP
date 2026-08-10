"""Focused q10/r4 search for stronger resource-cost decoy collisions.

Idea:
- Keep the proven `r4` weak pair `{ue2, ue6}`.
- Make `ue4` look more similar in instantaneous cost, without making it truly
  weak under the teacher objective.
- Search only a small local grid so we can quickly test whether a larger
  `teacher - resource-cost` gap is available near the working showcase.
"""

from __future__ import annotations

import argparse
import copy
import csv
import itertools
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


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def _set_ue_rule(spec: dict, ue_id: str, patch: dict[str, float | int | list[float]]) -> None:
    for window in spec["windows"]:
        spec_rule = window["ue_rules"][ue_id]
        for key, value in patch.items():
            spec_rule[key] = copy.deepcopy(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-spec", type=Path, default=Path("p3_6r4_q10_history_conflict_spec.json"))
    parser.add_argument("--out-dir", type=Path, default=Path("q10_decoy_collision_search"))
    parser.add_argument("--epochs", type=int, default=120)
    args = parser.parse_args()

    base_spec_path = (ROOT / args.base_spec).resolve() if not args.base_spec.is_absolute() else args.base_spec.resolve()
    out_dir = (ROOT / args.out_dir).resolve() if not args.out_dir.is_absolute() else args.out_dir.resolve()
    specs_dir = out_dir / "specs"
    runs_dir = out_dir / "runs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    base_spec = _load_json(base_spec_path)
    leaderboard: list[dict] = []

    combos = list(
        itertools.product(
            [2, 3],              # ue4 previous quality
            [11.2, 11.6, 12.0],  # ue4 cqi_now_raw
            [0.72, 0.78, 0.84],  # ue4 rb_scale
            [9.0, 9.2],          # ue2 cqi_now_raw
            [0.64, 0.68],        # ue2 rb_scale
            [10.6, 10.9],        # ue6 cqi_now_raw
            [0.80, 0.86],        # ue6 rb_scale
        )
    )

    for index, combo in enumerate(combos, start=1):
        ue4_prevq, ue4_cqi, ue4_rb, ue2_cqi, ue2_rb, ue6_cqi, ue6_rb = combo
        spec = copy.deepcopy(base_spec)
        variant_name = (
            f"p3_6r7_{index:03d}_"
            f"u4p{ue4_prevq}_u4c{str(ue4_cqi).replace('.','')}_u4r{str(ue4_rb).replace('.','')}_"
            f"u2c{str(ue2_cqi).replace('.','')}_u2r{str(ue2_rb).replace('.','')}_"
            f"u6c{str(ue6_cqi).replace('.','')}_u6r{str(ue6_rb).replace('.','')}"
        )
        spec["name"] = variant_name
        spec["out_dir"] = f"{variant_name}_bundle"
        spec["intent"] = "Automated q10 decoy-collision search variant."
        _set_ue_rule(
            spec,
            "4",
            {
                "previous_quality": ue4_prevq,
                "cqi_now_raw": ue4_cqi,
                "rb_scale": ue4_rb,
                "history_offsets": [0.4, 0.2, 0.1, 0.0],
            },
        )
        _set_ue_rule(
            spec,
            "2",
            {
                "cqi_now_raw": ue2_cqi,
                "rb_scale": ue2_rb,
            },
        )
        _set_ue_rule(
            spec,
            "6",
            {
                "cqi_now_raw": ue6_cqi,
                "rb_scale": ue6_rb,
            },
        )

        spec_path = specs_dir / f"{variant_name}.json"
        _save_json(spec_path, spec)
        build_code, build_log = _run(
            [sys.executable, str(ROOT / "build_family_window_transform_bundle.py"), "--spec", str(spec_path)]
        )
        (runs_dir / f"{variant_name}_build.log").write_text(build_log, encoding="utf-8")
        if build_code != 0:
            leaderboard.append({"variant_name": variant_name, "status": f"build_failed_{build_code}"})
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
                "1|2|3|4|5|6",
                "--train-window-start",
                "27.7",
                "--train-window-end",
                "27.9",
                "--test-window-start",
                "28.0",
                "--test-window-end",
                "28.2",
                "--feature-mode",
                "history_cost_quality",
                "--epochs",
                str(args.epochs),
            ]
        )
        (eval_dir / "run.log").write_text(eval_log, encoding="utf-8")
        if eval_code != 0:
            leaderboard.append({"variant_name": variant_name, "status": f"eval_failed_{eval_code}"})
            continue

        summary = json.loads((eval_dir / "split_summary.json").read_text(encoding="utf-8"))
        comparison = {row["method"]: row for row in _read_csv(eval_dir / "main_comparison.csv")}
        teacher = float(comparison["Offline teacher"]["utility"])
        resource = float(comparison["Resource-cost k-means"]["utility"])
        legra = float(comparison["LE-GRA MVP"]["utility"])
        cqi = float(comparison["CQI k-means"]["utility"])
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

    leaderboard.sort(
        key=lambda row: (
            float(row["teacher_minus_resource_cost"]) if row.get("status") == "ok" else -999.0,
            min(int(row.get("train_positive_gain_count", 0)), int(row.get("test_positive_gain_count", 0))) if row.get("status") == "ok" else -999,
            float(row.get("teacher_utility", -999.0)) if row.get("status") == "ok" else -999.0,
        ),
        reverse=True,
    )
    _write_csv(out_dir / "leaderboard.csv", leaderboard)
    print(f"variant_count={len(leaderboard)}")
    for row in leaderboard[:20]:
        print(row)


if __name__ == "__main__":
    main()
