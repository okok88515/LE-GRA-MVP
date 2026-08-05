"""Join P3.1 SUMO mobility with normalized P3.2 Simu5G radio exports."""

from __future__ import annotations

import csv
from collections import defaultdict, deque
from decimal import Decimal
from pathlib import Path

import numpy as np

from trace_io import HISTORY_COLUMNS, SCHEMA_VERSION


def _read(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _time(value: str) -> Decimal:
    return Decimal(value)


def _optional_float(value: str) -> str | float:
    return "" if value == "" else float(value)


def _optional_int(value: str) -> str | int:
    return "" if value == "" else int(value)


def _write(path: Path, rows: list[dict], fallback: list[str]) -> None:
    fields = list(rows[0]) if rows else fallback
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build_trace_bundle(
    mobility_dir: Path | str,
    radio_dir: Path | str,
    out_dir: Path | str,
    *,
    history_steps: int = 5,
    min_users: int = 1,
    max_users: int = 0,
) -> dict[str, int]:
    if history_steps != len(HISTORY_COLUMNS):
        raise ValueError(f"Schema v1 requires exactly {len(HISTORY_COLUMNS)} CQI steps")
    if min_users <= 0 or max_users < 0 or (max_users and max_users < min_users):
        raise ValueError("Invalid min/max user settings")
    mobility_dir, radio_dir, out_dir = Path(mobility_dir), Path(radio_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    mobility = _read(mobility_dir / "sumo_mobility.csv")
    radio_users = _read(radio_dir / "radio_users.csv")
    radio_rbs = _read(radio_dir / "radio_rbs.csv")
    mobility_by_key = {}
    for row in mobility:
        key = (_time(row["timestamp_s"]), row["ue_id"])
        if key in mobility_by_key:
            raise ValueError(f"Duplicate mobility row: {key}")
        mobility_by_key[key] = row

    user_by_key = {}
    user_history: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=history_steps))
    eligible_by_snapshot: dict[tuple[Decimal, str], list[dict]] = defaultdict(list)
    for row in sorted(radio_users, key=lambda item: (_time(item["timestamp_s"]), item["ue_id"])):
        timestamp, ue_id = _time(row["timestamp_s"]), row["ue_id"]
        key = (timestamp, ue_id)
        if key in user_by_key:
            raise ValueError(f"Duplicate radio user row: {key}")
        if key not in mobility_by_key:
            raise ValueError(f"Radio row has no matching SUMO mobility: {key}")
        cqi = float(row["wideband_cqi"])
        if not 1.0 <= cqi <= 15.0:
            raise ValueError(f"CQI outside 1..15: {key}")
        previous_quality = int(row["previous_quality"])
        if not 0 <= previous_quality < 6:
            raise ValueError(f"Invalid previous quality: {key}")
        total_rbs, rb_available = int(row["total_rbs"]), int(row["rb_available"])
        if not 0 < rb_available <= total_rbs:
            raise ValueError(f"Invalid RB budget: {key}")
        user_history[ue_id].append(cqi)
        enriched = {
            **row,
            "_timestamp": timestamp,
            "_history": list(user_history[ue_id]),
            "_mobility": mobility_by_key[key],
        }
        user_by_key[key] = enriched
        if len(enriched["_history"]) == history_steps:
            eligible_by_snapshot[(timestamp, row["serving_gnb"])].append(enriched)

    rbs_by_key: dict[tuple[Decimal, str], list[dict]] = defaultdict(list)
    seen_rb_keys = set()
    for row in radio_rbs:
        key = (_time(row["timestamp_s"]), row["ue_id"])
        rb_key = (*key, int(row["rb_index"]))
        if rb_key in seen_rb_keys:
            raise ValueError(f"Duplicate radio RB row: {rb_key}")
        seen_rb_keys.add(rb_key)
        if key not in user_by_key:
            raise ValueError(f"RB row has no radio user row: {key}")
        if row["serving_gnb"] != user_by_key[key]["serving_gnb"]:
            raise ValueError(f"Serving-gNB mismatch for RB row: {rb_key}")
        if float(row["rate_kbps"]) < 0.0:
            raise ValueError(f"Negative RB rate: {rb_key}")
        rbs_by_key[key].append(row)

    scenario_rows, output_users, output_rbs = [], [], []
    dropped_warmup = len(radio_users) - sum(len(rows) for rows in eligible_by_snapshot.values())
    scenario_number = 0
    for (timestamp, gnb_id), users in sorted(eligible_by_snapshot.items()):
        if len(users) < min_users:
            continue
        if max_users and len(users) > max_users:
            users = sorted(
                users,
                key=lambda row: (float(row["_mobility"]["distance_m"]), row["ue_id"]),
            )[:max_users]
        users = sorted(users, key=lambda row: row["ue_id"])
        total_values = {int(row["total_rbs"]) for row in users}
        budget_values = {int(row["rb_available"]) for row in users}
        if len(total_values) != 1 or len(budget_values) != 1:
            raise ValueError(f"Inconsistent RB configuration at {timestamp}/{gnb_id}")
        total_rbs, rb_available = total_values.pop(), budget_values.pop()
        for row in users:
            rb_indices = sorted(int(item["rb_index"]) for item in rbs_by_key[(timestamp, row["ue_id"])])
            if rb_indices != list(range(total_rbs)):
                raise ValueError(f"Incomplete RB vector at {timestamp}/{row['ue_id']}")

        scenario_id = f"simu5g_{scenario_number:08d}"
        scenario_number += 1
        scenario_rows.append({
            "schema_version": SCHEMA_VERSION,
            "scenario_id": scenario_id,
            "timestamp_s": str(timestamp),
            "serving_gnb": gnb_id,
            "rb_available": rb_available,
            "total_rbs": total_rbs,
            "dispersion": "simu5g",
        })
        for user_index, row in enumerate(users):
            mobility_row = row["_mobility"]
            history = row["_history"]
            output_users.append({
                "scenario_id": scenario_id,
                "ue_id": row["ue_id"],
                "user_index": user_index,
                **{name: history[i] for i, name in enumerate(HISTORY_COLUMNS)},
                "cqi_now": int(np.clip(np.rint(history[-1]), 1, 15)),
                "previous_quality": int(row["previous_quality"]),
                "distance_m": float(mobility_row["distance_m"]),
                "speed_mps": float(mobility_row["speed_mps"]),
                "direction_to_gnb": float(mobility_row["direction_to_gnb"]),
                "x_m": float(mobility_row["x_m"]),
                "y_m": float(mobility_row["y_m"]),
                "rsrp_dbm": _optional_float(row.get("rsrp_dbm", "")),
                "rsrq_db": _optional_float(row.get("rsrq_db", "")),
                "wideband_sinr_db": _optional_float(row.get("wideband_sinr_db", "")),
                "mcs": _optional_int(row.get("mcs", "")),
            })
            for rb_row in sorted(rbs_by_key[(timestamp, row["ue_id"])], key=lambda item: int(item["rb_index"])):
                output_rbs.append({
                    "scenario_id": scenario_id,
                    "ue_id": row["ue_id"],
                    "user_index": user_index,
                    "rb_index": int(rb_row["rb_index"]),
                    "rate_kbps": float(rb_row["rate_kbps"]),
                    "sinr_db": _optional_float(rb_row.get("sinr_db", "")),
                    "cqi": _optional_float(rb_row.get("cqi", "")),
                })

    _write(out_dir / "scenarios.csv", scenario_rows, [
        "schema_version", "scenario_id", "timestamp_s", "serving_gnb",
        "rb_available", "total_rbs", "dispersion",
    ])
    _write(out_dir / "users.csv", output_users, [
        "scenario_id", "ue_id", "user_index", *HISTORY_COLUMNS, "cqi_now",
        "previous_quality", "distance_m", "speed_mps", "direction_to_gnb",
        "x_m", "y_m", "rsrp_dbm", "rsrq_db", "wideband_sinr_db", "mcs",
    ])
    _write(out_dir / "rb_rates.csv", output_rbs, [
        "scenario_id", "ue_id", "user_index", "rb_index", "rate_kbps", "sinr_db", "cqi",
    ])
    return {
        "scenarios": len(scenario_rows),
        "users": len(output_users),
        "rb_rows": len(output_rbs),
        "dropped_warmup_user_rows": dropped_warmup,
    }
