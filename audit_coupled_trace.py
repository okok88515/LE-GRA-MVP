"""Audit a coupled SUMO+Veins+Simu5G bundle before learner experiments."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import le_gra_mvp as mvp
from trace_io import load_trace_bundle


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    if len(values) == 1:
        return values[0]
    values = sorted(values)
    pos = (len(values) - 1) * q
    left = math.floor(pos)
    right = math.ceil(pos)
    if left == right:
        return values[left]
    weight = pos - left
    return values[left] * (1.0 - weight) + values[right] * weight


def _summary_row(section: str, metric: str, value, note: str = "") -> dict:
    return {
        "section": section,
        "metric": metric,
        "value": value,
        "note": note,
    }


def _pair_profile_gap(a_rates: list[float], b_rates: list[float]) -> tuple[float, float]:
    diffs = [abs(x - y) for x, y in zip(a_rates, b_rates)]
    return float(sum(diffs) / len(diffs)), float(max(diffs))


def audit_bundle(
    bundle_dir: Path | str,
    out_dir: Path | str,
    *,
    pair_cqi_threshold: float = 0.5,
    pair_profile_gap_threshold_kbps: float = 1.0,
    validate_teacher: bool = True,
) -> dict[str, float]:
    bundle_dir, out_dir = Path(bundle_dir), Path(out_dir)

    bundle_scenarios = _read_csv(bundle_dir / "bundle/scenarios.csv")
    bundle_users = _read_csv(bundle_dir / "bundle/users.csv")
    bundle_rbs = _read_csv(bundle_dir / "bundle/rb_rates.csv")
    radio_users = _read_csv(bundle_dir / "radio/radio_users.csv")
    radio_rbs = _read_csv(bundle_dir / "radio/radio_rbs.csv")
    mobility_scenarios = _read_csv(bundle_dir / "mobility/sumo_scenarios.csv")
    mobility_rows = _read_csv(bundle_dir / "mobility/sumo_mobility.csv")
    metadata = json.loads((bundle_dir / "radio/export_metadata.json").read_text(encoding="utf-8"))

    scenario_timestamp = {
        row["scenario_id"]: row["timestamp_s"]
        for row in bundle_scenarios
    }
    scenario_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in bundle_users:
        scenario_rows[row["scenario_id"]].append(row)
    rb_rows_by_user: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in bundle_rbs:
        rb_rows_by_user[(row["scenario_id"], row["ue_id"])].append(row)

    snapshot_rows: list[dict] = []
    ambiguous_rows: list[dict] = []
    user_counts = []
    cqi_values = []
    pressure_values = []
    per_user_profile_ranges = []
    per_user_profile_std = []
    per_user_rate_mean = []
    multi_ue_snapshots = 0
    total_pairs = 0
    ambiguous_pairs = 0

    for scenario in bundle_scenarios:
        scenario_id = scenario["scenario_id"]
        users = sorted(scenario_rows[scenario_id], key=lambda item: int(item["user_index"]))
        user_counts.append(len(users))
        if len(users) >= 2:
            multi_ue_snapshots += 1
        pressure = int(scenario["rb_available"]) / int(scenario["total_rbs"])
        pressure_values.append(pressure)

        scenario_cqis = [float(row["cqi_now"]) for row in users]
        cqi_values.extend(scenario_cqis)
        scenario_rate_values = []
        scenario_profile_ranges = []
        scenario_profile_stds = []
        for user in users:
            profile = sorted(
                rb_rows_by_user[(scenario_id, user["ue_id"])],
                key=lambda item: int(item["rb_index"]),
            )
            rates = [float(row["rate_kbps"]) for row in profile]
            scenario_rate_values.extend(rates)
            per_user_rate_mean.append(float(statistics.fmean(rates)))
            profile_range = max(rates) - min(rates)
            profile_std = statistics.pstdev(rates)
            per_user_profile_ranges.append(profile_range)
            per_user_profile_std.append(profile_std)
            scenario_profile_ranges.append(profile_range)
            scenario_profile_stds.append(profile_std)

        pair_count = 0
        scenario_ambiguous = 0
        for left, right in combinations(users, 2):
            pair_count += 1
            total_pairs += 1
            left_profile = [
                float(row["rate_kbps"])
                for row in sorted(
                    rb_rows_by_user[(scenario_id, left["ue_id"])],
                    key=lambda item: int(item["rb_index"]),
                )
            ]
            right_profile = [
                float(row["rate_kbps"])
                for row in sorted(
                    rb_rows_by_user[(scenario_id, right["ue_id"])],
                    key=lambda item: int(item["rb_index"]),
                )
            ]
            cqi_gap = abs(float(left["cqi_now"]) - float(right["cqi_now"]))
            mean_gap, max_gap = _pair_profile_gap(left_profile, right_profile)
            is_ambiguous = (
                cqi_gap <= pair_cqi_threshold and
                mean_gap > pair_profile_gap_threshold_kbps
            )
            scenario_ambiguous += int(is_ambiguous)
            ambiguous_pairs += int(is_ambiguous)
            ambiguous_rows.append({
                "scenario_id": scenario_id,
                "timestamp_s": scenario_timestamp[scenario_id],
                "ue_id_a": left["ue_id"],
                "ue_id_b": right["ue_id"],
                "cqi_a": left["cqi_now"],
                "cqi_b": right["cqi_now"],
                "cqi_gap": f"{cqi_gap:.6f}",
                "mean_profile_gap_kbps": f"{mean_gap:.6f}",
                "max_profile_gap_kbps": f"{max_gap:.6f}",
                "ambiguous_pair": int(is_ambiguous),
            })

        snapshot_rows.append({
            "scenario_id": scenario_id,
            "timestamp_s": scenario_timestamp[scenario_id],
            "serving_gnb": scenario["serving_gnb"],
            "user_count": len(users),
            "rb_available": scenario["rb_available"],
            "total_rbs": scenario["total_rbs"],
            "resource_pressure_ratio": f"{pressure:.6f}",
            "cqi_min": f"{min(scenario_cqis):.6f}",
            "cqi_median": f"{statistics.median(scenario_cqis):.6f}",
            "cqi_max": f"{max(scenario_cqis):.6f}",
            "cqi_unique_count": len(set(scenario_cqis)),
            "cqi_saturation_ratio": f"{sum(value >= 15.0 for value in scenario_cqis) / len(scenario_cqis):.6f}",
            "per_band_rate_min_kbps": f"{min(scenario_rate_values):.6f}",
            "per_band_rate_median_kbps": f"{statistics.median(scenario_rate_values):.6f}",
            "per_band_rate_max_kbps": f"{max(scenario_rate_values):.6f}",
            "mean_user_profile_range_kbps": f"{statistics.fmean(scenario_profile_ranges):.6f}",
            "mean_user_profile_std_kbps": f"{statistics.fmean(scenario_profile_stds):.6f}",
            "pair_count": pair_count,
            "ambiguous_pair_count": scenario_ambiguous,
            "ambiguous_pair_ratio": (
                f"{scenario_ambiguous / pair_count:.6f}" if pair_count else ""
            ),
        })

    retained_pairs = {(scenario_timestamp[row["scenario_id"]], row["ue_id"]) for row in bundle_users}
    dropped_radio_user_rows = sum(
        (row["timestamp_s"], row["ue_id"]) not in retained_pairs
        for row in radio_users
    )
    dropped_mobility_rows = sum(
        (row["timestamp_s"], row["ue_id"]) not in retained_pairs
        for row in mobility_rows
    )

    ue_timeline_rows: list[dict] = []
    quality_values = []
    quality_switches = 0
    total_quality_transitions = 0
    handovers = 0
    by_ue_radio: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in radio_users:
        by_ue_radio[row["ue_id"]].append(row)
        quality_values.append(int(row["previous_quality"]))
    for ue_id, rows in sorted(by_ue_radio.items()):
        rows = sorted(rows, key=lambda item: float(item["timestamp_s"]))
        handover_count = 0
        quality_switch_count = 0
        for index in range(1, len(rows)):
            handover_count += int(rows[index]["serving_gnb"] != rows[index - 1]["serving_gnb"])
            quality_switch_count += int(rows[index]["previous_quality"] != rows[index - 1]["previous_quality"])
        handovers += handover_count
        quality_switches += quality_switch_count
        total_quality_transitions += max(0, len(rows) - 1)
        ue_timeline_rows.append({
            "ue_id": ue_id,
            "snapshot_count": len(rows),
            "first_timestamp_s": rows[0]["timestamp_s"],
            "last_timestamp_s": rows[-1]["timestamp_s"],
            "unique_serving_gnbs": len({row["serving_gnb"] for row in rows}),
            "handover_count": handover_count,
            "unique_previous_qualities": len({row["previous_quality"] for row in rows}),
            "quality_switch_count": quality_switch_count,
        })

    teacher_ok = 0
    teacher_error = ""
    if validate_teacher:
        try:
            scenarios = load_trace_bundle(bundle_dir / "bundle", feature_mode="history_cost_quality")
            for scenario in scenarios:
                mvp.offline_teacher_groups(
                    scenario,
                    max_groups=min(3, len(scenario.cqi_now)),
                    switch_beta=0.5,
                )
            teacher_ok = 1
        except Exception as exc:  # pragma: no cover - surfaced via audit output
            teacher_error = str(exc)

    quality_counter = Counter(quality_values)
    cqi_counter = Counter(round(value, 6) for value in cqi_values)
    summary_rows = [
        _summary_row("bundle", "scenario_count", len(bundle_scenarios)),
        _summary_row("bundle", "bundle_user_rows", len(bundle_users)),
        _summary_row("bundle", "bundle_rb_rows", len(bundle_rbs)),
        _summary_row("bundle", "mobility_scenario_rows", len(mobility_scenarios)),
        _summary_row("bundle", "mobility_user_rows", len(mobility_rows)),
        _summary_row("bundle", "radio_user_rows", len(radio_users)),
        _summary_row("bundle", "radio_rb_rows", len(radio_rbs)),
        _summary_row("join", "dropped_radio_user_rows", dropped_radio_user_rows),
        _summary_row("join", "dropped_mobility_rows", dropped_mobility_rows),
        _summary_row("join", "bundle_user_retention_ratio", f"{len(bundle_users) / len(radio_users):.6f}" if radio_users else ""),
        _summary_row("snapshot", "active_ues_min", min(user_counts)),
        _summary_row("snapshot", "active_ues_median", f"{statistics.median(user_counts):.6f}"),
        _summary_row("snapshot", "active_ues_max", max(user_counts)),
        _summary_row("snapshot", "multi_ue_snapshot_count", multi_ue_snapshots),
        _summary_row("snapshot", "serving_gnb_unique_count", len({row['serving_gnb'] for row in bundle_scenarios})),
        _summary_row("cqi", "cqi_unique_values", "|".join(str(int(value)) if float(value).is_integer() else str(value) for value in sorted(cqi_counter))),
        _summary_row("cqi", "cqi_min", min(cqi_values)),
        _summary_row("cqi", "cqi_median", f"{statistics.median(cqi_values):.6f}"),
        _summary_row("cqi", "cqi_max", max(cqi_values)),
        _summary_row("cqi", "cqi_saturation_ratio", f"{sum(value >= 15.0 for value in cqi_values) / len(cqi_values):.6f}"),
        _summary_row("rate", "per_user_profile_range_mean_kbps", f"{statistics.fmean(per_user_profile_ranges):.6f}"),
        _summary_row("rate", "per_user_profile_range_max_kbps", f"{max(per_user_profile_ranges):.6f}"),
        _summary_row("rate", "per_user_profile_std_mean_kbps", f"{statistics.fmean(per_user_profile_std):.6f}"),
        _summary_row("rate", "per_user_rate_mean_p50_kbps", f"{statistics.median(per_user_rate_mean):.6f}"),
        _summary_row("rate", "per_user_rate_mean_p95_kbps", f"{_quantile(per_user_rate_mean, 0.95):.6f}"),
        _summary_row("ambiguity", "pair_count", total_pairs),
        _summary_row("ambiguity", "ambiguous_pair_count", ambiguous_pairs),
        _summary_row("ambiguity", "ambiguous_pair_ratio", f"{(ambiguous_pairs / total_pairs) if total_pairs else 0.0:.6f}"),
        _summary_row("pressure", "rb_available_unique_values", "|".join(sorted({row["rb_available"] for row in bundle_scenarios}))),
        _summary_row("pressure", "total_rbs_unique_values", "|".join(sorted({row["total_rbs"] for row in bundle_scenarios}))),
        _summary_row("pressure", "resource_pressure_ratio_min", f"{min(pressure_values):.6f}"),
        _summary_row("pressure", "resource_pressure_ratio_median", f"{statistics.median(pressure_values):.6f}"),
        _summary_row("pressure", "resource_pressure_ratio_max", f"{max(pressure_values):.6f}"),
        _summary_row("quality", "previous_quality_unique_values", "|".join(str(key) for key in sorted(quality_counter))),
        _summary_row("quality", "previous_quality_source", metadata.get("previous_quality_source", "")),
        _summary_row("quality", "quality_switch_count", quality_switches),
        _summary_row("quality", "quality_switch_ratio", f"{(quality_switches / total_quality_transitions) if total_quality_transitions else 0.0:.6f}"),
        _summary_row("quality", "missing_previous_quality_ratio", f"{sum(not row['previous_quality'] for row in radio_users) / len(radio_users):.6f}" if radio_users else ""),
        _summary_row("handover", "handover_count", handovers),
        _summary_row("handover", "handover_ue_count", sum(int(row["handover_count"]) > 0 for row in ue_timeline_rows)),
        _summary_row("teacher", "teacher_validation_pass", teacher_ok, teacher_error),
    ]

    gate_rows = [
        {
            "gate": "multi_ue_snapshots_at_least_5",
            "passed": int(multi_ue_snapshots >= 5),
            "observed": multi_ue_snapshots,
            "target": ">= 5",
            "note": "P3.6 requires enough multi-UE snapshots to study grouping.",
        },
        {
            "gate": "cqi_not_fully_saturated",
            "passed": int(len(cqi_counter) > 1 and sum(value >= 15.0 for value in cqi_values) / len(cqi_values) < 0.95),
            "observed": f"unique={len(cqi_counter)}, saturation={sum(value >= 15.0 for value in cqi_values) / len(cqi_values):.6f}",
            "target": "unique > 1 and saturation < 0.95",
            "note": "All-CQI-15 traces are not informative for learner ambiguity.",
        },
        {
            "gate": "per_band_dispersion_present",
            "passed": int(max(per_user_profile_ranges) > 0.0),
            "observed": f"max_range_kbps={max(per_user_profile_ranges):.6f}",
            "target": "> 0",
            "note": "Need intra-profile variation, not flat per-band rates.",
        },
        {
            "gate": "ambiguous_pairs_present",
            "passed": int(ambiguous_pairs > 0),
            "observed": ambiguous_pairs,
            "target": "> 0",
            "note": "Need same/similar-CQI but different RB-profile user pairs.",
        },
        {
            "gate": "measured_previous_quality",
            "passed": int(metadata.get("previous_quality_source", "") != "explicit_experiment_control_not_video_measurement"),
            "observed": metadata.get("previous_quality_source", ""),
            "target": "not explicit experiment control",
            "note": "P3.6 must use measured or defensible adaptive video state.",
        },
        {
            "gate": "teacher_validation",
            "passed": int(teacher_ok == 1),
            "observed": teacher_ok,
            "target": "1",
            "note": teacher_error or "P3.2 join, P3.0 load, and offline teacher passed.",
        },
    ]

    _write_csv(out_dir / "summary.csv", summary_rows)
    _write_csv(out_dir / "snapshot_metrics.csv", snapshot_rows)
    _write_csv(out_dir / "ambiguous_pairs.csv", ambiguous_rows)
    _write_csv(out_dir / "ue_timeline_metrics.csv", ue_timeline_rows)
    _write_csv(out_dir / "acceptance_gates.csv", gate_rows)

    return {
        "scenario_count": len(bundle_scenarios),
        "multi_ue_snapshot_count": multi_ue_snapshots,
        "cqi_unique_count": len(cqi_counter),
        "cqi_saturation_ratio": sum(value >= 15.0 for value in cqi_values) / len(cqi_values),
        "max_profile_range_kbps": max(per_user_profile_ranges),
        "ambiguous_pair_count": ambiguous_pairs,
        "handover_count": handovers,
        "quality_switch_count": quality_switches,
        "teacher_validation_pass": teacher_ok,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", type=Path, default=Path("p3_5_coupled_bundle"))
    parser.add_argument("--out-dir", type=Path, default=Path("p3_6_coupled_audit"))
    parser.add_argument("--pair-cqi-threshold", type=float, default=0.5)
    parser.add_argument("--pair-profile-gap-threshold-kbps", type=float, default=1.0)
    parser.add_argument("--no-validate-teacher", action="store_true")
    args = parser.parse_args()

    summary = audit_bundle(
        args.bundle_dir,
        args.out_dir,
        pair_cqi_threshold=args.pair_cqi_threshold,
        pair_profile_gap_threshold_kbps=args.pair_profile_gap_threshold_kbps,
        validate_teacher=not args.no_validate_teacher,
    )
    print("P3.6 coupled audit:")
    for key, value in summary.items():
        print(f"  {key}={value}")


if __name__ == "__main__":
    main()
