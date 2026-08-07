"""Build P3.6n-6 by extending and masking the late weak-pair regime from n5."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6n5_temporal_swap_bundle"
DST = ROOT / "p3_6n6_masked_pair_bundle"

TARGET_GNB = "gnb_2"
TARGET_UE_IDS = "3|4|5|6"
LATE_START_S = 27.9
LATE_END_S = 29.9
WEAK_PAIR = {"4", "5"}
STRONG_PAIR = {"3", "6"}


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


def _matching_target_scenarios(bundle_root: Path) -> set[str]:
    _, scenario_rows = _read_csv(bundle_root / "bundle" / "scenarios.csv")
    _, user_rows = _read_csv(bundle_root / "bundle" / "users.csv")
    users_by_scenario: dict[str, list[dict[str, str]]] = {}
    for row in user_rows:
        users_by_scenario.setdefault(row["scenario_id"], []).append(row)

    matched: set[str] = set()
    for row in scenario_rows:
        ts = float(row["timestamp_s"])
        if row["serving_gnb"] != TARGET_GNB or ts < LATE_START_S - 1e-9 or ts > LATE_END_S + 1e-9:
            continue
        family = sorted(
            users_by_scenario.get(row["scenario_id"], []),
            key=lambda item: int(item["user_index"]),
        )
        if "|".join(item["ue_id"] for item in family) == TARGET_UE_IDS:
            matched.add(row["scenario_id"])
    return matched


def _adjust_weak_rate(ue_id: str, rate: float) -> float:
    if ue_id == "4":
        if rate >= 600.0:
            return rate * 0.74
        if rate >= 400.0:
            return rate * 0.78
        return rate * 0.82
    if rate >= 420.0:
        return rate * 0.68
    if rate >= 300.0:
        return rate * 0.74
    return rate * 0.82


def _adjust_strong_rate(rate: float) -> float:
    if rate >= 1100.0:
        return rate * 0.96
    return rate * 0.98


def main() -> None:
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)

    target_scenario_ids = _matching_target_scenarios(DST)

    scenario_path = DST / "bundle" / "scenarios.csv"
    scenario_fields, scenario_rows = _read_csv(scenario_path)
    for row in scenario_rows:
        if row["scenario_id"] in target_scenario_ids:
            row["rb_available"] = "3"
    _write_csv(scenario_path, scenario_fields, scenario_rows)

    for rel_dir, filename in [("bundle", "rb_rates.csv"), ("radio", "radio_rbs.csv")]:
        path = DST / rel_dir / filename
        fields, rows = _read_csv(path)
        for row in rows:
            if "scenario_id" in row:
                if row["scenario_id"] not in target_scenario_ids:
                    continue
                ue_id = row["ue_id"]
            else:
                ts = float(row["timestamp_s"])
                if row["serving_gnb"] != TARGET_GNB or ts < LATE_START_S - 1e-9 or ts > LATE_END_S + 1e-9:
                    continue
                ue_id = row["ue_id"]
            rate = float(row["rate_kbps"])
            if ue_id in WEAK_PAIR:
                row["rate_kbps"] = f"{max(1.0, _adjust_weak_rate(ue_id, rate)):.6f}"
            elif ue_id in STRONG_PAIR:
                row["rate_kbps"] = f"{max(1.0, _adjust_strong_rate(rate)):.6f}"
        _write_csv(path, fields, rows)

    users_path = DST / "bundle" / "users.csv"
    user_fields, user_rows = _read_csv(users_path)
    touched = 0
    for row in user_rows:
        if row["scenario_id"] not in target_scenario_ids:
            continue
        ue_id = row["ue_id"]
        current = float(row["cqi_now_raw"])
        if ue_id == "4":
            adjusted = max(11.2, min(12.2, current + 1.8))
            row["previous_quality"] = "3"
            row["cqi_now_raw"] = f"{adjusted:.2f}"
            row["cqi_now"] = str(int(round(adjusted)))
            row["cqi_t_minus_4"] = f"{_clip_cqi(adjusted - 1.1):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(adjusted - 0.8):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(adjusted - 0.6):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(adjusted - 0.3):.2f}"
            touched += 1
        elif ue_id == "5":
            adjusted = max(10.9, min(11.8, current + 1.1))
            row["previous_quality"] = "3"
            row["cqi_now_raw"] = f"{adjusted:.2f}"
            row["cqi_now"] = str(int(round(adjusted)))
            row["cqi_t_minus_4"] = f"{_clip_cqi(adjusted - 1.0):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(adjusted - 0.8):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(adjusted - 0.6):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(adjusted - 0.4):.2f}"
            touched += 1
        elif ue_id in STRONG_PAIR:
            adjusted = min(13.2, current - 0.8)
            row["previous_quality"] = "3"
            row["cqi_now_raw"] = f"{adjusted:.2f}"
            row["cqi_now"] = str(int(round(adjusted)))
            row["cqi_t_minus_4"] = f"{_clip_cqi(adjusted - 0.7):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(adjusted - 0.5):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(adjusted - 0.3):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(adjusted - 0.2):.2f}"
            touched += 1
    _write_csv(users_path, user_fields, user_rows)

    metadata_path = DST / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6n6_masked_pair_bundle",
        "base_bundle": SRC.name,
        "target_family": f"{TARGET_UE_IDS}@{TARGET_GNB}",
        "late_start_s": LATE_START_S,
        "late_end_s": LATE_END_S,
        "intent": (
            "extend the late weak pair {ue4, ue5} while masking it on simple "
            "CQI/history features so teacher pressure stays but baseline "
            "separability should become less trivial"
        ),
        "weak_pair_ue_ids": sorted(WEAK_PAIR),
        "strong_pair_ue_ids": sorted(STRONG_PAIR),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6n-6 masked-pair bundle:")
    print(f"  target_family={TARGET_UE_IDS}@{TARGET_GNB}")
    print(f"  late_window_s={LATE_START_S}~{LATE_END_S}")
    print(f"  target_scenarios={len(target_scenario_ids)}")
    print(f"  modified_user_rows={touched}")


if __name__ == "__main__":
    main()
