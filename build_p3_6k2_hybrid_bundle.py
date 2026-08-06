"""Build the P3.6k-2 hybrid tail-window redesign for 3|4|5|6 @ gnb_2."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6i2_coupled_bundle"
DST = ROOT / "p3_6k2_hybrid_bundle"
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


def _ue5_factor(rate_kbps: float) -> float:
    # Strong tail-window cost signal: make ue 5 meaningfully more expensive
    # without touching the other three users' RB profiles.
    if rate_kbps >= 1128.0:
        return 0.84
    if rate_kbps >= 984.0:
        return 0.80
    return 0.90


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
        scenario_id = row["scenario_id"]
        if row["serving_gnb"] != TARGET_GNB or float(row["timestamp_s"]) < WINDOW_START_S:
            continue
        scenario_family = sorted(
            scenario_users.get(scenario_id, []),
            key=lambda item: int(item["user_index"]),
        )
        if "|".join(item["ue_id"] for item in scenario_family) == TARGET_UE_IDS:
            target_scenario_ids.add(scenario_id)

    for rel_dir, filename in [("bundle", "rb_rates.csv"), ("radio", "radio_rbs.csv")]:
        path = DST / rel_dir / filename
        fields, rows = _read_csv(path)
        modified = 0
        for row in rows:
            scenario_id = row.get("scenario_id")
            timestamp_s = float(row.get("timestamp_s", "0") or 0.0)
            serving_gnb = row.get("serving_gnb", "")
            is_target = (
                row["ue_id"] == "5"
                and (
                    scenario_id in target_scenario_ids
                    or (serving_gnb == TARGET_GNB and timestamp_s >= WINDOW_START_S)
                )
            )
            if not is_target:
                continue
            row["rate_kbps"] = f"{max(1.0, float(row['rate_kbps']) * _ue5_factor(float(row['rate_kbps']))):.6f}"
            modified += 1
        _write_csv(path, fields, rows)
        print(f"{rel_dir}_{filename}_modified={modified}")

    users_path = DST / "bundle" / "users.csv"
    user_fields, user_rows = _read_csv(users_path)
    quality_modified = 0
    for row in user_rows:
        if row["scenario_id"] not in target_scenario_ids:
            continue
        if row["ue_id"] == "5":
            row["previous_quality"] = "0"
            quality_modified += 1
        elif row["ue_id"] in {"3", "4", "6"}:
            row["previous_quality"] = "2"
            quality_modified += 1
    _write_csv(users_path, user_fields, user_rows)

    metadata_path = DST / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6k2_hybrid_tail_window",
        "base_bundle": "p3_6i2_coupled_bundle",
        "target_family": f"{TARGET_UE_IDS}@{TARGET_GNB}",
        "window_start_s": WINDOW_START_S,
        "target_ue_id": "5",
        "ue5_rate_transform": {
            ">=1128_kbps": 0.84,
            ">=984_kbps": 0.80,
            "else": 0.90,
        },
        "previous_quality_override": {
            "5": 0,
            "3": 2,
            "4": 2,
            "6": 2,
        },
        "intent": (
            "align a strong tail-window cost penalty on ue 5 with a localized "
            "quality-history divergence so the teacher begins isolating ue 5 in "
            "the 3|4|5|6@gnb_2 family"
        ),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6k-2 hybrid bundle:")
    print(f"  copied_from={SRC.name}")
    print(f"  target_family={TARGET_UE_IDS}@{TARGET_GNB}")
    print(f"  target_scenarios={len(target_scenario_ids)}")
    print(f"  previous_quality_modified_rows={quality_modified}")


if __name__ == "__main__":
    main()
