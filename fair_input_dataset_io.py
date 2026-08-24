"""Loader for compressed fair-input benchmark datasets."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp


@dataclass(frozen=True)
class FairInputRecord:
    scenario_id: str
    physical_state_id: str
    dispersion: str
    frequency_profile: str
    load_level: str
    rb_budget_ratio: float
    rb_available: int
    total_rbs: int
    n_users: int
    seed: int
    draw_index: int
    shard_path: str
    array_index: int


def load_index(dataset_dir: Path | str) -> list[FairInputRecord]:
    dataset_dir = Path(dataset_dir)
    with (dataset_dir / "scenario_index.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [FairInputRecord(
        scenario_id=row["scenario_id"],
        physical_state_id=row["physical_state_id"],
        dispersion=row["dispersion"],
        frequency_profile=row["frequency_profile"],
        load_level=row["load_level"],
        rb_budget_ratio=float(row["rb_budget_ratio"]),
        rb_available=int(row["rb_available"]),
        total_rbs=int(row["total_rbs"]),
        n_users=int(row["n_users"]),
        seed=int(row["seed"]),
        draw_index=int(row["draw_index"]),
        shard_path=row["shard_path"],
        array_index=int(row["array_index"]),
    ) for row in rows]


class FairInputDataset:
    def __init__(self, dataset_dir: Path | str):
        self.dataset_dir = Path(dataset_dir)
        self.records = load_index(self.dataset_dir)
        self._shards: dict[str, np.lib.npyio.NpzFile] = {}

    def close(self) -> None:
        for shard in self._shards.values():
            shard.close()
        self._shards.clear()

    def __enter__(self) -> "FairInputDataset":
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def _shard(self, relative_path: str) -> np.lib.npyio.NpzFile:
        if relative_path not in self._shards:
            self._shards[relative_path] = np.load(
                self.dataset_dir / relative_path, allow_pickle=False
            )
        return self._shards[relative_path]

    def scenario(self, record: FairInputRecord, feature_mode: str = "full_context") -> mvp.Scenario:
        shard = self._shard(record.shard_path)
        idx = record.array_index
        n_users, total_rbs = shard["rb_rates"][idx].shape
        nan_user = np.full(n_users, np.nan, dtype=float)
        scenario = mvp.Scenario(
            features=np.empty((n_users, 0), dtype=np.float32),
            cqi_history=shard["cqi_history"][idx].astype(float),
            cqi_now=shard["cqi_now"][idx].astype(int),
            rb_rates=shard["rb_rates"][idx].astype(float),
            rb_available=record.rb_available,
            previous_quality=shard["previous_quality"][idx].astype(int),
            distance=shard["distance_m"][idx].astype(float),
            speed=shard["speed"][idx].astype(float),
            direction_to_gnb=shard["direction_to_gnb"][idx].astype(float),
            rsrp_dbm=nan_user.copy(),
            rsrq_db=nan_user.copy(),
            wideband_sinr_db=nan_user.copy(),
            rb_sinr_db=np.full((n_users, total_rbs), np.nan, dtype=float),
            mcs=nan_user.copy(),
            dispersion=record.dispersion,
            speed_history=shard["speed_history"][idx].astype(float),
        )
        scenario.features = mvp.build_feature_matrix(scenario, feature_mode)
        return scenario
