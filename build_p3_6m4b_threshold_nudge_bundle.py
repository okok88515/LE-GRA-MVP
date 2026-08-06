"""Build P3.6m-4b by nudging the 43.6 snapshot across the positive threshold.

Start from the successful P3.6m-2 regime and modify only `ue 15` at `43.6s` so
the decoy-positive regime may extend from `43.7~43.9` to `43.6~43.9`.
"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6m2_positive_family_decoy_bundle"
DST = ROOT / "p3_6m4b_threshold_nudge_bundle"
TARGET_GNB = "gnb_1"
TARGET_UE_IDS = "0|1|15|2|3|4|5"
TARGET_TIMESTAMP_S = 43.6
PRIMARY_UE_ID = "15"


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


def _ue15_factor(rate_kbps: float) -> float:
    if rate_kbps >= 1128.0:
        return 0.58
    if rate_kbps >= 984.0:
        return 0.55
    return 0.68


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
        if row["serving_gnb"] != TARGET_GNB or abs(float(row["timestamp_s"]) - TARGET_TIMESTAMP_S) > 1e-9:
            continue
        family = sorted(
            scenario_users.get(row["scenario_id"], []),
            key=lambda item: int(item["user_index"]),
        )
        if "|".join(item["ue_id"] for item in family) == TARGET_UE_IDS:
            target_scenario_ids.add(row["scenario_id"])

    for rel_dir, filename in [("bundle", "rb_rates.csv"), ("radio", "radio_rbs.csv")]:
        path = DST / rel_dir / filename
        fields, rows = _read_csv(path)
        for row in rows:
            if "scenario_id" in row:
                if row["scenario_id"] not in target_scenario_ids or row["ue_id"] != PRIMARY_UE_ID:
                    continue
            else:
                if (
                    row["serving_gnb"] != TARGET_GNB
                    or abs(float(row["timestamp_s"]) - TARGET_TIMESTAMP_S) > 1e-9
                    or row["ue_id"] != PRIMARY_UE_ID
                ):
                    continue
            rate = float(row["rate_kbps"])
            row["rate_kbps"] = f"{max(1.0, rate * _ue15_factor(rate)):.6f}"
        _write_csv(path, fields, rows)

    users_path = DST / "bundle" / "users.csv"
    fields, rows = _read_csv(users_path)
    for row in rows:
        if row["scenario_id"] not in target_scenario_ids or row["ue_id"] != PRIMARY_UE_ID:
            continue
        current = float(row["cqi_now_raw"])
        row["cqi_now_raw"] = f"{_clip_cqi(current - 4.0):.2f}"
        row["cqi_now"] = str(int(round(float(row["cqi_now_raw"]))))
        row["cqi_t_minus_4"] = f"{_clip_cqi(float(row['cqi_now_raw']) + 1.0):.2f}"
        row["cqi_t_minus_3"] = f"{_clip_cqi(float(row['cqi_now_raw']) + 0.6):.2f}"
        row["cqi_t_minus_2"] = f"{_clip_cqi(float(row['cqi_now_raw']) + 0.2):.2f}"
        row["cqi_t_minus_1"] = f"{_clip_cqi(float(row['cqi_now_raw']) - 1.4):.2f}"
    _write_csv(users_path, fields, rows)

    metadata_path = DST / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6m4b_threshold_nudge_bundle",
        "base_bundle": SRC.name,
        "target_family": f"{TARGET_UE_IDS}@{TARGET_GNB}",
        "target_timestamp_s": TARGET_TIMESTAMP_S,
        "intent": (
            "nudge only ue15 at 43.6s so the existing decoy-positive regime may "
            "extend one step earlier without redesigning the whole window"
        ),
        "ue15_rate_factors": {">=1128_kbps": 0.58, ">=984_kbps": 0.55, "else": 0.68},
        "ue15_cqi_now_raw_delta": -4.0,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6m-4b threshold nudge bundle:")
    print(f"  target_family={TARGET_UE_IDS}@{TARGET_GNB}")
    print(f"  target_timestamp_s={TARGET_TIMESTAMP_S}")
    print(f"  target_scenarios={len(target_scenario_ids)}")


if __name__ == "__main__":
    main()
