"""Build P3.6n-2 by combining continuity gap with tighter resource pressure.

Start from `p3_6n1_quality_gap_bundle` and make the `3|4|5|6 @ gnb_2` window
more likely to reward splitting by:

- preserving the quality-memory gap
- tightening the RB budget in the target window
- further weakening `ue 5` link quality / rate support
"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6n1_quality_gap_bundle"
DST = ROOT / "p3_6n2_quality_gap_pressure_bundle"

TARGET_GNB = "gnb_2"
TARGET_UE_IDS = "3|4|5|6"
WINDOW_START_S = 25.8
WINDOW_END_S = 29.9
PRIMARY_WEAK_UE = "5"
TARGET_RB_AVAILABLE = 5


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


def _ue5_factor(rate_kbps: float) -> float:
    if rate_kbps >= 984.0:
        return 0.68
    if rate_kbps >= 808.0:
        return 0.62
    return 0.78


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

    scenarios_path = DST / "bundle" / "scenarios.csv"
    scenario_fields, scenario_rows = _read_csv(scenarios_path)
    scenario_mods = 0
    for row in scenario_rows:
        if row["scenario_id"] in target_scenario_ids:
            row["rb_available"] = str(TARGET_RB_AVAILABLE)
            scenario_mods += 1
    _write_csv(scenarios_path, scenario_fields, scenario_rows)

    for rel_dir, filename in [("bundle", "rb_rates.csv"), ("radio", "radio_rbs.csv")]:
        path = DST / rel_dir / filename
        fields, rows = _read_csv(path)
        for row in rows:
            if "scenario_id" in row:
                if row["scenario_id"] not in target_scenario_ids or row["ue_id"] != PRIMARY_WEAK_UE:
                    continue
            else:
                ts = float(row["timestamp_s"])
                if (
                    row["serving_gnb"] != TARGET_GNB
                    or ts < WINDOW_START_S - 1e-9
                    or ts > WINDOW_END_S + 1e-9
                    or row["ue_id"] != PRIMARY_WEAK_UE
                ):
                    continue
            rate = float(row["rate_kbps"])
            row["rate_kbps"] = f"{max(1.0, rate * _ue5_factor(rate)):.6f}"
        _write_csv(path, fields, rows)

    users_path = DST / "bundle" / "users.csv"
    user_fields, user_rows = _read_csv(users_path)
    user_mods = 0
    for row in user_rows:
        if row["scenario_id"] not in target_scenario_ids or row["ue_id"] != PRIMARY_WEAK_UE:
            continue
        current = max(1.0, float(row["cqi_now_raw"]) - 1.2)
        row["cqi_now_raw"] = f"{current:.2f}"
        row["cqi_now"] = str(int(round(current)))
        row["cqi_t_minus_4"] = f"{_clip_cqi(current - 2.4):.2f}"
        row["cqi_t_minus_3"] = f"{_clip_cqi(current - 2.0):.2f}"
        row["cqi_t_minus_2"] = f"{_clip_cqi(current - 1.6):.2f}"
        row["cqi_t_minus_1"] = f"{_clip_cqi(current - 1.0):.2f}"
        user_mods += 1
    _write_csv(users_path, user_fields, user_rows)

    metadata_path = DST / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6n2_quality_gap_pressure_bundle",
        "base_bundle": SRC.name,
        "target_family": f"{TARGET_UE_IDS}@{TARGET_GNB}",
        "window_start_s": WINDOW_START_S,
        "window_end_s": WINDOW_END_S,
        "intent": (
            "start from the continuity-gap regime and add tighter RB pressure "
            "plus extra ue5 weakening so teacher splitting becomes worthwhile"
        ),
        "primary_weak_ue_id": PRIMARY_WEAK_UE,
        "target_rb_available": TARGET_RB_AVAILABLE,
        "ue5_cqi_now_raw_delta": -1.2,
        "ue5_rate_factor_schedule": {
            ">=984_kbps": 0.68,
            ">=808_kbps": 0.62,
            "else": 0.78,
        },
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6n-2 quality-gap pressure bundle:")
    print(f"  target_family={TARGET_UE_IDS}@{TARGET_GNB}")
    print(f"  target_window_s={WINDOW_START_S}~{WINDOW_END_S}")
    print(f"  target_scenarios={len(target_scenario_ids)}")
    print(f"  scenario_rows_modified={scenario_mods}")
    print(f"  weak_user_rows_modified={user_mods}")


if __name__ == "__main__":
    main()
