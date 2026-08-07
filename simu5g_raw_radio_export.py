"""Normalize the raw P3.4 Simu5G recorder output into the P3.2 schema."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path

VIDEO_BITRATES_KBPS = (200.0, 550.0, 1500.0, 3000.0, 5800.0, 7500.0)


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


def _highest_quality_for_capacity(capacity_kbps: float) -> int:
    quality = 0
    for index, bitrate in enumerate(VIDEO_BITRATES_KBPS):
        if capacity_kbps >= bitrate:
            quality = index
    return quality


def _ue_behavior_profile(ue_id: str) -> dict[str, float | int | str]:
    """Assign a deterministic adaptation profile to each UE.

    The mapping is fixed from UE id so the same trace always yields the same
    QoE-state heterogeneity without introducing uncontrolled randomness.
    """

    try:
        numeric_id = int(ue_id)
    except ValueError:
        numeric_id = sum(ord(ch) for ch in ue_id)
    profile_index = numeric_id % 3
    if profile_index == 0:
        return {
            "demand_class": "conservative",
            "initial_quality": 0,
            "initial_buffer_s": 3.2,
            "bootstrap_factor": 0.48,
            "ewma_alpha": 0.22,
            "capacity_discount": 0.90,
            "upgrade_buffer_s": 5.2,
            "max_upgrade_step": 1,
        }
    if profile_index == 1:
        return {
            "demand_class": "balanced",
            "initial_quality": 1,
            "initial_buffer_s": 2.0,
            "bootstrap_factor": 0.55,
            "ewma_alpha": 0.35,
            "capacity_discount": 0.95,
            "upgrade_buffer_s": 4.0,
            "max_upgrade_step": 1,
        }
    return {
        "demand_class": "aggressive",
        "initial_quality": 2,
        "initial_buffer_s": 1.1,
        "bootstrap_factor": 0.66,
        "ewma_alpha": 0.46,
        "capacity_discount": 1.02,
        "upgrade_buffer_s": 2.5,
        "max_upgrade_step": 2,
    }


def _ue_behavior_profile_family_divergence(ue_id: str) -> dict[str, float | int | str]:
    """Targeted profile set for P3.6j-1.

    The goal is to keep the p3_6i2 traffic interaction structure unchanged
    while enlarging previous-quality divergence inside the informative
    families. Higher-demand users start with more quality/buffer headroom and
    are allowed to sustain or upgrade quality more easily; lower-demand users
    are deliberately more cautious.
    """

    high_anchor = {"0", "1", "15", "31"}
    low_anchor = {"2", "3", "4", "5", "6", "7"}
    if ue_id in high_anchor:
        return {
            "demand_class": "high_anchor",
            "initial_quality": 3,
            "initial_buffer_s": 5.4,
            "bootstrap_factor": 0.78,
            "ewma_alpha": 0.52,
            "capacity_discount": 1.06,
            "upgrade_buffer_s": 1.8,
            "max_upgrade_step": 2,
            "min_quality": 2,
            "max_quality": 5,
        }
    if ue_id in low_anchor:
        return {
            "demand_class": "low_anchor",
            "initial_quality": 0,
            "initial_buffer_s": 1.0,
            "bootstrap_factor": 0.44,
            "ewma_alpha": 0.20,
            "capacity_discount": 0.82,
            "upgrade_buffer_s": 6.2,
            "max_upgrade_step": 1,
            "min_quality": 0,
            "max_quality": 1,
        }
    return {
        "demand_class": "bridge",
        "initial_quality": 1,
        "initial_buffer_s": 2.4,
        "bootstrap_factor": 0.58,
        "ewma_alpha": 0.33,
        "capacity_discount": 0.93,
        "upgrade_buffer_s": 4.2,
        "max_upgrade_step": 1,
        "min_quality": 1,
        "max_quality": 3,
    }


def _derive_quality_states(
    snapshot_records: list[dict],
    snapshot_period_s: float,
    *,
    heterogeneous_profiles: bool = False,
    family_divergence_profiles: bool = False,
    seg01_targeted_window_mode: str | None = None,
) -> tuple[dict[tuple[Decimal, str], int], list[dict]]:
    by_ue: dict[str, list[dict]] = defaultdict(list)
    active_users_by_snapshot: dict[tuple[Decimal, str], int] = defaultdict(int)
    for record in snapshot_records:
        by_ue[record["ue_id"]].append(record)
        active_users_by_snapshot[(record["timestamp"], record["serving_gnb"])] += 1

    previous_quality_by_key: dict[tuple[Decimal, str], int] = {}
    state_rows: list[dict] = []
    for ue_id, records in sorted(by_ue.items()):
        if family_divergence_profiles:
            profile = _ue_behavior_profile_family_divergence(ue_id)
        elif heterogeneous_profiles:
            profile = _ue_behavior_profile(ue_id)
        else:
            profile = {
                "demand_class": "uniform",
                "initial_quality": 1,
                "initial_buffer_s": 2.0,
                "bootstrap_factor": 0.55,
                "ewma_alpha": 0.35,
                "capacity_discount": 0.95,
                "upgrade_buffer_s": 4.0,
                "max_upgrade_step": 1,
                "min_quality": 0,
                "max_quality": len(VIDEO_BITRATES_KBPS) - 1,
            }
        quality = int(profile["initial_quality"])
        buffer_s = float(profile["initial_buffer_s"])
        ewma_capacity_kbps: float | None = None
        last_timestamp: Decimal | None = None
        for record in sorted(records, key=lambda item: (item["timestamp"], item["serving_gnb"])):
            timestamp = record["timestamp"]
            if seg01_targeted_window_mode:
                if Decimal("43.7") <= timestamp <= Decimal("43.9"):
                    if seg01_targeted_window_mode == "hard":
                        if ue_id in {"0", "1", "15"}:
                            quality = max(quality, 3)
                        elif ue_id in {"2", "3", "4", "5"}:
                            quality = min(quality, 0)
                    elif seg01_targeted_window_mode == "mild":
                        if ue_id in {"0", "1", "15"}:
                            quality = max(quality, 2)
                        elif ue_id in {"2", "3", "4", "5"}:
                            quality = min(quality, 1)
            dt = snapshot_period_s if last_timestamp is None else max(
                snapshot_period_s,
                float(timestamp - last_timestamp),
            )
            active_users = active_users_by_snapshot[(timestamp, record["serving_gnb"])]
            achievable_kbps = sum(record["rates_desc"][:record["rb_available"]])
            effective_capacity_kbps = achievable_kbps / active_users
            if ewma_capacity_kbps is None:
                ewma_capacity_kbps = effective_capacity_kbps * float(profile["bootstrap_factor"])
            else:
                alpha = float(profile["ewma_alpha"])
                ewma_capacity_kbps = (1.0 - alpha) * ewma_capacity_kbps + alpha * effective_capacity_kbps

            previous_quality_by_key[(timestamp, ue_id)] = quality
            playback_kbps = VIDEO_BITRATES_KBPS[quality]
            buffer_s = max(
                0.0,
                min(
                    12.0,
                    buffer_s + dt * (effective_capacity_kbps - playback_kbps) / max(playback_kbps, 1.0),
                ),
            )

            if buffer_s < 1.0:
                capacity_margin = 0.72
            elif buffer_s < 3.0:
                capacity_margin = 0.82
            elif buffer_s < 6.0:
                capacity_margin = 0.90
            else:
                capacity_margin = 0.97
            safe_capacity_kbps = min(
                effective_capacity_kbps * float(profile["capacity_discount"]),
                ewma_capacity_kbps * capacity_margin,
            )
            target_quality = _highest_quality_for_capacity(safe_capacity_kbps)

            if target_quality < quality:
                next_quality = target_quality
            elif target_quality > quality and buffer_s >= float(profile["upgrade_buffer_s"]):
                next_quality = min(target_quality, quality + int(profile["max_upgrade_step"]))
            else:
                next_quality = quality
            next_quality = max(
                int(profile.get("min_quality", 0)),
                min(int(profile.get("max_quality", len(VIDEO_BITRATES_KBPS) - 1)), next_quality),
            )

            state_rows.append({
                "timestamp_s": str(timestamp),
                "ue_id": ue_id,
                "demand_class": profile["demand_class"],
                "serving_gnb": record["serving_gnb"],
                "active_ues_same_gnb": active_users,
                "raw_feedback_timestamp_s": str(record["latest_time"]),
                "achievable_kbps_if_all_budget_assigned": f"{achievable_kbps:.6f}",
                "effective_capacity_kbps": f"{effective_capacity_kbps:.6f}",
                "ewma_capacity_kbps": f"{ewma_capacity_kbps:.6f}",
                "buffer_s": f"{buffer_s:.6f}",
                "previous_quality": quality,
                "next_quality": next_quality,
                "stalled": int(buffer_s <= 0.0),
            })
            quality = next_quality
            last_timestamp = timestamp
    return previous_quality_by_key, state_rows


def export_raw_radio(
    raw_csv: Path | str,
    out_dir: Path | str,
    *,
    slot_duration_ms: float,
    snapshot_period_s: float,
    rb_budget_ratio: float,
    previous_quality: int = 3,
    previous_quality_mode: str = "constant",
    ue_id_by_module: dict[str, str] | None = None,
) -> dict[str, int]:
    if slot_duration_ms <= 0:
        raise ValueError("slot_duration_ms must be positive")
    if snapshot_period_s <= 0:
        raise ValueError("snapshot_period_s must be positive")
    if not 0 < rb_budget_ratio <= 1:
        raise ValueError("rb_budget_ratio must be in (0, 1]")
    if previous_quality_mode not in {
        "constant",
        "deterministic_controller",
        "deterministic_controller_heterogeneous",
        "deterministic_controller_family_divergence",
        "deterministic_controller_seg01_targeted",
        "deterministic_controller_seg01_targeted_mild",
    }:
        raise ValueError(
            "previous_quality_mode must be 'constant', "
            "'deterministic_controller', 'deterministic_controller_heterogeneous', "
            "'deterministic_controller_family_divergence', or "
            "'deterministic_controller_seg01_targeted', or "
            "'deterministic_controller_seg01_targeted_mild'"
        )
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

    snapshot_records: list[dict] = []
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
        snapshot_records.append({
            "timestamp": timestamp,
            "ue_id": ue_id,
            "serving_gnb": gnb_id,
            "wideband_cqi": wideband_cqi,
            "total_bands": total_bands,
            "rb_available": rb_available,
            "latest_time": latest_time,
            "rows": rows,
            "rates_desc": sorted(
                (float(by_band[band]["tbs_bits_per_slot"]) / slot_duration_ms for band in range(total_bands)),
                reverse=True,
            ),
        })

    records_by_ue_time: dict[tuple[Decimal, str], dict] = {}
    collapsed_duplicates = 0
    for record in snapshot_records:
        key = (record["timestamp"], record["ue_id"])
        prior = records_by_ue_time.get(key)
        if prior is None or record["latest_time"] > prior["latest_time"]:
            if prior is not None:
                collapsed_duplicates += 1
            records_by_ue_time[key] = record
        elif prior is not None:
            collapsed_duplicates += 1
    snapshot_records = sorted(
        records_by_ue_time.values(),
        key=lambda item: (item["timestamp"], item["ue_id"]),
    )

    if previous_quality_mode == "constant":
        previous_quality_by_key = {
            (record["timestamp"], record["ue_id"]): previous_quality
            for record in snapshot_records
        }
        quality_state_rows = []
        previous_quality_source = "explicit_experiment_control_not_video_measurement"
    else:
        previous_quality_by_key, quality_state_rows = _derive_quality_states(
            snapshot_records,
            snapshot_period_s,
            heterogeneous_profiles=(
                previous_quality_mode == "deterministic_controller_heterogeneous"
            ),
            family_divergence_profiles=(
                previous_quality_mode == "deterministic_controller_family_divergence"
            ),
            seg01_targeted_window_mode=(
                "hard"
                if previous_quality_mode == "deterministic_controller_seg01_targeted"
                else "mild"
                if previous_quality_mode == "deterministic_controller_seg01_targeted_mild"
                else None
            ),
        )
        if previous_quality_mode == "deterministic_controller_heterogeneous":
            previous_quality_source = (
                "deterministic_heterogeneous_adaptation_controller_from_radio_capacity_and_cell_load"
            )
        elif previous_quality_mode == "deterministic_controller_seg01_targeted":
            previous_quality_source = (
                "deterministic_seg01_targeted_quality_divergence_controller_from_radio_capacity_and_cell_load"
            )
        elif previous_quality_mode == "deterministic_controller_seg01_targeted_mild":
            previous_quality_source = (
                "deterministic_seg01_targeted_mild_quality_divergence_controller_from_radio_capacity_and_cell_load"
            )
        elif previous_quality_mode == "deterministic_controller_family_divergence":
            previous_quality_source = (
                "deterministic_family_divergence_adaptation_controller_from_radio_capacity_and_cell_load"
            )
        else:
            previous_quality_source = (
                "deterministic_adaptation_controller_from_radio_capacity_and_cell_load"
            )

    user_rows: list[dict] = []
    rb_rows: list[dict] = []
    for record in snapshot_records:
        timestamp = record["timestamp"]
        ue_id = record["ue_id"]
        gnb_id = record["serving_gnb"]
        user_rows.append({
            "timestamp_s": str(timestamp),
            "ue_id": ue_id,
            "serving_gnb": gnb_id,
            "wideband_cqi": f"{record['wideband_cqi']:.6f}",
            "previous_quality": previous_quality_by_key[(timestamp, ue_id)],
            "total_rbs": record["total_bands"],
            "rb_available": record["rb_available"],
            "wideband_sinr_db": "",
            "rsrp_dbm": "",
            "rsrq_db": "",
            "mcs": "",
        })
        rows = record["rows"]
        by_band = {int(row["band_index"]): row for row in rows}
        for band in range(record["total_bands"]):
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
    if quality_state_rows:
        _write_csv(out_dir / "quality_state.csv", [
            "timestamp_s", "ue_id", "demand_class", "serving_gnb", "active_ues_same_gnb",
            "raw_feedback_timestamp_s", "achievable_kbps_if_all_budget_assigned",
            "effective_capacity_kbps", "ewma_capacity_kbps", "buffer_s",
            "previous_quality", "next_quality", "stalled",
        ], quality_state_rows)
    metadata = {
        "schema": "legra-simu5g-radio-export-v1",
        "source": "Simu5G LteMacEnb ALLBANDS feedback",
        "rate_source": "Simu5G NrAmc::computeBitsPerRbBackground",
        "rate_formula": "rate_kbps = tbs_bits_per_slot / slot_duration_ms",
        "slot_duration_ms": slot_duration_ms,
        "snapshot_period_s": snapshot_period_s,
        "snapshot_rule": (
            "latest complete UE feedback in each floor-aligned time bin; "
            "if multiple gNB observations remain for one UE/time bin, keep the latest raw timestamp"
        ),
        "rb_budget_ratio": rb_budget_ratio,
        "rb_budget_rule": "round(total_logical_bands * ratio), clipped to [1, total]",
        "previous_quality": previous_quality,
        "previous_quality_mode": previous_quality_mode,
        "previous_quality_source": previous_quality_source,
        "rb_abstraction": "Simu5G logical band",
        "sinr_source": "not_exported_in_p3_4",
        "ue_id_source": (
            "Simu5G_internal_node_id" if ue_id_by_module is None
            else "SUMO_external_id_joined_by_OMNeT_module_path"
        ),
        "collapsed_same_bin_duplicates": collapsed_duplicates,
    }
    if previous_quality_mode in {
        "deterministic_controller",
        "deterministic_controller_heterogeneous",
        "deterministic_controller_family_divergence",
        "deterministic_controller_seg01_targeted",
        "deterministic_controller_seg01_targeted_mild",
    }:
        metadata["quality_controller"] = {
            "type": (
                "ewma_buffer_adaptation_seg01_targeted_mild"
                if previous_quality_mode == "deterministic_controller_seg01_targeted_mild"
                else
                "ewma_buffer_adaptation_seg01_targeted"
                if previous_quality_mode == "deterministic_controller_seg01_targeted"
                else
                "ewma_buffer_adaptation_family_divergence"
                if previous_quality_mode == "deterministic_controller_family_divergence"
                else
                "ewma_buffer_adaptation_heterogeneous"
                if previous_quality_mode == "deterministic_controller_heterogeneous"
                else "ewma_buffer_adaptation"
            ),
            "bitrates_kbps": list(VIDEO_BITRATES_KBPS),
            "effective_capacity_rule": (
                "sum(top rb_available per-band rates) divided by active UE count "
                "in the same (timestamp, serving_gnb) snapshot"
            ),
            "ewma_rule": (
                "per-UE alpha profile; uniform mode uses 0.65 * previous + 0.35 * current"
            ),
            "buffer_range_s": [0.0, 12.0],
            "initial_quality": (
                {"high_anchor": 2, "low_anchor": 1, "bridge": 1}
                if previous_quality_mode == "deterministic_controller_seg01_targeted_mild"
                else
                {"high_anchor": 3, "low_anchor": 0, "bridge": 1}
                if previous_quality_mode == "deterministic_controller_seg01_targeted"
                else
                {"high_anchor": 3, "low_anchor": 0, "bridge": 1}
                if previous_quality_mode == "deterministic_controller_family_divergence"
                else
                {"conservative": 0, "balanced": 1, "aggressive": 2}
                if previous_quality_mode == "deterministic_controller_heterogeneous"
                else 1
            ),
            "initial_buffer_s": (
                {"high_anchor": 4.2, "low_anchor": 2.1, "bridge": 2.4}
                if previous_quality_mode == "deterministic_controller_seg01_targeted_mild"
                else
                {"high_anchor": 5.4, "low_anchor": 1.0, "bridge": 2.4}
                if previous_quality_mode == "deterministic_controller_seg01_targeted"
                else
                {"high_anchor": 5.4, "low_anchor": 1.0, "bridge": 2.4}
                if previous_quality_mode == "deterministic_controller_family_divergence"
                else
                {"conservative": 3.2, "balanced": 2.0, "aggressive": 1.1}
                if previous_quality_mode == "deterministic_controller_heterogeneous"
                else 2.0
            ),
            "quality_bounds": (
                {"high_anchor": [2, 2], "low_anchor": [1, 1], "bridge": [1, 3], "target_window_s": [43.7, 43.9]}
                if previous_quality_mode == "deterministic_controller_seg01_targeted_mild"
                else
                {"high_anchor": [3, 5], "low_anchor": [0, 0], "bridge": [1, 3], "target_window_s": [43.7, 43.9]}
                if previous_quality_mode == "deterministic_controller_seg01_targeted"
                else
                {"high_anchor": [2, 5], "low_anchor": [0, 1], "bridge": [1, 3]}
                if previous_quality_mode == "deterministic_controller_family_divergence"
                else [0, 5]
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
        "collapsed_same_bin_duplicates": collapsed_duplicates,
        "quality_state_rows": len(quality_state_rows),
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
