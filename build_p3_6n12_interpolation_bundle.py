"""Build an interpolation variant between n10 and n11.

This script starts from the successful `n10` late-state-hold bundle and applies
controllable simple-feature compression on the late window `27.9s ~ 28.8s`.
It is meant for threshold sweeps, not one-off hand-edited redesigns.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6n10_late_state_hold_bundle"

TARGET_GNB = "gnb_2"
TARGET_UE_IDS = "3|4|5|6"
LATE_START_S = 27.9
LATE_END_S = 28.8


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _clip_cqi(value: float) -> float:
    return max(1.0, min(15.0, value))


def _matching_target_scenarios(bundle_root: Path) -> set[str]:
    _, scenario_rows = _read_csv(bundle_root / "bundle" / "scenarios.csv")
    _, user_rows = _read_csv(bundle_root / "bundle" / "users.csv")
    users_by_scenario: dict[str, list[dict[str, str]]] = {}
    for row in user_rows:
        users_by_scenario.setdefault(row["scenario_id"], []).append(row)

    matched: set[str] = set()
    for row in scenario_rows:
        ts = float(row["timestamp_s"])
        if row["serving_gnb"] != TARGET_GNB or ts < LATE_START_S - 1e-9 or ts > LATE_END_S + 1e-9:
            continue
        family = sorted(
            users_by_scenario.get(row["scenario_id"], []),
            key=lambda item: int(item["user_index"]),
        )
        if "|".join(item["ue_id"] for item in family) == TARGET_UE_IDS:
            matched.add(row["scenario_id"])
    return matched


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--ue4-uplift", type=float, default=0.0)
    parser.add_argument("--ue5-uplift", type=float, default=0.0)
    parser.add_argument("--strong-downshift", type=float, default=0.0)
    parser.add_argument("--weak-prevq", type=int, default=1)
    parser.add_argument("--strong-prevq", type=int, default=4)
    parser.add_argument("--label", type=str, default="n12_interpolation")
    args = parser.parse_args()

    if args.out_dir.exists():
        shutil.rmtree(args.out_dir)
    shutil.copytree(SRC, args.out_dir)

    target_scenario_ids = _matching_target_scenarios(args.out_dir)

    user_path = args.out_dir / "bundle" / "users.csv"
    user_fields, user_rows = _read_csv(user_path)
    touched = 0
    for row in user_rows:
        if row["scenario_id"] not in target_scenario_ids:
            continue
        ue_id = row["ue_id"]
        current = float(row["cqi_now_raw"])
        if ue_id == "4":
            adjusted = _clip_cqi(current + args.ue4_uplift)
            row["previous_quality"] = str(args.weak_prevq)
            row["cqi_now_raw"] = f"{adjusted:.2f}"
            row["cqi_now"] = str(int(round(adjusted)))
            row["cqi_t_minus_4"] = f"{_clip_cqi(adjusted - 2.4):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(adjusted - 2.0):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(adjusted - 1.6):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(adjusted - 1.2):.2f}"
            touched += 1
        elif ue_id == "5":
            adjusted = _clip_cqi(current + args.ue5_uplift)
            row["previous_quality"] = str(args.weak_prevq)
            row["cqi_now_raw"] = f"{adjusted:.2f}"
            row["cqi_now"] = str(int(round(adjusted)))
            row["cqi_t_minus_4"] = f"{_clip_cqi(adjusted - 1.0):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(adjusted - 0.8):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(adjusted - 0.5):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(adjusted - 0.3):.2f}"
            touched += 1
        elif ue_id in {"3", "6"} and args.strong_downshift > 0.0:
            adjusted = _clip_cqi(current - args.strong_downshift)
            row["previous_quality"] = str(args.strong_prevq)
            row["cqi_now_raw"] = f"{adjusted:.2f}"
            row["cqi_now"] = str(int(round(adjusted)))
            row["cqi_t_minus_4"] = f"{_clip_cqi(adjusted - 0.6):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(adjusted - 0.4):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(adjusted - 0.2):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(adjusted - 0.1):.2f}"
            touched += 1
    _write_csv(user_path, user_fields, user_rows)

    metadata_path = args.out_dir / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": args.label,
        "base_bundle": SRC.name,
        "target_family": f"{TARGET_UE_IDS}@{TARGET_GNB}",
        "late_start_s": LATE_START_S,
        "late_end_s": LATE_END_S,
        "ue4_uplift": args.ue4_uplift,
        "ue5_uplift": args.ue5_uplift,
        "strong_downshift": args.strong_downshift,
        "weak_prevq": args.weak_prevq,
        "strong_prevq": args.strong_prevq,
        "intent": (
            "interpolate between n10 and n11 to locate the threshold where the "
            "late pair segment survives teacher-side but simple inference begins "
            "to become insufficient"
        ),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6n-12 interpolation bundle:")
    print(f"  out_dir={args.out_dir}")
    print(f"  ue4_uplift={args.ue4_uplift}")
    print(f"  ue5_uplift={args.ue5_uplift}")
    print(f"  strong_downshift={args.strong_downshift}")
    print(f"  weak_prevq={args.weak_prevq}")
    print(f"  strong_prevq={args.strong_prevq}")
    print(f"  target_scenarios={len(target_scenario_ids)}")
    print(f"  touched_rows={touched}")


if __name__ == "__main__":
    main()
