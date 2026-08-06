"""Build the P3.6k-5 dual-weak decoy bundle on top of P3.6k-4."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6k4_decoy_history_bundle"
DST = ROOT / "p3_6k5_dualweak_decoy_bundle"
TARGET_GNB = "gnb_2"
TARGET_UE_IDS = "3|4|5|6"
WINDOW_START_S = 29.2


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _ue4_factor(rate_kbps: float) -> float:
    # Moderate penalty only: enough to make ue 4 look like a plausible decoy,
    # but hopefully not enough to replace ue 5 as the teacher-isolated user.
    if rate_kbps >= 1128.0:
        return 0.95
    if rate_kbps >= 984.0:
        return 0.92
    return 0.97


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
        if row["serving_gnb"] != TARGET_GNB or float(row["timestamp_s"]) < WINDOW_START_S:
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
            if row.get("scenario_id") not in target_scenario_ids or row["ue_id"] != "4":
                continue
            row["rate_kbps"] = f"{max(1.0, float(row['rate_kbps']) * _ue4_factor(float(row['rate_kbps']))):.6f}"
            modified += 1
        _write_csv(path, fields, rows)
        rb_mod_counts[f"{rel_dir}_{filename}"] = modified

    users_path = DST / "bundle" / "users.csv"
    user_fields, user_rows = _read_csv(users_path)
    pq_modified = 0
    for row in user_rows:
        if row["scenario_id"] not in target_scenario_ids or row["ue_id"] != "4":
            continue
        row["previous_quality"] = "1"
        pq_modified += 1
    _write_csv(users_path, user_fields, user_rows)

    metadata_path = DST / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6k5_dualweak_decoy",
        "base_bundle": "p3_6k4_decoy_history_bundle",
        "target_family": f"{TARGET_UE_IDS}@{TARGET_GNB}",
        "window_start_s": WINDOW_START_S,
        "intent": (
            "add a moderate secondary weakness to ue 4 on top of the k-4 "
            "history decoy so ue 4 and ue 5 both look weak in raw features, "
            "while teacher should still prefer isolating only ue 5"
        ),
        "ue4_rate_transform": {
            ">=1128_kbps": 0.95,
            ">=984_kbps": 0.92,
            "else": 0.97,
        },
        "ue4_previous_quality_override": 1,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6k-5 dual-weak decoy bundle:")
    print(f"  copied_from={SRC.name}")
    print(f"  target_family={TARGET_UE_IDS}@{TARGET_GNB}")
    print(f"  target_scenarios={len(target_scenario_ids)}")
    for key, value in rb_mod_counts.items():
        print(f"  {key}_modified={value}")
    print(f"  previous_quality_modified_rows={pq_modified}")


if __name__ == "__main__":
    main()
