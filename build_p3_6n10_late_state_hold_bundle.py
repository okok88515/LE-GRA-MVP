"""Build P3.6n-10 by holding the n5 late weak-pair state past the 28.3 cliff."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6n5_temporal_swap_bundle"
DST = ROOT / "p3_6n10_late_state_hold_bundle"

TARGET_GNB = "gnb_2"
TARGET_UE_IDS = "3|4|5|6"
REFERENCE_TS = 28.3
HOLD_START_S = 28.4
HOLD_END_S = 28.8


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _matching_target_scenarios(bundle_root: Path) -> dict[float, str]:
    _, scenario_rows = _read_csv(bundle_root / "bundle" / "scenarios.csv")
    _, user_rows = _read_csv(bundle_root / "bundle" / "users.csv")
    users_by_scenario: dict[str, list[dict[str, str]]] = {}
    for row in user_rows:
        users_by_scenario.setdefault(row["scenario_id"], []).append(row)

    matched: dict[float, str] = {}
    for row in scenario_rows:
        ts = float(row["timestamp_s"])
        if row["serving_gnb"] != TARGET_GNB:
            continue
        family = sorted(
            users_by_scenario.get(row["scenario_id"], []),
            key=lambda item: int(item["user_index"]),
        )
        if "|".join(item["ue_id"] for item in family) == TARGET_UE_IDS:
            matched[ts] = row["scenario_id"]
    return matched


def main() -> None:
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)

    target_scenarios = _matching_target_scenarios(DST)
    reference_sid = target_scenarios[REFERENCE_TS]
    hold_sids = {
        sid
        for ts, sid in target_scenarios.items()
        if HOLD_START_S - 1e-9 <= ts <= HOLD_END_S + 1e-9
    }

    # Copy the full weak-pair user-side state for ue4/ue5 from 28.3 to the
    # immediate post-cliff timestamps, so we can test whether the family can be
    # turned into a short positive segment at all before doing subtler redesigns.
    user_path = DST / "bundle" / "users.csv"
    user_fields, user_rows = _read_csv(user_path)
    ref_users = {
        row["ue_id"]: row
        for row in user_rows
        if row["scenario_id"] == reference_sid and row["ue_id"] in {"4", "5"}
    }
    touched_users = 0
    for row in user_rows:
        if row["scenario_id"] not in hold_sids or row["ue_id"] not in {"4", "5"}:
            continue
        ref = ref_users[row["ue_id"]]
        for key in (
            "previous_quality",
            "cqi_now_raw",
            "cqi_now",
            "cqi_t_minus_4",
            "cqi_t_minus_3",
            "cqi_t_minus_2",
            "cqi_t_minus_1",
        ):
            row[key] = ref[key]
        touched_users += 1
    _write_csv(user_path, user_fields, user_rows)

    for rel_dir, filename in [("bundle", "rb_rates.csv"), ("radio", "radio_rbs.csv")]:
        path = DST / rel_dir / filename
        fields, rows = _read_csv(path)
        ref_rows = [
            row for row in rows if row.get("scenario_id") == reference_sid and row["ue_id"] in {"4", "5"}
        ]
        ref_by_key = {
            (row["ue_id"], row["rb_index"]): row["rate_kbps"]
            for row in ref_rows
        }
        touched_rates = 0
        for row in rows:
            sid = row.get("scenario_id")
            if sid not in hold_sids or row["ue_id"] not in {"4", "5"}:
                continue
            row["rate_kbps"] = ref_by_key[(row["ue_id"], row["rb_index"])]
            touched_rates += 1
        _write_csv(path, fields, rows)

    metadata_path = DST / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6n10_late_state_hold_bundle",
        "base_bundle": SRC.name,
        "target_family": f"{TARGET_UE_IDS}@{TARGET_GNB}",
        "reference_ts": REFERENCE_TS,
        "hold_start_s": HOLD_START_S,
        "hold_end_s": HOLD_END_S,
        "intent": (
            "copy the full ue4/ue5 late weak-pair state from the last positive "
            "snapshot at 28.3s into the immediate post-cliff neighborhood, to "
            "test whether this family can support a short sustained teacher-"
            "positive segment at all"
        ),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6n-10 late-state hold bundle:")
    print(f"  target_family={TARGET_UE_IDS}@{TARGET_GNB}")
    print(f"  reference_ts={REFERENCE_TS}")
    print(f"  hold_window_s={HOLD_START_S}~{HOLD_END_S}")
    print(f"  hold_scenarios={len(hold_sids)}")
    print(f"  touched_user_rows={touched_users}")


if __name__ == "__main__":
    main()
