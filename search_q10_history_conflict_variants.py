"""Focused search around the successful q10/r4 history-conflict corridor.

This script automates a small but repeatable family-window redesign sweep:
1. clone the successful `r4` spec,
2. inject mild history-side decoys or weak-pair rebalancing,
3. rebuild the transformed bundle,
4. run family-preserving focused evaluation,
5. rank variants by `teacher - resource-cost` gap.

The goal is not broad exploration. It is a local search around the current
best showcase, where we already know the corridor is valid and informative.
"""

from __future__ import annotations

import argparse
import copy
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


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _offset_plus(values: list[float], delta: float) -> list[float]:
    return [round(value + delta, 3) for value in values]


def _build_variant_specs(base_spec: dict) -> list[dict]:
    variants: list[dict] = []

    def add_variant(
        suffix: str,
        intent_suffix: str,
        patch_fn,
    ) -> None:
        spec = copy.deepcopy(base_spec)
        spec["name"] = f"{base_spec['name']}_{suffix}"
        spec["out_dir"] = f"{base_spec['out_dir']}_{suffix}_bundle"
        spec["intent"] = f"{base_spec.get('intent', '')} {intent_suffix}".strip()
        patch_fn(spec)
        variants.append(spec)

    def patch_all_windows(spec: dict, ue_id: str, patch: dict) -> None:
        for window in spec["windows"]:
            rule = window["ue_rules"][ue_id]
            rule.update(copy.deepcopy(patch))

    def patch_all_windows_custom(spec: dict, ue_id: str, fn) -> None:
        for window in spec["windows"]:
            fn(window["ue_rules"][ue_id], window)

    add_variant(
        "d1_ue4_decoy_mild",
        "Add a mild ue4 history-side decoy without making its instantaneous cost clearly weak.",
        lambda spec: patch_all_windows_custom(
            spec,
            "4",
            lambda rule, _window: (
                rule.__setitem__("history_offsets", _offset_plus(rule["history_offsets"], 0.45)),
                rule.__setitem__("rb_scale", round(float(rule["rb_scale"]) * 0.99, 3)),
            ),
        ),
    )
    add_variant(
        "d2_ue4_decoy_medium",
        "Strengthen the ue4 history-side decoy while keeping its current CQI relatively high.",
        lambda spec: patch_all_windows_custom(
            spec,
            "4",
            lambda rule, _window: (
                rule.__setitem__("history_offsets", _offset_plus(rule["history_offsets"], 0.75)),
                rule.__setitem__("rb_scale", round(float(rule["rb_scale"]) * 0.97, 3)),
                rule.__setitem__("previous_quality", 1),
            ),
        ),
    )
    add_variant(
        "d3_ue5_decoy_mild",
        "Use ue5 as the history-side decoy instead of ue4, to see whether the baseline is more sensitive to that flank.",
        lambda spec: patch_all_windows_custom(
            spec,
            "5",
            lambda rule, _window: (
                rule.__setitem__("history_offsets", _offset_plus(rule["history_offsets"], 0.5)),
                rule.__setitem__("rb_scale", round(float(rule["rb_scale"]) * 0.985, 3)),
                rule.__setitem__("previous_quality", 3),
            ),
        ),
    )
    add_variant(
        "d4_dual_decoy_mild",
        "Spread the history conflict across ue4 and ue5 so the weak pair is less trivially isolated by non-temporal ranking.",
        lambda spec: (
            patch_all_windows_custom(
                spec,
                "4",
                lambda rule, _window: (
                    rule.__setitem__("history_offsets", _offset_plus(rule["history_offsets"], 0.35)),
                    rule.__setitem__("rb_scale", round(float(rule["rb_scale"]) * 0.99, 3)),
                ),
            ),
            patch_all_windows_custom(
                spec,
                "5",
                lambda rule, _window: (
                    rule.__setitem__("history_offsets", _offset_plus(rule["history_offsets"], 0.35)),
                    rule.__setitem__("rb_scale", round(float(rule["rb_scale"]) * 0.99, 3)),
                    rule.__setitem__("previous_quality", 3),
                ),
            ),
        ),
    )
    add_variant(
        "d5_tighter_ue6_mild_ue4",
        "Keep ue4 mildly confusing, but slightly reduce ue6 cost distinctiveness to avoid giving resource-cost a free answer.",
        lambda spec: (
            patch_all_windows_custom(
                spec,
                "4",
                lambda rule, _window: rule.__setitem__(
                    "history_offsets",
                    _offset_plus(rule["history_offsets"], 0.45),
                ),
            ),
            patch_all_windows_custom(
                spec,
                "6",
                lambda rule, _window: (
                    rule.__setitem__("rb_scale", round(float(rule["rb_scale"]) + 0.04, 3)),
                    rule.__setitem__("cqi_now_raw", round(float(rule["cqi_now_raw"]) + 0.1, 3)),
                ),
            ),
        ),
    )
    add_variant(
        "d6_weaker_ue2_stronger_decoy",
        "Increase the asymmetry between the two true weak users while also creating a stronger decoy flank.",
        lambda spec: (
            patch_all_windows_custom(
                spec,
                "2",
                lambda rule, _window: (
                    rule.__setitem__("rb_scale", round(float(rule["rb_scale"]) - 0.03, 3)),
                    rule.__setitem__("cqi_now_raw", round(float(rule["cqi_now_raw"]) - 0.1, 3)),
                ),
            ),
            patch_all_windows_custom(
                spec,
                "4",
                lambda rule, _window: (
                    rule.__setitem__("history_offsets", _offset_plus(rule["history_offsets"], 0.8)),
                    rule.__setitem__("rb_scale", round(float(rule["rb_scale"]) * 0.97, 3)),
                ),
            ),
        ),
    )
    return variants


def _run(command: list[str], *, cwd: Path) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.returncode, completed.stdout + completed.stderr


def _main_comparison_map(path: Path) -> dict[str, dict[str, str]]:
    rows = _read_csv(path)
    return {row["method"]: row for row in rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-spec",
        type=Path,
        default=Path("p3_6r4_q10_history_conflict_spec.json"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("q10_history_conflict_variant_search"),
    )
    parser.add_argument("--feature-mode", default="history_cost_quality")
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--seed", type=int, default=9)
    args = parser.parse_args()

    base_spec_path = (ROOT / args.base_spec).resolve() if not args.base_spec.is_absolute() else args.base_spec.resolve()
    out_dir = (ROOT / args.out_dir).resolve() if not args.out_dir.is_absolute() else args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    specs_dir = out_dir / "specs"
    runs_dir = out_dir / "runs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    base_spec = _load_json(base_spec_path)
    variant_specs = _build_variant_specs(base_spec)
    leaderboard_rows: list[dict] = []

    for index, spec in enumerate(variant_specs, start=1):
        spec_path = specs_dir / f"{index:02d}_{spec['name']}.json"
        _save_json(spec_path, spec)

        build_code, build_output = _run(
            [sys.executable, str(ROOT / "build_family_window_transform_bundle.py"), "--spec", str(spec_path)],
            cwd=ROOT,
        )
        build_log_path = runs_dir / f"{index:02d}_{spec['name']}_build.log"
        build_log_path.write_text(build_output, encoding="utf-8")
        if build_code != 0:
            leaderboard_rows.append(
                {
                    "rank_key": -999.0,
                    "variant_name": spec["name"],
                    "status": f"build_failed_{build_code}",
                    "teacher_minus_resource_cost": "",
                    "teacher_minus_cqi": "",
                    "teacher_utility": "",
                    "resource_cost_utility": "",
                    "legra_utility": "",
                    "train_positive_gain_count": "",
                    "test_positive_gain_count": "",
                    "bundle_dir": spec["out_dir"],
                    "spec_path": str(spec_path),
                }
            )
            continue

        eval_dir = runs_dir / f"{index:02d}_{spec['name']}_{args.feature_mode}"
        eval_dir.mkdir(parents=True, exist_ok=True)
        eval_code, eval_output = _run(
            [
                sys.executable,
                str(ROOT / "run_focused_family_temporal_learner.py"),
                "--bundle-dir",
                str(ROOT / spec["out_dir"] / "bundle"),
                "--out-dir",
                str(eval_dir),
                "--serving-gnb",
                base_spec["family"]["serving_gnb"],
                "--ue-ids",
                base_spec["family"]["target_ue_ids"],
                "--train-window-start",
                "27.7",
                "--train-window-end",
                "27.9",
                "--test-window-start",
                "28.0",
                "--test-window-end",
                "28.2",
                "--feature-mode",
                args.feature_mode,
                "--epochs",
                str(args.epochs),
                "--seed",
                str(args.seed),
            ],
            cwd=ROOT,
        )
        (eval_dir / "run.log").write_text(eval_output, encoding="utf-8")
        if eval_code != 0:
            leaderboard_rows.append(
                {
                    "rank_key": -998.0,
                    "variant_name": spec["name"],
                    "status": f"eval_failed_{eval_code}",
                    "teacher_minus_resource_cost": "",
                    "teacher_minus_cqi": "",
                    "teacher_utility": "",
                    "resource_cost_utility": "",
                    "legra_utility": "",
                    "train_positive_gain_count": "",
                    "test_positive_gain_count": "",
                    "bundle_dir": spec["out_dir"],
                    "spec_path": str(spec_path),
                }
            )
            continue

        comparison = _main_comparison_map(eval_dir / "main_comparison.csv")
        summary = json.loads((eval_dir / "split_summary.json").read_text(encoding="utf-8"))
        teacher_utility = float(comparison["Offline teacher"]["utility"])
        resource_cost_utility = float(comparison["Resource-cost k-means"]["utility"])
        cqi_utility = float(comparison["CQI k-means"]["utility"])
        legra_utility = float(comparison["LE-GRA MVP"]["utility"])
        row = {
            "rank_key": teacher_utility - resource_cost_utility,
            "variant_name": spec["name"],
            "status": "ok",
            "teacher_minus_resource_cost": teacher_utility - resource_cost_utility,
            "teacher_minus_cqi": teacher_utility - cqi_utility,
            "teacher_utility": teacher_utility,
            "resource_cost_utility": resource_cost_utility,
            "legra_utility": legra_utility,
            "train_positive_gain_count": summary["train_positive_gain_count"],
            "test_positive_gain_count": summary["test_positive_gain_count"],
            "bundle_dir": spec["out_dir"],
            "spec_path": str(spec_path),
        }
        leaderboard_rows.append(row)

    leaderboard_rows.sort(
        key=lambda row: (
            float(row["rank_key"]),
            float(row["teacher_utility"] or -1.0),
            float(row["test_positive_gain_count"] or -1.0),
        ),
        reverse=True,
    )
    for row in leaderboard_rows:
        row.pop("rank_key", None)
    _write_csv(out_dir / "leaderboard.csv", leaderboard_rows)

    print("q10 history-conflict variant search:")
    for row in leaderboard_rows:
        if row["status"] != "ok":
            print(f"  {row['variant_name']}: {row['status']}")
            continue
        print(
            "  "
            f"{row['variant_name']}: gap={float(row['teacher_minus_resource_cost']):.4f}, "
            f"teacher={float(row['teacher_utility']):.4f}, "
            f"resource_cost={float(row['resource_cost_utility']):.4f}, "
            f"test_positive={row['test_positive_gain_count']}"
        )


if __name__ == "__main__":
    main()
