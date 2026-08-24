"""Validate structure, checksums, invariants, and intended data variation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from fair_input_dataset_io import FairInputDataset, load_index


REQUIRED_ARRAYS = {
    "cqi_history", "cqi_now", "previous_quality", "rb_rates",
    "distance_m", "speed", "direction_to_gnb", "speed_history",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(dataset_dir: Path) -> None:
    manifest = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    records = load_index(dataset_dir)
    if not records:
        raise AssertionError("scenario_index.csv is empty")
    if len({r.scenario_id for r in records}) != len(records):
        raise AssertionError("scenario_id is not unique")

    expected_loads = set(manifest["parameters"]["loads"])
    by_physical_profile: dict[tuple[str, str], set[str]] = defaultdict(set)
    for record in records:
        by_physical_profile[(record.physical_state_id, record.frequency_profile)].add(record.load_level)
        if not 0 < record.rb_available <= record.total_rbs:
            raise AssertionError(f"invalid RB budget: {record.scenario_id}")
    bad_loads = [key for key, loads in by_physical_profile.items() if loads != expected_loads]
    if bad_loads:
        raise AssertionError(f"missing load counterfactuals for {bad_loads[:3]}")

    common_by_dispersion: dict[str, dict[str, np.ndarray]] = {}
    profile_rb_std: dict[str, list[float]] = defaultdict(list)
    mean_rate_by_dispersion: dict[str, dict[str, float]] = defaultdict(dict)
    for entry in manifest["shards"]:
        path = dataset_dir / entry["path"]
        if sha256_file(path) != entry["sha256"]:
            raise AssertionError(f"checksum mismatch: {path}")
        with np.load(path, allow_pickle=False) as shard:
            if set(shard.files) != REQUIRED_ARRAYS:
                raise AssertionError(f"array schema mismatch in {path}: {shard.files}")
            cqi_history = shard["cqi_history"]
            cqi_now = shard["cqi_now"]
            previous = shard["previous_quality"]
            rates = shard["rb_rates"]
            if cqi_history.shape != (entry["physical_scenarios"], cqi_now.shape[1], 5):
                raise AssertionError(f"history shape mismatch in {path}")
            if rates.shape[:2] != cqi_now.shape:
                raise AssertionError(f"RB shape mismatch in {path}")
            if previous.shape != cqi_now.shape:
                raise AssertionError(f"previous-quality shape mismatch in {path}")
            if np.any((cqi_now < 1) | (cqi_now > 15)):
                raise AssertionError(f"CQI outside 1..15 in {path}")
            if np.any((previous < 0) | (previous > 5)):
                raise AssertionError(f"previous quality outside 0..5 in {path}")
            if np.any(~np.isfinite(rates)) or np.any(rates < 0):
                raise AssertionError(f"invalid RB rate in {path}")

            dispersion = entry["dispersion"]
            profile = entry["frequency_profile"]
            common = {
                name: shard[name].copy()
                for name in ("cqi_history", "cqi_now", "previous_quality", "distance_m", "speed", "direction_to_gnb")
            }
            if dispersion not in common_by_dispersion:
                common_by_dispersion[dispersion] = common
            else:
                for name, values in common.items():
                    if not np.array_equal(values, common_by_dispersion[dispersion][name]):
                        raise AssertionError(f"{name} changed across profiles for {dispersion}")
            profile_rb_std[profile].append(float(rates.std(axis=2).mean()))
            mean_rate_by_dispersion[dispersion][profile] = float(rates.mean())

    dispersion_std = {
        dispersion: float(common["cqi_now"].std())
        for dispersion, common in common_by_dispersion.items()
    }
    if set(dispersion_std) == {"low", "mid_v2", "high"}:
        if not dispersion_std["low"] < dispersion_std["mid_v2"] < dispersion_std["high"]:
            raise AssertionError(f"CQI dispersion ordering failed: {dispersion_std}")

    profile_means = {name: float(np.mean(values)) for name, values in profile_rb_std.items()}
    if set(profile_means) == {"aligned", "moderate", "strong"}:
        if not profile_means["aligned"] < profile_means["moderate"] < profile_means["strong"]:
            raise AssertionError(f"frequency-selectivity ordering failed: {profile_means}")

    # The profile axis should change frequency shape rather than silently
    # creating a materially different mean-channel-strength condition.
    for dispersion, profile_rates in mean_rate_by_dispersion.items():
        if len(profile_rates) > 1:
            ratio = max(profile_rates.values()) / min(profile_rates.values())
            if ratio > 1.05:
                raise AssertionError(
                    f"mean RB rate differs by more than 5% across profiles "
                    f"for {dispersion}: {profile_rates}"
                )

    for dispersion, common in common_by_dispersion.items():
        cqi = common["cqi_now"].reshape(-1)
        previous = common["previous_quality"].reshape(-1)
        legacy = np.clip(cqi // 3, 0, 5)
        difference_ratio = float(np.mean(previous != legacy))
        if not 0.10 <= difference_ratio <= 0.70:
            raise AssertionError(
                f"previous-quality state is still redundant or implausibly "
                f"different for {dispersion}: {difference_ratio}"
            )

    # Round-trip one record per dispersion/profile/load through the public loader.
    sampled = {}
    with FairInputDataset(dataset_dir) as dataset:
        for record in dataset.records:
            key = (record.dispersion, record.frequency_profile, record.load_level)
            if key in sampled:
                continue
            scenario = dataset.scenario(record)
            if scenario.rb_rates.shape != (record.n_users, record.total_rbs):
                raise AssertionError(f"loader shape mismatch: {record.scenario_id}")
            if scenario.rb_available != record.rb_available:
                raise AssertionError(f"loader budget mismatch: {record.scenario_id}")
            sampled[key] = record.scenario_id

    with (dataset_dir / "data_quality_summary.csv").open(newline="", encoding="utf-8") as handle:
        qa_rows = list(csv.DictReader(handle))
    if len(qa_rows) != len(manifest["shards"]):
        raise AssertionError("QA row count does not match shard count")

    counts = Counter((r.dispersion, r.frequency_profile, r.load_level) for r in records)
    print(f"PASS dataset={dataset_dir}")
    print(f"  indexed scenarios: {len(records)}")
    print(f"  physical/profile states: {len(by_physical_profile)}")
    print(f"  shards: {len(manifest['shards'])}")
    print(f"  CQI std: {dispersion_std}")
    print(f"  mean per-user RB-rate std: {profile_means}")
    print(f"  mean RB rate by dispersion/profile: {dict(mean_rate_by_dispersion)}")
    print(f"  per-cell counts: {sorted(set(counts.values()))}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset_dir", type=Path)
    args = parser.parse_args()
    validate(args.dataset_dir)


if __name__ == "__main__":
    main()
