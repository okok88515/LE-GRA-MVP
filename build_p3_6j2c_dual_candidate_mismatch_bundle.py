"""Build the P3.6j-2c dual-candidate mismatch variant from the p3_6i2 bundle."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6i2_coupled_bundle"
DST = ROOT / "p3_6j2c_dual_candidate_mismatch_bundle"
TARGET_TIMESTAMPS = {"43.8"}
TARGET_GNB = "gnb_1"
PRIMARY_UE = "4"
SECONDARY_UE = "5"


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _primary_transform(rate_kbps: float) -> float:
    # Strongly compress the top end for one main-group user so it becomes a
    # plausible split candidate without changing metadata CQI.
    if rate_kbps >= 1128.0:
        factor = 0.70
    elif rate_kbps >= 984.0:
        factor = 0.84
    else:
        factor = 0.94
    return max(1.0, rate_kbps * factor)


def _secondary_transform(rate_kbps: float) -> float:
    # Apply a lighter, broader penalty to a second main-group user. The goal is
    # to create a competing candidate family rather than a single obvious outlier.
    if rate_kbps >= 1128.0:
        factor = 0.92
    elif rate_kbps >= 984.0:
        factor = 0.95
    else:
        factor = 0.98
    return max(1.0, rate_kbps * factor)


def _transform_rate(ue_id: str, rate_kbps: float) -> float:
    if ue_id == PRIMARY_UE:
        return _primary_transform(rate_kbps)
    if ue_id == SECONDARY_UE:
        return _secondary_transform(rate_kbps)
    return rate_kbps


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
                row["ue_id"] in {PRIMARY_UE, SECONDARY_UE}
                and (
                    row.get("scenario_id") in scenario_ids
                    or (
                        row.get("timestamp_s") in TARGET_TIMESTAMPS
                        and row.get("serving_gnb") == TARGET_GNB
                    )
                )
            )
            if not is_target:
                continue
            row["rate_kbps"] = f"{_transform_rate(row['ue_id'], float(row['rate_kbps'])):.6f}"
            modified += 1
        _write_csv(path, fields, rows)
        print(f"{rel_dir}_{filename}_modified={modified}")

    metadata_path = DST / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6j2c_dual_candidate_mismatch",
        "base_bundle": "p3_6i2_coupled_bundle",
        "target_timestamps_s": sorted(TARGET_TIMESTAMPS),
        "target_serving_gnb": TARGET_GNB,
        "target_ue_ids": [PRIMARY_UE, SECONDARY_UE],
        "rate_transform": {
            PRIMARY_UE: {
                ">=1128_kbps": 0.70,
                ">=984_kbps": 0.84,
                "else": 0.94,
            },
            SECONDARY_UE: {
                ">=1128_kbps": 0.92,
                ">=984_kbps": 0.95,
                "else": 0.98,
            },
        },
        "intent": (
            "create a dual-candidate split snapshot inside seg_01 by perturbing "
            "two strong main-group users with complementary cost-shape penalties "
            "while leaving CQI, mobility, and previous quality unchanged"
        ),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6j-2c dual-candidate mismatch bundle:")
    print(f"  copied_from={SRC.name}")
    print(f"  target_scenarios={len(scenario_ids)}")
    print(f"  target_ue_ids={[PRIMARY_UE, SECONDARY_UE]}")


if __name__ == "__main__":
    main()
