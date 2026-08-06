"""Rank near-miss families for dual-candidate targeted redesign."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import le_gra_mvp as mvp
import numpy as np


POS_EPS = 1e-9


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


def _to_float(value: str, default: float = 0.0) -> float:
    if value in ("", None):
        return default
    return float(value)


def _norm(values: list[float]) -> list[float]:
    lo = min(values)
    hi = max(values)
    if hi - lo <= 1e-9:
        return [0.5 for _ in values]
    return [(value - lo) / (hi - lo) for value in values]


def load_near_miss_families(audit_rows: list[dict]) -> list[tuple[str, str, list[dict]]]:
    by_family: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in audit_rows:
        if _to_float(row["teacher_gain_vs_single"]) > POS_EPS:
            continue
        if int(_to_float(row["user_count"])) < 4:
            continue
        by_family[(row["ue_ids"], row["serving_gnb"])].append(row)
    return sorted(by_family.items(), key=lambda item: (item[0][1], item[0][0]))


def build_mean_cost_lookup(rb_rows: list[dict[str, str]]) -> dict[tuple[str, str], float]:
    rates_by_user: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rb_rows:
        rates_by_user[(row["scenario_id"], row["ue_id"])].append(_to_float(row["rate_kbps"]))

    mean_cost: dict[tuple[str, str], float] = {}
    for key, rates in rates_by_user.items():
        cost_vec = mvp.user_resource_cost_vector(np.array([rates], dtype=float))
        mean_cost[key] = float(cost_vec.mean(axis=1)[0])
    return mean_cost


def family_user_rows(users_rows: list[dict], family_rows: list[dict]) -> dict[str, list[dict]]:
    scenario_ids = {row["scenario_id"] for row in family_rows}
    rows: dict[str, list[dict]] = defaultdict(list)
    for row in users_rows:
        if row["scenario_id"] not in scenario_ids:
            continue
        rows[row["ue_id"]].append(row)
    return rows


def score_family(
    family_rows: list[dict],
    per_ue_rows: dict[str, list[dict]],
    mean_cost_lookup: dict[tuple[str, str], float],
) -> dict | None:
    ue_ids = sorted(per_ue_rows.keys(), key=lambda value: int(value))
    if len(ue_ids) < 4:
        return None

    mean_cost = []
    mean_neg_cqi = []
    mean_prev_weak = []
    for ue_id in ue_ids:
        rows = per_ue_rows[ue_id]
        mean_cost.append(
            sum(mean_cost_lookup[(row["scenario_id"], ue_id)] for row in rows) / len(rows)
        )
        mean_neg_cqi.append(-sum(_to_float(row["cqi_now"]) for row in rows) / len(rows))
        mean_prev_weak.append(-sum(_to_float(row["previous_quality"]) for row in rows) / len(rows))

    cost_norm = _norm(mean_cost)
    cqi_norm = _norm(mean_neg_cqi)
    prev_norm = _norm(mean_prev_weak)
    weakness = [
        0.55 * cost_norm[idx] + 0.35 * cqi_norm[idx] + 0.10 * prev_norm[idx]
        for idx in range(len(ue_ids))
    ]
    ordered = sorted(
        zip(ue_ids, weakness, mean_cost, [-value for value in mean_neg_cqi], [-value for value in mean_prev_weak]),
        key=lambda item: item[1],
        reverse=True,
    )
    if len(ordered) < 3:
        return None

    top1, top2, third = ordered[0], ordered[1], ordered[2]
    dual_closeness = 1.0 - min(1.0, abs(top1[1] - top2[1]) / 0.25)
    separation_from_third = max(0.0, min(1.0, (top2[1] - third[1]) / 0.25))

    family_cqi_range = max(_to_float(row["cqi_range"]) for row in family_rows)
    family_cost_range = max(_to_float(row["resource_cost_range"]) for row in family_rows)
    family_prev_range = max(_to_float(row["previous_quality_range"]) for row in family_rows)
    snapshot_count = len(family_rows)
    if family_cqi_range < 3.0 and family_cost_range < 0.333333:
        return None

    rank_score = (
        5.0 * dual_closeness
        + 4.0 * separation_from_third
        + 1.8 * family_cost_range
        + 0.75 * family_cqi_range
        + 0.5 * family_prev_range
        + 0.03 * snapshot_count
    )
    return {
        "rank_score": f"{rank_score:.12f}",
        "ue_ids": family_rows[0]["ue_ids"],
        "serving_gnb": family_rows[0]["serving_gnb"],
        "scenario_count": snapshot_count,
        "max_cqi_range": f"{family_cqi_range:.1f}",
        "max_resource_cost_range": f"{family_cost_range:.6f}",
        "max_previous_quality_range": f"{family_prev_range:.1f}",
        "candidate_1_ue_id": top1[0],
        "candidate_1_weakness": f"{top1[1]:.6f}",
        "candidate_1_mean_cost": f"{top1[2]:.6f}",
        "candidate_1_mean_cqi": f"{top1[3]:.6f}",
        "candidate_1_mean_previous_quality": f"{top1[4]:.6f}",
        "candidate_2_ue_id": top2[0],
        "candidate_2_weakness": f"{top2[1]:.6f}",
        "candidate_2_mean_cost": f"{top2[2]:.6f}",
        "candidate_2_mean_cqi": f"{top2[3]:.6f}",
        "candidate_2_mean_previous_quality": f"{top2[4]:.6f}",
        "third_ue_id": third[0],
        "third_weakness": f"{third[1]:.6f}",
        "dual_candidate_closeness": f"{dual_closeness:.6f}",
        "candidate_gap_over_third": f"{separation_from_third:.6f}",
        "first_time_s": f"{min(_to_float(row['timestamp_s']) for row in family_rows):.1f}",
        "last_time_s": f"{max(_to_float(row['timestamp_s']) for row in family_rows):.1f}",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-csv", type=Path, required=True)
    parser.add_argument("--users-csv", type=Path, required=True)
    parser.add_argument("--rb-rates-csv", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    audit_rows = _read_csv(args.audit_csv)
    users_rows = _read_csv(args.users_csv)
    rb_rows = _read_csv(args.rb_rates_csv)
    mean_cost_lookup = build_mean_cost_lookup(rb_rows)
    rankings = []
    for (_ue_ids, _gnb), family_rows in load_near_miss_families(audit_rows):
        scored = score_family(
            family_rows,
            family_user_rows(users_rows, family_rows),
            mean_cost_lookup,
        )
        if scored is not None:
            rankings.append(scored)

    rankings.sort(key=lambda item: float(item["rank_score"]), reverse=True)
    for index, row in enumerate(rankings, start=1):
        row["rank"] = index

    args.out_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(args.out_dir / "dual_candidate_family_ranking.csv", rankings)
    _write_csv(args.out_dir / "top10_dual_candidate_family_ranking.csv", rankings[:10])
    (args.out_dir / "summary.txt").write_text(
        "\n".join(
            [
                f"audit_csv={args.audit_csv}",
                f"candidate_family_count={len(rankings)}",
                (
                    f"top_family={rankings[0]['ue_ids']} @ {rankings[0]['serving_gnb']}"
                    if rankings
                    else "top_family="
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
