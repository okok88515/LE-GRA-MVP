"""Run a batch P3.6m family-bank search from dual-candidate rankings.

This script applies the successful P3.6l-4 pattern in a generic way:

- candidate_1 becomes the primary weak user
- candidate_2 becomes a light temporal decoy
- the remaining users keep a stronger continuity prior

Each prototype bundle is built serially, then audited serially to avoid partial
CSV reads while the bundle is still being written.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_BASE_BUNDLE = ROOT / "p3_6i2_coupled_bundle"
DEFAULT_RANKING_CSV = ROOT / "p3_6l_dual_candidate_ranking_v2" / "top10_dual_candidate_family_ranking.csv"
DEFAULT_OUT_DIR = ROOT / "p3_6m_family_bank"


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _clip_cqi(value: float) -> float:
    return max(1.0, min(15.0, value))


def _primary_factor(rate_kbps: float) -> float:
    if rate_kbps >= 1128.0:
        return 0.82
    if rate_kbps >= 984.0:
        return 0.78
    return 0.88


def _decoy_factor(rate_kbps: float) -> float:
    if rate_kbps >= 1128.0:
        return 0.985
    if rate_kbps >= 984.0:
        return 0.975
    return 0.99


def _safe_name(text: str) -> str:
    return text.replace("|", "_").replace("@", "_at_")


def _run(args: list[str]) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def _read_summary_metrics(path: Path) -> dict[str, str]:
    _, rows = _read_csv(path)
    return {row["metric"]: row["value"] for row in rows}


def _summarize_target_rows(
    target_ue_ids: str,
    target_gnb: str,
    audit_csv: Path,
    *,
    window_start_s: float,
    window_end_s: float,
) -> dict[str, float]:
    _, rows = _read_csv(audit_csv)
    target_rows = [
        row
        for row in rows
        if row["ue_ids"] == target_ue_ids and row["serving_gnb"] == target_gnb
    ]
    window_rows = [
        row
        for row in target_rows
        if window_start_s <= float(row["timestamp_s"]) <= window_end_s
    ]
    positive = [row for row in target_rows if float(row["teacher_gain_vs_single"]) > 1e-9]
    window_positive = [row for row in window_rows if float(row["teacher_gain_vs_single"]) > 1e-9]
    window_multi_group = [row for row in window_rows if int(float(row["teacher_group_count"])) > 1]
    max_gain = max((float(row["teacher_gain_vs_single"]) for row in target_rows), default=0.0)
    window_max_gain = max((float(row["teacher_gain_vs_single"]) for row in window_rows), default=0.0)
    mean_gain = (
        sum(float(row["teacher_gain_vs_single"]) for row in target_rows) / len(target_rows)
        if target_rows
        else 0.0
    )
    window_mean_gain = (
        sum(float(row["teacher_gain_vs_single"]) for row in window_rows) / len(window_rows)
        if window_rows
        else 0.0
    )
    return {
        "target_positive_gain_count": len(positive),
        "target_max_gain_vs_single": max_gain,
        "target_mean_gain_vs_single": mean_gain,
        "window_scenario_count": len(window_rows),
        "window_positive_gain_count": len(window_positive),
        "window_multi_group_count": len(window_multi_group),
        "window_max_gain_vs_single": window_max_gain,
        "window_mean_gain_vs_single": window_mean_gain,
    }


def _collect_target_scenarios(
    scenario_rows: list[dict[str, str]],
    user_rows: list[dict[str, str]],
    *,
    target_ue_ids: str,
    serving_gnb: str,
    window_start_s: float,
    window_end_s: float,
) -> set[str]:
    scenario_users: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in user_rows:
        scenario_users[row["scenario_id"]].append(row)

    target_ids: set[str] = set()
    for row in scenario_rows:
        timestamp_s = float(row["timestamp_s"])
        if row["serving_gnb"] != serving_gnb or not (window_start_s <= timestamp_s <= window_end_s):
            continue
        family = sorted(
            scenario_users.get(row["scenario_id"], []),
            key=lambda item: int(item["user_index"]),
        )
        if "|".join(item["ue_id"] for item in family) == target_ue_ids:
            target_ids.add(row["scenario_id"])
    return target_ids


def _apply_bundle_transform(
    *,
    src_bundle_root: Path,
    dst_bundle_root: Path,
    target_ue_ids: str,
    target_gnb: str,
    window_start_s: float,
    window_end_s: float,
    primary_ue_id: str,
    decoy_ue_id: str,
) -> dict[str, int]:
    if dst_bundle_root.exists():
        shutil.rmtree(dst_bundle_root)
    shutil.copytree(src_bundle_root, dst_bundle_root)

    _, scenario_rows = _read_csv(dst_bundle_root / "bundle" / "scenarios.csv")
    _, user_rows = _read_csv(dst_bundle_root / "bundle" / "users.csv")
    scenario_meta = {row["scenario_id"]: row for row in scenario_rows}
    target_scenario_ids = _collect_target_scenarios(
        scenario_rows,
        user_rows,
        target_ue_ids=target_ue_ids,
        serving_gnb=target_gnb,
        window_start_s=window_start_s,
        window_end_s=window_end_s,
    )

    rb_mod_counts: dict[str, int] = {}
    for rel_dir, filename in [("bundle", "rb_rates.csv"), ("radio", "radio_rbs.csv")]:
        path = dst_bundle_root / rel_dir / filename
        fields, rows = _read_csv(path)
        modified = 0
        for row in rows:
            if "scenario_id" in row:
                if row["scenario_id"] not in target_scenario_ids:
                    continue
            else:
                timestamp_s = float(row["timestamp_s"])
                if row["serving_gnb"] != target_gnb or not (window_start_s <= timestamp_s <= window_end_s):
                    continue
            rate = float(row["rate_kbps"])
            if row["ue_id"] == primary_ue_id:
                row["rate_kbps"] = f"{max(1.0, rate * _primary_factor(rate)):.6f}"
                modified += 1
            elif row["ue_id"] == decoy_ue_id:
                row["rate_kbps"] = f"{max(1.0, rate * _decoy_factor(rate)):.6f}"
                modified += 1
        _write_csv(path, fields, rows)
        rb_mod_counts[f"{rel_dir}_{filename}"] = modified

    strong_ues = set(target_ue_ids.split("|")) - {primary_ue_id, decoy_ue_id}
    users_path = dst_bundle_root / "bundle" / "users.csv"
    user_fields, rows = _read_csv(users_path)
    pq_modified = 0
    history_modified = 0
    for row in rows:
        if row["scenario_id"] not in target_scenario_ids:
            continue
        current = float(row["cqi_now_raw"])
        if row["ue_id"] == primary_ue_id:
            row["previous_quality"] = "0"
            row["cqi_t_minus_4"] = f"{_clip_cqi(current + 0.9):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(current + 0.6):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(current + 0.1):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(current - 1.1):.2f}"
            pq_modified += 1
            history_modified += 1
        elif row["ue_id"] == decoy_ue_id:
            row["previous_quality"] = "2"
            row["cqi_t_minus_4"] = f"{_clip_cqi(current + 0.8):.2f}"
            row["cqi_t_minus_3"] = f"{_clip_cqi(current + 0.9):.2f}"
            row["cqi_t_minus_2"] = f"{_clip_cqi(current + 0.7):.2f}"
            row["cqi_t_minus_1"] = f"{_clip_cqi(current - 0.8):.2f}"
            pq_modified += 1
            history_modified += 1
        elif row["ue_id"] in strong_ues:
            row["previous_quality"] = str(max(int(float(row["previous_quality"])), 2))
            pq_modified += 1
    _write_csv(users_path, user_fields, rows)

    metadata_path = dst_bundle_root / "radio" / "export_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["postprocess_variant"] = {
        "name": dst_bundle_root.name,
        "base_bundle": src_bundle_root.name,
        "target_family": f"{target_ue_ids}@{target_gnb}",
        "window_s": [window_start_s, window_end_s],
        "primary_weak_ue_id": primary_ue_id,
        "decoy_ue_id": decoy_ue_id,
        "intent": (
            "batch P3.6m primary-weak plus light-decoy family-bank search "
            "built from the generic P3.6l-4 transform"
        ),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    return {
        "target_scenarios": len(target_scenario_ids),
        "previous_quality_modified_rows": pq_modified,
        "history_modified_rows": history_modified,
        **rb_mod_counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-bundle-root", type=Path, default=DEFAULT_BASE_BUNDLE)
    parser.add_argument("--ranking-csv", type=Path, default=DEFAULT_RANKING_CSV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--include-ranks",
        nargs="*",
        type=int,
        default=None,
        help="Optional explicit ranks to build instead of the first top-k rows.",
    )
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    _, ranking_rows = _read_csv(args.ranking_csv)
    if args.include_ranks:
        allowed = {str(value) for value in args.include_ranks}
        selected = [row for row in ranking_rows if row["rank"] in allowed]
    else:
        selected = ranking_rows[: args.top_k]

    summary_rows: list[dict[str, str]] = []
    for row in selected:
        ue_ids = row["ue_ids"]
        serving_gnb = row["serving_gnb"]
        primary_ue_id = row["candidate_1_ue_id"]
        decoy_ue_id = row["candidate_2_ue_id"]
        first_time_s = float(row["first_time_s"])
        last_time_s = float(row["last_time_s"])

        family_tag = f"rank{row['rank']}_{_safe_name(ue_ids)}_{serving_gnb}"
        bundle_root = args.out_dir / f"{family_tag}_bundle"
        audit_root = args.out_dir / f"{family_tag}_teacher_audit"
        focus_root = args.out_dir / f"{family_tag}_focus_mining"

        build_metrics = _apply_bundle_transform(
            src_bundle_root=args.base_bundle_root,
            dst_bundle_root=bundle_root,
            target_ue_ids=ue_ids,
            target_gnb=serving_gnb,
            window_start_s=first_time_s,
            window_end_s=last_time_s,
            primary_ue_id=primary_ue_id,
            decoy_ue_id=decoy_ue_id,
        )

        _run(
            [
                sys.executable,
                "run_p3_6_teacher_decision_audit.py",
                "--bundle-dir",
                str(bundle_root / "bundle"),
                "--out-dir",
                str(audit_root),
            ]
        )
        _run(
            [
                sys.executable,
                "mine_focus_slices.py",
                "--audit-csv",
                str(audit_root / "full_bundle" / "scenario_teacher_decisions.csv"),
                "--out-dir",
                str(focus_root),
            ]
        )

        full_summary = _read_summary_metrics(audit_root / "full_bundle" / "summary.csv")
        target_metrics = _summarize_target_rows(
            ue_ids,
            serving_gnb,
            audit_root / "full_bundle" / "scenario_teacher_decisions.csv",
            window_start_s=first_time_s,
            window_end_s=last_time_s,
        )
        _, positive_segments = _read_csv(focus_root / "positive_segments.csv")
        summary_rows.append(
            {
                "rank": row["rank"],
                "family_tag": family_tag,
                "target_ue_ids": ue_ids,
                "serving_gnb": serving_gnb,
                "primary_weak_ue_id": primary_ue_id,
                "decoy_ue_id": decoy_ue_id,
                "window_start_s": f"{first_time_s:.1f}",
                "window_end_s": f"{last_time_s:.1f}",
                "target_scenario_count": str(build_metrics["target_scenarios"]),
                "target_positive_gain_count": str(target_metrics["target_positive_gain_count"]),
                "target_max_gain_vs_single": f"{target_metrics['target_max_gain_vs_single']:.12f}",
                "target_mean_gain_vs_single": f"{target_metrics['target_mean_gain_vs_single']:.12f}",
                "window_scenario_count": str(target_metrics["window_scenario_count"]),
                "window_positive_gain_count": str(target_metrics["window_positive_gain_count"]),
                "window_multi_group_count": str(target_metrics["window_multi_group_count"]),
                "window_max_gain_vs_single": f"{target_metrics['window_max_gain_vs_single']:.12f}",
                "window_mean_gain_vs_single": f"{target_metrics['window_mean_gain_vs_single']:.12f}",
                "full_bundle_positive_gain_count": full_summary.get("positive_gain_count", "0"),
                "full_bundle_positive_gain_ratio": full_summary.get("positive_gain_ratio", "0"),
                "focus_positive_segment_count": str(len(positive_segments)),
            }
        )

    summary_rows.sort(
        key=lambda item: (
            -int(item["window_positive_gain_count"]),
            -int(item["window_multi_group_count"]),
            -float(item["window_max_gain_vs_single"]),
            -int(item["target_positive_gain_count"]),
            -int(item["focus_positive_segment_count"]),
            int(item["rank"]),
        )
    )
    for index, row in enumerate(summary_rows, start=1):
        row["summary_rank"] = str(index)

    summary_path = args.out_dir / "family_bank_summary.csv"
    if summary_rows:
        _write_csv(summary_path, list(summary_rows[0].keys()), summary_rows)
    else:
        summary_path.write_text("", encoding="utf-8")
    (args.out_dir / "summary.txt").write_text(
        "\n".join(
            [
                f"ranking_csv={args.ranking_csv}",
                f"selected_family_count={len(summary_rows)}",
                (
                    f"best_family={summary_rows[0]['target_ue_ids']} @ {summary_rows[0]['serving_gnb']}"
                    if summary_rows
                    else "best_family="
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"selected_family_count={len(summary_rows)}")
    if summary_rows:
        best = summary_rows[0]
        print(
            "best_family="
            f"{best['target_ue_ids']} @ {best['serving_gnb']} "
            f"(target_positive_gain_count={best['target_positive_gain_count']}, "
            f"target_max_gain_vs_single={best['target_max_gain_vs_single']})"
        )


if __name__ == "__main__":
    main()
