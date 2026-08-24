"""Build the versioned fair-input benchmark dataset.

Large per-RB arrays are stored as compressed NumPy shards.  Human-auditable
scenario metadata and QA statistics are written as CSV/JSON.  The generated
directory is reproducible and intentionally not committed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp
from run_standard_matrix import LOAD_RATIOS


DATASET_VERSION = "1.0"
DISPERSIONS = ("low", "mid_v2", "high")
FREQUENCY_PROFILES = ("aligned", "moderate", "strong")
DEFAULT_SEEDS = tuple(range(1, 31))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_hash(path: Path) -> str:
    return sha256_file(path) if path.exists() else "missing"


def git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def lagged_previous_quality(cqi_history: np.ndarray) -> np.ndarray:
    """Build a pre-decision QoE state from lagged CQI with fixed hysteresis."""

    lagged_cqi = np.clip(np.rint(cqi_history[:, -2]).astype(int), 1, 15)
    quality = np.clip(lagged_cqi // 3, 0, len(mvp.VIDEO_BITRATES_KBPS) - 1)
    prior_trend = cqi_history[:, -2] - cqi_history[:, 0]
    # Adaptation lags an improving channel and temporarily preserves quality
    # when the channel has recently degraded.
    hysteresis = np.where(prior_trend > 1.0, -1, np.where(prior_trend < -1.0, 1, 0))
    return np.clip(quality + hysteresis, 0, len(mvp.VIDEO_BITRATES_KBPS) - 1).astype(np.int8)


def profile_rb_rates(base: mvp.Scenario, profile: str, derived_seed: int) -> np.ndarray:
    """Apply a controlled RB-frequency profile to an unchanged user state."""

    np.random.seed(derived_seed)
    if profile == "aligned":
        # The historical generator uses 1.15-CQI independent noise here.  For
        # this controlled profile axis, aligned means an intentionally flat
        # RB response; keep only light measurement-scale variation so the
        # moderate/strong conditions represent increasing selectivity.
        rb_cqi = np.clip(
            base.cqi_now[:, None]
            + np.random.normal(0.0, 0.25, size=base.rb_rates.shape),
            1,
            15,
        )
    elif profile == "moderate":
        rb_cqi = mvp.generate_corridor_general_rb_cqi(
            base.cqi_now,
            base.distance,
            base.speed,
            base.direction_to_gnb,
            base.rb_rates.shape[1],
        )
    elif profile == "strong":
        rb_cqi = mvp.generate_cqi_ambiguous_rb_cqi(
            base.cqi_now,
            base.direction_to_gnb,
            base.rb_rates.shape[1],
        )
    else:
        raise ValueError(f"Unknown frequency profile: {profile}")
    return mvp.cqi_to_rate_kbps(rb_cqi).astype(np.float32)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def make_base_scenarios(
    dispersion: str,
    seeds: list[int],
    snapshots_per_seed: int,
    users: int,
    rbs: int,
) -> tuple[list[mvp.Scenario], list[tuple[int, int]]]:
    scenarios: list[mvp.Scenario] = []
    provenance: list[tuple[int, int]] = []
    for seed in seeds:
        mvp.set_seed(seed)
        for draw_index in range(snapshots_per_seed):
            scenario = mvp.generate_scenario(
                users,
                rbs,
                dispersion,
                "aligned",
                rb_budget_ratio=LOAD_RATIOS["medium"],
            )
            scenario.previous_quality = lagged_previous_quality(scenario.cqi_history)
            scenarios.append(scenario)
            provenance.append((seed, draw_index))
    return scenarios, provenance


def stack_common(scenarios: list[mvp.Scenario]) -> dict[str, np.ndarray]:
    return {
        "cqi_history": np.stack([s.cqi_history for s in scenarios]).astype(np.float32),
        "cqi_now": np.stack([s.cqi_now for s in scenarios]).astype(np.int8),
        "previous_quality": np.stack([s.previous_quality for s in scenarios]).astype(np.int8),
        "distance_m": np.stack([s.distance for s in scenarios]).astype(np.float32),
        "speed": np.stack([s.speed for s in scenarios]).astype(np.float32),
        "direction_to_gnb": np.stack([s.direction_to_gnb for s in scenarios]).astype(np.float32),
        "speed_history": np.stack([s.speed_history for s in scenarios]).astype(np.float32),
    }


def summarize_cell(
    dispersion: str,
    profile: str,
    common: dict[str, np.ndarray],
    rb_rates: np.ndarray,
) -> dict:
    cqi = common["cqi_now"].reshape(-1)
    history = common["cqi_history"].reshape(-1, common["cqi_history"].shape[-1])
    previous = common["previous_quality"].reshape(-1)
    legacy_previous = np.clip(cqi // 3, 0, len(mvp.VIDEO_BITRATES_KBPS) - 1)
    per_user_rb_std = rb_rates.std(axis=2).reshape(-1)
    current_equals_previous_cqi = np.rint(history[:, -2]).astype(int) == cqi
    return {
        "dispersion": dispersion,
        "frequency_profile": profile,
        "physical_scenarios": int(common["cqi_now"].shape[0]),
        "user_observations": int(cqi.size),
        "cqi_mean": float(cqi.mean()),
        "cqi_std": float(cqi.std()),
        "cqi_p05": float(np.percentile(cqi, 5)),
        "cqi_p50": float(np.percentile(cqi, 50)),
        "cqi_p95": float(np.percentile(cqi, 95)),
        "cqi15_ratio": float(np.mean(cqi == 15)),
        "cqi_le5_ratio": float(np.mean(cqi <= 5)),
        "lagged_cqi_equals_current_ratio": float(np.mean(current_equals_previous_cqi)),
        "previous_quality_differs_from_legacy_ratio": float(np.mean(previous != legacy_previous)),
        "previous_quality_std": float(previous.std()),
        "rb_rate_mean": float(rb_rates.mean()),
        "per_user_rb_rate_std_mean": float(per_user_rb_std.mean()),
        "per_user_rb_rate_std_p95": float(np.percentile(per_user_rb_std, 95)),
    }


def build(args: argparse.Namespace) -> None:
    out_dir: Path = args.out_dir
    shard_dir = out_dir / "shards"
    out_dir.mkdir(parents=True, exist_ok=True)
    shard_dir.mkdir(parents=True, exist_ok=True)

    index_rows: list[dict] = []
    qa_rows: list[dict] = []
    shard_entries: list[dict] = []
    physical_count = 0

    for dispersion_index, dispersion in enumerate(args.dispersions):
        print(f"[{dispersion}] generating common user states...", flush=True)
        scenarios, provenance = make_base_scenarios(
            dispersion,
            args.seeds,
            args.snapshots_per_seed,
            args.users,
            args.rbs,
        )
        common = stack_common(scenarios)
        for profile_index, profile in enumerate(args.frequency_profiles):
            print(f"[{dispersion}/{profile}] deriving RB profiles...", flush=True)
            rb_rates = np.stack([
                profile_rb_rates(
                    scenario,
                    profile,
                    derived_seed=(
                        1_000_003 * (dispersion_index + 1)
                        + 10_007 * (profile_index + 1)
                        + 101 * seed
                        + draw_index
                    ),
                )
                for scenario, (seed, draw_index) in zip(scenarios, provenance)
            ])
            shard_name = f"{dispersion}__{profile}.npz"
            shard_path = shard_dir / shard_name
            np.savez_compressed(shard_path, **common, rb_rates=rb_rates)
            shard_entries.append({
                "dispersion": dispersion,
                "frequency_profile": profile,
                "path": f"shards/{shard_name}",
                "sha256": sha256_file(shard_path),
                "bytes": shard_path.stat().st_size,
                "physical_scenarios": len(scenarios),
            })
            qa_rows.append(summarize_cell(dispersion, profile, common, rb_rates))

            for array_index, (seed, draw_index) in enumerate(provenance):
                physical_id = f"{dispersion}__seed{seed:03d}__draw{draw_index:03d}"
                for load_level in args.loads:
                    ratio = LOAD_RATIOS[load_level]
                    index_rows.append({
                        "scenario_id": f"{physical_id}__{profile}__{load_level}",
                        "physical_state_id": physical_id,
                        "dispersion": dispersion,
                        "frequency_profile": profile,
                        "load_level": load_level,
                        "rb_budget_ratio": ratio,
                        "rb_available": max(1, int(round(ratio * args.rbs))),
                        "total_rbs": args.rbs,
                        "n_users": args.users,
                        "seed": seed,
                        "draw_index": draw_index,
                        "shard_path": f"shards/{shard_name}",
                        "array_index": array_index,
                    })
            physical_count += len(scenarios)
        del scenarios, common

    write_csv(out_dir / "scenario_index.csv", list(index_rows[0]), index_rows)
    write_csv(out_dir / "data_quality_summary.csv", list(qa_rows[0]), qa_rows)

    manifest = {
        "dataset_name": "fair_input_dataset_v1",
        "dataset_version": DATASET_VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_head_before_build": git_head(),
        "protocol_file": "FAIR_INPUT_DATASET_V1.md",
        "generator": {
            "script": "build_fair_input_dataset.py",
            "script_sha256": source_hash(Path(__file__)),
            "mvp_sha256": source_hash(Path(mvp.__file__)),
        },
        "parameters": {
            "users": args.users,
            "rbs": args.rbs,
            "seeds": args.seeds,
            "snapshots_per_seed": args.snapshots_per_seed,
            "dispersions": args.dispersions,
            "frequency_profiles": args.frequency_profiles,
            "loads": {name: LOAD_RATIOS[name] for name in args.loads},
            "scenario_mode_for_common_state": "aligned",
            "previous_quality_rule": "lagged_cqi_with_fixed_trend_hysteresis_v1",
        },
        "counts": {
            "physical_profile_scenarios": physical_count,
            "load_expanded_scenarios": len(index_rows),
            "user_observations_per_profile": len(args.seeds) * args.snapshots_per_seed * args.users,
        },
        "array_schema": {
            "cqi_history": "float32 [scenario,user,5]",
            "cqi_now": "int8 [scenario,user]",
            "previous_quality": "int8 [scenario,user]",
            "rb_rates": "float32 [scenario,user,rb] kbps",
            "distance_m": "float32 [scenario,user]",
            "speed": "float32 [scenario,user] generator-native km/h",
            "direction_to_gnb": "float32 [scenario,user]",
            "speed_history": "float32 [scenario,user,5] generator-native km/h",
        },
        "shards": shard_entries,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {out_dir}: {physical_count} physical/profile scenarios, "
        f"{len(index_rows)} load-expanded rows, {len(shard_entries)} shards.",
        flush=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("fair_input_dataset_v1"))
    parser.add_argument("--users", type=int, default=150)
    parser.add_argument("--rbs", type=int, default=100)
    parser.add_argument("--seeds", nargs="+", type=int, default=list(DEFAULT_SEEDS))
    parser.add_argument("--snapshots-per-seed", type=int, default=20)
    parser.add_argument("--dispersions", nargs="+", choices=DISPERSIONS, default=list(DISPERSIONS))
    parser.add_argument(
        "--frequency-profiles", nargs="+", choices=FREQUENCY_PROFILES,
        default=list(FREQUENCY_PROFILES),
    )
    parser.add_argument("--loads", nargs="+", choices=list(LOAD_RATIOS), default=list(LOAD_RATIOS))
    args = parser.parse_args()
    if args.users <= 1 or args.rbs <= 0 or args.snapshots_per_seed <= 0 or not args.seeds:
        parser.error("users, rbs, snapshots-per-seed, and seeds must be positive")
    return args


if __name__ == "__main__":
    build(parse_args())
