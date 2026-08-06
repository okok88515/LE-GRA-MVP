"""Build the P3.6j-2 cost-mismatch variant from the p3_6i2 bundle."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6i2_coupled_bundle"
DST = ROOT / "p3_6j2_cost_mismatch_bundle"
TARGET_TIMESTAMPS = {"43.7", "43.8", "43.9"}
TARGET_GNB = "gnb_1"
TARGET_UE = "15"


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _scale_rate(rb_index: int, rate_kbps: float) -> float:
    # Increase cost without changing wideband CQI metadata. Stronger penalty on
    # the best logical bands makes the achievable-rate profile less favorable.
    if rb_index < 8:
        factor = 0.62
    elif rb_index < 16:
        factor = 0.76
    else:
        factor = 0.88
    return max(1.0, rate_kbps * factor)


def main() -> None:
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)

    scenario_ids: set[str] = set()
    scenario_fields, scenario_rows = _read_csv(DST / "bundle" / "scenarios.csv")
    for row in scenario_rows:
        if row["timestamp_s"] in TARGET_TIMESTAMPS and row["serving_gnb"] == TARGET_GNB:
            scenario_ids.add(row["scenario_id"])

    rb_path = DST / "bundle" / "rb_rates.csv"
    rb_fields, rb_rows = _read_csv(rb_path)
    modified_rb_rows = 0
    for row in rb_rows:
        if row["scenario_id"] in scenario_ids and row["ue_id"] == TARGET_UE:
            rate = float(row["rate_kbps"])
            rb_index = int(row["rb_index"])
            row["rate_kbps"] = f"{_scale_rate(rb_index, rate):.6f}"
            modified_rb_rows += 1
    _write_csv(rb_path, rb_fields, rb_rows)

    radio_rbs_path = DST / "radio" / "radio_rbs.csv"
    radio_fields, radio_rows = _read_csv(radio_rbs_path)
    modified_radio_rows = 0
    for row in radio_rows:
        if (
            row["timestamp_s"] in TARGET_TIMESTAMPS
            and row["serving_gnb"] == TARGET_GNB
            and row["ue_id"] == TARGET_UE
        ):
            rate = float(row["rate_kbps"])
            rb_index = int(row["rb_index"])
            row["rate_kbps"] = f"{_scale_rate(rb_index, rate):.6f}"
            modified_radio_rows += 1
    _write_csv(radio_rbs_path, radio_fields, radio_rows)

    metadata_path = DST / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6j2_cost_mismatch",
        "base_bundle": "p3_6i2_coupled_bundle",
        "target_timestamps_s": sorted(TARGET_TIMESTAMPS),
        "target_serving_gnb": TARGET_GNB,
        "target_ue_id": TARGET_UE,
        "rb_rate_scaling": {
            "rb_0_7": 0.62,
            "rb_8_15": 0.76,
            "rb_16_24": 0.88,
        },
        "intent": (
            "increase per-band resource cost for the teacher-isolated UE while "
            "leaving CQI / previous_quality / mobility unchanged"
        ),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6j-2 cost-mismatch bundle:")
    print(f"  copied_from={SRC.name}")
    print(f"  target_scenarios={len(scenario_ids)}")
    print(f"  modified_bundle_rb_rows={modified_rb_rows}")
    print(f"  modified_radio_rb_rows={modified_radio_rows}")


if __name__ == "__main__":
    main()
