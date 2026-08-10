"""Mine reusable family-preserving positive corridors from teacher audits."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@dataclass
class Segment:
    bundle_name: str
    audit_dir: str
    serving_gnb: str
    ue_ids: str
    rows: list[dict[str, str]]


def _bundle_name_from_audit_dir(audit_dir: str) -> str:
    return audit_dir.removesuffix("_teacher_audit")


def _scenario_key(row: dict[str, str]) -> tuple[str, str]:
    return row["serving_gnb"], row["ue_ids"]


def _is_positive(row: dict[str, str], min_gain: float, min_group_count: int) -> bool:
    return (
        float(row["teacher_gain_vs_single"]) >= min_gain
        and int(row["teacher_group_count"]) >= min_group_count
    )


def _is_near_miss(row: dict[str, str], near_miss_gain: float, min_group_count: int) -> bool:
    return (
        float(row["teacher_gain_vs_single"]) >= near_miss_gain
        and int(row["teacher_group_count"]) >= min_group_count
    )


def _segment_rows(
    rows: list[dict[str, str]],
    *,
    predicate,
    max_gap_s: float,
) -> list[list[dict[str, str]]]:
    segments: list[list[dict[str, str]]] = []
    current: list[dict[str, str]] = []
    previous_ts: float | None = None
    for row in sorted(rows, key=lambda item: float(item["timestamp_s"])):
        if not predicate(row):
            if current:
                segments.append(current)
                current = []
            previous_ts = None
            continue
        ts = float(row["timestamp_s"])
        if current and previous_ts is not None and ts - previous_ts > max_gap_s + 1e-9:
            segments.append(current)
            current = []
        current.append(row)
        previous_ts = ts
    if current:
        segments.append(current)
    return segments


def _summarize_segment(segment_id: str, segment: Segment) -> dict:
    gains = [float(row["teacher_gain_vs_single"]) for row in segment.rows]
    cqi_ranges = [float(row["cqi_range"]) for row in segment.rows]
    cost_ranges = [float(row["resource_cost_range"]) for row in segment.rows]
    group_counts = [int(row["teacher_group_count"]) for row in segment.rows]
    return {
        "bundle_name": segment.bundle_name,
        "audit_dir": segment.audit_dir,
        "segment_id": segment_id,
        "serving_gnb": segment.serving_gnb,
        "ue_ids": segment.ue_ids,
        "user_count": int(segment.rows[0]["user_count"]),
        "start_time_s": float(segment.rows[0]["timestamp_s"]),
        "end_time_s": float(segment.rows[-1]["timestamp_s"]),
        "snapshot_count": len(segment.rows),
        "mean_gain_vs_single": sum(gains) / len(gains),
        "max_gain_vs_single": max(gains),
        "mean_teacher_group_count": sum(group_counts) / len(group_counts),
        "max_teacher_group_count": max(group_counts),
        "min_cqi_range": min(cqi_ranges),
        "max_cqi_range": max(cqi_ranges),
        "min_resource_cost_range": min(cost_ranges),
        "max_resource_cost_range": max(cost_ranges),
        "teacher_group_patterns": len({row["teacher_groups"] for row in segment.rows}),
    }


def _candidate_splits(segment_id: str, segment: Segment) -> list[dict]:
    rows = sorted(segment.rows, key=lambda item: float(item["timestamp_s"]))
    candidates = []
    for split_index in range(1, len(rows)):
        train_rows = rows[:split_index]
        test_rows = rows[split_index:]
        split_ts = float(test_rows[0]["timestamp_s"])
        candidates.append(
            {
                "bundle_name": segment.bundle_name,
                "audit_dir": segment.audit_dir,
                "segment_id": segment_id,
                "serving_gnb": segment.serving_gnb,
                "ue_ids": segment.ue_ids,
                "segment_start_s": float(rows[0]["timestamp_s"]),
                "segment_end_s": float(rows[-1]["timestamp_s"]),
                "suggested_split_s": split_ts,
                "train_scenarios": len(train_rows),
                "test_scenarios": len(test_rows),
                "train_mean_gain_vs_single": sum(float(row["teacher_gain_vs_single"]) for row in train_rows) / len(train_rows),
                "test_mean_gain_vs_single": sum(float(row["teacher_gain_vs_single"]) for row in test_rows) / len(test_rows),
                "train_positive_gain_count": sum(float(row["teacher_gain_vs_single"]) > 1e-9 for row in train_rows),
                "test_positive_gain_count": sum(float(row["teacher_gain_vs_single"]) > 1e-9 for row in test_rows),
                "balance_score": min(len(train_rows), len(test_rows)),
            }
        )
    candidates.sort(
        key=lambda row: (
            row["balance_score"],
            min(row["train_positive_gain_count"], row["test_positive_gain_count"]),
            min(row["train_mean_gain_vs_single"], row["test_mean_gain_vs_single"]),
        ),
        reverse=True,
    )
    return candidates


def _summarize_near_miss(bundle_name: str, audit_dir: str, key: tuple[str, str], rows: list[dict[str, str]]) -> dict:
    gains = [float(row["teacher_gain_vs_single"]) for row in rows]
    return {
        "bundle_name": bundle_name,
        "audit_dir": audit_dir,
        "serving_gnb": key[0],
        "ue_ids": key[1],
        "user_count": int(rows[0]["user_count"]),
        "snapshot_count": len(rows),
        "start_time_s": float(rows[0]["timestamp_s"]),
        "end_time_s": float(rows[-1]["timestamp_s"]),
        "mean_gain_vs_single": sum(gains) / len(gains),
        "max_gain_vs_single": max(gains),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-glob", default="p3_6*_teacher_audit")
    parser.add_argument("--split-name", default="full_bundle")
    parser.add_argument("--out-dir", type=Path, default=Path("family_corridor_mining"))
    parser.add_argument("--min-gain", type=float, default=1e-9)
    parser.add_argument("--near-miss-gain", type=float, default=0.02)
    parser.add_argument("--min-group-count", type=int, default=2)
    parser.add_argument("--min-segment-length", type=int, default=3)
    parser.add_argument("--max-gap-s", type=float, default=0.11)
    parser.add_argument("--top-k-candidates-per-segment", type=int, default=3)
    args = parser.parse_args()

    out_dir = (ROOT / args.out_dir).resolve() if not args.out_dir.is_absolute() else args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    segment_rows: list[dict] = []
    candidate_rows: list[dict] = []
    near_miss_rows: list[dict] = []

    for audit_path in sorted(ROOT.glob(args.audit_glob)):
        decision_path = audit_path / args.split_name / "scenario_teacher_decisions.csv"
        if not decision_path.exists():
            continue
        audit_rows = _read_csv(decision_path)
        grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
        for row in audit_rows:
            grouped.setdefault(_scenario_key(row), []).append(row)
        bundle_name = _bundle_name_from_audit_dir(audit_path.name)
        local_segment_index = 0
        for key, rows in sorted(grouped.items()):
            positive_segments = _segment_rows(
                rows,
                predicate=lambda row: _is_positive(row, args.min_gain, args.min_group_count),
                max_gap_s=args.max_gap_s,
            )
            kept_positive = [
                segment for segment in positive_segments
                if len(segment) >= args.min_segment_length
            ]
            for segment in kept_positive:
                local_segment_index += 1
                segment_id = f"seg_{local_segment_index:02d}"
                segment_obj = Segment(
                    bundle_name=bundle_name,
                    audit_dir=audit_path.name,
                    serving_gnb=key[0],
                    ue_ids=key[1],
                    rows=segment,
                )
                segment_rows.append(_summarize_segment(segment_id, segment_obj))
                candidate_rows.extend(
                    _candidate_splits(segment_id, segment_obj)[: args.top_k_candidates_per_segment]
                )

            near_miss_segments = _segment_rows(
                rows,
                predicate=lambda row: (
                    _is_near_miss(row, args.near_miss_gain, args.min_group_count)
                    and not _is_positive(row, args.min_gain, args.min_group_count)
                ),
                max_gap_s=args.max_gap_s,
            )
            for segment in near_miss_segments:
                if len(segment) < args.min_segment_length:
                    continue
                near_miss_rows.append(
                    _summarize_near_miss(bundle_name, audit_path.name, key, segment)
                )

    segment_rows.sort(
        key=lambda row: (
            row["max_gain_vs_single"],
            row["mean_gain_vs_single"],
            row["snapshot_count"],
            row["user_count"],
        ),
        reverse=True,
    )
    candidate_rows.sort(
        key=lambda row: (
            row["balance_score"],
            min(row["train_positive_gain_count"], row["test_positive_gain_count"]),
            min(row["train_mean_gain_vs_single"], row["test_mean_gain_vs_single"]),
        ),
        reverse=True,
    )
    near_miss_rows.sort(
        key=lambda row: (
            row["max_gain_vs_single"],
            row["mean_gain_vs_single"],
            row["snapshot_count"],
        ),
        reverse=True,
    )

    _write_csv(out_dir / "positive_segments.csv", segment_rows)
    _write_csv(out_dir / "candidate_temporal_slices.csv", candidate_rows)
    _write_csv(out_dir / "near_miss_families.csv", near_miss_rows)

    summary_lines = [
        f"positive_segment_count={len(segment_rows)}",
        f"candidate_temporal_slice_count={len(candidate_rows)}",
        f"near_miss_family_count={len(near_miss_rows)}",
    ]
    if segment_rows:
        best = segment_rows[0]
        summary_lines.extend(
            [
                f"top_bundle={best['bundle_name']}",
                f"top_segment_id={best['segment_id']}",
                f"top_serving_gnb={best['serving_gnb']}",
                f"top_ue_ids={best['ue_ids']}",
                f"top_start_time_s={best['start_time_s']}",
                f"top_end_time_s={best['end_time_s']}",
                f"top_max_gain_vs_single={best['max_gain_vs_single']}",
            ]
        )
    (out_dir / "summary.txt").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print("Family corridor mining complete")
    for line in summary_lines:
        print(f"  {line}")


if __name__ == "__main__":
    main()
