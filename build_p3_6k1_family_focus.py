"""Build a focused audit package for a single P3.6 family."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _matching_scenario_ids(
    scenarios: list[dict[str, str]],
    users: list[dict[str, str]],
    *,
    target_ue_ids: str,
    serving_gnb: str,
) -> list[str]:
    users_by_scenario: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in users:
        users_by_scenario[row["scenario_id"]].append(row)

    matched = []
    for row in scenarios:
        if row["serving_gnb"] != serving_gnb:
            continue
        scenario_users = sorted(
            users_by_scenario[row["scenario_id"]],
            key=lambda item: int(item["user_index"]),
        )
        if "|".join(item["ue_id"] for item in scenario_users) == target_ue_ids:
            matched.append(row["scenario_id"])
    matched.sort(key=lambda scenario_id: float(next(item["timestamp_s"] for item in scenarios if item["scenario_id"] == scenario_id)))
    return matched


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", type=Path, default=Path("p3_6i2_coupled_bundle/bundle"))
    parser.add_argument(
        "--audit-csv",
        type=Path,
        default=Path("p3_6i2_teacher_audit/full_bundle/scenario_teacher_decisions.csv"),
    )
    parser.add_argument("--target-ue-ids", default="3|4|5|6")
    parser.add_argument("--serving-gnb", default="gnb_2")
    parser.add_argument("--out-dir", type=Path, default=Path("p3_6k1_family_focus"))
    args = parser.parse_args()

    scenarios = _read_csv(args.bundle_dir / "scenarios.csv")
    users = _read_csv(args.bundle_dir / "users.csv")
    rb_rows = _read_csv(args.bundle_dir / "rb_rates.csv")
    audit_rows = _read_csv(args.audit_csv)

    target_scenario_ids = _matching_scenario_ids(
        scenarios,
        users,
        target_ue_ids=args.target_ue_ids,
        serving_gnb=args.serving_gnb,
    )
    target_set = set(target_scenario_ids)
    audit_rows = [
        row
        for row in audit_rows
        if row["scenario_id"] in target_set
        and row["ue_ids"] == args.target_ue_ids
        and row["serving_gnb"] == args.serving_gnb
    ]
    audit_rows.sort(key=lambda row: float(row["timestamp_s"]))

    users_by_scenario: dict[str, list[dict[str, str]]] = defaultdict(list)
    rb_by_scenario: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in users:
        if row["scenario_id"] in target_set:
            users_by_scenario[row["scenario_id"]].append(row)
    for row in rb_rows:
        if row["scenario_id"] in target_set:
            rb_by_scenario[row["scenario_id"]].append(row)

    timeline_rows: list[dict] = []
    per_user_rows: list[dict] = []
    summary_rows: list[dict] = []

    per_user_series: dict[str, list[dict[str, float]]] = defaultdict(list)

    scenario_meta = {row["scenario_id"]: row for row in scenarios}
    for audit_row in audit_rows:
        sid = audit_row["scenario_id"]
        meta = scenario_meta[sid]
        user_rows = sorted(users_by_scenario[sid], key=lambda row: int(row["user_index"]))
        ue_index = {row["ue_id"]: idx for idx, row in enumerate(user_rows)}
        total_rbs = int(meta["total_rbs"])
        rates = np.full((len(user_rows), total_rbs), np.nan, dtype=float)
        for row in rb_by_scenario[sid]:
            rates[ue_index[row["ue_id"]], int(row["rb_index"])] = float(row["rate_kbps"])
        user_cost = mvp.user_resource_cost_vector(rates).mean(axis=1)

        timeline_rows.append(
            {
                "scenario_id": sid,
                "timestamp_s": audit_row["timestamp_s"],
                "teacher_group_count": audit_row["teacher_group_count"],
                "teacher_groups": audit_row["teacher_groups"],
                "teacher_gain_vs_single": audit_row["teacher_gain_vs_single"],
                "cqi_range": audit_row["cqi_range"],
                "resource_cost_range": audit_row["resource_cost_range"],
                "previous_quality_range": audit_row["previous_quality_range"],
                "rb_available": meta["rb_available"],
            }
        )

        for row, cost in zip(user_rows, user_cost):
            per_user_series[row["ue_id"]].append(
                {
                    "timestamp_s": float(audit_row["timestamp_s"]),
                    "cqi_now": float(row["cqi_now"]),
                    "previous_quality": float(row["previous_quality"]),
                    "distance_m": float(row["distance_m"]),
                    "mean_resource_cost": float(cost),
                }
            )
            per_user_rows.append(
                {
                    "scenario_id": sid,
                    "timestamp_s": audit_row["timestamp_s"],
                    "ue_id": row["ue_id"],
                    "user_index": row["user_index"],
                    "cqi_now": row["cqi_now"],
                    "previous_quality": row["previous_quality"],
                    "distance_m": row["distance_m"],
                    "mean_resource_cost": f"{float(cost):.6f}",
                }
            )

    for ue_id, series in sorted(per_user_series.items()):
        summary_rows.append(
            {
                "ue_id": ue_id,
                "snapshot_count": len(series),
                "cqi_min": f"{min(item['cqi_now'] for item in series):.1f}",
                "cqi_max": f"{max(item['cqi_now'] for item in series):.1f}",
                "previous_quality_min": f"{min(item['previous_quality'] for item in series):.1f}",
                "previous_quality_max": f"{max(item['previous_quality'] for item in series):.1f}",
                "distance_min_m": f"{min(item['distance_m'] for item in series):.2f}",
                "distance_max_m": f"{max(item['distance_m'] for item in series):.2f}",
                "cost_min": f"{min(item['mean_resource_cost'] for item in series):.6f}",
                "cost_max": f"{max(item['mean_resource_cost'] for item in series):.6f}",
            }
        )

    peak_rows = sorted(
        timeline_rows,
        key=lambda row: (
            float(row["resource_cost_range"]),
            float(row["cqi_range"]),
            -float(row["timestamp_s"]),
        ),
        reverse=True,
    )[:10]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(args.out_dir / "family_timeline.csv", timeline_rows)
    _write_csv(args.out_dir / "family_user_snapshot_metrics.csv", per_user_rows)
    _write_csv(args.out_dir / "family_user_summary.csv", summary_rows)
    _write_csv(args.out_dir / "peak_snapshots.csv", peak_rows)

    summary_text = [
        f"target_ue_ids={args.target_ue_ids}",
        f"serving_gnb={args.serving_gnb}",
        f"scenario_count={len(timeline_rows)}",
        f"first_time_s={timeline_rows[0]['timestamp_s'] if timeline_rows else ''}",
        f"last_time_s={timeline_rows[-1]['timestamp_s'] if timeline_rows else ''}",
        f"max_teacher_gain_vs_single={max(float(row['teacher_gain_vs_single']) for row in timeline_rows) if timeline_rows else 0.0}",
        f"max_cqi_range={max(float(row['cqi_range']) for row in timeline_rows) if timeline_rows else 0.0}",
        f"max_resource_cost_range={max(float(row['resource_cost_range']) for row in timeline_rows) if timeline_rows else 0.0}",
        f"max_previous_quality_range={max(float(row['previous_quality_range']) for row in timeline_rows) if timeline_rows else 0.0}",
    ]
    (args.out_dir / "summary.txt").write_text("\n".join(summary_text) + "\n", encoding="utf-8")

    print(f"scenario_count={len(timeline_rows)}")
    if timeline_rows:
        print(f"time_window={timeline_rows[0]['timestamp_s']}~{timeline_rows[-1]['timestamp_s']}")
        print(
            "peak_signal="
            f"cqi={max(float(row['cqi_range']) for row in timeline_rows)} "
            f"cost={max(float(row['resource_cost_range']) for row in timeline_rows)}"
        )


if __name__ == "__main__":
    main()
