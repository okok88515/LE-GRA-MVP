"""Build the P3.6j-2b shape-mismatch variant from the p3_6i2 bundle."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6i2_coupled_bundle"
DST = ROOT / "p3_6j2b_shape_mismatch_bundle"
TARGET_TIMESTAMPS = {"43.7", "43.8", "43.9"}
TARGET_GNB = "gnb_1"
TARGET_UE = "4"


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _shape_mismatch_rate(rate_kbps: float) -> float:
    # Reshape a CQI-15 user's multiset so top-end support becomes meaningfully
    # worse while leaving metadata CQI unchanged. This is not a pure uniform
    # penalty on the previously isolated user; it targets a strong-main-group
    # user to create a competing cost profile.
    if rate_kbps >= 1128.0:
        factor = 0.72
    elif rate_kbps >= 984.0:
        factor = 0.82
    else:
        factor = 0.92
    return max(1.0, rate_kbps * factor)


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
            is_target = (
                row["ue_id"] == TARGET_UE and (
                    row.get("scenario_id") in scenario_ids or
                    (
                        row.get("timestamp_s") in TARGET_TIMESTAMPS and
                        row.get("serving_gnb") == TARGET_GNB
                    )
                )
            )
            if not is_target:
                continue
            row["rate_kbps"] = f"{_shape_mismatch_rate(float(row['rate_kbps'])):.6f}"
            modified += 1
        _write_csv(path, fields, rows)
        print(f"{rel_dir}_{filename}_modified={modified}")

    metadata_path = DST / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6j2b_shape_mismatch",
        "base_bundle": "p3_6i2_coupled_bundle",
        "target_timestamps_s": sorted(TARGET_TIMESTAMPS),
        "target_serving_gnb": TARGET_GNB,
        "target_ue_id": TARGET_UE,
        "rate_transform": {
            ">=1128_kbps": 0.72,
            ">=984_kbps": 0.82,
            "else": 0.92,
        },
        "intent": (
            "create a competing high-CQI user whose sorted per-band rate profile "
            "becomes weaker without changing mobility, CQI metadata, or previous quality"
        ),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6j-2b shape-mismatch bundle:")
    print(f"  copied_from={SRC.name}")
    print(f"  target_scenarios={len(scenario_ids)}")
    print(f"  target_ue_id={TARGET_UE}")


if __name__ == "__main__":
    main()
