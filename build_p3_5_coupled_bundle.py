"""Build a P3.0 bundle from one coupled SUMO+Veins+Simu5G execution."""

from __future__ import annotations

import csv
import math
import tempfile
from collections import defaultdict
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path

import le_gra_mvp as mvp
from simu5g_raw_radio_export import export_raw_radio
from simu5g_trace_io import build_trace_bundle
from sumo_mobility_io import MOBILITY_SCHEMA_VERSION, read_gnbs
from trace_io import load_trace_bundle


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _bin(timestamp: str, period: Decimal) -> Decimal:
    value = Decimal(timestamp)
    return (value / period).to_integral_value(rounding=ROUND_FLOOR) * period


def _nearest(x: float, y: float, gnbs: list[dict]) -> tuple[dict, float]:
    gnb = min(gnbs, key=lambda item: (math.hypot(item["x_m"] - x, item["y_m"] - y), item["gnb_id"]))
    return gnb, math.hypot(gnb["x_m"] - x, gnb["y_m"] - y)


def build_coupled_bundle(
    raw_dir: Path | str,
    gnbs_csv: Path | str,
    out_dir: Path | str,
    *,
    snapshot_period_s: float = 0.1,
    slot_duration_ms: float = 1.0,
    rb_budget_ratio: float = 0.5,
    previous_quality: int = 3,
    previous_quality_mode: str = "constant",
) -> dict[str, int]:
    raw_dir, out_dir = Path(raw_dir), Path(out_dir)
    raw_mobility = _read(raw_dir / "raw_mobility.csv")
    raw_radio = _read(raw_dir / "raw_radio.csv")
    raw_radio_diag_path = raw_dir / "raw_radio_diag.csv"
    raw_radio_diag = _read(raw_radio_diag_path) if raw_radio_diag_path.exists() else []
    period = Decimal(str(snapshot_period_s))

    module_to_sumo: dict[str, str] = {}
    for row in raw_mobility:
        module, vehicle = row["ue_module_path"], row["sumo_vehicle_id"]
        prior = module_to_sumo.setdefault(module, vehicle)
        if prior != vehicle:
            raise ValueError(f"Module path reused by different SUMO IDs: {module}")
    if len(set(module_to_sumo.values())) != len(module_to_sumo):
        raise ValueError("One SUMO vehicle ID maps to multiple OMNeT modules")

    mobility_by_key = {
        (Decimal(row["timestamp_s"]), row["ue_module_path"]): row
        for row in raw_mobility
    }
    filtered_radio = [
        row for row in raw_radio
        if (_bin(row["timestamp_s"], period), row["ue_module_path"]) in mobility_by_key
    ]
    if not filtered_radio:
        raise ValueError("No common mobility/radio timestamps")
    latest_raw_timestamp: dict[tuple[Decimal, str], Decimal] = {}
    for row in filtered_radio:
        key = (_bin(row["timestamp_s"], period), row["ue_module_path"])
        timestamp = Decimal(row["timestamp_s"])
        prior = latest_raw_timestamp.get(key)
        if prior is None or timestamp > prior:
            latest_raw_timestamp[key] = timestamp
    filtered_radio = [
        row for row in filtered_radio
        if Decimal(row["timestamp_s"]) == latest_raw_timestamp[
            (_bin(row["timestamp_s"], period), row["ue_module_path"])
        ]
    ]
    filtered_radio_keys = {
        (
            row["timestamp_s"],
            row["ue_node_id"],
            row["gnb_node_id"],
            row["band_index"],
        )
        for row in filtered_radio
    }
    filtered_radio_diag = [
        row for row in raw_radio_diag
        if (
            row["timestamp_s"],
            row["ue_node_id"],
            row["gnb_node_id"],
            row["band_index"],
        ) in filtered_radio_keys
    ]

    radio_dir = out_dir / "radio"
    with tempfile.TemporaryDirectory(prefix="legra_p3_5_radio_") as temp_dir:
        mapped_raw = Path(temp_dir) / "mapped_raw_radio.csv"
        _write(mapped_raw, list(filtered_radio[0]), filtered_radio)
        mapped_diag = None
        if filtered_radio_diag:
            mapped_diag = Path(temp_dir) / "mapped_raw_radio_diag.csv"
            _write(mapped_diag, list(filtered_radio_diag[0]), filtered_radio_diag)
        radio_counts = export_raw_radio(
            mapped_raw,
            radio_dir,
            slot_duration_ms=slot_duration_ms,
            snapshot_period_s=snapshot_period_s,
            rb_budget_ratio=rb_budget_ratio,
            previous_quality=previous_quality,
            previous_quality_mode=previous_quality_mode,
            ue_id_by_module=module_to_sumo,
            raw_diag_csv=mapped_diag,
        )
    radio_users = _read(radio_dir / "radio_users.csv")
    retained = {(Decimal(row["timestamp_s"]), row["ue_id"]) for row in radio_users}

    gnbs = read_gnbs(gnbs_csv)
    by_vehicle: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in raw_mobility:
        by_vehicle[row["sumo_vehicle_id"]].append(row)

    observations: list[dict] = []
    for vehicle, rows in sorted(by_vehicle.items()):
        previous: tuple[float, float] | None = None
        step = 0
        for row in sorted(rows, key=lambda item: Decimal(item["timestamp_s"])):
            timestamp = Decimal(row["timestamp_s"])
            x, y = float(row["x_m"]), float(row["y_m"])
            if (timestamp, vehicle) not in retained:
                previous = (x, y)
                continue
            gnb, distance = _nearest(x, y, gnbs)
            if previous is None:
                dx = dy = 0.0
            else:
                dx, dy = x - previous[0], y - previous[1]
            motion = math.hypot(dx, dy)
            if motion == 0 or distance == 0:
                direction = 0.0
                angle = 0.0
            else:
                direction = max(-1.0, min(1.0, (dx * (gnb["x_m"] - x) + dy * (gnb["y_m"] - y)) / (motion * distance)))
                angle = math.degrees(math.atan2(dx, dy)) % 360.0
            observations.append({
                "timestamp_s": str(timestamp),
                "serving_gnb": gnb["gnb_id"],
                "ue_id": vehicle,
                "trajectory_step": step,
                "x_m": x,
                "y_m": y,
                "speed_mps": float(row["speed_mps"]),
                "angle_deg": angle,
                "distance_m": distance,
                "direction_to_gnb": direction,
                "lane_id": "",
                "lane_position_m": "",
                "slope_deg": "",
                "vehicle_type": "SUMO/TraCI",
            })
            previous = (x, y)
            step += 1

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in observations:
        grouped[(row["timestamp_s"], row["serving_gnb"])].append(row)
    mobility_dir = out_dir / "mobility"
    scenario_rows: list[dict] = []
    mobility_rows: list[dict] = []
    for index, ((timestamp, gnb), rows) in enumerate(sorted(grouped.items(), key=lambda item: (Decimal(item[0][0]), item[0][1]))):
        scenario_id = f"sumo_coupled_{index:08d}"
        rows = sorted(rows, key=lambda item: item["ue_id"])
        scenario_rows.append({
            "mobility_schema_version": MOBILITY_SCHEMA_VERSION,
            "scenario_id": scenario_id,
            "timestamp_s": timestamp,
            "serving_gnb": gnb,
            "user_count": len(rows),
        })
        for user_index, row in enumerate(rows):
            mobility_rows.append({"scenario_id": scenario_id, **row, "user_index": user_index})
    _write(mobility_dir / "sumo_scenarios.csv", [
        "mobility_schema_version", "scenario_id", "timestamp_s", "serving_gnb", "user_count",
    ], scenario_rows)
    _write(mobility_dir / "sumo_mobility.csv", [
        "scenario_id", "timestamp_s", "serving_gnb", "ue_id", "trajectory_step",
        "x_m", "y_m", "speed_mps", "angle_deg", "distance_m", "direction_to_gnb",
        "lane_id", "lane_position_m", "slope_deg", "vehicle_type", "user_index",
    ], mobility_rows)

    bundle_dir = out_dir / "bundle"
    join_counts = build_trace_bundle(mobility_dir, radio_dir, bundle_dir, min_users=1)
    scenarios = load_trace_bundle(bundle_dir, feature_mode="history_cost_quality")
    for scenario in scenarios:
        mvp.offline_teacher_groups(scenario, max_groups=min(3, len(scenario.cqi_now)), switch_beta=0.5)
    return {
        "sumo_vehicles": len(module_to_sumo),
        "mapped_radio_rows": len(filtered_radio),
        "mobility_rows": len(mobility_rows),
        **{f"radio_{name}": value for name, value in radio_counts.items()},
        **{f"bundle_{name}": value for name, value in join_counts.items()},
        "teacher_scenarios": len(scenarios),
    }


if __name__ == "__main__":
    counts = build_coupled_bundle(
        "p3_5_coupled_output",
        "p3_5_gnbs.csv",
        "p3_5_coupled_bundle",
    )
    print("P3.5 coupled bundle:")
    for name, value in counts.items():
        print(f"  {name}={value}")
