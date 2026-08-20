"""Sanity check: do the CQI k-means / resource-cost k-means / multi-feature
k-means comparisons hold up on REAL Simu5G+SUMO+Veins data (not the Python
synthetic generator)?

See `parse_real_simu5g_data.py` for full data provenance and modeling
choices. Only 15 usable scenarios per load level are available (limited by
how long all 24 vehicles stay simultaneously present with full 25-band CQI
coverage in this one 90s run) -- far fewer than the synthetic protocol's
60-90 per condition, so this is a directional sanity check, not a
confirmatory statistical test. No Holm correction / tight CI is claimed
here; report point estimates and raw win/loss counts only.

LE-GRA is NOT evaluated here -- training a model needs far more scenarios
than this one real run provides (see parse script docstring).
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp
from parse_real_simu5g_data import build_scenarios

KMAX = 3
SWITCH_BETA = 0.5
KMEANS_N_INIT = 10

METHODS = {
    "No grouping": lambda s: mvp.cqi_kmeans_grouping(s, 1, SWITCH_BETA, KMEANS_N_INIT),
    "CQI k-means": lambda s: mvp.cqi_kmeans_grouping(s, KMAX, SWITCH_BETA, KMEANS_N_INIT),
    "Resource-cost k-means": lambda s: mvp.resource_cost_kmeans_grouping(s, KMAX, SWITCH_BETA, KMEANS_N_INIT),
    "Multi-feature k-means": lambda s: mvp.multi_feature_kmeans_grouping(
        s, KMAX, SWITCH_BETA, feature_mode="full", kmeans_n_init=KMEANS_N_INIT
    ),
    "Offline teacher": lambda s: mvp.offline_teacher_groups_fast(s, KMAX, SWITCH_BETA),
}


DISPERSION_FILES = {
    "low": (Path("real_simu5g_data/raw_radio.csv"), Path("real_simu5g_data/raw_mobility.csv")),
    "mid": (Path("real_simu5g_data/mid_raw_radio.csv"), Path("real_simu5g_data/mid_raw_mobility.csv")),
    "high": (Path("real_simu5g_data/high_raw_radio.csv"), Path("real_simu5g_data/high_raw_mobility.csv")),
}


def main() -> None:
    all_rows = []
    for dispersion, (radio_path, mobility_path) in DISPERSION_FILES.items():
        for ratio, load_label in [(0.50, "light"), (0.25, "medium"), (0.10, "heavy")]:
            scenarios = build_scenarios(ratio, radio_path=radio_path, mobility_path=mobility_path)
            print(f"\n=== dispersion={dispersion} load={load_label} (rb_budget_ratio={ratio}, "
                  f"rb_available={scenarios[0].rb_available}/25, n={len(scenarios)}) ===")
            per_method_utility = {name: [] for name in METHODS}
            for idx, scenario in enumerate(scenarios):
                for name, fn in METHODS.items():
                    groups = fn(scenario)
                    result = mvp.allocate_and_evaluate(groups, scenario, SWITCH_BETA)
                    per_method_utility[name].append(result.utility)
                    all_rows.append({
                        "dispersion": dispersion, "load": load_label, "scenario_index": idx,
                        "method": name, "utility": result.utility,
                    })

            cqi = np.array(per_method_utility["CQI k-means"])
            for name in METHODS:
                vals = np.array(per_method_utility[name])
                diff = vals - cqi
                print(
                    f"{name:24s} mean_utility={vals.mean():+.5f}  vs CQI: mean_diff={diff.mean():+.5f} "
                    f"({(diff.mean()/abs(cqi.mean())*100 if cqi.mean() else float('nan')):+.2f}%) "
                    f"win={int((diff>0).sum())} tie={int((diff==0).sum())} loss={int((diff<0).sum())}"
                )

    out_dir = Path("real_simu5g_data")
    with (out_dir / "real_validation_results.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"\nWrote {out_dir / 'real_validation_results.csv'}")


if __name__ == "__main__":
    main()
