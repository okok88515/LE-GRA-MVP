"""Build P3.6n-9 by smoothing the late ue4 cliff inside the n5 family."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6n5_temporal_swap_bundle"
DST = ROOT / "p3_6n9_late_cliff_smoothing_bundle"

TARGET_GNB = "gnb_2"
TARGET_UE_IDS = "3|4|5|6"
LATE_START_S = 27.9
CLIFF_START_S = 28.4
LATE_END_S = 29.9


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


def _matching_target_scenarios(bundle_root: Path) -> dict[str, float]:
    _, scenario_rows = _read_csv(bundle_root / "bundle" / "scenarios.csv")
    _, user_rows = _read_csv(bundle_root / "bundle" / "users.csv")
    users_by_scenario: dict[str, list[dict[str, str]]] = {}
    for row in user_rows:
        users_by_scenario.setdefault(row["scenario_id"], []).append(row)

    matched: dict[str, float] = {}
    for row in scenario_rows:
        ts = float(row["timestamp_s"])
        if row["serving_gnb"] != TARGET_GNB or ts < LATE_START_S - 1e-9 or ts > LATE_END_S + 1e-9:
            continue
        family = sorted(
            users_by_scenario.get(row["scenario_id"], []),
            key=lambda item: int(item["user_index"]),
        )
        if "|".join(item["ue_id"] for item in family) == TARGET_UE_IDS:
            matched[row["scenario_id"]] = ts
    return matched


def main() -> None:
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)

    target_scenarios = _matching_target_scenarios(DST)
    cliff_scenario_ids = {
        sid for sid, ts in target_scenarios.items() if ts >= CLIFF_START_S - 1e-9
    }

    # Keep the same family and base pressure as n5, but gently hold ue4 down
    # after 28.4s so the late-window pair does not rebound immediately.
    for rel_dir, filename in [("bundle", "rb_rates.csv"), ("radio", "radio_rbs.csv")]:
        path = DST / rel_dir / filename
        fields, rows = _read_csv(path)
        for row in rows:
            sid = row.get("scenario_id")
            if sid not in cliff_scenario_ids:
                continue
            ue_id = row["ue_id"]
            rate = float(row["rate_kbps"])
            if ue_id == "4":
                row["rate_kbps"] = f"{max(1.0, rate * 0.88):.6f}"
            elif ue_id == "5":
                row["rate_kbps"] = f"{max(1.0, rate * 0.97):.6f}"
        _write_csv(path, fields, rows)

    users_path = DST / "bundle" / "users.csv"
    user_fields, user_rows = _read_csv(users_path)
    touched = 0
    for row in user_rows:
        sid = row["scenario_id"]
        if sid not in cliff_scenario_ids:
            continue
        ue_id = row["ue_id"]
        current = float(row["cqi_now_raw"])
        if ue_id == "4":
            adjusted = min(current, 9.45)
            row["previous_quality"] = "1"
            row["cqi_now_raw"] = f"{adjusted:.2f}"
            row["cqi_now"] = str(int(round(adjusted)))
            row["cqi_t_minus_4"] = f"{_clip_cqi(adjusted - 2.4):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(adjusted - 2.0):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(adjusted - 1.6):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(adjusted - 1.2):.2f}"
            touched += 1
        elif ue_id == "5":
            adjusted = min(current, 9.20)
            row["previous_quality"] = "2"
            row["cqi_now_raw"] = f"{adjusted:.2f}"
            row["cqi_now"] = str(int(round(adjusted)))
            row["cqi_t_minus_4"] = f"{_clip_cqi(adjusted - 1.0):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(adjusted - 0.8):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(adjusted - 0.5):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(adjusted - 0.3):.2f}"
            touched += 1
    _write_csv(users_path, user_fields, user_rows)

    metadata_path = DST / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6n9_late_cliff_smoothing_bundle",
        "base_bundle": SRC.name,
        "target_family": f"{TARGET_UE_IDS}@{TARGET_GNB}",
        "late_start_s": LATE_START_S,
        "cliff_start_s": CLIFF_START_S,
        "late_end_s": LATE_END_S,
        "intent": (
            "start from the n5 temporal-swap family and only smooth the ue4 "
            "rebound after 28.4s, to test whether the short late positive pair "
            "segment can be extended without fully re-masking the weak pair"
        ),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6n-9 late-cliff smoothing bundle:")
    print(f"  target_family={TARGET_UE_IDS}@{TARGET_GNB}")
    print(f"  cliff_window_s={CLIFF_START_S}~{LATE_END_S}")
    print(f"  target_scenarios={len(target_scenarios)}")
    print(f"  touched_rows={touched}")


if __name__ == "__main__":
    main()
