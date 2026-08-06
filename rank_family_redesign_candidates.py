"""Rank alternative family targets for post-plateau redesign."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _candidate_score(rows: list[dict[str, str]]) -> float:
    max_cqi = max(float(row["cqi_range"]) for row in rows)
    max_cost = max(float(row["resource_cost_range"]) for row in rows)
    max_prev = max(float(row["previous_quality_range"]) for row in rows)
    user_count = max(int(row["user_count"]) for row in rows)
    scenario_count = len(rows)
    start_time = min(float(row["timestamp_s"]) for row in rows)
    end_time = max(float(row["timestamp_s"]) for row in rows)
    duration = end_time - start_time
    # Heuristic: prioritize families with strong CQI spread, meaningful cost
    # spread, enough users, and enough temporal support to allow redesign.
    return (
        1.8 * max_cqi
        + 2.2 * max_cost
        + 0.8 * max_prev
        + 0.15 * user_count
        + 0.03 * scenario_count
        + 0.08 * duration
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--audit-csv",
        type=Path,
        default=Path("p3_6i2_teacher_audit/full_bundle/scenario_teacher_decisions.csv"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("p3_6k_family_ranking"),
    )
    parser.add_argument(
        "--include-positive",
        action="store_true",
        help="Include already-positive families instead of focusing on near-miss families only.",
    )
    args = parser.parse_args()

    rows = _read_csv(args.audit_csv)
    by_family: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_family[(row["ue_ids"], row["serving_gnb"])].append(row)

    ranked_rows: list[dict[str, object]] = []
    for (ue_ids, serving_gnb), family_rows in by_family.items():
        max_gain = max(float(row["teacher_gain_vs_single"]) for row in family_rows)
        if not args.include_positive and max_gain > 1e-9:
            continue
        user_count = max(int(row["user_count"]) for row in family_rows)
        max_cqi = max(float(row["cqi_range"]) for row in family_rows)
        max_cost = max(float(row["resource_cost_range"]) for row in family_rows)
        max_prev = max(float(row["previous_quality_range"]) for row in family_rows)
        start_time = min(float(row["timestamp_s"]) for row in family_rows)
        end_time = max(float(row["timestamp_s"]) for row in family_rows)
        score = _candidate_score(family_rows)
        ranked_rows.append(
            {
                "rank_score": f"{score:.12f}",
                "ue_ids": ue_ids,
                "serving_gnb": serving_gnb,
                "scenario_count": len(family_rows),
                "user_count": user_count,
                "max_teacher_gain_vs_single": f"{max_gain:.12f}",
                "max_cqi_range": f"{max_cqi:.1f}",
                "max_resource_cost_range": f"{max_cost:.6f}",
                "max_previous_quality_range": f"{max_prev:.1f}",
                "first_time_s": f"{start_time:.1f}",
                "last_time_s": f"{end_time:.1f}",
                "duration_s": f"{(end_time - start_time):.1f}",
            }
        )

    ranked_rows.sort(key=lambda row: float(row["rank_score"]), reverse=True)
    for index, row in enumerate(ranked_rows, start=1):
        row["rank"] = index

    _write_csv(args.out_dir / "family_redesign_ranking.csv", ranked_rows)
    top_rows = ranked_rows[:10]
    _write_csv(args.out_dir / "top10_family_redesign_ranking.csv", top_rows)
    (args.out_dir / "summary.txt").write_text(
        "\n".join(
            [
                f"audit_csv={args.audit_csv}",
                f"candidate_family_count={len(ranked_rows)}",
                f"top_family={top_rows[0]['ue_ids']} @ {top_rows[0]['serving_gnb']}" if top_rows else "top_family=",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"candidate_family_count={len(ranked_rows)}")
    if top_rows:
        print(
            "top_family="
            f"{top_rows[0]['ue_ids']}@{top_rows[0]['serving_gnb']}"
            f" score={top_rows[0]['rank_score']}"
        )


if __name__ == "__main__":
    main()
