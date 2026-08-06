"""Build the P3.6m-2 positive-family decoy bundle.

Starting from the real positive-gain family `0|1|15|2|3|4|5 @ gnb_1`, this
variant keeps `ue 15` as the true split-worthy weak user while injecting `ue 4`
as a lighter history-driven decoy.
"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6i2_coupled_bundle"
DST = ROOT / "p3_6m2_positive_family_decoy_bundle"
TARGET_GNB = "gnb_1"
TARGET_UE_IDS = "0|1|15|2|3|4|5"
WINDOW_START_S = 43.4
WINDOW_END_S = 43.9
PRIMARY_UE_ID = "15"
DECOY_UE_ID = "4"


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


def _ue4_decoy_factor(rate_kbps: float) -> float:
    if rate_kbps >= 1128.0:
        return 0.985
    if rate_kbps >= 984.0:
        return 0.980
    return 0.990


def main() -> None:
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)

    _, scenario_rows = _read_csv(DST / "bundle" / "scenarios.csv")
    _, user_rows = _read_csv(DST / "bundle" / "users.csv")
    scenario_users: dict[str, list[dict[str, str]]] = {}
    for row in user_rows:
        scenario_users.setdefault(row["scenario_id"], []).append(row)

    target_scenario_ids: set[str] = set()
    for row in scenario_rows:
        timestamp_s = float(row["timestamp_s"])
        if row["serving_gnb"] != TARGET_GNB or not (WINDOW_START_S <= timestamp_s <= WINDOW_END_S):
            continue
        family = sorted(
            scenario_users.get(row["scenario_id"], []),
            key=lambda item: int(item["user_index"]),
        )
        if "|".join(item["ue_id"] for item in family) == TARGET_UE_IDS:
            target_scenario_ids.add(row["scenario_id"])

    rb_mod_counts: dict[str, int] = {}
    for rel_dir, filename in [("bundle", "rb_rates.csv"), ("radio", "radio_rbs.csv")]:
        path = DST / rel_dir / filename
        fields, rows = _read_csv(path)
        modified = 0
        for row in rows:
            if "scenario_id" in row:
                if row["scenario_id"] not in target_scenario_ids:
                    continue
            else:
                timestamp_s = float(row["timestamp_s"])
                if row["serving_gnb"] != TARGET_GNB or not (WINDOW_START_S <= timestamp_s <= WINDOW_END_S):
                    continue
            if row["ue_id"] != DECOY_UE_ID:
                continue
            rate = float(row["rate_kbps"])
            row["rate_kbps"] = f"{max(1.0, rate * _ue4_decoy_factor(rate)):.6f}"
            modified += 1
        _write_csv(path, fields, rows)
        rb_mod_counts[f"{rel_dir}_{filename}"] = modified

    users_path = DST / "bundle" / "users.csv"
    user_fields, rows = _read_csv(users_path)
    decoy_history_rows = 0
    primary_history_rows = 0
    for row in rows:
        if row["scenario_id"] not in target_scenario_ids:
            continue
        current = float(row["cqi_now_raw"])
        if row["ue_id"] == DECOY_UE_ID:
            row["cqi_t_minus_4"] = f"{_clip_cqi(current + 0.9):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(current + 0.6):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(current + 0.1):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(current - 1.0):.2f}"
            decoy_history_rows += 1
        elif row["ue_id"] == PRIMARY_UE_ID:
            row["cqi_t_minus_4"] = f"{_clip_cqi(current + 1.0):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(current + 0.6):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(current + 0.2):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(current - 1.4):.2f}"
            primary_history_rows += 1
    _write_csv(users_path, user_fields, rows)

    metadata_path = DST / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6m2_positive_family_decoy_bundle",
        "base_bundle": "p3_6i2_coupled_bundle",
        "target_family": f"{TARGET_UE_IDS}@{TARGET_GNB}",
        "window_s": [WINDOW_START_S, WINDOW_END_S],
        "primary_weak_ue_id": PRIMARY_UE_ID,
        "decoy_ue_id": DECOY_UE_ID,
        "intent": (
            "preserve the real positive-gain ue15 isolation regime while "
            "injecting ue4 as a lighter history-driven decoy for learner-side "
            "ambiguity"
        ),
        "rate_transforms": {
            "ue4": {">=1128_kbps": 0.985, ">=984_kbps": 0.980, "else": 0.990},
        },
        "history_patterns": {
            "ue15": "reinforced_recent_decline_primary_weak",
            "ue4": "recent_decline_light_decoy",
        },
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6m-2 positive-family decoy bundle:")
    print(f"  copied_from={SRC.name}")
    print(f"  target_family={TARGET_UE_IDS}@{TARGET_GNB}")
    print(f"  target_scenarios={len(target_scenario_ids)}")
    for key, value in rb_mod_counts.items():
        print(f"  {key}_modified={value}")
    print(f"  primary_history_rows={primary_history_rows}")
    print(f"  decoy_history_rows={decoy_history_rows}")


if __name__ == "__main__":
    main()
