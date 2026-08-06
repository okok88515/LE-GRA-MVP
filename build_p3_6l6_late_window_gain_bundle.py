"""Build the P3.6l-6 late-window gain bundle from the l-4 regime."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6l4_primary_weak_bundle"
DST = ROOT / "p3_6l6_late_window_gain_bundle"
TARGET_GNB = "gnb_2"
TARGET_UE_IDS = "1|2|4|5"
WINDOW_START_S = 23.7
WINDOW_END_S = 23.9


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


def _ue4_late_factor(rate_kbps: float) -> float:
    if rate_kbps >= 1128.0:
        return 0.74
    if rate_kbps >= 984.0:
        return 0.70
    return 0.82


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
            if row.get("scenario_id") not in target_scenario_ids or row["ue_id"] != "4":
                continue
            rate = float(row["rate_kbps"])
            row["rate_kbps"] = f"{max(1.0, rate * _ue4_late_factor(rate)):.6f}"
            modified += 1
        _write_csv(path, fields, rows)
        rb_mod_counts[f"{rel_dir}_{filename}"] = modified

    users_path = DST / "bundle" / "users.csv"
    user_fields, user_rows = _read_csv(users_path)
    pq_modified = 0
    history_modified = 0
    for row in user_rows:
        if row["scenario_id"] not in target_scenario_ids or row["ue_id"] != "4":
            continue
        current = float(row["cqi_now_raw"])
        row["previous_quality"] = "0"
        row["cqi_t_minus_4"] = f"{_clip_cqi(current + 0.8):.2f}"
        row["cqi_t_minus_3"] = f"{_clip_cqi(current + 0.3):.2f}"
        row["cqi_t_minus_2"] = f"{_clip_cqi(current - 0.4):.2f}"
        row["cqi_t_minus_1"] = f"{_clip_cqi(current - 1.6):.2f}"
        pq_modified += 1
        history_modified += 1
    _write_csv(users_path, user_fields, user_rows)

    metadata_path = DST / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6l6_late_window_gain_bundle",
        "base_bundle": "p3_6l4_primary_weak_bundle",
        "target_family": f"{TARGET_UE_IDS}@{TARGET_GNB}",
        "window_s": [WINDOW_START_S, WINDOW_END_S],
        "intent": (
            "keep the l-4 split structure intact and only deepen ue4 weakness "
            "inside the late split window so tie-utility split may cross into "
            "positive gain without changing earlier family geometry"
        ),
        "late_rate_transform": {
            "ue4": {">=1128_kbps": 0.74, ">=984_kbps": 0.70, "else": 0.82},
        },
        "late_previous_quality_override": {"4": 0},
        "late_history_pattern": {"4": "deeper_recent_decline_only_inside_split_window"},
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6l-6 late-window gain bundle:")
    print(f"  copied_from={SRC.name}")
    print(f"  target_family={TARGET_UE_IDS}@{TARGET_GNB}")
    print(f"  target_scenarios={len(target_scenario_ids)}")
    for key, value in rb_mod_counts.items():
        print(f"  {key}_modified={value}")
    print(f"  previous_quality_modified_rows={pq_modified}")
    print(f"  history_modified_rows={history_modified}")


if __name__ == "__main__":
    main()
