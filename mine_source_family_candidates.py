"""Rank source-family candidates from existing teacher-decision audit CSVs.

This script scans the repo for `scenario_teacher_decisions.csv` files and
summarizes each `(serving_gnb, ue_ids)` family by its *best* observed source
audit, instead of naively aggregating duplicated follow-up audits together.

The goal is to answer:

1. Which families ever produced positive-gain split regimes?
2. Which ones have the longest contiguous positive segments?
3. Which ones are likely already exhausted versus still worth revisiting?
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


POS_EPS = 1e-9
TIME_GAP_EPS = 0.11


@dataclass
class Row:
    source: str
    timestamp_s: float
    serving_gnb: str
    ue_ids: str
    teacher_group_count: int
    teacher_gain_vs_single: float
    previous_quality_range: float
    cqi_range: float


def _read_rows(path: Path) -> list[Row]:
    rows: list[Row] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            rows.append(
                Row(
                    source=str(path.parent.parent),
                    timestamp_s=float(raw.get("timestamp_s", 0.0) or 0.0),
                    serving_gnb=raw.get("serving_gnb", ""),
                    ue_ids=raw.get("ue_ids", ""),
                    teacher_group_count=int(float(raw.get("teacher_group_count", 0) or 0)),
                    teacher_gain_vs_single=float(raw.get("teacher_gain_vs_single", 0.0) or 0.0),
                    previous_quality_range=float(raw.get("previous_quality_range", 0.0) or 0.0),
                    cqi_range=float(raw.get("cqi_range", 0.0) or 0.0),
                )
            )
    return rows


def _find_positive_segments(rows: list[Row]) -> list[list[Row]]:
    rows = sorted(rows, key=lambda row: row.timestamp_s)
    segments: list[list[Row]] = []
    current: list[Row] = []
    for row in rows:
        if row.teacher_gain_vs_single <= POS_EPS:
            if current:
                segments.append(current)
                current = []
            continue
        if not current:
            current = [row]
            continue
        if abs(row.timestamp_s - current[-1].timestamp_s) <= TIME_GAP_EPS:
            current.append(row)
        else:
            segments.append(current)
            current = [row]
    if current:
        segments.append(current)
    return segments


def _family_rows_by_source(root: Path) -> dict[tuple[str, str], dict[str, list[Row]]]:
    result: dict[tuple[str, str], dict[str, list[Row]]] = defaultdict(lambda: defaultdict(list))
    for path in root.glob("**/scenario_teacher_decisions.csv"):
        if ".git" in path.parts:
            continue
        try:
            rows = _read_rows(path)
        except Exception:
            continue
        for row in rows:
            result[(row.serving_gnb, row.ue_ids)][row.source].append(row)
    return result


def _summarize_best_source(
    family_sources: dict[str, list[Row]],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    best_source_name = ""
    best_rows: list[Row] = []
    best_segments: list[list[Row]] = []
    best_score = (-1, -1, -1.0)

    source_details: list[dict[str, str]] = []
    for source_name, rows in sorted(family_sources.items()):
        segments = _find_positive_segments(rows)
        positive_count = sum(1 for row in rows if row.teacher_gain_vs_single > POS_EPS)
        best_segment_len = max((len(seg) for seg in segments), default=0)
        max_gain = max((row.teacher_gain_vs_single for row in rows), default=0.0)
        groups = sorted({row.teacher_group_count for row in rows if row.teacher_gain_vs_single > POS_EPS})
        source_details.append(
            {
                "source_audit": source_name,
                "positive_snapshot_count": str(positive_count),
                "positive_segment_count": str(len(segments)),
                "best_segment_len": str(best_segment_len),
                "max_gain_vs_single": f"{max_gain:.12f}",
                "positive_group_counts": "|".join(str(g) for g in groups) if groups else "",
            }
        )
        score = (best_segment_len, positive_count, max_gain)
        if score > best_score:
            best_score = score
            best_source_name = source_name
            best_rows = rows
            best_segments = segments

    positive_rows = [row for row in best_rows if row.teacher_gain_vs_single > POS_EPS]
    best_segment = max(best_segments, key=len) if best_segments else []
    summary = {
        "source_audit": best_source_name,
        "positive_snapshot_count": str(len(positive_rows)),
        "positive_segment_count": str(len(best_segments)),
        "best_segment_len": str(len(best_segment)),
        "best_segment_start_s": f"{best_segment[0].timestamp_s:.1f}" if best_segment else "",
        "best_segment_end_s": f"{best_segment[-1].timestamp_s:.1f}" if best_segment else "",
        "max_gain_vs_single": (
            f"{max((row.teacher_gain_vs_single for row in positive_rows), default=0.0):.12f}"
        ),
        "mean_positive_gain_vs_single": (
            f"{(sum(row.teacher_gain_vs_single for row in positive_rows) / len(positive_rows)):.12f}"
            if positive_rows
            else "0.000000000000"
        ),
        "positive_group_counts": (
            "|".join(str(g) for g in sorted({row.teacher_group_count for row in positive_rows}))
            if positive_rows
            else ""
        ),
        "mean_positive_previous_quality_range": (
            f"{(sum(row.previous_quality_range for row in positive_rows) / len(positive_rows)):.6f}"
            if positive_rows
            else "0.000000"
        ),
        "mean_positive_cqi_range": (
            f"{(sum(row.cqi_range for row in positive_rows) / len(positive_rows)):.6f}"
            if positive_rows
            else "0.000000"
        ),
        "source_count": str(len(family_sources)),
    }
    return summary, source_details


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
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
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    families = _family_rows_by_source(args.root.resolve())
    ranking_rows: list[dict[str, str]] = []
    detail_rows: list[dict[str, str]] = []

    for (serving_gnb, ue_ids), family_sources in sorted(families.items()):
        summary, source_details = _summarize_best_source(family_sources)
        positive_count = int(summary["positive_snapshot_count"])
        if positive_count <= 0:
            continue
        ranking_rows.append(
            {
                "serving_gnb": serving_gnb,
                "ue_ids": ue_ids,
                **summary,
            }
        )
        for detail in source_details:
            detail_rows.append(
                {
                    "serving_gnb": serving_gnb,
                    "ue_ids": ue_ids,
                    **detail,
                }
            )

    ranking_rows.sort(
        key=lambda row: (
            int(row["best_segment_len"]),
            int(row["positive_snapshot_count"]),
            float(row["max_gain_vs_single"]),
        ),
        reverse=True,
    )

    _write_csv(args.out_dir / "family_candidate_ranking.csv", ranking_rows)
    _write_csv(args.out_dir / "family_candidate_source_details.csv", detail_rows)

    top_lines = [
        f"positive_family_count={len(ranking_rows)}",
    ]
    for index, row in enumerate(ranking_rows[:10], start=1):
        top_lines.append(
            "rank_{idx}={ue_ids}@{gnb} best_segment={seg_len} "
            "positive={pos} max_gain={gain} source={source}".format(
                idx=index,
                ue_ids=row["ue_ids"],
                gnb=row["serving_gnb"],
                seg_len=row["best_segment_len"],
                pos=row["positive_snapshot_count"],
                gain=row["max_gain_vs_single"],
                source=row["source_audit"],
            )
        )
    (args.out_dir / "summary.txt").write_text("\n".join(top_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
