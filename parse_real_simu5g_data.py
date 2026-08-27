"""Parse real Simu5G+SUMO+Veins output (P3.7 clean validation run) into
`le_gra_mvp.Scenario` objects, and run the same non-learned comparison
methods used throughout this project's synthetic validation.

Data provenance
----------------
`real_simu5g_data/raw_radio.csv` / `raw_mobility.csv` come from an actual
OMNeT++ 6.3.0 + INET 4.6.0 + Simu5G 1.4.3 + Veins 5.3.1 simulation (WSL
`LE-GRA-opp-env`, `~/p3_5_workspace/p3_7_clean_validation_scenario`), NOT the
Python synthetic generator. This scenario reuses the P3.6 "informative"
network/gNB layout verbatim (2 gNBs at (200,80) and (200,320) in a 400x400m
area, 25 bands) with only one change: the SUMO route file's 24 vehicles are
sorted globally by departure time (the original file was grouped by route,
which SUMO silently truncated to 10/24 vehicles -- confirmed via the
`Route file should be sorted by departure time` warnings in that run's log).
No vehicle count, speed, or route was tuned to chase a particular CQI
pattern -- this is the plain single-vehicle-type, 4-direction design that
predates the "targeted family" scenario redesigns.

What this script does NOT attempt: training a fresh LE-GRA model on this
data. One 90s run yields 15 usable one-second snapshots where all 24 vehicles
have complete 25-band coverage and 5 steps of history -- nowhere near
enough to split into a meaningful train/test set for a neural net (the
synthetic protocol uses 60-90 training scenarios per condition). Only the
non-learned baselines (CQI k-means, resource-cost k-means, multi-feature
k-means) are compared here; LE-GRA validation on real data would need many
more simulation runs, which is out of scope for this pass.

Modeling choices (disclosed, not hidden)
------------------------------------------
- Native `wideband_cqi` is unavailable in the restored recorder export, so
  this script derives a wideband CQI proxy as
  round(mean(per-band CQI)) per user per snapshot, clipped to [1, 15].
- Per-band CQI within a 1-second bucket uses the LAST report in that bucket
  (closest to "the most recent CQI report as of this allocation cycle"),
  not an average.
- distance/speed/direction_to_gnb are computed from real per-timestep
  (x, y, speed) mobility traces against the gNB position each car is
  reportedly served by; rsrp/rsrq/sinr/mcs are NOT in this export and are
  left as NaN (`build_feature_matrix`'s `_safe_feature_column` already
  handles this -- those columns are unused by CQI/resource-cost/multi-
  feature k-means anyway).
"""

from __future__ import annotations

import csv
import gzip
import re
from pathlib import Path
from typing import TextIO

import numpy as np

import le_gra_mvp as mvp

DATA_DIR = Path("real_simu5g_data")
N_USERS = 24
N_BANDS = 25
GNB_POS = {1: (200.0, 80.0), 2: (200.0, 320.0)}
CAR_RE = re.compile(r"car\[(\d+)\]")


def open_csv_text(path: Path) -> TextIO:
    """Open either an ordinary CSV or a per-run gzip archive as text."""

    if path.suffix == ".gz":
        return gzip.open(path, mode="rt", encoding="utf-8", newline="")
    return path.open(encoding="utf-8", newline="")


def load_radio(path: Path) -> dict[tuple[int, int], dict[int, int]]:
    """Return {(bucket_second, car_index): {band_index: cqi}} using the last
    report per (bucket, car, band)."""

    data: dict[tuple[int, int], dict[int, int]] = {}
    gnb_of: dict[tuple[int, int], int] = {}
    with open_csv_text(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            car = int(CAR_RE.search(row["ue_module_path"]).group(1))
            bucket = int(round(float(row["timestamp_s"])))
            key = (bucket, car)
            data.setdefault(key, {})[int(row["band_index"])] = int(row["cqi"])
            gnb_of[key] = int(row["gnb_node_id"])
    return data, gnb_of


def load_mobility(path: Path) -> dict[tuple[int, int], tuple[float, float, float]]:
    """Return {(bucket_second, car_index): (x, y, speed)} using the report
    closest to each integer second."""

    best: dict[tuple[int, int], tuple[float, float, float, float]] = {}
    with open_csv_text(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = float(row["timestamp_s"])
            car = int(row["sumo_vehicle_id"])
            bucket = int(round(t))
            dist_to_bucket = abs(t - bucket)
            key = (bucket, car)
            if key not in best or dist_to_bucket < best[key][3]:
                best[key] = (float(row["x_m"]), float(row["y_m"]), float(row["speed_mps"]), dist_to_bucket)
    return {k: v[:3] for k, v in best.items()}


def build_scenarios(
    rb_budget_ratio: float,
    history_len: int = 5,
    radio_path: Path | None = None,
    mobility_path: Path | None = None,
    n_users: int = N_USERS,
    gnb_pos: dict[int, tuple[float, float]] | None = None,
) -> list[mvp.Scenario]:
    """`n_users` and `gnb_pos` default to this project's original 24-vehicle
    scenario constants (`N_USERS`, `GNB_POS`) for full backward
    compatibility. Pass explicit overrides for a differently-scaled
    scenario -- e.g. the direction-4 scale pilot uses `n_users=40,
    gnb_pos={1: (400.0, 160.0), 2: (400.0, 640.0)}`
    (`REAL_SIMU5G_SCALE_PILOT.md`)."""

    if gnb_pos is None:
        gnb_pos = GNB_POS
    radio, gnb_of = load_radio(radio_path or (DATA_DIR / "raw_radio.csv"))
    mobility = load_mobility(mobility_path or (DATA_DIR / "raw_mobility.csv"))

    all_buckets = sorted({b for b, _ in radio})
    usable_buckets = [
        t for t in all_buckets
        if all((t - lag, car) in radio and len(radio[(t - lag, car)]) == N_BANDS for lag in range(history_len) for car in range(n_users))
        and all((t, car) in mobility for car in range(n_users))
    ]

    scenarios = []
    for t in usable_buckets:
        band_cqi_now = np.zeros((n_users, N_BANDS), dtype=float)
        history = np.zeros((n_users, history_len), dtype=float)
        distance = np.zeros(n_users, dtype=float)
        speed = np.zeros(n_users, dtype=float)
        direction = np.zeros(n_users, dtype=float)

        for car in range(n_users):
            for lag in range(history_len):
                bucket = t - (history_len - 1 - lag)
                bands = radio[(bucket, car)]
                band_vals = np.array([bands[b] for b in range(N_BANDS)], dtype=float)
                wideband = float(np.clip(np.rint(band_vals.mean()), 1, 15))
                history[car, lag] = wideband
                if bucket == t:
                    band_cqi_now[car] = band_vals

            x, y, spd = mobility[(t, car)]
            gnb_id = gnb_of[(t, car)]
            gx, gy = gnb_pos[gnb_id]
            distance[car] = float(np.hypot(x - gx, y - gy))
            speed[car] = spd
            if spd > 0.5:
                x_prev, y_prev, _ = mobility.get((t - 1, car), (x, y, spd))
                vx, vy = x - x_prev, y - y_prev
                to_gnb = np.array([gx - x, gy - y])
                v = np.array([vx, vy])
                denom = (np.linalg.norm(v) * np.linalg.norm(to_gnb)) + 1e-9
                direction[car] = float(np.dot(v, to_gnb) / denom) if denom > 1e-6 else 0.0

        cqi_now = np.clip(np.rint(history[:, -1]).astype(int), 1, 15)
        rb_rates = mvp.cqi_to_rate_kbps(band_cqi_now)
        rb_available = max(1, int(round(rb_budget_ratio * N_BANDS)))

        nan_col = np.full(n_users, np.nan)
        scenario = mvp.Scenario(
            features=np.zeros((n_users, 1), dtype=np.float32),
            cqi_history=history,
            cqi_now=cqi_now,
            rb_rates=rb_rates,
            rb_available=rb_available,
            previous_quality=np.zeros(n_users, dtype=int),
            distance=distance,
            speed=speed,
            direction_to_gnb=direction,
            rsrp_dbm=nan_col.copy(),
            rsrq_db=nan_col.copy(),
            wideband_sinr_db=nan_col.copy(),
            rb_sinr_db=np.full((n_users, N_BANDS), np.nan),
            mcs=nan_col.copy(),
            dispersion="real_p3_7",
            speed_history=None,
        )
        scenarios.append(scenario)
    return scenarios


if __name__ == "__main__":
    for ratio, label in [(0.50, "light"), (0.25, "medium"), (0.10, "heavy")]:
        scenarios = build_scenarios(ratio)
        print(f"{label} (rb_budget_ratio={ratio}): {len(scenarios)} usable real scenarios, "
              f"rb_available={scenarios[0].rb_available if scenarios else 'n/a'}/{N_BANDS}")
