"""Build the P3.6j-2f third-candidate collapse variant from the p3_6i2 bundle."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6i2_coupled_bundle"
DST = ROOT / "p3_6j2f_third_candidate_collapse_bundle"
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


def _rate_factor(ue_id: str, rate_kbps: float) -> float:
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
    if ue_id == "0":
        # Third-candidate signal: lightly degrade one additional strong user to
        # push the teacher outside the two-user plateau.
        if rate_kbps >= 1128.0:
            return 0.94
        if rate_kbps >= 984.0:
            return 0.97
        return 0.99
    return 1.0


def _quality_override(ue_id: str, timestamp_s: str) -> int | None:
    if timestamp_s not in TARGET_TIMESTAMPS:
        return None
    if ue_id == "15":
        return 2
    if ue_id in {"4", "5"}:
        return 0
    return None


def main() -> None:
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)

    scenario_ids: set[str] = set()
    _, scenario_rows = _read_csv(DST / "bundle" / "scenarios.csv")
    scenario_timestamp = {row["scenario_id"]: row["timestamp_s"] for row in scenario_rows}
    for row in scenario_rows:
        if row["timestamp_s"] in TARGET_TIMESTAMPS and row["serving_gnb"] == TARGET_GNB:
            scenario_ids.add(row["scenario_id"])

    for rel_dir, filename in [("bundle", "rb_rates.csv"), ("radio", "radio_rbs.csv")]:
        path = DST / rel_dir / filename
        fields, rows = _read_csv(path)
        modified = 0
        for row in rows:
            if row["ue_id"] not in {"0", "4", "5"}:
                continue
            is_target = (
                row.get("scenario_id") in scenario_ids
                or (
                    row.get("timestamp_s") in TARGET_TIMESTAMPS
                    and row.get("serving_gnb") == TARGET_GNB
                )
            )
            if not is_target:
                continue
            factor = _rate_factor(row["ue_id"], float(row["rate_kbps"]))
            row["rate_kbps"] = f"{max(1.0, float(row['rate_kbps']) * factor):.6f}"
            modified += 1
        _write_csv(path, fields, rows)
        print(f"{rel_dir}_{filename}_modified={modified}")

    users_path = DST / "bundle" / "users.csv"
    user_fields, user_rows = _read_csv(users_path)
    quality_modified = 0
    for row in user_rows:
        if row["scenario_id"] not in scenario_ids:
            continue
        override = _quality_override(row["ue_id"], scenario_timestamp[row["scenario_id"]])
        if override is None:
            continue
        row["previous_quality"] = str(override)
        quality_modified += 1
    _write_csv(users_path, user_fields, user_rows)

    metadata_path = DST / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6j2f_third_candidate_collapse",
        "base_bundle": "p3_6i2_coupled_bundle",
        "target_timestamps_s": sorted(TARGET_TIMESTAMPS),
        "target_serving_gnb": TARGET_GNB,
        "target_ue_ids": ["0", "4", "5", "15"],
        "rate_transform": {
            "4": {">=1128_kbps": 0.70, ">=984_kbps": 0.84, "else": 0.94},
            "5": {">=1128_kbps": 0.92, ">=984_kbps": 0.95, "else": 0.98},
            "0": {">=1128_kbps": 0.94, ">=984_kbps": 0.97, "else": 0.99},
        },
        "previous_quality_override": {
            "15": 2,
            "4": 0,
            "5": 0,
        },
        "intent": (
            "leave the two-user plateau by adding a third cost-side candidate and "
            "a local previous-quality offset, testing whether the teacher expands "
            "to richer partitions or collapses back to single-group behavior"
        ),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6j-2f third-candidate collapse bundle:")
    print(f"  copied_from={SRC.name}")
    print(f"  target_scenarios={len(scenario_ids)}")
    print("  rate_modified_ues=['0', '4', '5']")
    print("  previous_quality_modified_rows=", quality_modified)


if __name__ == "__main__":
    main()
