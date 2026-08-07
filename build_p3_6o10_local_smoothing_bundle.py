"""Build the P3.6o-10 local-smoothing bundle from o8."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6o8_gain_recovery_bundle"
DST = ROOT / "p3_6o10_local_smoothing_bundle"
TARGET_GNB = "gnb_2"
TARGET_UE_IDS = "0|1|2|3|4"
WINDOW_START_S = 18.7
WINDOW_END_S = 19.2
SMOOTH_START_S = 18.8


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

    scenario_fields, scenario_rows = _read_csv(DST / "bundle" / "scenarios.csv")
    scenario_ts: dict[str, float] = {}

    _, user_rows = _read_csv(DST / "bundle" / "users.csv")
    scenario_users: dict[str, list[dict[str, str]]] = {}
    for row in user_rows:
        scenario_users.setdefault(row["scenario_id"], []).append(row)

    target_scenario_ids: set[str] = set()
    smooth_target_ids: set[str] = set()
    for row in scenario_rows:
        timestamp_s = float(row["timestamp_s"])
        scenario_ts[row["scenario_id"]] = timestamp_s
        if row["serving_gnb"] != TARGET_GNB or not (WINDOW_START_S <= timestamp_s <= WINDOW_END_S):
            continue
        family = sorted(
            scenario_users.get(row["scenario_id"], []),
            key=lambda item: int(item["user_index"]),
        )
        if "|".join(item["ue_id"] for item in family) == TARGET_UE_IDS:
            target_scenario_ids.add(row["scenario_id"])
            if timestamp_s >= SMOOTH_START_S - 1e-9:
                smooth_target_ids.add(row["scenario_id"])

    rb_mod_counts: dict[str, int] = {}
    for rel_dir, filename in [("bundle", "rb_rates.csv"), ("radio", "radio_rbs.csv")]:
        path = DST / rel_dir / filename
        fields, rows = _read_csv(path)
        modified = 0
        for row in rows:
            if row.get("scenario_id") not in smooth_target_ids:
                continue
            rate = float(row["rate_kbps"])
            if row["ue_id"] == "0":
                row["rate_kbps"] = f"{max(1.0, rate * 1.03):.6f}"
                modified += 1
            elif row["ue_id"] == "1":
                row["rate_kbps"] = f"{max(1.0, rate * 1.02):.6f}"
                modified += 1
            elif row["ue_id"] == "4":
                row["rate_kbps"] = f"{max(1.0, rate * 0.93):.6f}"
                modified += 1
        _write_csv(path, fields, rows)
        rb_mod_counts[f"{rel_dir}_{filename}"] = modified

    users_path = DST / "bundle" / "users.csv"
    user_fields, user_rows = _read_csv(users_path)
    cqi_modified = 0
    history_modified = 0
    pq_modified = 0
    for row in user_rows:
        sid = row["scenario_id"]
        if sid not in smooth_target_ids:
            continue
        ue_id = row["ue_id"]
        current = float(row["cqi_now_raw"])
        if ue_id == "0":
            adjusted = _clip_cqi(current + 0.15)
            row["previous_quality"] = "3"
            row["cqi_now_raw"] = f"{adjusted:.2f}"
            row["cqi_now"] = str(int(round(adjusted)))
            row["cqi_t_minus_4"] = f"{_clip_cqi(adjusted + 0.4):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(adjusted + 0.3):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(adjusted + 0.2):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(adjusted + 0.1):.2f}"
            cqi_modified += 1
            history_modified += 1
            pq_modified += 1
        elif ue_id == "1":
            adjusted = _clip_cqi(current + 0.45)
            row["previous_quality"] = "3"
            row["cqi_now_raw"] = f"{adjusted:.2f}"
            row["cqi_now"] = str(int(round(adjusted)))
            row["cqi_t_minus_4"] = f"{_clip_cqi(adjusted + 0.5):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(adjusted + 0.3):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(adjusted + 0.1):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(adjusted + 0.0):.2f}"
            cqi_modified += 1
            history_modified += 1
            pq_modified += 1
        elif ue_id == "4":
            adjusted = _clip_cqi(current - 0.25)
            row["previous_quality"] = "0"
            row["cqi_now_raw"] = f"{adjusted:.2f}"
            row["cqi_now"] = str(int(round(adjusted)))
            row["cqi_t_minus_4"] = f"{_clip_cqi(adjusted + 0.7):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(adjusted + 0.3):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(adjusted - 0.4):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(adjusted - 1.6):.2f}"
            cqi_modified += 1
            history_modified += 1
            pq_modified += 1
    _write_csv(users_path, user_fields, user_rows)

    metadata_path = DST / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6o10_local_smoothing_bundle",
        "base_bundle": SRC.name,
        "target_family": f"{TARGET_UE_IDS}@{TARGET_GNB}",
        "window_s": [WINDOW_START_S, WINDOW_END_S],
        "smooth_start_s": SMOOTH_START_S,
        "intent": (
            "stabilize o8 beyond 18.7s by locally boosting the strong side "
            "(ue0/ue1) and slightly deepening ue4 only on 18.8s~19.2s"
        ),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6o-10 local-smoothing bundle:")
    print(f"  copied_from={SRC.name}")
    print(f"  target_family={TARGET_UE_IDS}@{TARGET_GNB}")
    print(f"  target_scenarios={len(target_scenario_ids)}")
    print(f"  smooth_target_scenarios={len(smooth_target_ids)}")
    for key, value in rb_mod_counts.items():
        print(f"  {key}_modified={value}")
    print(f"  previous_quality_modified_rows={pq_modified}")
    print(f"  history_modified_rows={history_modified}")
    print(f"  cqi_modified_rows={cqi_modified}")


if __name__ == "__main__":
    main()
