"""CLI for converting SUMO FCD output into P3.1 mobility staging CSVs."""

from __future__ import annotations

import argparse
from pathlib import Path

from sumo_mobility_io import export_mobility_staging


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fcd", type=Path, required=True)
    parser.add_argument("--gnbs", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("sumo_mobility_staging"))
    parser.add_argument("--min-users", type=int, default=1)
    parser.add_argument("--max-users", type=int, default=0, help="0 keeps every UE")
    args = parser.parse_args()
    scenarios, mobility = export_mobility_staging(
        args.fcd,
        args.gnbs,
        args.out_dir,
        min_users=args.min_users,
        max_users=args.max_users,
    )
    unique_ues = len({row["ue_id"] for row in mobility})
    print(f"Saved {args.out_dir / 'sumo_scenarios.csv'}", flush=True)
    print(f"Saved {args.out_dir / 'sumo_mobility.csv'}", flush=True)
    print(
        f"P3.1 export complete: snapshots={len(scenarios)}, "
        f"rows={len(mobility)}, unique_ues={unique_ues}",
        flush=True,
    )


if __name__ == "__main__":
    main()

