"""Focused learner-hook sweep on the new r8 challenge regime."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import run_focused_family_temporal_learner as focused
import run_p3_6_coupled_learner as learner
import le_gra_mvp as mvp


ROOT = Path(__file__).resolve().parent


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _run_config(name: str, **train_kwargs) -> dict:
    bundle_dir = ROOT / "p3_6r8_q10_temporal_decoy_flicker_bundle" / "bundle"
    out_dir = ROOT / "_tmp_r8_hook_sweeps" / name
    out_dir.mkdir(parents=True, exist_ok=True)

    mvp.set_seed(9)
    export_metadata = learner._load_export_metadata(bundle_dir)
    scenarios, metadata_rows = focused._select_family_rows(
        bundle_dir,
        feature_mode="history_cost_quality",
        serving_gnb="gnb_2",
        ue_ids_signature="1|2|3|4|5|6",
    )
    train, train_meta = focused._filter_window(
        scenarios,
        metadata_rows,
        start_s=27.7,
        end_s=28.0,
    )
    test, test_meta = focused._filter_window(
        scenarios,
        metadata_rows,
        start_s=28.1,
        end_s=28.2,
    )
    model = learner.train_trace_model(
        train,
        test,
        feature_mode="history_cost_quality",
        max_groups=3,
        switch_beta=0.5,
        epochs=120,
        pair_sampling="random_balanced",
        pairs_per_class=64,
        grouping_mode=train_kwargs.pop("grouping_mode", "kmeans_embedding"),
        progress_label=f"r8 sweep {name}",
        **train_kwargs,
    )
    method_rows, grouping_cache = learner.evaluate_trace_methods(
        test,
        model,
        max_groups=3,
        switch_beta=0.5,
        kmeans_n_init=10,
        progress_label=f"r8 sweep {name}",
    )
    diag_rows = learner.evaluate_trace_teacher_imitation(
        test,
        grouping_cache,
        max_groups=3,
        switch_beta=0.5,
        metadata_rows=test_meta,
        feature_mode="history_cost_quality",
        scenario_mode="focused_family_temporal",
        load_level=f"focused_family_rb_{int(round(export_metadata['rb_budget_ratio'] * 100)):02d}",
        rb_budget_ratio=export_metadata["rb_budget_ratio"],
        seed=9,
        progress_label=f"r8 sweep {name}",
    )
    summary = {
        "config": name,
        "selected_epoch": model.selected_epoch,
        "selection_validation_loss": model.selection_validation_loss,
        "train_positive_gain_count": focused._teacher_positive_gain_count(train, max_groups=3, switch_beta=0.5),
        "test_positive_gain_count": focused._teacher_positive_gain_count(test, max_groups=3, switch_beta=0.5),
    }
    (out_dir / "split_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    _write_csv(out_dir / "main_comparison.csv", method_rows)
    _write_csv(out_dir / "teacher_imitation_diagnostics.csv", diag_rows)
    by_method = {row["method"]: row for row in method_rows}
    return {
        "config": name,
        "teacher": float(by_method["Offline teacher"]["utility"]),
        "resource": float(by_method["Resource-cost k-means"]["utility"]),
        "legra": float(by_method["LE-GRA MVP"]["utility"]),
        "multifeature": float(by_method["Multi-feature k-means"]["utility"]),
        "cqi": float(by_method["CQI k-means"]["utility"]),
        "gap_tr": float(by_method["Offline teacher"]["utility"]) - float(by_method["Resource-cost k-means"]["utility"]),
        "gap_tl": float(by_method["Offline teacher"]["utility"]) - float(by_method["LE-GRA MVP"]["utility"]),
    }


def main() -> None:
    out_root = ROOT / "_tmp_r8_hook_sweeps"
    out_root.mkdir(parents=True, exist_ok=True)
    configs = [
        (
            "baseline",
            dict(
                supervision_weight_mode="uniform",
                hard_positive_scale=2.5,
                hard_negative_scale=1.5,
                scenario_weight_mode="uniform",
                positive_gain_boost=4,
                multigroup_boost=2,
                prototype_weight=0.0,
                prototype_margin=1.0,
                membership_weight=0.0,
                candidate_membership_weight=0.0,
                candidate_top_k=2,
                candidate_secondary_scale=2.0,
                frontier_contrast_weight=0.0,
                frontier_negative_top_k=2,
                frontier_margin=0.25,
                focus_support_indices=None,
                focus_only_warmup_epochs=0,
            ),
        ),
        (
            "resource_anchor_hybrid",
            dict(
                supervision_weight_mode="uniform",
                hard_positive_scale=2.5,
                hard_negative_scale=1.5,
                scenario_weight_mode="positive_multigroup_focus",
                positive_gain_boost=6,
                multigroup_boost=4,
                prototype_weight=0.0,
                prototype_margin=1.0,
                membership_weight=0.0,
                candidate_membership_weight=0.0,
                candidate_top_k=2,
                candidate_secondary_scale=2.0,
                frontier_contrast_weight=0.0,
                frontier_negative_top_k=2,
                frontier_margin=0.25,
                focus_support_indices=None,
                focus_only_warmup_epochs=0,
                grouping_mode="resource_anchor_hybrid",
            ),
        ),
        (
            "scenario_focus",
            dict(
                supervision_weight_mode="uniform",
                hard_positive_scale=2.5,
                hard_negative_scale=1.5,
                scenario_weight_mode="positive_multigroup_focus",
                positive_gain_boost=6,
                multigroup_boost=4,
                prototype_weight=0.0,
                prototype_margin=1.0,
                membership_weight=0.0,
                candidate_membership_weight=0.0,
                candidate_top_k=2,
                candidate_secondary_scale=2.0,
                frontier_contrast_weight=0.0,
                frontier_negative_top_k=2,
                frontier_margin=0.25,
                focus_support_indices=None,
                focus_only_warmup_epochs=0,
            ),
        ),
        (
            "scenario_focus_resource_anchor",
            dict(
                supervision_weight_mode="uniform",
                hard_positive_scale=2.5,
                hard_negative_scale=1.5,
                scenario_weight_mode="positive_multigroup_focus",
                positive_gain_boost=6,
                multigroup_boost=4,
                prototype_weight=0.0,
                prototype_margin=1.0,
                membership_weight=0.0,
                candidate_membership_weight=0.0,
                candidate_top_k=2,
                candidate_secondary_scale=2.0,
                frontier_contrast_weight=0.0,
                frontier_negative_top_k=2,
                frontier_margin=0.25,
                focus_support_indices=None,
                focus_only_warmup_epochs=0,
                grouping_mode="resource_anchor_hybrid",
            ),
        ),
        (
            "candidate_bce",
            dict(
                supervision_weight_mode="uniform",
                hard_positive_scale=2.5,
                hard_negative_scale=1.5,
                scenario_weight_mode="positive_multigroup_focus",
                positive_gain_boost=6,
                multigroup_boost=4,
                prototype_weight=0.0,
                prototype_margin=1.0,
                membership_weight=0.0,
                candidate_membership_weight=1.0,
                candidate_top_k=2,
                candidate_secondary_scale=2.5,
                frontier_contrast_weight=0.0,
                frontier_negative_top_k=2,
                frontier_margin=0.25,
                focus_support_indices=None,
                focus_only_warmup_epochs=0,
            ),
        ),
        (
            "frontier",
            dict(
                supervision_weight_mode="uniform",
                hard_positive_scale=2.5,
                hard_negative_scale=1.5,
                scenario_weight_mode="positive_multigroup_focus",
                positive_gain_boost=6,
                multigroup_boost=4,
                prototype_weight=0.0,
                prototype_margin=1.0,
                membership_weight=0.0,
                candidate_membership_weight=0.0,
                candidate_top_k=2,
                candidate_secondary_scale=2.0,
                frontier_contrast_weight=0.5,
                frontier_negative_top_k=2,
                frontier_margin=0.25,
                focus_support_indices=None,
                focus_only_warmup_epochs=0,
            ),
        ),
        (
            "candidate_plus_frontier",
            dict(
                supervision_weight_mode="uniform",
                hard_positive_scale=2.5,
                hard_negative_scale=1.5,
                scenario_weight_mode="positive_multigroup_focus",
                positive_gain_boost=6,
                multigroup_boost=4,
                prototype_weight=0.0,
                prototype_margin=1.0,
                membership_weight=0.0,
                candidate_membership_weight=1.0,
                candidate_top_k=2,
                candidate_secondary_scale=2.5,
                frontier_contrast_weight=0.5,
                frontier_negative_top_k=2,
                frontier_margin=0.25,
                focus_support_indices=None,
                focus_only_warmup_epochs=0,
            ),
        ),
        (
            "prototype_membership",
            dict(
                supervision_weight_mode="uniform",
                hard_positive_scale=2.5,
                hard_negative_scale=1.5,
                scenario_weight_mode="positive_multigroup_focus",
                positive_gain_boost=6,
                multigroup_boost=4,
                prototype_weight=0.25,
                prototype_margin=1.0,
                membership_weight=0.5,
                candidate_membership_weight=0.0,
                candidate_top_k=2,
                candidate_secondary_scale=2.0,
                frontier_contrast_weight=0.0,
                frontier_negative_top_k=2,
                frontier_margin=0.25,
                focus_support_indices=None,
                focus_only_warmup_epochs=0,
            ),
        ),
        (
            "pair_warmup",
            dict(
                supervision_weight_mode="uniform",
                hard_positive_scale=2.5,
                hard_negative_scale=1.5,
                scenario_weight_mode="positive_multigroup_focus",
                positive_gain_boost=6,
                multigroup_boost=4,
                prototype_weight=0.0,
                prototype_margin=1.0,
                membership_weight=0.0,
                candidate_membership_weight=0.0,
                candidate_top_k=2,
                candidate_secondary_scale=2.0,
                frontier_contrast_weight=0.0,
                frontier_negative_top_k=2,
                frontier_margin=0.25,
                focus_support_indices=[0, 1, 2],
                focus_only_warmup_epochs=40,
            ),
        ),
        (
            "pair_warmup_plus_candidate",
            dict(
                supervision_weight_mode="uniform",
                hard_positive_scale=2.5,
                hard_negative_scale=1.5,
                scenario_weight_mode="positive_multigroup_focus",
                positive_gain_boost=6,
                multigroup_boost=4,
                prototype_weight=0.0,
                prototype_margin=1.0,
                membership_weight=0.0,
                candidate_membership_weight=1.0,
                candidate_top_k=2,
                candidate_secondary_scale=2.5,
                frontier_contrast_weight=0.0,
                frontier_negative_top_k=2,
                frontier_margin=0.25,
                focus_support_indices=[0, 1, 2],
                focus_only_warmup_epochs=40,
            ),
        ),
        (
            "pair_warmup_plus_frontier",
            dict(
                supervision_weight_mode="uniform",
                hard_positive_scale=2.5,
                hard_negative_scale=1.5,
                scenario_weight_mode="positive_multigroup_focus",
                positive_gain_boost=6,
                multigroup_boost=4,
                prototype_weight=0.0,
                prototype_margin=1.0,
                membership_weight=0.0,
                candidate_membership_weight=0.0,
                candidate_top_k=2,
                candidate_secondary_scale=2.0,
                frontier_contrast_weight=0.5,
                frontier_negative_top_k=2,
                frontier_margin=0.25,
                focus_support_indices=[0, 1, 2],
                focus_only_warmup_epochs=40,
            ),
        ),
        (
            "pair_warmup_candidate_frontier",
            dict(
                supervision_weight_mode="uniform",
                hard_positive_scale=2.5,
                hard_negative_scale=1.5,
                scenario_weight_mode="positive_multigroup_focus",
                positive_gain_boost=6,
                multigroup_boost=4,
                prototype_weight=0.0,
                prototype_margin=1.0,
                membership_weight=0.0,
                candidate_membership_weight=1.0,
                candidate_top_k=2,
                candidate_secondary_scale=2.5,
                frontier_contrast_weight=0.5,
                frontier_negative_top_k=2,
                frontier_margin=0.25,
                focus_support_indices=[0, 1, 2],
                focus_only_warmup_epochs=40,
            ),
        ),
    ]
    rows = []
    for name, kwargs in configs:
        rows.append(_run_config(name, **kwargs))
    rows.sort(key=lambda row: (row["gap_tl"], -row["legra"]), reverse=False)
    _write_csv(out_root / "leaderboard.csv", rows)
    print(*rows, sep="\n")


if __name__ == "__main__":
    main()
