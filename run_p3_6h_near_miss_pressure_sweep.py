"""P3.6h targeted RB-pressure sweep for near-miss split families."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from build_p3_5_coupled_bundle import build_coupled_bundle


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "p3_6e_coupled_output"
GNBS_CSV = ROOT / "p3_6e_gnbs.csv"
BASE_AUDIT = ROOT / "p3_6e3_teacher_audit" / "full_bundle" / "scenario_teacher_decisions.csv"
OUT_ROOT = ROOT / "p3_6h_pressure_sweep"
RATIOS = [0.32, 0.28, 0.24, 0.20]
TOP_NEAR_MISS = [
    ("1|2|3|4|5|6", "gnb_2"),
    ("2|3|4|5|6", "gnb_2"),
    ("0|1|2|3|4|5", "gnb_2"),
    ("3|31|4|5|6", "gnb_2"),
]


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


def _teacher_rows(bundle_dir: Path) -> list[dict]:
    from run_p3_6_coupled_learner import _subset_scenarios
    from run_p3_6_teacher_decision_audit import _scenario_row
    import le_gra_mvp as mvp

    all_users = _read_csv(bundle_dir / "bundle" / "users.csv")
    all_ue_ids = sorted({row["ue_id"] for row in all_users})
    scenarios, metadata_rows = _subset_scenarios(
        bundle_dir / "bundle",
        set(all_ue_ids),
        "history_cost_quality",
        min_users=2,
    )
    rows = []
    for metadata, scenario in zip(metadata_rows, scenarios):
        teacher_groups = mvp.offline_teacher_groups(
            scenario,
            max_groups=len(scenario.cqi_now),
            switch_beta=0.5,
        )
        rows.append(_scenario_row(metadata, scenario, teacher_groups, 0.5, "full_bundle"))
    return rows


def _ratio_tag(ratio: float) -> str:
    return f"rb_{int(round(ratio * 100)):03d}"


def _base_positive_keys() -> set[tuple[str, str]]:
    rows = _read_csv(BASE_AUDIT)
    return {
        (row["ue_ids"], row["serving_gnb"])
        for row in rows
        if float(row["teacher_gain_vs_single"]) > 1e-9
    }


def main() -> None:
    OUT_ROOT.mkdir(exist_ok=True)
    base_positive = _base_positive_keys()
    family_rows = []
    summary_rows = []
    positive_rows = []

    for ratio in RATIOS:
        tag = _ratio_tag(ratio)
        run_dir = OUT_ROOT / tag
        bundle_dir = run_dir / "coupled_bundle"
        counts = build_coupled_bundle(
            RAW_DIR,
            GNBS_CSV,
            bundle_dir,
            rb_budget_ratio=ratio,
            previous_quality_mode="deterministic_controller_heterogeneous",
        )
        teacher_rows = _teacher_rows(bundle_dir)
        _write_csv(run_dir / "scenario_teacher_decisions.csv", teacher_rows)

        positive = [row for row in teacher_rows if float(row["teacher_gain_vs_single"]) > 1e-9]
        positive_counter = Counter((row["ue_ids"], row["serving_gnb"]) for row in positive)
        positive_keys = set(positive_counter)
        new_positive_keys = positive_keys.difference(base_positive)

        summary_rows.append(
            {
                "ratio_tag": tag,
                "rb_budget_ratio": ratio,
                "teacher_scenarios": counts["teacher_scenarios"],
                "positive_snapshot_count": len(positive),
                "positive_family_count": len(positive_keys),
                "new_positive_family_count_vs_rb_032": len(new_positive_keys),
                "max_teacher_gain_vs_single": max(
                    (float(row["teacher_gain_vs_single"]) for row in teacher_rows),
                    default=0.0,
                ),
            }
        )

        for (ue_ids, serving_gnb), count in sorted(
            positive_counter.items(),
            key=lambda item: (-item[1], item[0][0], item[0][1]),
        ):
            matching = [
                row
                for row in positive
                if row["ue_ids"] == ue_ids and row["serving_gnb"] == serving_gnb
            ]
            positive_rows.append(
                {
                    "ratio_tag": tag,
                    "rb_budget_ratio": ratio,
                    "ue_ids": ue_ids,
                    "serving_gnb": serving_gnb,
                    "positive_snapshot_count": count,
                    "first_time_s": min(float(row["timestamp_s"]) for row in matching),
                    "last_time_s": max(float(row["timestamp_s"]) for row in matching),
                    "max_teacher_gain_vs_single": max(float(row["teacher_gain_vs_single"]) for row in matching),
                    "max_cqi_range": max(float(row["cqi_range"]) for row in matching),
                    "max_resource_cost_range": max(float(row["resource_cost_range"]) for row in matching),
                    "new_positive_family_vs_rb_032": int((ue_ids, serving_gnb) in new_positive_keys),
                }
            )

        teacher_by_family = {}
        for row in teacher_rows:
            key = (row["ue_ids"], row["serving_gnb"])
            teacher_by_family.setdefault(key, []).append(row)
        for ue_ids, serving_gnb in TOP_NEAR_MISS:
            family = teacher_by_family.get((ue_ids, serving_gnb), [])
            if not family:
                continue
            gains = [float(row["teacher_gain_vs_single"]) for row in family]
            positive_count = sum(gain > 1e-9 for gain in gains)
            family_rows.append(
                {
                    "ratio_tag": tag,
                    "rb_budget_ratio": ratio,
                    "ue_ids": ue_ids,
                    "serving_gnb": serving_gnb,
                    "scenario_count": len(family),
                    "positive_snapshot_count": positive_count,
                    "positive_ratio": positive_count / len(family),
                    "max_teacher_gain_vs_single": max(gains),
                    "max_cqi_range": max(float(row["cqi_range"]) for row in family),
                    "max_resource_cost_range": max(float(row["resource_cost_range"]) for row in family),
                    "first_time_s": min(float(row["timestamp_s"]) for row in family),
                    "last_time_s": max(float(row["timestamp_s"]) for row in family),
                }
            )

    _write_csv(OUT_ROOT / "pressure_sweep_summary.csv", summary_rows)
    _write_csv(OUT_ROOT / "positive_families.csv", positive_rows)
    _write_csv(OUT_ROOT / "target_near_miss_progression.csv", family_rows)
    (OUT_ROOT / "run_metadata.json").write_text(
        json.dumps(
            {
                "ratios": RATIOS,
                "raw_dir": str(RAW_DIR),
                "gnbs_csv": str(GNBS_CSV),
                "previous_quality_mode": "deterministic_controller_heterogeneous",
                "top_near_miss_families": [
                    {"ue_ids": ue_ids, "serving_gnb": serving_gnb}
                    for ue_ids, serving_gnb in TOP_NEAR_MISS
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print("P3.6h pressure sweep complete")
    for row in summary_rows:
        print(
            f"  rb={row['rb_budget_ratio']:.2f}: positive_snapshots={row['positive_snapshot_count']}, "
            f"positive_families={row['positive_family_count']}, "
            f"new_families={row['new_positive_family_count_vs_rb_032']}, "
            f"max_gain={row['max_teacher_gain_vs_single']:.6f}"
        )


if __name__ == "__main__":
    main()
