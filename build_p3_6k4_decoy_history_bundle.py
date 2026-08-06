"""Build the P3.6k-4 decoy-history bundle on top of the P3.6k-2 hybrid regime."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6k2_hybrid_bundle"
DST = ROOT / "p3_6k4_decoy_history_bundle"
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


def _clip_cqi(value: float) -> float:
    return max(1.0, min(15.0, value))


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

    users_path = DST / "bundle" / "users.csv"
    user_fields, user_rows = _read_csv(users_path)
    modified_rows = 0
    for row in user_rows:
        if row["scenario_id"] not in target_scenario_ids:
            continue
        current = float(row["cqi_now_raw"])
        if row["ue_id"] == "4":
            # Decoy weak-history user: sharp recent decline while current CQI
            # remains in the strong-user range. This should look suspicious to
            # per-snapshot clustering without changing teacher economics.
            history = [
                _clip_cqi(current + 1.0),
                _clip_cqi(current + 0.8),
                _clip_cqi(current + 0.1),
                _clip_cqi(current - 1.2),
            ]
        elif row["ue_id"] == "5":
            # True teacher-isolated user: mildly recovering recent history, so
            # the raw temporal shape looks less obviously weak than ue 4.
            history = [
                _clip_cqi(current - 1.0),
                _clip_cqi(current - 0.5),
                _clip_cqi(current - 0.2),
                _clip_cqi(current + 0.3),
            ]
        else:
            continue

        row["cqi_t_minus_4"] = f"{history[0]:.2f}"
        row["cqi_t_minus_3"] = f"{history[1]:.2f}"
        row["cqi_t_minus_2"] = f"{history[2]:.2f}"
        row["cqi_t_minus_1"] = f"{history[3]:.2f}"
        modified_rows += 1
    _write_csv(users_path, user_fields, user_rows)

    metadata_path = DST / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6k4_decoy_history",
        "base_bundle": "p3_6k2_hybrid_bundle",
        "target_family": f"{TARGET_UE_IDS}@{TARGET_GNB}",
        "window_start_s": WINDOW_START_S,
        "intent": (
            "create a temporal-history decoy on ue 4 while keeping the teacher "
            "economics of isolating ue 5 unchanged, to test whether learned "
            "embeddings resist snapshot-level temporal-shape confusion better "
            "than raw multi-feature k-means"
        ),
        "bundle_user_overrides": {
            "ue4_history_pattern": "recent_decline_decoy",
            "ue5_history_pattern": "mild_recovery_true_weak_user",
        },
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6k-4 decoy-history bundle:")
    print(f"  copied_from={SRC.name}")
    print(f"  target_family={TARGET_UE_IDS}@{TARGET_GNB}")
    print(f"  target_scenarios={len(target_scenario_ids)}")
    print(f"  modified_bundle_user_rows={modified_rows}")


if __name__ == "__main__":
    main()
