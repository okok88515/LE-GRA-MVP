"""Versioned CSV trace-bundle I/O for LE-GRA and SUMO/Simu5G adapters."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Sequence

import numpy as np

import le_gra_mvp as mvp


SCHEMA_VERSION = "1.0"
HISTORY_COLUMNS = [
    "cqi_t_minus_4",
    "cqi_t_minus_3",
    "cqi_t_minus_2",
    "cqi_t_minus_1",
    "cqi_now_raw",
]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _optional(value: float | int | None) -> str | float | int:
    return "" if value is None else value


def export_trace_bundle(
    scenarios: Sequence[mvp.Scenario],
    out_dir: Path | str,
    *,
    scenario_ids: Sequence[str] | None = None,
    timestamps_s: Sequence[float] | None = None,
    serving_gnbs: Sequence[str] | None = None,
    ue_ids: Sequence[Sequence[str]] | None = None,
) -> None:
    """Export scenarios without inventing unavailable radio measurements."""

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    count = len(scenarios)
    scenario_ids = list(scenario_ids or [f"scenario_{i:06d}" for i in range(count)])
    timestamps_s = list(timestamps_s or [float(i) for i in range(count)])
    serving_gnbs = list(serving_gnbs or ["gnb_0"] * count)
    if not (len(scenario_ids) == len(timestamps_s) == len(serving_gnbs) == count):
        raise ValueError("Scenario metadata lengths must match scenarios")
    if len(set(scenario_ids)) != count:
        raise ValueError("scenario_ids must be unique")

    scenario_rows, user_rows, rb_rows = [], [], []
    for scenario_number, scenario in enumerate(scenarios):
        scenario_id = scenario_ids[scenario_number]
        n_users, total_rbs = scenario.rb_rates.shape
        current_ue_ids = (
            list(ue_ids[scenario_number]) if ue_ids is not None
            else [f"ue_{user_index:04d}" for user_index in range(n_users)]
        )
        if len(current_ue_ids) != n_users or len(set(current_ue_ids)) != n_users:
            raise ValueError(f"Invalid UE IDs for {scenario_id}")
        scenario_rows.append({
            "schema_version": SCHEMA_VERSION,
            "scenario_id": scenario_id,
            "timestamp_s": timestamps_s[scenario_number],
            "serving_gnb": serving_gnbs[scenario_number],
            "rb_available": scenario.rb_available,
            "total_rbs": total_rbs,
            "dispersion": scenario.dispersion,
        })
        for user_index, ue_id in enumerate(current_ue_ids):
            history = scenario.cqi_history[user_index]
            user_rows.append({
                "scenario_id": scenario_id,
                "ue_id": ue_id,
                "user_index": user_index,
                **{name: history[i] for i, name in enumerate(HISTORY_COLUMNS)},
                "cqi_now": int(scenario.cqi_now[user_index]),
                "previous_quality": int(scenario.previous_quality[user_index]),
                "distance_m": scenario.distance[user_index],
                "speed_mps": scenario.speed[user_index],
                "direction_to_gnb": scenario.direction_to_gnb[user_index],
                "x_m": "",
                "y_m": "",
                "rsrp_dbm": "",
                "rsrq_db": "",
                "wideband_sinr_db": "",
                "mcs": "",
            })
            for rb_index in range(total_rbs):
                rb_rows.append({
                    "scenario_id": scenario_id,
                    "ue_id": ue_id,
                    "user_index": user_index,
                    "rb_index": rb_index,
                    "rate_kbps": scenario.rb_rates[user_index, rb_index],
                    "sinr_db": "",
                    "cqi": "",
                })

    _write_csv(out_dir / "scenarios.csv", list(scenario_rows[0]) if scenario_rows else [
        "schema_version", "scenario_id", "timestamp_s", "serving_gnb",
        "rb_available", "total_rbs", "dispersion",
    ], scenario_rows)
    _write_csv(out_dir / "users.csv", list(user_rows[0]) if user_rows else [
        "scenario_id", "ue_id", "user_index", *HISTORY_COLUMNS, "cqi_now",
        "previous_quality", "distance_m", "speed_mps", "direction_to_gnb",
        "x_m", "y_m", "rsrp_dbm", "rsrq_db", "wideband_sinr_db", "mcs",
    ], user_rows)
    _write_csv(out_dir / "rb_rates.csv", list(rb_rows[0]) if rb_rows else [
        "scenario_id", "ue_id", "user_index", "rb_index", "rate_kbps",
        "sinr_db", "cqi",
    ], rb_rows)


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing trace table: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_trace_bundle(
    bundle_dir: Path | str,
    *,
    feature_mode: str = "history_cost_quality",
) -> list[mvp.Scenario]:
    """Validate and load a trace bundle in scenarios.csv order."""

    bundle_dir = Path(bundle_dir)
    scenario_rows = _read_rows(bundle_dir / "scenarios.csv")
    user_rows = _read_rows(bundle_dir / "users.csv")
    rb_rows = _read_rows(bundle_dir / "rb_rates.csv")
    users_by_scenario: dict[str, list[dict[str, str]]] = defaultdict(list)
    rbs_by_scenario: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in user_rows:
        users_by_scenario[row["scenario_id"]].append(row)
    for row in rb_rows:
        rbs_by_scenario[row["scenario_id"]].append(row)

    known_ids = {row["scenario_id"] for row in scenario_rows}
    dangling = (set(users_by_scenario) | set(rbs_by_scenario)) - known_ids
    if dangling:
        raise ValueError(f"Rows reference unknown scenarios: {sorted(dangling)}")

    scenarios = []
    for metadata in scenario_rows:
        scenario_id = metadata["scenario_id"]
        if metadata["schema_version"] != SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported schema version {metadata['schema_version']} in {scenario_id}"
            )
        total_rbs = int(metadata["total_rbs"])
        rb_available = int(metadata["rb_available"])
        users = sorted(users_by_scenario[scenario_id], key=lambda row: int(row["user_index"]))
        indices = [int(row["user_index"]) for row in users]
        if indices != list(range(len(users))):
            raise ValueError(f"Non-contiguous user_index in {scenario_id}")
        if not 0 < rb_available <= total_rbs:
            raise ValueError(f"Invalid RB budget in {scenario_id}")

        n_users = len(users)
        cqi_history = np.asarray(
            [[float(row[name]) for name in HISTORY_COLUMNS] for row in users], dtype=float
        )
        cqi_now = np.asarray([int(row["cqi_now"]) for row in users], dtype=int)
        previous_quality = np.asarray(
            [int(row["previous_quality"]) for row in users], dtype=int
        )
        if np.any((cqi_now < 1) | (cqi_now > 15)):
            raise ValueError(f"CQI outside 1..15 in {scenario_id}")
        if np.any((previous_quality < 0) | (previous_quality >= len(mvp.VIDEO_BITRATES_KBPS))):
            raise ValueError(f"Invalid previous quality in {scenario_id}")

        rates = np.full((n_users, total_rbs), np.nan, dtype=float)
        ue_id_by_index = {int(row["user_index"]): row["ue_id"] for row in users}
        for row in rbs_by_scenario[scenario_id]:
            user_index, rb_index = int(row["user_index"]), int(row["rb_index"])
            if not (0 <= user_index < n_users and 0 <= rb_index < total_rbs):
                raise ValueError(f"RB index outside matrix in {scenario_id}")
            if row["ue_id"] != ue_id_by_index[user_index]:
                raise ValueError(f"UE ID/index mismatch in {scenario_id}")
            if not np.isnan(rates[user_index, rb_index]):
                raise ValueError(f"Duplicate UE/RB row in {scenario_id}")
            rates[user_index, rb_index] = float(row["rate_kbps"])
        if np.isnan(rates).any() or np.any(rates < 0):
            raise ValueError(f"Missing or negative RB rates in {scenario_id}")

        scenario = mvp.Scenario(
            features=np.empty((n_users, 0), dtype=np.float32),
            cqi_history=cqi_history,
            cqi_now=cqi_now,
            rb_rates=rates,
            rb_available=rb_available,
            previous_quality=previous_quality,
            distance=np.asarray([float(row["distance_m"]) for row in users]),
            speed=np.asarray([float(row["speed_mps"]) for row in users]),
            direction_to_gnb=np.asarray([float(row["direction_to_gnb"]) for row in users]),
            dispersion=metadata.get("dispersion", "") or "trace",
        )
        scenario.features = mvp.build_feature_matrix(scenario, feature_mode)
        scenarios.append(scenario)
    return scenarios

