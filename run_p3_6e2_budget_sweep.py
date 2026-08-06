"""Run the P3.6e-2 tighter-budget sweep on the P3.6e raw coupled trace."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from audit_coupled_trace import audit_bundle
from build_p3_5_coupled_bundle import build_coupled_bundle
from run_p3_6_coupled_learner import _load_export_metadata, _read_csv, _subset_scenarios, choose_trajectory_split
from run_p3_6_teacher_decision_audit import _run_split_audit


RAW_DIR = Path("p3_6e_coupled_output")
GNBS_CSV = Path("p3_6e_gnbs.csv")
OUT_ROOT = Path("p3_6e2_budget_sweep")
BUDGET_RATIOS = [0.50, 0.40, 0.32]
FEATURE_MODE = "history_cost_quality"
SWITCH_BETA = 0.5
MIN_USERS = 2
TEST_UE_COUNT = 3


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _read_summary_csv(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    key_field = "metric" if "metric" in rows[0] else "gate"
    value_field = "value" if "value" in rows[0] else "observed"
    return {row[key_field]: row[value_field] for row in rows}


def _run_teacher_audit(bundle_root: Path, out_dir: Path) -> dict:
    bundle_dir = bundle_root / "bundle"
    export_metadata = _load_export_metadata(bundle_dir)
    all_users = _read_csv(bundle_dir / "users.csv")
    all_ue_ids = sorted({row["ue_id"] for row in all_users})
    split = choose_trajectory_split(
        bundle_dir,
        test_ue_count=TEST_UE_COUNT,
        feature_mode=FEATURE_MODE,
        min_users=MIN_USERS,
    )
    full_scenarios, full_metadata = _subset_scenarios(
        bundle_dir,
        set(all_ue_ids),
        FEATURE_MODE,
        min_users=MIN_USERS,
    )
    test_scenarios, test_metadata = _subset_scenarios(
        bundle_dir,
        set(split["test_ue_ids"]),
        FEATURE_MODE,
        min_users=MIN_USERS,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    _run_split_audit(
        bundle_dir,
        full_scenarios,
        full_metadata,
        switch_beta=SWITCH_BETA,
        split_name="full_bundle",
        out_dir=out_dir,
    )
    _run_split_audit(
        bundle_dir,
        test_scenarios,
        test_metadata,
        switch_beta=SWITCH_BETA,
        split_name="learner_test_split",
        out_dir=out_dir,
    )
    run_metadata = {
        "bundle_dir": str(bundle_dir),
        "feature_mode": FEATURE_MODE,
        "switch_beta": SWITCH_BETA,
        "min_users": MIN_USERS,
        "export_rb_budget_ratio": export_metadata["rb_budget_ratio"],
        "trajectory_split_test_ue_ids": split["test_ue_ids"],
        "trajectory_split_train_ue_ids": split["train_ue_ids"],
    }
    (out_dir / "run_metadata.json").write_text(json.dumps(run_metadata, indent=2) + "\n", encoding="utf-8")
    return run_metadata


def _ratio_tag(value: float) -> str:
    return f"rb_{int(round(value * 100)):03d}"


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    comparison_rows = []
    for ratio in BUDGET_RATIOS:
        tag = _ratio_tag(ratio)
        bundle_root = OUT_ROOT / tag / "bundle_root"
        audit_dir = OUT_ROOT / tag / "coupled_audit"
        teacher_dir = OUT_ROOT / tag / "teacher_audit"

        counts = build_coupled_bundle(
            RAW_DIR,
            GNBS_CSV,
            bundle_root,
            rb_budget_ratio=ratio,
            previous_quality_mode="deterministic_controller",
        )
        audit_bundle(bundle_root, audit_dir)
        teacher_metadata = _run_teacher_audit(bundle_root, teacher_dir)

        coupled_summary = _read_summary_csv(audit_dir / "summary.csv")
        full_teacher_summary = _read_summary_csv(teacher_dir / "full_bundle" / "summary.csv")
        test_teacher_summary = _read_summary_csv(teacher_dir / "learner_test_split" / "summary.csv")

        comparison_rows.append(
            {
                "rb_budget_ratio": ratio,
                "tag": tag,
                "bundle_scenarios": counts["bundle_scenarios"],
                "bundle_users": counts["bundle_users"],
                "teacher_scenarios": counts["teacher_scenarios"],
                "multi_ue_snapshot_count": coupled_summary["multi_ue_snapshot_count"],
                "active_ues_median": coupled_summary["active_ues_median"],
                "cqi_saturation_ratio": coupled_summary["cqi_saturation_ratio"],
                "ambiguous_pair_count": coupled_summary["ambiguous_pair_count"],
                "ambiguous_pair_ratio": coupled_summary["ambiguous_pair_ratio"],
                "handover_count": coupled_summary["handover_count"],
                "quality_switch_count": coupled_summary["quality_switch_count"],
                "full_multi_group_count": full_teacher_summary["multi_group_count"],
                "full_multi_group_ratio": full_teacher_summary["multi_group_ratio"],
                "full_positive_gain_count": full_teacher_summary["positive_gain_count"],
                "full_positive_gain_ratio": full_teacher_summary["positive_gain_ratio"],
                "full_max_teacher_gain_vs_single": full_teacher_summary["max_teacher_gain_vs_single"],
                "test_multi_group_count": test_teacher_summary["multi_group_count"],
                "test_multi_group_ratio": test_teacher_summary["multi_group_ratio"],
                "test_positive_gain_count": test_teacher_summary["positive_gain_count"],
                "test_positive_gain_ratio": test_teacher_summary["positive_gain_ratio"],
                "test_max_teacher_gain_vs_single": test_teacher_summary["max_teacher_gain_vs_single"],
                "test_ue_ids": "|".join(teacher_metadata["trajectory_split_test_ue_ids"]),
            }
        )
        print(
            f"[{tag}] bundle_scenarios={counts['bundle_scenarios']} "
            f"full_multi_group_ratio={full_teacher_summary['multi_group_ratio']} "
            f"test_multi_group_ratio={test_teacher_summary['multi_group_ratio']}"
        )

    _write_csv(OUT_ROOT / "budget_sweep_comparison.csv", comparison_rows)
    (OUT_ROOT / "run_metadata.json").write_text(
        json.dumps(
            {
                "raw_dir": str(RAW_DIR),
                "gnbs_csv": str(GNBS_CSV),
                "budget_ratios": BUDGET_RATIOS,
                "feature_mode": FEATURE_MODE,
                "switch_beta": SWITCH_BETA,
                "min_users": MIN_USERS,
                "test_ue_count": TEST_UE_COUNT,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("P3.6e-2 budget sweep complete")


if __name__ == "__main__":
    main()
