"""Same paper-style dispersion breakdown as `run_dispersion_metrics_breakdown.py`,
extended with LE-GRA MVP as a 6th method. Requires training one model per
dispersion level (LE-GRA's embedding is scenario-generic within a condition,
not per-scenario, so one trained model is reused across every test scenario
for that dispersion level -- same as everywhere else in this project).

Protocol differences from the no-LE-GRA script
------------------------------------------------
- Per dispersion level, a fresh training set (`--train-scenarios`, default 60)
  is generated from a seed range disjoint from the test seeds (offset by
  90000), teacher-labeled via the exact fast DP, and used to train one
  MLPEncoder with the repo's default recipe (feature_mode="history_cost",
  epochs=6, pair_sampling="random_balanced", pairs_per_class=160,
  hidden_dim=48, embedding_dim=8, lr=0.01) -- see
  `run_legra_resource_cost_ablation.train_model_with_labels`.
- Test scenarios are generated once per dispersion (across all seeds) before
  training, since `train_model_with_labels` builds/normalizes `.features` on
  both train and test scenarios together (using train-set statistics) --
  needed before LE-GRA can be evaluated on them.
- Everything else (scenario_mode=aligned, load=medium, users, Kmax,
  switch_beta, kmeans_n_init, metrics, %-of-best summary) is identical to
  `run_dispersion_metrics_breakdown.py`.
"""

from __future__ import annotations

import argparse
import csv
import random
import time
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp
from run_standard_matrix import LOAD_RATIOS
from run_legra_resource_cost_ablation import train_model_with_labels

DISPERSIONS = ["low", "mid_v2", "high"]
METRICS = ["utility", "adr_kbps", "served_ratio", "average_quality", "system_spectral_efficiency"]
TRAIN_SEED_OFFSET = 90000


def progress(message: str) -> None:
    print(message, flush=True)


def build_methods(model: mvp.MLPEncoder) -> dict:
    return {
        "No grouping": lambda s, kmax, beta, n_init: [list(range(len(s.cqi_now)))],
        "CQI k-means": lambda s, kmax, beta, n_init: mvp.cqi_kmeans_grouping(s, kmax, beta, n_init),
        "Resource-cost k-means": lambda s, kmax, beta, n_init: mvp.resource_cost_kmeans_grouping(s, kmax, beta, n_init),
        "Multi-feature k-means": lambda s, kmax, beta, n_init: mvp.multi_feature_kmeans_grouping(
            s, kmax, beta, feature_mode="full", kmeans_n_init=n_init
        ),
        "Offline teacher": lambda s, kmax, beta, n_init: mvp.offline_teacher_groups_fast(s, kmax, beta),
        "LE-GRA MVP": lambda s, kmax, beta, n_init: mvp.learned_grouping(s, model, kmax, beta, n_init),
    }


def train_for_dispersion(dispersion: str, test_scenarios: list, args) -> mvp.MLPEncoder:
    mvp.set_seed(TRAIN_SEED_OFFSET)
    random.seed(TRAIN_SEED_OFFSET)
    train_scenarios = [
        mvp.generate_scenario(args.users, args.rbs, dispersion, "aligned", rb_budget_ratio=args.rb_budget_ratio)
        for _ in range(args.train_scenarios)
    ]
    progress(f"  [{dispersion}] generating {len(train_scenarios)} teacher labels for training...")
    t0 = time.perf_counter()
    teacher_groups = [mvp.offline_teacher_groups_fast(s, args.kmax, args.switch_beta) for s in train_scenarios]
    teacher_labels = [mvp.pairwise_labels(g, args.users) for g in teacher_groups]
    progress(f"  [{dispersion}] teacher labels done in {time.perf_counter() - t0:.1f}s, training model...")

    mvp.set_seed(TRAIN_SEED_OFFSET)
    random.seed(TRAIN_SEED_OFFSET)
    model = train_model_with_labels(
        train_scenarios, test_scenarios, teacher_labels,
        feature_mode="history_cost", epochs=6,
        pair_sampling="random_balanced", pairs_per_class=160,
        progress_label=f"legra-{dispersion}",
    )
    progress(f"  [{dispersion}] model trained.")
    return model


def run_matrix(args) -> list[dict]:
    rows = []
    started = time.perf_counter()
    for dispersion in DISPERSIONS:
        progress(f"=== dispersion={dispersion} ({time.perf_counter() - started:.1f}s elapsed) ===")

        # Generate all test scenarios for this dispersion up front (needed
        # before training, since training normalizes test .features too).
        all_test = []
        for seed in args.seeds:
            mvp.set_seed(seed)
            random.seed(seed)
            scenarios = [
                mvp.generate_scenario(args.users, args.rbs, dispersion, "aligned", rb_budget_ratio=args.rb_budget_ratio)
                for _ in range(args.scenarios_per_condition)
            ]
            for scenario_index, scenario in enumerate(scenarios):
                all_test.append((seed, scenario_index, scenario))

        model = train_for_dispersion(dispersion, [s for _, _, s in all_test], args)
        methods = build_methods(model)

        for job_idx, (seed, scenario_index, scenario) in enumerate(all_test, start=1):
            if job_idx % 200 == 0:
                progress(f"  [{dispersion}] evaluated {job_idx}/{len(all_test)} test scenarios "
                         f"({time.perf_counter() - started:.1f}s elapsed)")
            for method_name, method_fn in methods.items():
                groups = method_fn(scenario, args.kmax, args.switch_beta, args.kmeans_n_init)
                result = mvp.allocate_and_evaluate(groups, scenario, args.switch_beta)
                rows.append({
                    "dispersion": dispersion,
                    "seed": seed,
                    "scenario_index": scenario_index,
                    "method": method_name,
                    "utility": result.utility,
                    "adr_kbps": result.adr_kbps,
                    "served_ratio": result.served_ratio,
                    "average_quality": result.average_quality,
                    "system_spectral_efficiency": result.system_spectral_efficiency,
                })
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict], methods: list[str]) -> list[dict]:
    summary = []
    for dispersion in DISPERSIONS:
        cell = [r for r in rows if r["dispersion"] == dispersion]
        for metric in METRICS:
            means = {}
            for method in methods:
                vals = [r[metric] for r in cell if r["method"] == method]
                means[method] = float(np.mean(vals))
            best = max(means.values())
            for method in methods:
                pct = (means[method] / best * 100.0) if best != 0 else float("nan")
                summary.append({
                    "dispersion": dispersion,
                    "metric": metric,
                    "method": method,
                    "mean": means[method],
                    "pct_of_best": pct,
                })
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--users", type=int, default=150)
    parser.add_argument("--rbs", type=int, default=100)
    parser.add_argument("--kmax", type=int, default=3)
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--kmeans-n-init", type=int, default=10)
    parser.add_argument("--rb-budget-ratio", type=float, default=LOAD_RATIOS["medium"])
    parser.add_argument("--scenarios-per-condition", type=int, default=20)
    parser.add_argument("--seeds", nargs="+", type=int, default=list(range(1, 31)))
    parser.add_argument("--train-scenarios", type=int, default=60)
    parser.add_argument("--out-dir", type=Path, default=Path("dispersion_metrics_breakdown_legra_results"))
    args = parser.parse_args()

    started = time.perf_counter()
    progress(
        f"Protocol: scenario_mode=aligned, dispersions={DISPERSIONS}, load=medium "
        f"(rb_budget_ratio={args.rb_budget_ratio}), users={args.users}, seeds={len(args.seeds)}, "
        f"scenarios_per_condition={args.scenarios_per_condition}, train_scenarios={args.train_scenarios}"
    )
    rows = run_matrix(args)
    methods = list(dict.fromkeys(r["method"] for r in rows))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "per_scenario_results.csv", rows)

    summary = summarize(rows, methods)
    write_csv(args.out_dir / "summary_pct_of_best.csv", summary)

    print("\n=== Summary: mean and % of best method, by dispersion x metric (incl. LE-GRA) ===")
    for dispersion in DISPERSIONS:
        print(f"\n-- dispersion={dispersion} --")
        for metric in METRICS:
            print(f"  {metric}:")
            for r in summary:
                if r["dispersion"] == dispersion and r["metric"] == metric:
                    print(f"    {r['method']:24s} mean={r['mean']:10.4f}  {r['pct_of_best']:6.2f}% of best")

    progress(f"\nDone in {time.perf_counter() - started:.1f}s. Wrote {args.out_dir}/")


if __name__ == "__main__":
    main()
