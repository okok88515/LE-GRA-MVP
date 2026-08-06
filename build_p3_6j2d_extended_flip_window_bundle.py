"""Build the P3.6j-2d extended flip-window variant from the p3_6i2 bundle."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6i2_coupled_bundle"
DST = ROOT / "p3_6j2d_extended_flip_window_bundle"
TARGET_TIMESTAMPS = {"43.8", "43.9"}
TARGET_GNB = "gnb_1"


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _factor_for(ue_id: str, timestamp_s: str, rate_kbps: float) -> float:
    if timestamp_s == "43.8":
        # Reuse the successful j-2c flip snapshot as the center of the window.
        if ue_id == "4":
            if rate_kbps >= 1128.0:
                return 0.70
            if rate_kbps >= 984.0:
                return 0.84
            return 0.94
        if ue_id == "5":
            if rate_kbps >= 1128.0:
                return 0.92
            if rate_kbps >= 984.0:
                return 0.95
            return 0.98
    if timestamp_s == "43.9":
        # Keep pressure in the following snapshot, but make it milder so the
        # family does not fully collapse.
        if ue_id == "4":
            if rate_kbps >= 1128.0:
                return 0.88
            if rate_kbps >= 984.0:
                return 0.68
            return 0.90
        if ue_id == "5":
            if rate_kbps >= 1128.0:
                return 0.84
            if rate_kbps >= 984.0:
                return 0.90
            return 0.96
    return 1.0


def main() -> None:
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)

    scenario_ids: set[str] = set()
    _, scenario_rows = _read_csv(DST / "bundle" / "scenarios.csv")
    for row in scenario_rows:
        if row["timestamp_s"] in TARGET_TIMESTAMPS and row["serving_gnb"] == TARGET_GNB:
            scenario_ids.add(row["scenario_id"])

    for rel_dir, filename in [("bundle", "rb_rates.csv"), ("radio", "radio_rbs.csv")]:
        path = DST / rel_dir / filename
        fields, rows = _read_csv(path)
        modified = 0
        for row in rows:
            timestamp_s = row.get("timestamp_s", "")
            scenario_id = row.get("scenario_id")
            if row["ue_id"] not in {"4", "5"}:
                continue
            is_target = (
                scenario_id in scenario_ids
                or (timestamp_s in TARGET_TIMESTAMPS and row.get("serving_gnb") == TARGET_GNB)
            )
            if not is_target:
                continue
            factor = _factor_for(row["ue_id"], timestamp_s or "43.8", float(row["rate_kbps"]))
            row["rate_kbps"] = f"{max(1.0, float(row['rate_kbps']) * factor):.6f}"
            modified += 1
        _write_csv(path, fields, rows)
        print(f"{rel_dir}_{filename}_modified={modified}")

    metadata_path = DST / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6j2d_extended_flip_window",
        "base_bundle": "p3_6i2_coupled_bundle",
        "target_timestamps_s": sorted(TARGET_TIMESTAMPS),
        "target_serving_gnb": TARGET_GNB,
        "target_ue_ids": ["4", "5"],
        "rate_transform": {
            "43.8": {
                "4": {">=1128_kbps": 0.70, ">=984_kbps": 0.84, "else": 0.94},
                "5": {">=1128_kbps": 0.92, ">=984_kbps": 0.95, "else": 0.98},
            },
            "43.9": {
                "4": {">=1128_kbps": 0.88, ">=984_kbps": 0.68, "else": 0.90},
                "5": {">=1128_kbps": 0.84, ">=984_kbps": 0.90, "else": 0.96},
            },
        },
        "intent": (
            "extend the dual-candidate pressure window beyond the single j-2c flip "
            "snapshot while preserving positive teacher gain in the surrounding "
            "seg_01 family"
        ),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6j-2d extended flip-window bundle:")
    print(f"  copied_from={SRC.name}")
    print(f"  target_scenarios={len(scenario_ids)}")
    print("  target_ue_ids=['4', '5']")


if __name__ == "__main__":
    main()
