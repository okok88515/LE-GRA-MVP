"""CLI: join SUMO mobility staging with Simu5G radio CSVs."""

from __future__ import annotations

import argparse
from pathlib import Path

from simu5g_trace_io import build_trace_bundle


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mobility-dir", type=Path, required=True)
    parser.add_argument("--radio-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("sumo_simu5g_trace_bundle"))
    parser.add_argument("--min-users", type=int, default=1)
    parser.add_argument("--max-users", type=int, default=0)
    args = parser.parse_args()
    stats = build_trace_bundle(
        args.mobility_dir,
        args.radio_dir,
        args.out_dir,
        min_users=args.min_users,
        max_users=args.max_users,
    )
    for filename in ("scenarios.csv", "users.csv", "rb_rates.csv"):
        print(f"Saved {args.out_dir / filename}", flush=True)
    print(f"P3.2 join complete: {stats}", flush=True)


if __name__ == "__main__":
    main()
