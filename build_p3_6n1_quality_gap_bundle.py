"""Build P3.6n-1 by injecting a continuity/quality-memory gap into 3|4|5|6 @ gnb_2.

Start from the original coupled bundle and preserve the existing CQI / RB-cost
structure. Only reshape the quality-memory signal so `ue 5` becomes a sustained
weak-continuity user while the peers stay continuity-stable.
"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6i2_coupled_bundle"
DST = ROOT / "p3_6n1_quality_gap_bundle"

TARGET_GNB = "gnb_2"
TARGET_UE_IDS = "3|4|5|6"
WINDOW_START_S = 25.8
WINDOW_END_S = 29.9

PRIMARY_WEAK_UE = "5"
STABLE_UE_IDS = {"3", "4", "6"}


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


def _matching_target_scenarios() -> set[str]:
    _, scenario_rows = _read_csv(DST / "bundle" / "scenarios.csv")
    _, user_rows = _read_csv(DST / "bundle" / "users.csv")
    users_by_scenario: dict[str, list[dict[str, str]]] = {}
    for row in user_rows:
        users_by_scenario.setdefault(row["scenario_id"], []).append(row)

    matched: set[str] = set()
    for row in scenario_rows:
        ts = float(row["timestamp_s"])
        if row["serving_gnb"] != TARGET_GNB or ts < WINDOW_START_S - 1e-9 or ts > WINDOW_END_S + 1e-9:
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

    target_scenario_ids = _matching_target_scenarios()

    users_path = DST / "bundle" / "users.csv"
    user_fields, user_rows = _read_csv(users_path)
    modified_rows = 0
    weak_rows = 0
    stable_rows = 0
    for row in user_rows:
        if row["scenario_id"] not in target_scenario_ids:
            continue
        ue_id = row["ue_id"]
        current = float(row["cqi_now_raw"])
        if ue_id == PRIMARY_WEAK_UE:
            row["previous_quality"] = "1"
            # Make the recent history look persistently weak rather than just instantaneously weak.
            row["cqi_t_minus_4"] = f"{_clip_cqi(current - 2.6):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(current - 2.2):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(current - 1.8):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(current - 1.2):.2f}"
            weak_rows += 1
            modified_rows += 1
        elif ue_id in STABLE_UE_IDS:
            row["previous_quality"] = "4"
            # Keep peers history smooth and slightly stronger to reinforce continuity contrast.
            row["cqi_t_minus_4"] = f"{_clip_cqi(current - 0.2):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(current - 0.1):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(current):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(current):.2f}"
            stable_rows += 1
            modified_rows += 1
    _write_csv(users_path, user_fields, user_rows)

    metadata_path = DST / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6n1_quality_gap_bundle",
        "base_bundle": SRC.name,
        "target_family": f"{TARGET_UE_IDS}@{TARGET_GNB}",
        "window_start_s": WINDOW_START_S,
        "window_end_s": WINDOW_END_S,
        "intent": (
            "inject a sustained previous-quality / continuity gap for ue5 while "
            "keeping the original CQI and RB-cost structure of the 3|4|5|6 family"
        ),
        "primary_weak_ue_id": PRIMARY_WEAK_UE,
        "stable_peer_ue_ids": sorted(STABLE_UE_IDS),
        "weak_previous_quality": 1,
        "stable_previous_quality": 4,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6n-1 quality-gap bundle:")
    print(f"  target_family={TARGET_UE_IDS}@{TARGET_GNB}")
    print(f"  target_window_s={WINDOW_START_S}~{WINDOW_END_S}")
    print(f"  target_scenarios={len(target_scenario_ids)}")
    print(f"  modified_user_rows={modified_rows}")
    print(f"  weak_rows={weak_rows}")
    print(f"  stable_rows={stable_rows}")


if __name__ == "__main__":
    main()
