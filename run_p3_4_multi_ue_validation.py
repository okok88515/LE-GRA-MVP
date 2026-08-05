"""Validate the small real Simu5G multi-UE P3.4 trace."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from simu5g_raw_radio_export import export_raw_radio


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    root = Path("p3_4_actual_radio")
    raw_path = root / "multi_ue_raw_radio.csv"
    out_dir = root / "multi_ue_normalized"
    counts = export_raw_radio(
        raw_path,
        out_dir,
        slot_duration_ms=1.0,
        snapshot_period_s=0.1,
        rb_budget_ratio=0.5,
        previous_quality=3,
    )
    users = _read(out_dir / "radio_users.csv")
    rbs = _read(out_dir / "radio_rbs.csv")
    by_user_snapshot: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rbs:
        by_user_snapshot[(row["timestamp_s"], row["ue_id"])].append(row)

    assert counts == {
        "raw_rows": 10020,
        "radio_users": 105,
        "radio_rbs": 630,
        "dropped_out_of_coverage": 0,
    }
    assert len({row["ue_id"] for row in users}) == 5
    assert all(row["total_rbs"] == "6" and row["rb_available"] == "3" for row in users)
    assert all(
        sorted(int(row["rb_index"]) for row in rows) == list(range(6))
        for rows in by_user_snapshot.values()
    )
    assert len({row["cqi"] for row in rbs}) >= 4
    assert len({row["rate_kbps"] for row in rbs}) >= 4
    assert any(len({row["cqi"] for row in rows}) > 1 for rows in by_user_snapshot.values())
    print(
        "P3.4 MULTI-UE PASS: 5 UEs, complete 6-band snapshots, "
        "and real cross-user/per-band CQI-TBS variation verified"
    )


if __name__ == "__main__":
    main()
