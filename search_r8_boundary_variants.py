"""Local search around the successful r8 boundary-flicker regime."""

from __future__ import annotations

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


def _extract_utility(run_dir: Path) -> dict[str, float]:
    rows = _read_csv(run_dir / "main_comparison.csv")
    by_method = {row["method"]: row for row in rows}
    return {
        "teacher": float(by_method["Offline teacher"]["utility"]),
        "resource": float(by_method["Resource-cost k-means"]["utility"]),
        "legra": float(by_method["LE-GRA MVP"]["utility"]),
        "cqi": float(by_method["CQI k-means"]["utility"]),
        "multifeature": float(by_method["Multi-feature k-means"]["utility"]),
    }


def _window(spec: dict, start_s: float) -> dict:
    for window in spec["windows"]:
        if abs(float(window["start_s"]) - start_s) <= 1e-9:
            return window
    raise KeyError(start_s)


def main() -> None:
    base_spec = _load_json(ROOT / "p3_6r8_q10_temporal_decoy_flicker_spec.json")
    out_root = ROOT / "r8_boundary_variant_search"
    specs_dir = out_root / "specs"
    runs_dir = out_root / "runs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    leaderboard: list[dict] = []
    combos = list(
        itertools.product(
            [0.68, 0.72],  # ue4 singleton-time rb_scale at 28.0 / 28.2
            [0.94, 0.98],  # ue4 pair-time rb_scale at 28.1
            [0.82, 0.86],  # ue6 pair-time rb_scale at 28.1
            [0.86, 0.90],  # ue6 singleton-time rb_scale at 28.2
        )
    )

    for index, (u4_single, u4_pair, u6_pair, u6_single) in enumerate(combos, start=1):
        spec = copy.deepcopy(base_spec)
        variant_name = (
            f"p3_6r8s_{index:02d}_"
            f"u4s{str(u4_single).replace('.','')}_"
            f"u4p{str(u4_pair).replace('.','')}_"
            f"u6p{str(u6_pair).replace('.','')}_"
            f"u6s{str(u6_single).replace('.','')}"
        )
        spec["name"] = variant_name
        spec["out_dir"] = f"{variant_name}_bundle"
        spec["intent"] = "Automated local search around r8 boundary-flicker regime."

        for ts in [28.0, 28.2]:
            _window(spec, ts)["ue_rules"]["4"]["rb_scale"] = u4_single
        _window(spec, 28.1)["ue_rules"]["4"]["rb_scale"] = u4_pair
        _window(spec, 28.1)["ue_rules"]["6"]["rb_scale"] = u6_pair
        _window(spec, 28.2)["ue_rules"]["6"]["rb_scale"] = u6_single

        spec_path = specs_dir / f"{variant_name}.json"
        _save_json(spec_path, spec)
        build_code, build_log = _run(
            [sys.executable, str(ROOT / "build_family_window_transform_bundle.py"), "--spec", str(spec_path)]
        )
        (runs_dir / f"{variant_name}_build.log").write_text(build_log, encoding="utf-8")
        if build_code != 0:
            leaderboard.append({"variant_name": variant_name, "status": f"build_failed_{build_code}"})
            continue

        row: dict[str, object] = {
            "variant_name": variant_name,
            "status": "ok",
            "u4_single_rb_scale": u4_single,
            "u4_pair_rb_scale": u4_pair,
            "u6_pair_rb_scale": u6_pair,
            "u6_single_rb_scale": u6_single,
            "bundle_dir": spec["out_dir"],
            "spec_path": str(spec_path),
        }
        for mode_name, grouping_mode in [
            ("baseline", "kmeans_embedding"),
            ("anchor", "resource_anchor_hybrid"),
        ]:
            run_dir = runs_dir / f"{variant_name}_{mode_name}"
            run_dir.mkdir(parents=True, exist_ok=True)
            eval_code, eval_log = _run(
                [
                    sys.executable,
                    str(ROOT / "run_focused_family_temporal_learner.py"),
                    "--bundle-dir",
                    str(ROOT / spec["out_dir"] / "bundle"),
                    "--out-dir",
                    str(run_dir),
                    "--serving-gnb",
                    "gnb_2",
                    "--ue-ids",
                    "1|2|3|4|5|6",
                    "--train-window-start",
                    "27.7",
                    "--train-window-end",
                    "28.0",
                    "--test-window-start",
                    "28.1",
                    "--test-window-end",
                    "28.2",
                    "--feature-mode",
                    "history_cost_quality",
                    "--epochs",
                    "120",
                    "--grouping-mode",
                    grouping_mode,
                ]
            )
            (run_dir / "run.log").write_text(eval_log, encoding="utf-8")
            if eval_code != 0:
                row["status"] = f"{mode_name}_eval_failed_{eval_code}"
                break
            utility = _extract_utility(run_dir)
            for metric_name, value in utility.items():
                row[f"{mode_name}_{metric_name}"] = value
        if row["status"] == "ok":
            row["teacher_minus_resource"] = float(row["baseline_teacher"]) - float(row["baseline_resource"])
            row["baseline_gap"] = float(row["baseline_teacher"]) - float(row["baseline_legra"])
            row["anchor_gap"] = float(row["anchor_teacher"]) - float(row["anchor_legra"])
            row["anchor_gain_over_baseline"] = float(row["anchor_legra"]) - float(row["baseline_legra"])
        leaderboard.append(row)

    leaderboard.sort(
        key=lambda row: (
            float(row.get("anchor_gain_over_baseline", -999.0)),
            float(row.get("teacher_minus_resource", -999.0)),
        ),
        reverse=True,
    )
    _write_csv(out_root / "leaderboard.csv", leaderboard)
    for row in leaderboard:
        print(row)


if __name__ == "__main__":
    main()
