"""Mine positive segments, temporal slices, and near-miss families from a teacher audit CSV."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


POS_EPS = 1e-9
TIME_GAP_EPS = 0.11


def _to_float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    value = row.get(key, "")
    if value in ("", None):
        return default
    return float(value)


def load_rows(
    audit_csv: Path,
    *,
    target_ue_ids: str | None = None,
    target_serving_gnb: str | None = None,
) -> list[dict]:
    with audit_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            if target_ue_ids is not None and row.get("ue_ids") != target_ue_ids:
                continue
            if target_serving_gnb is not None and row.get("serving_gnb") != target_serving_gnb:
                continue
            row["timestamp_s"] = _to_float(row, "timestamp_s")
            row["user_count"] = int(_to_float(row, "user_count"))
            row["teacher_group_count"] = int(_to_float(row, "teacher_group_count"))
            row["teacher_gain_vs_single"] = _to_float(row, "teacher_gain_vs_single")
            row["cqi_range"] = _to_float(row, "cqi_range")
            row["resource_cost_range"] = _to_float(row, "resource_cost_range")
            row["previous_quality_range"] = _to_float(row, "previous_quality_range")
            row["distance_range_m"] = _to_float(row, "distance_range_m")
            row["rb_budget_ratio_snapshot"] = _to_float(row, "rb_budget_ratio_snapshot")
            rows.append(row)
    rows.sort(key=lambda item: (item["ue_ids"], item["timestamp_s"], item["scenario_id"]))
    return rows


def find_segments(rows: list[dict]) -> list[list[dict]]:
    segments: list[list[dict]] = []
    current: list[dict] = []
    for row in rows:
        if row["teacher_gain_vs_single"] <= POS_EPS:
            if current:
                segments.append(current)
                current = []
            continue

        if not current:
            current = [row]
            continue

        prev = current[-1]
        same_family = (
            row["ue_ids"] == prev["ue_ids"]
            and row["serving_gnb"] == prev["serving_gnb"]
            and abs(row["timestamp_s"] - prev["timestamp_s"]) <= TIME_GAP_EPS
        )
        if same_family:
            current.append(row)
        else:
            segments.append(current)
            current = [row]
    if current:
        segments.append(current)
    return segments


def summarize_segments(segments: list[list[dict]]) -> list[dict]:
    summary = []
    for index, segment in enumerate(segments, start=1):
        times = [row["timestamp_s"] for row in segment]
        gains = [row["teacher_gain_vs_single"] for row in segment]
        cqi_ranges = [row["cqi_range"] for row in segment]
        cost_ranges = [row["resource_cost_range"] for row in segment]
        summary.append(
            {
                "segment_id": f"seg_{index:02d}",
                "ue_ids": segment[0]["ue_ids"],
                "serving_gnb": segment[0]["serving_gnb"],
                "user_count": segment[0]["user_count"],
                "start_time_s": f"{min(times):.1f}",
                "end_time_s": f"{max(times):.1f}",
                "snapshot_count": len(segment),
                "mean_gain_vs_single": f"{sum(gains) / len(gains):.12f}",
                "max_gain_vs_single": f"{max(gains):.12f}",
                "min_cqi_range": f"{min(cqi_ranges):.1f}",
                "max_cqi_range": f"{max(cqi_ranges):.1f}",
                "min_resource_cost_range": f"{min(cost_ranges):.6f}",
                "max_resource_cost_range": f"{max(cost_ranges):.6f}",
            }
        )
    return summary


def propose_temporal_slices(rows: list[dict], segments: list[list[dict]]) -> list[dict]:
    by_family: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        by_family[(row["ue_ids"], row["serving_gnb"])].append(row)

    candidates = []
    for index, segment in enumerate(segments, start=1):
        family_rows = by_family[(segment[0]["ue_ids"], segment[0]["serving_gnb"])]
        positive_times = [row["timestamp_s"] for row in segment]
        start_time = min(positive_times)
        end_time = max(positive_times)
        for split_time in positive_times[:-1]:
            train_positive = sum(
                1
                for row in family_rows
                if row["timestamp_s"] <= split_time and row["teacher_gain_vs_single"] > POS_EPS
            )
            test_positive = sum(
                1
                for row in family_rows
                if row["timestamp_s"] > split_time
                and row["timestamp_s"] <= end_time
                and row["teacher_gain_vs_single"] > POS_EPS
            )
            if train_positive <= 0 or test_positive <= 0:
                continue
            focus_train = sum(1 for row in family_rows if row["timestamp_s"] <= split_time)
            focus_test = sum(1 for row in family_rows if split_time < row["timestamp_s"] <= end_time)
            candidates.append(
                {
                    "segment_id": f"seg_{index:02d}",
                    "ue_ids": segment[0]["ue_ids"],
                    "serving_gnb": segment[0]["serving_gnb"],
                    "segment_start_s": f"{start_time:.1f}",
                    "segment_end_s": f"{end_time:.1f}",
                    "suggested_split_s": f"{split_time:.1f}",
                    "focus_train_scenarios": focus_train,
                    "focus_test_scenarios": focus_test,
                    "focus_train_positive_gain_count": train_positive,
                    "focus_test_positive_gain_count": test_positive,
                }
            )
    candidates.sort(
        key=lambda item: (
            -min(item["focus_train_positive_gain_count"], item["focus_test_positive_gain_count"]),
            -item["focus_test_positive_gain_count"],
            item["suggested_split_s"],
        )
    )
    return candidates


def summarize_near_miss(rows: list[dict]) -> list[dict]:
    by_family: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        by_family[(row["ue_ids"], row["serving_gnb"])].append(row)

    near_miss = []
    for (ue_ids, serving_gnb), family_rows in by_family.items():
        max_gain = max(row["teacher_gain_vs_single"] for row in family_rows)
        max_user_count = max(row["user_count"] for row in family_rows)
        max_cqi = max(row["cqi_range"] for row in family_rows)
        max_cost = max(row["resource_cost_range"] for row in family_rows)
        max_prev = max(row["previous_quality_range"] for row in family_rows)
        if max_gain > POS_EPS or max_user_count < 4:
            continue
        if max_cqi < 3 and max_cost < 0.5:
            continue
        near_miss.append(
            {
                "ue_ids": ue_ids,
                "serving_gnb": serving_gnb,
                "scenario_count": len(family_rows),
                "user_count": max_user_count,
                "max_teacher_gain_vs_single": f"{max_gain:.12f}",
                "max_cqi_range": f"{max_cqi:.1f}",
                "max_resource_cost_range": f"{max_cost:.6f}",
                "max_previous_quality_range": f"{max_prev:.1f}",
                "first_time_s": f"{min(row['timestamp_s'] for row in family_rows):.1f}",
                "last_time_s": f"{max(row['timestamp_s'] for row in family_rows):.1f}",
            }
        )
    near_miss.sort(
        key=lambda item: (
            -float(item["max_resource_cost_range"]),
            -float(item["max_cqi_range"]),
            -item["scenario_count"],
        )
    )
    return near_miss


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-csv", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--target-ue-ids",
        type=str,
        default=None,
        help="Optional exact ue_ids family filter (for example: 0|1|15|2|3|4|5).",
    )
    parser.add_argument(
        "--target-serving-gnb",
        type=str,
        default=None,
        help="Optional exact serving_gnb filter paired with --target-ue-ids.",
    )
    args = parser.parse_args()

    rows = load_rows(
        args.audit_csv,
        target_ue_ids=args.target_ue_ids,
        target_serving_gnb=args.target_serving_gnb,
    )
    segments = find_segments(rows)
    segment_rows = summarize_segments(segments)
    candidate_rows = propose_temporal_slices(rows, segments)
    near_miss_rows = summarize_near_miss(rows)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "positive_segments.csv", segment_rows)
    write_csv(args.out_dir / "candidate_temporal_slices.csv", candidate_rows)
    write_csv(args.out_dir / "near_miss_families.csv", near_miss_rows)
    (args.out_dir / "summary.txt").write_text(
        "\n".join(
            [
                f"positive_segment_count={len(segment_rows)}",
                f"candidate_temporal_slice_count={len(candidate_rows)}",
                f"near_miss_family_count={len(near_miss_rows)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
