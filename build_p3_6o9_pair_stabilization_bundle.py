"""Build the P3.6o-9 pair-stabilization bundle from o8."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6o8_gain_recovery_bundle"
DST = ROOT / "p3_6o9_pair_stabilization_bundle"
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
            if row["ue_id"] == "4":
                rate = float(row["rate_kbps"])
                row["rate_kbps"] = f"{max(1.0, rate * 0.95):.6f}"
                modified += 1
            elif row["ue_id"] == "0":
                rate = float(row["rate_kbps"])
                row["rate_kbps"] = f"{max(1.0, rate * 1.02):.6f}"
                modified += 1
        _write_csv(path, fields, rows)
        rb_mod_counts[f"{rel_dir}_{filename}"] = modified

    users_path = DST / "bundle" / "users.csv"
    user_fields, user_rows = _read_csv(users_path)
    cqi_modified = 0
    history_modified = 0
    for row in user_rows:
        if row["scenario_id"] not in target_scenario_ids:
            continue
        if row["ue_id"] == "4":
            adjusted = _clip_cqi(float(row["cqi_now_raw"]) - 0.25)
            row["cqi_now_raw"] = f"{adjusted:.2f}"
            row["cqi_now"] = str(int(round(adjusted)))
            row["cqi_t_minus_4"] = f"{_clip_cqi(adjusted + 0.7):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(adjusted + 0.3):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(adjusted - 0.5):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(adjusted - 1.6):.2f}"
            cqi_modified += 1
            history_modified += 1
        elif row["ue_id"] == "0":
            adjusted = _clip_cqi(float(row["cqi_now_raw"]) + 0.15)
            row["cqi_now_raw"] = f"{adjusted:.2f}"
            row["cqi_now"] = str(int(round(adjusted)))
            row["cqi_t_minus_4"] = f"{_clip_cqi(adjusted + 0.5):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(adjusted + 0.4):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(adjusted + 0.2):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(adjusted + 0.1):.2f}"
            cqi_modified += 1
            history_modified += 1
    _write_csv(users_path, user_fields, user_rows)

    metadata_path = DST / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6o9_pair_stabilization_bundle",
        "base_bundle": SRC.name,
        "target_family": f"{TARGET_UE_IDS}@{TARGET_GNB}",
        "window_s": [WINDOW_START_S, WINDOW_END_S],
        "intent": (
            "stabilize o8's first positive {ue3, ue4} split by slightly pulling "
            "ue0 further into the strong cluster and deepening ue4 only a little"
        ),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6o-9 pair-stabilization bundle:")
    print(f"  copied_from={SRC.name}")
    print(f"  target_family={TARGET_UE_IDS}@{TARGET_GNB}")
    print(f"  target_scenarios={len(target_scenario_ids)}")
    for key, value in rb_mod_counts.items():
        print(f"  {key}_modified={value}")
    print(f"  cqi_modified_rows={cqi_modified}")
    print(f"  history_modified_rows={history_modified}")


if __name__ == "__main__":
    main()
