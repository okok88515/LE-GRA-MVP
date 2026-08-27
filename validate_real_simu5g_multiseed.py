"""Validate protocol-v3 real Simu5G runs and write aggregate QA artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from parse_real_simu5g_data import build_scenarios


DISPERSIONS = ("low", "mid", "high")
RB_RATIO = {"low": 0.5, "mid": 0.5, "high": 0.5}


def parse_seed_spec(spec: str) -> tuple[int, ...]:
    seeds: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", maxsplit=1)
            start, end = int(start_text), int(end_text)
            if end < start:
                raise ValueError(f"descending seed range is invalid: {part}")
            seeds.update(range(start, end + 1))
        else:
            seeds.add(int(part))
    if not seeds or min(seeds) < 0:
        raise ValueError("at least one non-negative seed is required")
    return tuple(sorted(seeds))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(
    root: Path,
    expected_seeds: tuple[int, ...],
    n_users: int = 24,
    gnb_pos: dict[int, tuple[float, float]] | None = None,
    expected_scenarios: int = 15,
    min_radio_rows: int = 4_500_000,
    min_mobility_rows: int = 10_000,
) -> list[dict[str, object]]:
    """`n_users`/`gnb_pos`/`expected_scenarios`/`min_*_rows` default to the
    original 24-vehicle scenario's validated values for full backward
    compatibility. Pass overrides for a differently-scaled scenario -- e.g.
    the direction-4 scale pilot uses `n_users=40,
    gnb_pos={1: (400.0, 160.0), 2: (400.0, 640.0)}, expected_scenarios=5,
    min_radio_rows=..., min_mobility_rows=...` (`REAL_SIMU5G_SCALE_PILOT.md`)."""

    rows: list[dict[str, object]] = []
    mobility_by_seed: dict[int, set[str]] = defaultdict(set)
    route_metadata_by_seed: dict[int, set[str]] = defaultdict(set)

    for seed in expected_seeds:
        for dispersion in DISPERSIONS:
            run_dir = root / dispersion / f"seed_{seed:04d}"
            manifest_path = run_dir / "run_manifest.json"
            if not manifest_path.is_file():
                raise AssertionError(f"missing manifest: {manifest_path}")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            if manifest["status"] != "complete":
                raise AssertionError(f"run is not complete: {run_dir}")
            if manifest["protocol_version"] != "3.0":
                raise AssertionError(f"wrong protocol version: {run_dir}")
            if manifest["seed"] != seed or manifest["dispersion"] != dispersion:
                raise AssertionError(f"manifest identity mismatch: {run_dir}")
            if manifest["omnetpp_seed_set"] != seed or manifest["sumo_seed"] != seed:
                raise AssertionError(f"seed mismatch: {run_dir}")
            # Seeded vehicle speeds change how long cars remain in the scene,
            # so total row counts are expected to vary. These lower bounds
            # catch truncation; the parser completeness gate below is the
            # authoritative learner-facing check.
            if manifest["radio"]["rows_including_header"] < min_radio_rows:
                raise AssertionError(f"radio export appears truncated: {run_dir}")
            if manifest["mobility"]["rows_including_header"] < min_mobility_rows:
                raise AssertionError(f"mobility export appears truncated: {run_dir}")

            radio_path = run_dir / manifest["radio"]["file"]
            mobility_path = run_dir / manifest["mobility"]["file"]
            for path, section in (
                (radio_path, manifest["radio"]),
                (mobility_path, manifest["mobility"]),
            ):
                actual = sha256_file(path)
                if actual != section["gzip_sha256"]:
                    raise AssertionError(f"gzip hash mismatch: {path}")

            mobility_hash = manifest["mobility"]["uncompressed_sha256"]
            mobility_by_seed[seed].add(mobility_hash)
            metadata_path = run_dir / "scenario" / "mobility_seed.json"
            route_metadata_by_seed[seed].add(sha256_file(metadata_path))

            scenarios = build_scenarios(
                RB_RATIO[dispersion],
                radio_path=radio_path,
                mobility_path=mobility_path,
                n_users=n_users,
                gnb_pos=gnb_pos,
            )
            if len(scenarios) != expected_scenarios:
                raise AssertionError(
                    f"expected {expected_scenarios} complete scenarios, got {len(scenarios)}: {run_dir}"
                )
            cqi = np.concatenate([scenario.cqi_now for scenario in scenarios])
            rows.append(
                {
                    "dispersion": dispersion,
                    "seed": seed,
                    "usable_scenarios": len(scenarios),
                    "users": int(scenarios[0].cqi_now.size),
                    "bands": int(scenarios[0].rb_rates.shape[1]),
                    "history_steps": int(scenarios[0].cqi_history.shape[1]),
                    "cqi_mean": float(cqi.mean()),
                    "cqi_std": float(cqi.std()),
                    "cqi_min": int(cqi.min()),
                    "cqi_p05": float(np.quantile(cqi, 0.05)),
                    "cqi_median": float(np.median(cqi)),
                    "cqi_p95": float(np.quantile(cqi, 0.95)),
                    "cqi_max": int(cqi.max()),
                    "duration_s": int(manifest["duration_s"]),
                    "radio_gzip_bytes": radio_path.stat().st_size,
                    "mobility_gzip_bytes": mobility_path.stat().st_size,
                    "radio_uncompressed_sha256": manifest["radio"]["uncompressed_sha256"],
                    "mobility_uncompressed_sha256": mobility_hash,
                }
            )
            print(
                f"PASS {dispersion}/seed_{seed:04d}: scenarios={len(scenarios)} "
                f"CQI={cqi.mean():.3f}+/-{cqi.std():.3f}",
                flush=True,
            )

    for seed in expected_seeds:
        if len(mobility_by_seed[seed]) != 1:
            raise AssertionError(
                f"seed {seed}: low/mid/high do not share one mobility trajectory"
            )
        if len(route_metadata_by_seed[seed]) != 1:
            raise AssertionError(
                f"seed {seed}: low/mid/high route metadata differs"
            )
    n_seeds = len(expected_seeds)
    if len({next(iter(mobility_by_seed[seed])) for seed in expected_seeds}) != n_seeds:
        raise AssertionError(f"expected {n_seeds} unique mobility trajectories across seeds")
    if len({next(iter(route_metadata_by_seed[seed])) for seed in expected_seeds}) != n_seeds:
        raise AssertionError(f"expected {n_seeds} unique generated route profiles across seeds")
    return rows


def write_outputs(
    root: Path, rows: list[dict[str, object]], expected_seeds: tuple[int, ...], label: str = ""
) -> None:
    suffix = f"_{label}" if label else ""
    csv_path = root / f"multiseed_qa{suffix}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    by_dispersion: dict[str, dict[str, float]] = {}
    for dispersion in DISPERSIONS:
        subset = [row for row in rows if row["dispersion"] == dispersion]
        by_dispersion[dispersion] = {
            "runs": len(subset),
            "usable_scenarios": sum(int(row["usable_scenarios"]) for row in subset),
            "mean_of_run_cqi_means": float(np.mean([row["cqi_mean"] for row in subset])),
            "mean_of_run_cqi_stds": float(np.mean([row["cqi_std"] for row in subset])),
            "min_run_cqi_mean": float(np.min([row["cqi_mean"] for row in subset])),
            "max_run_cqi_mean": float(np.max([row["cqi_mean"] for row in subset])),
        }

    aggregate = {
        "dataset": "real_simu5g_multiseed_data",
        "protocol_version": "3.0",
        "status": "validated",
        "dispersions": list(DISPERSIONS),
        "seeds": list(expected_seeds),
        "runs": len(rows),
        "usable_scenarios": sum(int(row["usable_scenarios"]) for row in rows),
        "unique_mobility_trajectories": len(expected_seeds),
        "same_mobility_across_dispersions_for_each_seed": True,
        "by_dispersion": by_dispersion,
        "qa_csv": csv_path.name,
    }
    (root / f"aggregate_manifest{suffix}.json").write_text(
        json.dumps(aggregate, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root", type=Path, nargs="?", default=Path("real_simu5g_multiseed_data")
    )
    parser.add_argument(
        "--seeds", default="1-10",
        help="Seed spec to validate, e.g. 1-10 or 11-30 or 1,3,8 (default: 1-10)",
    )
    parser.add_argument(
        "--label", default="",
        help="Suffix for output files (multiseed_qa_<label>.csv, "
        "aggregate_manifest_<label>.json) so a non-default --seeds run never "
        "overwrites the original seeds=1-10 QA artifacts.",
    )
    parser.add_argument("--n-users", type=int, default=24, help="Override for a differently-scaled scenario")
    parser.add_argument(
        "--gnb-pos", default="",
        help='Override gNB positions as "id1:x1,y1;id2:x2,y2", e.g. "1:400,160;2:400,640"',
    )
    parser.add_argument("--expected-scenarios", type=int, default=15)
    parser.add_argument("--min-radio-rows", type=int, default=4_500_000)
    parser.add_argument("--min-mobility-rows", type=int, default=10_000)
    args = parser.parse_args()
    expected_seeds = parse_seed_spec(args.seeds)
    if args.seeds != "1-10" and not args.label:
        raise SystemExit("pass --label when validating a non-default --seeds range")
    gnb_pos = None
    if args.gnb_pos:
        gnb_pos = {}
        for entry in args.gnb_pos.split(";"):
            gnb_id, coords = entry.split(":")
            x, y = coords.split(",")
            gnb_pos[int(gnb_id)] = (float(x), float(y))
    rows = validate(
        args.root, expected_seeds,
        n_users=args.n_users, gnb_pos=gnb_pos, expected_scenarios=args.expected_scenarios,
        min_radio_rows=args.min_radio_rows, min_mobility_rows=args.min_mobility_rows,
    )
    write_outputs(args.root, rows, expected_seeds, args.label)
    print(
        f"MULTISEED_QA_PASS runs={len(rows)} scenarios="
        f"{sum(int(row['usable_scenarios']) for row in rows)}"
    )


if __name__ == "__main__":
    main()
