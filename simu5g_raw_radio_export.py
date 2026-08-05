"""Normalize the raw P3.4 Simu5G recorder output into the P3.2 schema."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path


RAW_FIELDS = {
    "timestamp_s",
    "ue_node_id",
    "gnb_node_id",
    "band_index",
    "cqi",
    "tbs_bits_per_slot",
    "total_bands",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = RAW_FIELDS.difference(reader.fieldnames or ())
        if missing:
            raise ValueError(f"Missing raw recorder columns: {sorted(missing)}")
        return list(reader)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _bin_time(timestamp: Decimal, period: Decimal) -> Decimal:
    return (timestamp / period).to_integral_value(rounding=ROUND_FLOOR) * period


def export_raw_radio(
    raw_csv: Path | str,
    out_dir: Path | str,
    *,
    slot_duration_ms: float,
    snapshot_period_s: float,
    rb_budget_ratio: float,
    previous_quality: int,
    ue_id_by_module: dict[str, str] | None = None,
) -> dict[str, int]:
    if slot_duration_ms <= 0:
        raise ValueError("slot_duration_ms must be positive")
    if snapshot_period_s <= 0:
        raise ValueError("snapshot_period_s must be positive")
    if not 0 < rb_budget_ratio <= 1:
        raise ValueError("rb_budget_ratio must be in (0, 1]")
    if not 0 <= previous_quality < 6:
        raise ValueError("previous_quality must be in [0, 5]")

    raw_rows = _read_csv(Path(raw_csv))
    period = Decimal(str(snapshot_period_s))
    snapshots: dict[tuple[Decimal, str, str], dict[Decimal, list[dict]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in raw_rows:
        timestamp = Decimal(row["timestamp_s"])
        if ue_id_by_module is None:
            ue_id = f"ue_{row['ue_node_id']}"
        else:
            module_path = row.get("ue_module_path", "")
            if module_path not in ue_id_by_module:
                raise ValueError(f"No SUMO ID mapping for module path: {module_path!r}")
            ue_id = ue_id_by_module[module_path]
        key = (
            _bin_time(timestamp, period),
            ue_id,
            f"gnb_{row['gnb_node_id']}",
        )
        snapshots[key][timestamp].append(row)

    user_rows: list[dict] = []
    rb_rows: list[dict] = []
    for (timestamp, ue_id, gnb_id), observations in sorted(snapshots.items()):
        # Feedback may arrive more than once in one study interval. Keep the
        # latest complete observation and assign the common bin timestamp.
        latest_time = max(observations)
        rows = observations[latest_time]
        totals = {int(row["total_bands"]) for row in rows}
        if len(totals) != 1:
            raise ValueError(f"Inconsistent total_bands at {latest_time}/{ue_id}")
        total_bands = totals.pop()
        by_band = {int(row["band_index"]): row for row in rows}
        if len(by_band) != len(rows):
            raise ValueError(f"Duplicate band at {latest_time}/{ue_id}")
        if sorted(by_band) != list(range(total_bands)):
            raise ValueError(f"Incomplete band vector at {latest_time}/{ue_id}")

        cqis = [float(by_band[band]["cqi"]) for band in range(total_bands)]
        if any(cqi < 0 or cqi > 15 for cqi in cqis):
            raise ValueError(f"CQI outside 0..15 at {latest_time}/{ue_id}")
        wideband_cqi = sum(cqis) / total_bands
        if wideband_cqi < 1:
            # P3.2 defines usable attached UEs as CQI 1..15. Do not clamp or
            # fabricate an out-of-coverage observation.
            continue

        rb_available = max(1, min(total_bands, round(total_bands * rb_budget_ratio)))
        user_rows.append({
            "timestamp_s": str(timestamp),
            "ue_id": ue_id,
            "serving_gnb": gnb_id,
            "wideband_cqi": f"{wideband_cqi:.6f}",
            "previous_quality": previous_quality,
            "total_rbs": total_bands,
            "rb_available": rb_available,
            "wideband_sinr_db": "",
            "rsrp_dbm": "",
            "rsrq_db": "",
            "mcs": "",
        })
        for band in range(total_bands):
            raw = by_band[band]
            # bits/slot divided by ms/slot is numerically kbit/s.
            rate_kbps = float(raw["tbs_bits_per_slot"]) / slot_duration_ms
            rb_rows.append({
                "timestamp_s": str(timestamp),
                "ue_id": ue_id,
                "serving_gnb": gnb_id,
                "rb_index": band,
                "rate_kbps": f"{rate_kbps:.6f}",
                "sinr_db": "",
                "cqi": raw["cqi"],
            })

    out_dir = Path(out_dir)
    _write_csv(out_dir / "radio_users.csv", [
        "timestamp_s", "ue_id", "serving_gnb", "wideband_cqi",
        "previous_quality", "total_rbs", "rb_available",
        "wideband_sinr_db", "rsrp_dbm", "rsrq_db", "mcs",
    ], user_rows)
    _write_csv(out_dir / "radio_rbs.csv", [
        "timestamp_s", "ue_id", "serving_gnb", "rb_index", "rate_kbps",
        "sinr_db", "cqi",
    ], rb_rows)
    metadata = {
        "schema": "legra-simu5g-radio-export-v1",
        "source": "Simu5G LteMacEnb ALLBANDS feedback",
        "rate_source": "Simu5G NrAmc::computeBitsPerRbBackground",
        "rate_formula": "rate_kbps = tbs_bits_per_slot / slot_duration_ms",
        "slot_duration_ms": slot_duration_ms,
        "snapshot_period_s": snapshot_period_s,
        "snapshot_rule": "latest complete UE feedback in each floor-aligned time bin",
        "rb_budget_ratio": rb_budget_ratio,
        "rb_budget_rule": "round(total_logical_bands * ratio), clipped to [1, total]",
        "previous_quality": previous_quality,
        "previous_quality_source": "explicit_experiment_control_not_video_measurement",
        "rb_abstraction": "Simu5G logical band",
        "sinr_source": "not_exported_in_p3_4",
        "ue_id_source": (
            "Simu5G_internal_node_id" if ue_id_by_module is None
            else "SUMO_external_id_joined_by_OMNeT_module_path"
        ),
    }
    (out_dir / "export_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "raw_rows": len(raw_rows),
        "radio_users": len(user_rows),
        "radio_rbs": len(rb_rows),
        "dropped_out_of_coverage": len(snapshots) - len(user_rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-csv", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--slot-duration-ms", type=float, required=True)
    parser.add_argument("--snapshot-period-s", type=float, default=0.1)
    parser.add_argument("--rb-budget-ratio", type=float, required=True)
    parser.add_argument("--previous-quality", type=int, required=True)
    args = parser.parse_args()
    counts = export_raw_radio(
        args.raw_csv,
        args.out_dir,
        slot_duration_ms=args.slot_duration_ms,
        snapshot_period_s=args.snapshot_period_s,
        rb_budget_ratio=args.rb_budget_ratio,
        previous_quality=args.previous_quality,
    )
    print("P3.4 normalized radio export:")
    for name, value in counts.items():
        print(f"  {name}={value}")


if __name__ == "__main__":
    main()
