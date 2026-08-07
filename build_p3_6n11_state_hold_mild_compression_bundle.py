"""Build P3.6n-11 by mildly compressing simple feature separability on top of n10."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6n10_late_state_hold_bundle"
DST = ROOT / "p3_6n11_state_hold_mild_compression_bundle"

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
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)

    target_scenario_ids = _matching_target_scenarios(DST)

    user_path = DST / "bundle" / "users.csv"
    user_fields, user_rows = _read_csv(user_path)
    touched = 0
    for row in user_rows:
        if row["scenario_id"] not in target_scenario_ids:
            continue
        ue_id = row["ue_id"]
        current = float(row["cqi_now_raw"])
        if ue_id == "4":
            adjusted = _clip_cqi(current + 0.45)
            row["previous_quality"] = "2"
            row["cqi_now_raw"] = f"{adjusted:.2f}"
            row["cqi_now"] = str(int(round(adjusted)))
            row["cqi_t_minus_4"] = f"{_clip_cqi(adjusted - 1.8):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(adjusted - 1.5):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(adjusted - 1.2):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(adjusted - 0.8):.2f}"
            touched += 1
        elif ue_id == "5":
            adjusted = _clip_cqi(current + 0.25)
            row["previous_quality"] = "2"
            row["cqi_now_raw"] = f"{adjusted:.2f}"
            row["cqi_now"] = str(int(round(adjusted)))
            row["cqi_t_minus_4"] = f"{_clip_cqi(adjusted - 0.9):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(adjusted - 0.7):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(adjusted - 0.5):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(adjusted - 0.3):.2f}"
            touched += 1
        elif ue_id in {"3", "6"}:
            adjusted = _clip_cqi(current - 0.25)
            row["previous_quality"] = "3"
            row["cqi_now_raw"] = f"{adjusted:.2f}"
            row["cqi_now"] = str(int(round(adjusted)))
            row["cqi_t_minus_4"] = f"{_clip_cqi(adjusted - 0.5):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(adjusted - 0.4):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(adjusted - 0.2):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(adjusted - 0.1):.2f}"
            touched += 1
    _write_csv(user_path, user_fields, user_rows)

    metadata_path = DST / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6n11_state_hold_mild_compression_bundle",
        "base_bundle": SRC.name,
        "target_family": f"{TARGET_UE_IDS}@{TARGET_GNB}",
        "late_start_s": LATE_START_S,
        "late_end_s": LATE_END_S,
        "intent": (
            "keep the successful n10 late pair segment, but mildly compress the "
            "simple CQI / previous-quality separability so we can test whether "
            "this source can move from easy toward learner-hard without losing "
            "the teacher-positive regime"
        ),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6n-11 state-hold mild compression bundle:")
    print(f"  target_family={TARGET_UE_IDS}@{TARGET_GNB}")
    print(f"  late_window_s={LATE_START_S}~{LATE_END_S}")
    print(f"  target_scenarios={len(target_scenario_ids)}")
    print(f"  touched_rows={touched}")


if __name__ == "__main__":
    main()
