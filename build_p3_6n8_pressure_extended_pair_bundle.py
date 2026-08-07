"""Build P3.6n-8 by extending n5's late weak pair using only pressure/rate edits."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6n5_temporal_swap_bundle"
DST = ROOT / "p3_6n8_pressure_extended_pair_bundle"

TARGET_GNB = "gnb_2"
TARGET_UE_IDS = "3|4|5|6"
LATE_START_S = 27.9
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
            else:
                ts = float(row["timestamp_s"])
                if row["serving_gnb"] != TARGET_GNB or ts < LATE_START_S - 1e-9 or ts > LATE_END_S + 1e-9:
                    continue
            ue_id = row["ue_id"]
            rate = float(row["rate_kbps"])
            if ue_id == "4":
                row["rate_kbps"] = f"{max(1.0, rate * 0.72):.6f}"
            elif ue_id == "5":
                row["rate_kbps"] = f"{max(1.0, rate * 0.78):.6f}"
            elif ue_id in {"3", "6"}:
                row["rate_kbps"] = f"{max(1.0, rate * 0.96):.6f}"
        _write_csv(path, fields, rows)

    metadata_path = DST / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6n8_pressure_extended_pair_bundle",
        "base_bundle": SRC.name,
        "target_family": f"{TARGET_UE_IDS}@{TARGET_GNB}",
        "late_start_s": LATE_START_S,
        "late_end_s": LATE_END_S,
        "intent": (
            "keep n5's late user-side quality features untouched, and test whether "
            "extra pressure plus stronger rb-rate skew alone can extend the "
            "{ue4, ue5} weak-pair regime"
        ),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6n-8 pressure-extended pair bundle:")
    print(f"  target_family={TARGET_UE_IDS}@{TARGET_GNB}")
    print(f"  late_window_s={LATE_START_S}~{LATE_END_S}")
    print(f"  target_scenarios={len(target_scenario_ids)}")


if __name__ == "__main__":
    main()
