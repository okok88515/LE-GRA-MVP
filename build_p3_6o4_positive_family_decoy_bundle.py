"""Build the P3.6o-4 positive-family decoy bundle on 0|1|2|3|4@gnb_2."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6i2_coupled_bundle"
DST = ROOT / "p3_6o4_positive_family_decoy_bundle"
TARGET_GNB = "gnb_2"
TARGET_UE_IDS = "0|1|2|3|4"
WINDOW_START_S = 18.7
WINDOW_END_S = 19.2


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
    if rate_kbps >= 984.0:
        return 0.975
    if rate_kbps >= 808.0:
        return 0.965
    return 0.985


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
            if row.get("scenario_id") not in target_scenario_ids:
                continue
            if row["ue_id"] != "4":
                continue
            rate = float(row["rate_kbps"])
            row["rate_kbps"] = f"{max(1.0, rate * _ue4_factor(rate)):.6f}"
            modified += 1
        _write_csv(path, fields, rows)
        rb_mod_counts[f"{rel_dir}_{filename}"] = modified

    users_path = DST / "bundle" / "users.csv"
    user_fields, user_rows = _read_csv(users_path)
    pq_modified = 0
    history_modified = 0
    for row in user_rows:
        if row["scenario_id"] not in target_scenario_ids:
            continue
        current = float(row["cqi_now_raw"])
        if row["ue_id"] == "3":
            row["previous_quality"] = "1"
            row["cqi_t_minus_4"] = f"{_clip_cqi(current + 0.7):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(current + 0.4):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(current - 0.1):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(current - 1.0):.2f}"
            pq_modified += 1
            history_modified += 1
        elif row["ue_id"] == "4":
            row["previous_quality"] = "1"
            row["cqi_t_minus_4"] = f"{_clip_cqi(current + 0.9):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(current + 0.8):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(current + 0.5):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(current - 0.6):.2f}"
            pq_modified += 1
            history_modified += 1
        elif row["ue_id"] in {"0", "1", "2"}:
            row["previous_quality"] = "2"
            pq_modified += 1
    _write_csv(users_path, user_fields, user_rows)

    metadata_path = DST / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6o4_positive_family_decoy_bundle",
        "base_bundle": "p3_6i2_coupled_bundle",
        "target_family": f"{TARGET_UE_IDS}@{TARGET_GNB}",
        "window_s": [WINDOW_START_S, WINDOW_END_S],
        "intent": (
            "preserve the existing positive-gain ue3 isolation regime while "
            "injecting ue4 as a lighter temporal decoy that may alter split "
            "structure without destroying the gain basin"
        ),
        "rate_transforms": {
            "ue4": {">=984_kbps": 0.975, ">=808_kbps": 0.965, "else": 0.985},
        },
        "previous_quality_override": {"3": 1, "4": 1, "0": 2, "1": 2, "2": 2},
        "history_patterns": {
            "ue3": "primary_weak_recent_decline",
            "ue4": "light_decoy_late_drop",
        },
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6o-4 positive-family decoy bundle:")
    print(f"  copied_from={SRC.name}")
    print(f"  target_family={TARGET_UE_IDS}@{TARGET_GNB}")
    print(f"  target_scenarios={len(target_scenario_ids)}")
    for key, value in rb_mod_counts.items():
        print(f"  {key}_modified={value}")
    print(f"  previous_quality_modified_rows={pq_modified}")
    print(f"  history_modified_rows={history_modified}")


if __name__ == "__main__":
    main()
