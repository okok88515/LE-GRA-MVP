import csv
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
AUDIT_CSV = ROOT / "p3_6e3_teacher_audit" / "full_bundle" / "scenario_teacher_decisions.csv"
OUT_DIR = ROOT / "p3_6g_focus_mining"

POS_EPS = 1e-9
TIME_GAP_EPS = 0.11


def _to_float(row, key, default=0.0):
    value = row.get(key, "")
    if value in ("", None):
        return default
    return float(value)


def load_rows():
    with AUDIT_CSV.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
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


def find_segments(rows):
    segments = []
    current = []
    for row in rows:
        is_positive = row["teacher_gain_vs_single"] > POS_EPS
        if not is_positive:
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


def summarize_segments(segments):
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


def propose_temporal_slices(rows, segments):
    by_family = defaultdict(list)
    for row in rows:
        by_family[(row["ue_ids"], row["serving_gnb"])].append(row)

    candidates = []
    for index, segment in enumerate(segments, start=1):
        family_key = (segment[0]["ue_ids"], segment[0]["serving_gnb"])
        family_rows = by_family[family_key]
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
            focus_test = sum(
                1 for row in family_rows if row["timestamp_s"] > split_time and row["timestamp_s"] <= end_time
            )
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


def summarize_near_miss(rows):
    by_family = defaultdict(list)
    for row in rows:
        by_family[(row["ue_ids"], row["serving_gnb"])].append(row)

    near_miss = []
    for (ue_ids, serving_gnb), family_rows in by_family.items():
        max_gain = max(row["teacher_gain_vs_single"] for row in family_rows)
        if max_gain > POS_EPS:
            continue
        max_user_count = max(row["user_count"] for row in family_rows)
        if max_user_count < 4:
            continue
        max_cqi = max(row["cqi_range"] for row in family_rows)
        max_cost = max(row["resource_cost_range"] for row in family_rows)
        max_prev = max(row["previous_quality_range"] for row in family_rows)
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


def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    rows = load_rows()
    OUT_DIR.mkdir(exist_ok=True)

    segments = find_segments(rows)
    segment_rows = summarize_segments(segments)
    candidate_rows = propose_temporal_slices(rows, segments)
    near_miss_rows = summarize_near_miss(rows)

    write_csv(OUT_DIR / "positive_segments.csv", segment_rows)
    write_csv(OUT_DIR / "candidate_temporal_slices.csv", candidate_rows)
    write_csv(OUT_DIR / "near_miss_families.csv", near_miss_rows)

    summary_lines = [
        f"positive_segment_count={len(segment_rows)}",
        f"candidate_temporal_slice_count={len(candidate_rows)}",
        f"near_miss_family_count={len(near_miss_rows)}",
    ]
    (OUT_DIR / "summary.txt").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
