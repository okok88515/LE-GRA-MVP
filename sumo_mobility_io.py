"""Parse SUMO FCD XML into deterministic LE-GRA mobility staging tables."""

from __future__ import annotations

import csv
import math
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


MOBILITY_SCHEMA_VERSION = "1.0"


def read_gnbs(path: Path | str) -> list[dict]:
    path = Path(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("At least one gNB is required")
    gnbs = []
    for row in rows:
        gnbs.append({"gnb_id": row["gnb_id"], "x_m": float(row["x_m"]), "y_m": float(row["y_m"])})
    ids = [row["gnb_id"] for row in gnbs]
    if len(set(ids)) != len(ids):
        raise ValueError("gnb_id values must be unique")
    return gnbs


def _nearest_gnb(x_m: float, y_m: float, gnbs: list[dict]) -> tuple[dict, float]:
    ranked = sorted(
        gnbs,
        key=lambda gnb: (
            math.hypot(gnb["x_m"] - x_m, gnb["y_m"] - y_m),
            gnb["gnb_id"],
        ),
    )
    selected = ranked[0]
    return selected, math.hypot(selected["x_m"] - x_m, selected["y_m"] - y_m)


def _direction_to_gnb(
    x_m: float,
    y_m: float,
    angle_deg: float,
    speed_mps: float,
    gnb: dict,
) -> float:
    dx, dy = gnb["x_m"] - x_m, gnb["y_m"] - y_m
    distance = math.hypot(dx, dy)
    if speed_mps <= 0.0 or distance <= 0.0:
        return 0.0
    radians = math.radians(angle_deg)
    heading_x, heading_y = math.sin(radians), math.cos(radians)
    return max(-1.0, min(1.0, (heading_x * dx + heading_y * dy) / distance))


def parse_fcd(
    fcd_path: Path | str,
    gnbs: list[dict],
    *,
    min_users: int = 1,
    max_users: int = 0,
) -> tuple[list[dict], list[dict]]:
    """Stream FCD XML and return scenario and mobility rows."""

    if min_users <= 0 or max_users < 0:
        raise ValueError("min_users must be positive and max_users non-negative")
    if max_users and max_users < min_users:
        raise ValueError("max_users cannot be smaller than min_users")

    observations_by_snapshot: dict[tuple[float, str], list[dict]] = defaultdict(list)
    trajectory_steps: dict[str, int] = defaultdict(int)
    current_time: float | None = None
    for event, element in ET.iterparse(Path(fcd_path), events=("start", "end")):
        if event == "start" and element.tag == "timestep":
            current_time = float(element.attrib["time"])
        elif event == "end" and element.tag == "vehicle":
            if current_time is None:
                raise ValueError("Vehicle encountered outside a timestep")
            ue_id = element.attrib["id"]
            x_m, y_m = float(element.attrib["x"]), float(element.attrib["y"])
            angle_deg, speed_mps = float(element.attrib["angle"]), float(element.attrib["speed"])
            gnb, distance_m = _nearest_gnb(x_m, y_m, gnbs)
            observation = {
                "timestamp_s": current_time,
                "serving_gnb": gnb["gnb_id"],
                "ue_id": ue_id,
                "trajectory_step": trajectory_steps[ue_id],
                "x_m": x_m,
                "y_m": y_m,
                "speed_mps": speed_mps,
                "angle_deg": angle_deg,
                "distance_m": distance_m,
                "direction_to_gnb": _direction_to_gnb(x_m, y_m, angle_deg, speed_mps, gnb),
                "lane_id": element.attrib.get("lane", ""),
                "lane_position_m": element.attrib.get("pos", ""),
                "slope_deg": element.attrib.get("slope", ""),
                "vehicle_type": element.attrib.get("type", ""),
            }
            observations_by_snapshot[(current_time, gnb["gnb_id"])].append(observation)
            trajectory_steps[ue_id] += 1
            element.clear()
        elif event == "end" and element.tag == "timestep":
            current_time = None
            element.clear()

    scenario_rows, mobility_rows = [], []
    scenario_number = 0
    for (timestamp_s, gnb_id), observations in sorted(observations_by_snapshot.items()):
        if len(observations) < min_users:
            continue
        if max_users and len(observations) > max_users:
            observations = sorted(
                observations, key=lambda row: (row["distance_m"], row["ue_id"])
            )[:max_users]
        observations = sorted(observations, key=lambda row: row["ue_id"])
        scenario_id = f"sumo_{scenario_number:08d}"
        scenario_number += 1
        scenario_rows.append({
            "mobility_schema_version": MOBILITY_SCHEMA_VERSION,
            "scenario_id": scenario_id,
            "timestamp_s": timestamp_s,
            "serving_gnb": gnb_id,
            "user_count": len(observations),
        })
        for user_index, observation in enumerate(observations):
            mobility_rows.append({
                "scenario_id": scenario_id,
                **observation,
                "user_index": user_index,
            })
    return scenario_rows, mobility_rows


def _write_csv(path: Path, rows: list[dict], fallback_fields: list[str]) -> None:
    fields = list(rows[0]) if rows else fallback_fields
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def export_mobility_staging(
    fcd_path: Path | str,
    gnbs_path: Path | str,
    out_dir: Path | str,
    *,
    min_users: int = 1,
    max_users: int = 0,
) -> tuple[list[dict], list[dict]]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    scenarios, mobility = parse_fcd(
        fcd_path,
        read_gnbs(gnbs_path),
        min_users=min_users,
        max_users=max_users,
    )
    _write_csv(
        out_dir / "sumo_scenarios.csv",
        scenarios,
        ["mobility_schema_version", "scenario_id", "timestamp_s", "serving_gnb", "user_count"],
    )
    _write_csv(
        out_dir / "sumo_mobility.csv",
        mobility,
        [
            "scenario_id", "timestamp_s", "serving_gnb", "ue_id", "trajectory_step",
            "x_m", "y_m", "speed_mps", "angle_deg", "distance_m",
            "direction_to_gnb", "lane_id", "lane_position_m", "slope_deg",
            "vehicle_type", "user_index",
        ],
    )
    return scenarios, mobility

