"""Build a structural 3-subgroup ladder + temporal-crossover bundle from n10.

The design goal is no longer a local CQI sweep. Instead, we preserve the same
cross-traffic context as `p3_6n10_late_state_hold_bundle` and directly impose a
late-window structure with:

1. a persistent weak user (`ue4`)
2. a boundary user that changes over time (`ue5`)
3. a second boundary / upper-mid user that crosses with `ue5` (`ue6`)
4. one strong anchor (`ue3`)

This is the smallest attempt to create a regime that could naturally support
`2-group` / `3-group` ambiguity or at least a harder temporal split boundary.
"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "p3_6n10_late_state_hold_bundle"

TARGET_GNB = "gnb_2"
TARGET_UE_IDS = "3|4|5|6"
LATE_START_S = 27.9
PHASE_SPLIT_S = 28.3
LATE_END_S = 28.8


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


def _matching_target_scenarios(bundle_root: Path) -> dict[str, float]:
    _, scenario_rows = _read_csv(bundle_root / "bundle" / "scenarios.csv")
    _, user_rows = _read_csv(bundle_root / "bundle" / "users.csv")
    users_by_scenario: dict[str, list[dict[str, str]]] = {}
    for row in user_rows:
        users_by_scenario.setdefault(row["scenario_id"], []).append(row)

    matched: dict[str, float] = {}
    for row in scenario_rows:
        ts = float(row["timestamp_s"])
        if row["serving_gnb"] != TARGET_GNB or ts < LATE_START_S - 1e-9 or ts > LATE_END_S + 1e-9:
            continue
        family = sorted(
            users_by_scenario.get(row["scenario_id"], []),
            key=lambda item: int(item["user_index"]),
        )
        if "|".join(item["ue_id"] for item in family) == TARGET_UE_IDS:
            matched[row["scenario_id"]] = ts
    return matched


PHASE_A_USER_STATE = {
    "3": {
        "previous_quality": 4,
        "cqi_now_raw": 14.7,
        "history_offsets": [-0.3, -0.2, -0.1, 0.0],
        "rb_scale": 1.00,
    },
    "4": {
        "previous_quality": 1,
        "cqi_now_raw": 8.6,
        "history_offsets": [-2.4, -2.0, -1.6, -1.2],
        "rb_scale": 0.82,
    },
    "5": {
        "previous_quality": 2,
        "cqi_now_raw": 11.2,
        "history_offsets": [-1.4, -1.0, -0.7, -0.4],
        "rb_scale": 0.93,
    },
    "6": {
        "previous_quality": 4,
        "cqi_now_raw": 13.1,
        "history_offsets": [-0.9, -0.6, -0.3, -0.1],
        "rb_scale": 0.90,
    },
}

PHASE_B_USER_STATE = {
    "3": {
        "previous_quality": 4,
        "cqi_now_raw": 14.5,
        "history_offsets": [-0.4, -0.3, -0.2, -0.1],
        "rb_scale": 0.99,
    },
    "4": {
        "previous_quality": 1,
        "cqi_now_raw": 8.3,
        "history_offsets": [-2.2, -1.8, -1.4, -1.0],
        "rb_scale": 0.80,
    },
    "5": {
        "previous_quality": 3,
        "cqi_now_raw": 12.2,
        "history_offsets": [-1.2, -0.8, -0.4, -0.2],
        "rb_scale": 0.98,
    },
    "6": {
        "previous_quality": 3,
        "cqi_now_raw": 11.7,
        "history_offsets": [-1.3, -0.9, -0.5, -0.2],
        "rb_scale": 0.86,
    },
}


def _phase_state(ts: float) -> dict[str, dict[str, float | list[float]]]:
    return PHASE_A_USER_STATE if ts <= PHASE_SPLIT_S + 1e-9 else PHASE_B_USER_STATE


def main() -> None:
    out_dir = ROOT / "p3_6q3_three_group_ladder_bundle"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(SRC, out_dir)

    target_scenarios = _matching_target_scenarios(out_dir)

    user_path = out_dir / "bundle" / "users.csv"
    user_fields, user_rows = _read_csv(user_path)
    touched_user_rows = 0
    for row in user_rows:
        ts = target_scenarios.get(row["scenario_id"])
        ue_id = row["ue_id"]
        if ts is None or ue_id not in {"3", "4", "5", "6"}:
            continue
        state = _phase_state(ts)[ue_id]
        cqi_now_raw = float(state["cqi_now_raw"])
        offsets = list(state["history_offsets"])
        row["previous_quality"] = str(int(state["previous_quality"]))
        row["cqi_now_raw"] = f"{cqi_now_raw:.2f}"
        row["cqi_now"] = str(int(round(cqi_now_raw)))
        row["cqi_t_minus_4"] = f"{_clip_cqi(cqi_now_raw + offsets[0]):.2f}"
        row["cqi_t_minus_3"] = f"{_clip_cqi(cqi_now_raw + offsets[1]):.2f}"
        row["cqi_t_minus_2"] = f"{_clip_cqi(cqi_now_raw + offsets[2]):.2f}"
        row["cqi_t_minus_1"] = f"{_clip_cqi(cqi_now_raw + offsets[3]):.2f}"
        touched_user_rows += 1
    _write_csv(user_path, user_fields, user_rows)

    for rel_dir, filename in [("bundle", "rb_rates.csv"), ("radio", "radio_rbs.csv")]:
        rate_path = out_dir / rel_dir / filename
        fields, rows = _read_csv(rate_path)
        touched_rate_rows = 0
        for row in rows:
            ts = target_scenarios.get(row.get("scenario_id", ""))
            ue_id = row["ue_id"]
            if ts is None or ue_id not in {"3", "4", "5", "6"}:
                continue
            scale = float(_phase_state(ts)[ue_id]["rb_scale"])
            rate = float(row["rate_kbps"]) * scale
            row["rate_kbps"] = f"{rate:.6f}"
            touched_rate_rows += 1
        _write_csv(rate_path, fields, rows)

    metadata_path = out_dir / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": "p3_6q3_three_group_ladder_bundle",
        "base_bundle": SRC.name,
        "target_family": f"{TARGET_UE_IDS}@{TARGET_GNB}",
        "late_start_s": LATE_START_S,
        "phase_split_s": PHASE_SPLIT_S,
        "late_end_s": LATE_END_S,
        "intent": (
            "create a strong / boundary / weak ladder with a late temporal "
            "crossover between ue5 and ue6, while preserving the original "
            "cross-traffic context from n10"
        ),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("P3.6q-3 three-group ladder bundle:")
    print(f"  out_dir={out_dir}")
    print(f"  target_scenarios={len(target_scenarios)}")
    print(f"  touched_user_rows={touched_user_rows}")


if __name__ == "__main__":
    main()
