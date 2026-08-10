"""Audit how much optional radio-side signal is actually populated in a bundle."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _coverage(rows: list[dict[str, str]], field: str) -> tuple[int, int, float]:
    total = len(rows)
    present = sum(1 for row in rows if row.get(field, "").strip() != "")
    ratio = 0.0 if total == 0 else present / total
    return present, total, ratio


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--out-csv", type=Path, default=None)
    args = parser.parse_args()

    bundle_root = args.bundle_root
    radio_users = _read_csv(bundle_root / "radio" / "radio_users.csv")
    radio_rbs = _read_csv(bundle_root / "radio" / "radio_rbs.csv")
    bundle_users = _read_csv(bundle_root / "bundle" / "users.csv")
    bundle_rbs = _read_csv(bundle_root / "bundle" / "rb_rates.csv")

    checks = [
        ("radio_users", "wideband_sinr_db", radio_users),
        ("radio_users", "rsrp_dbm", radio_users),
        ("radio_users", "rsrq_db", radio_users),
        ("radio_users", "mcs", radio_users),
        ("radio_rbs", "sinr_db", radio_rbs),
        ("bundle_users", "wideband_sinr_db", bundle_users),
        ("bundle_users", "rsrp_dbm", bundle_users),
        ("bundle_users", "rsrq_db", bundle_users),
        ("bundle_users", "mcs", bundle_users),
        ("bundle_rb_rates", "sinr_db", bundle_rbs),
    ]

    rows = []
    for table_name, field_name, source_rows in checks:
        present, total, ratio = _coverage(source_rows, field_name)
        rows.append(
            {
                "bundle_root": str(bundle_root),
                "table": table_name,
                "field": field_name,
                "present_rows": present,
                "total_rows": total,
                "coverage_ratio": f"{ratio:.6f}",
            }
        )

    if args.out_csv is not None:
        args.out_csv.parent.mkdir(parents=True, exist_ok=True)
        with args.out_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    print("Radio signal coverage audit:")
    for row in rows:
        print(
            f"  {row['table']}.{row['field']}: "
            f"{row['present_rows']}/{row['total_rows']} "
            f"({row['coverage_ratio']})"
        )


if __name__ == "__main__":
    main()
