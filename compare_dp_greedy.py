"""Compare greedy allocation against exact DP allocation.

The comparison fixes the grouping candidates and evaluates the same grouping
with two allocation backends:

1. Greedy upgrade allocation.
2. Exact DP video-quality assignment under the RB budget.

DP is the constrained optimum for a given grouping because each group chooses
one discrete video quality level and the total RB cost must fit the RB budget.
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import le_gra_mvp as mvp


def greedy_allocate_and_evaluate(
    groups: list[list[int]],
    scenario: mvp.Scenario,
    switch_beta: float,
) -> mvp.EvalResult:
    remaining_rb = scenario.rb_available
    user_quality = np.full(len(scenario.cqi_now), -1, dtype=int)
    allocations: list[dict] = []

    for group in groups:
        if not group:
            continue
        group_rates = scenario.rb_rates[group].min(axis=0)
        sorted_rates = np.sort(group_rates)[::-1]
        need = mvp.rb_needed(sorted_rates, mvp.VIDEO_BITRATES_KBPS[0])
        if need is None or need > remaining_rb:
            continue
        remaining_rb -= need
        allocations.append({"users": group, "quality": 0, "rates": sorted_rates, "used": need})
        user_quality[group] = 0

    while remaining_rb > 0 and allocations:
        best = None
        for idx, alloc in enumerate(allocations):
            q = alloc["quality"]
            if q + 1 >= len(mvp.VIDEO_BITRATES_KBPS):
                continue
            next_need = mvp.rb_needed(alloc["rates"], mvp.VIDEO_BITRATES_KBPS[q + 1])
            if next_need is None:
                continue
            extra_rb = max(1, next_need - alloc["used"])
            if extra_rb > remaining_rb:
                continue
            users = alloc["users"]
            bitrate_gain = mvp.normalized_bitrate_score(q + 1) - mvp.normalized_bitrate_score(q)
            switch_change = (
                np.abs((q + 1) - scenario.previous_quality[users]).mean()
                - np.abs(q - scenario.previous_quality[users]).mean()
            ) / (len(mvp.VIDEO_BITRATES_KBPS) - 1)
            gain_per_rb = len(users) * (bitrate_gain - switch_beta * switch_change) / extra_rb
            if best is None or gain_per_rb > best[0]:
                best = (gain_per_rb, idx, next_need, extra_rb)
        if best is None:
            break
        _, idx, next_need, extra_rb = best
        allocations[idx]["quality"] += 1
        allocations[idx]["used"] = next_need
        remaining_rb -= extra_rb
        user_quality[allocations[idx]["users"]] = allocations[idx]["quality"]

    user_bitrate = np.zeros(len(scenario.cqi_now), dtype=float)
    served = user_quality >= 0
    user_bitrate[served] = mvp.VIDEO_BITRATES_KBPS[user_quality[served]]
    switching = np.zeros(len(scenario.cqi_now), dtype=float)
    switching[served] = np.abs(user_quality[served] - scenario.previous_quality[served]) / (
        len(mvp.VIDEO_BITRATES_KBPS) - 1
    )
    used_rb = scenario.rb_available - remaining_rb
    return mvp.EvalResult(
        utility=mvp.compute_qoe_utility(user_quality, scenario, switch_beta),
        adr_kbps=float(user_bitrate.mean()),
        used_spectral_efficiency=(
            float(user_bitrate.sum() / (used_rb * mvp.RB_BANDWIDTH_KHZ))
            if used_rb > 0 else 0.0
        ),
        system_spectral_efficiency=float(
            user_bitrate.sum() / (scenario.rb_available * mvp.RB_BANDWIDTH_KHZ)
        ),
        served_ratio=float(served.mean()),
        unserved_ratio=float(1.0 - served.mean()),
        average_quality=float(user_quality[served].mean()) if np.any(served) else 0.0,
        rb_utilization=float(used_rb / max(1, scenario.rb_available)),
        avg_switching=float(switching.mean()),
        fairness=mvp.jain_fairness(user_bitrate),
        groups=len(groups),
    )


def candidate_groups_for_scenario(
    scenario: mvp.Scenario,
    max_groups: int,
    switch_beta: float,
) -> dict[str, list[list[int]]]:
    return {
        "No grouping": mvp.no_grouping(scenario),
        "CQI k-means": mvp.cqi_kmeans_grouping(scenario, max_groups, switch_beta),
        "Resource-cost": mvp.resource_cost_kmeans_grouping(scenario, max_groups, switch_beta),
        "Teacher": mvp.offline_teacher_groups(scenario, max_groups, switch_beta),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", type=int, default=80)
    parser.add_argument("--users", type=int, default=12)
    parser.add_argument("--rbs", type=int, default=70)
    parser.add_argument("--max-groups", type=int, default=5)
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--scenario-mode", choices=["aligned", "ambiguous", "mixed"], default="ambiguous")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--out-dir", type=Path, default=Path("."))
    args = parser.parse_args()

    mvp.set_seed(args.seed)
    dispersions = ["high", "mid", "low"]
    scenarios = [
        mvp.generate_scenario(args.users, args.rbs, random.choice(dispersions), args.scenario_mode)
        for _ in range(args.scenarios)
    ]
    # Use generated scenarios only for allocation comparison; normalize is not
    # needed because no learned model is used.

    rows = []
    for scenario_idx, scenario in enumerate(scenarios):
        candidates = candidate_groups_for_scenario(scenario, args.max_groups, args.switch_beta)
        for grouping_name, groups in candidates.items():
            greedy = greedy_allocate_and_evaluate(groups, scenario, args.switch_beta)
            dp = mvp.allocate_and_evaluate(groups, scenario, args.switch_beta)
            rows.append(
                {
                    "scenario": scenario_idx,
                    "grouping": grouping_name,
                    "greedy_utility": greedy.utility,
                    "dp_utility": dp.utility,
                    "utility_gap": dp.utility - greedy.utility,
                    "greedy_adr": greedy.adr_kbps,
                    "dp_adr": dp.adr_kbps,
                    "adr_gap": dp.adr_kbps - greedy.adr_kbps,
                    "greedy_rb_util": greedy.rb_utilization,
                    "dp_rb_util": dp.rb_utilization,
                    "greedy_switching": greedy.avg_switching,
                    "dp_switching": dp.avg_switching,
                }
            )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "dp_vs_greedy_metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    groupings = sorted(set(r["grouping"] for r in rows))
    summary = []
    for grouping in groupings:
        subset = [r for r in rows if r["grouping"] == grouping]
        summary.append(
            {
                "grouping": grouping,
                "greedy_utility": float(np.mean([r["greedy_utility"] for r in subset])),
                "dp_utility": float(np.mean([r["dp_utility"] for r in subset])),
                "utility_gap": float(np.mean([r["utility_gap"] for r in subset])),
                "greedy_adr": float(np.mean([r["greedy_adr"] for r in subset])),
                "dp_adr": float(np.mean([r["dp_adr"] for r in subset])),
                "adr_gap": float(np.mean([r["adr_gap"] for r in subset])),
            }
        )

    summary_path = args.out_dir / "dp_vs_greedy_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)

    labels = [s["grouping"] for s in summary]
    x = np.arange(len(labels))
    width = 0.36
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), dpi=160)
    axes[0].bar(x - width / 2, [s["greedy_utility"] for s in summary], width, label="Greedy", color="#64748b")
    axes[0].bar(x + width / 2, [s["dp_utility"] for s in summary], width, label="DP", color="#2563eb")
    axes[0].set_title("QoE Utility")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=25, ha="right")
    axes[0].grid(axis="y", alpha=0.25)
    axes[0].legend()

    axes[1].bar(x - width / 2, [s["greedy_adr"] for s in summary], width, label="Greedy", color="#64748b")
    axes[1].bar(x + width / 2, [s["dp_adr"] for s in summary], width, label="DP", color="#2563eb")
    axes[1].set_title("ADR (kbps)")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=25, ha="right")
    axes[1].grid(axis="y", alpha=0.25)
    axes[1].legend()
    fig.suptitle(f"DP vs Greedy Allocation ({args.scenario_mode} scenarios)")
    fig.tight_layout()
    png_path = args.out_dir / "dp_vs_greedy_chart.png"
    fig.savefig(png_path, bbox_inches="tight")

    print(f"Saved {csv_path}")
    print(f"Saved {summary_path}")
    print(f"Saved {png_path}")
    print("\nSummary")
    for s in summary:
        print(
            f"{s['grouping']}: utility greedy={s['greedy_utility']:.4f}, "
            f"dp={s['dp_utility']:.4f}, gap={s['utility_gap']:.4f}; "
            f"ADR greedy={s['greedy_adr']:.1f}, dp={s['dp_adr']:.1f}, gap={s['adr_gap']:.1f}"
        )


if __name__ == "__main__":
    main()
