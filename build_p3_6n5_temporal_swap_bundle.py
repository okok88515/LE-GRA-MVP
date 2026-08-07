"""Build P3.6n-5 by creating a temporal weak-order swap between ue5 and ue4."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6n3_isolate_ue5_bundle"
DST = ROOT / "p3_6n5_temporal_swap_bundle"

TARGET_GNB = "gnb_2"
TARGET_UE_IDS = "3|4|5|6"
WINDOW_START_S = 25.8
WINDOW_END_S = 29.9
SWAP_START_S = 27.9

EARLY_PRIMARY_WEAK = "5"
LATE_PRIMARY_WEAK = "4"
SECONDARY_LATE_UE = "5"


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


def _ue4_factor(rate_kbps: float) -> float:
    if rate_kbps >= 1128.0:
        return 0.46
    if rate_kbps >= 984.0:
        return 0.42
    return 0.62


def _ue5_recover_factor(rate_kbps: float) -> float:
    if rate_kbps >= 360.0:
        return 1.24
    if rate_kbps >= 240.0:
        return 1.18
    return 1.12


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

    _, scenario_rows = _read_csv(DST / "bundle" / "scenarios.csv")
    target_scenario_ids = _matching_target_scenarios()
    late_target_ids = {
        row["scenario_id"]
        for row in scenario_rows
        if row["scenario_id"] in target_scenario_ids and float(row["timestamp_s"]) >= SWAP_START_S - 1e-9
    }

    for rel_dir, filename in [("bundle", "rb_rates.csv"), ("radio", "radio_rbs.csv")]:
        path = DST / rel_dir / filename
        fields, rows = _read_csv(path)
        for row in rows:
            if "scenario_id" in row:
                sid = row["scenario_id"]
                if sid not in late_target_ids:
                    continue
                ue_id = row["ue_id"]
            else:
                sid = None
                ts = float(row["timestamp_s"])
                if row["serving_gnb"] != TARGET_GNB or ts < SWAP_START_S - 1e-9 or ts > WINDOW_END_S + 1e-9:
                    continue
                ue_id = row["ue_id"]
            rate = float(row["rate_kbps"])
            if ue_id == LATE_PRIMARY_WEAK:
                row["rate_kbps"] = f"{max(1.0, rate * _ue4_factor(rate)):.6f}"
            elif ue_id == SECONDARY_LATE_UE:
                row["rate_kbps"] = f"{max(1.0, rate * _ue5_recover_factor(rate)):.6f}"
        _write_csv(path, fields, rows)

    users_path = DST / "bundle" / "users.csv"
    user_fields, user_rows = _read_csv(users_path)
    late_mods = 0
    for row in user_rows:
        if row["scenario_id"] not in late_target_ids:
            continue
        ue_id = row["ue_id"]
        current = float(row["cqi_now_raw"])
        if ue_id == LATE_PRIMARY_WEAK:
            adjusted = max(1.0, current - 3.2)
            row["previous_quality"] = "1"
            row["cqi_now_raw"] = f"{adjusted:.2f}"
            row["cqi_now"] = str(int(round(adjusted)))
            row["cqi_t_minus_4"] = f"{_clip_cqi(adjusted - 3.0):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(adjusted - 2.6):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(adjusted - 2.2):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(adjusted - 1.8):.2f}"
            late_mods += 1
        elif ue_id == SECONDARY_LATE_UE:
            adjusted = _clip_cqi(current + 1.6)
            row["previous_quality"] = "2"
            row["cqi_now_raw"] = f"{adjusted:.2f}"
            row["cqi_now"] = str(int(round(adjusted)))
            row["cqi_t_minus_4"] = f"{_clip_cqi(adjusted - 1.2):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(adjusted - 0.8):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(adjusted - 0.6):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(adjusted - 0.4):.2f}"
            late_mods += 1
    _write_csv(users_path, user_fields, user_rows)

    metadata_path = DST / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6n5_temporal_swap_bundle",
        "base_bundle": SRC.name,
        "target_family": f"{TARGET_UE_IDS}@{TARGET_GNB}",
        "window_start_s": WINDOW_START_S,
        "window_end_s": WINDOW_END_S,
        "swap_start_s": SWAP_START_S,
        "intent": (
            "start from ue5-isolation and create a late-window swap so the weak "
            "identity moves from ue5 to ue4, creating temporal weak-order ambiguity"
        ),
        "early_primary_weak_ue_id": EARLY_PRIMARY_WEAK,
        "late_primary_weak_ue_id": LATE_PRIMARY_WEAK,
        "late_secondary_recovered_ue_id": SECONDARY_LATE_UE,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6n-5 temporal-swap bundle:")
    print(f"  target_family={TARGET_UE_IDS}@{TARGET_GNB}")
    print(f"  target_window_s={WINDOW_START_S}~{WINDOW_END_S}")
    print(f"  swap_start_s={SWAP_START_S}")
    print(f"  target_scenarios={len(target_scenario_ids)}")
    print(f"  late_modified_user_rows={late_mods}")


if __name__ == "__main__":
    main()
