"""Bounded P2.5 audit of synthetic inputs and offline-teacher labels."""

from __future__ import annotations

import argparse
import csv
import itertools
import random
import time
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp


LOAD_RATIOS = {"light": 0.50, "medium": 0.25, "heavy": 0.10}
FEATURE_NAMES = [
    "cqi_t-4", "cqi_t-3", "cqi_t-2", "cqi_t-1", "cqi_now",
    "cost_q0", "cost_q1", "cost_q2", "cost_q3", "cost_q4", "cost_q5",
]


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def generate_split(args, seed: int, load: str):
    mvp.set_seed(seed)
    dispersions = ["high", "mid", "low"]
    ratio = LOAD_RATIOS[load]

    def make(count: int):
        return [
            mvp.generate_scenario(
                args.users,
                args.rbs,
                random.choice(dispersions),
                "ambiguous",
                rb_budget_ratio=ratio,
            )
            for _ in range(count)
        ]

    return make(args.train_scenarios), make(args.test_scenarios)


def teacher_landscape(scenario: mvp.Scenario, kmax: int, switch_beta: float):
    costs = mvp.user_resource_cost_vector(scenario.rb_rates)
    order = np.argsort(costs.mean(axis=1))
    utilities = []
    candidates = []
    for k in range(1, kmax + 1):
        for boundaries in itertools.combinations(range(1, len(order)), k - 1):
            groups = mvp.groups_from_sorted_boundaries(order, boundaries)
            utility = mvp.allocate_and_evaluate(groups, scenario, switch_beta).utility
            utilities.append(utility)
            candidates.append(groups)
    ranking = np.argsort(utilities)[::-1]
    best_idx = int(ranking[0])
    second = float(utilities[int(ranking[1])]) if len(ranking) > 1 else float(utilities[best_idx])
    best = float(utilities[best_idx])
    groups = candidates[best_idx]
    return groups, best, second, np.asarray(utilities)


def summarize_features(load: str, seed: int, split: str, scenarios, rows: list[dict]):
    values = np.vstack([mvp.build_feature_matrix(s, "history_cost") for s in scenarios])
    for index, name in enumerate(FEATURE_NAMES):
        column = values[:, index]
        rows.append({
            "load_level": load,
            "seed": seed,
            "split": split,
            "feature": name,
            "mean": float(np.mean(column)),
            "std": float(np.std(column)),
            "min": float(np.min(column)),
            "p05": float(np.quantile(column, 0.05)),
            "p50": float(np.quantile(column, 0.50)),
            "p95": float(np.quantile(column, 0.95)),
            "max": float(np.max(column)),
        })
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-scenarios", type=int, default=40)
    parser.add_argument("--test-scenarios", type=int, default=20)
    parser.add_argument("--users", type=int, default=24)
    parser.add_argument("--rbs", type=int, default=100)
    parser.add_argument("--kmax", type=int, default=3)
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--loads", nargs="+", choices=list(LOAD_RATIOS), default=["light", "medium"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[9, 17, 23])
    parser.add_argument("--out-dir", type=Path, default=Path("p2_5_data_audit"))
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    feature_rows, shift_rows, correlation_rows = [], [], []
    teacher_rows, group_rows, learnability_rows = [], [], []
    total = len(args.loads) * len(args.seeds)
    job = 0

    for load in args.loads:
        for seed in args.seeds:
            job += 1
            print(f"[{job}/{total}] load={load}, seed={seed}: generating data", flush=True)
            train, test = generate_split(args, seed, load)
            train_x = summarize_features(load, seed, "train", train, feature_rows)
            test_x = summarize_features(load, seed, "test", test, feature_rows)

            train_mean, train_std = train_x.mean(axis=0), train_x.std(axis=0) + 1e-8
            for idx, name in enumerate(FEATURE_NAMES):
                shift_rows.append({
                    "load_level": load,
                    "seed": seed,
                    "feature": name,
                    "standardized_mean_difference": float((test_x[:, idx].mean() - train_mean[idx]) / train_std[idx]),
                    "test_to_train_std_ratio": float(test_x[:, idx].std() / train_std[idx]),
                })

            corr = np.corrcoef(train_x, rowvar=False)
            for i, j in itertools.combinations(range(len(FEATURE_NAMES)), 2):
                correlation_rows.append({
                    "load_level": load,
                    "seed": seed,
                    "feature_a": FEATURE_NAMES[i],
                    "feature_b": FEATURE_NAMES[j],
                    "pearson_r": float(corr[i, j]),
                })

            all_scenarios = [("train", i, s) for i, s in enumerate(train)] + [
                ("test", i, s) for i, s in enumerate(test)
            ]
            for scenario_number, (split, scenario_index, scenario) in enumerate(all_scenarios, 1):
                if scenario_number == 1 or scenario_number % 10 == 0:
                    print(
                        f"[{job}/{total}] teacher audit {scenario_number}/{len(all_scenarios)} "
                        f"({time.perf_counter() - started:.1f}s)", flush=True
                    )
                groups, best, second, utilities = teacher_landscape(
                    scenario, args.kmax, args.switch_beta
                )
                no_group = mvp.allocate_and_evaluate(
                    [list(range(args.users))], scenario, args.switch_beta
                ).utility
                teacher_rows.append({
                    "load_level": load,
                    "seed": seed,
                    "split": split,
                    "scenario_index": scenario_index,
                    "dispersion": scenario.dispersion,
                    "teacher_k": len(groups),
                    "teacher_group_ids": "|".join(
                        str(value) for value in mvp.group_ids_from_groups(groups, args.users)
                    ),
                    "teacher_utility": best,
                    "no_group_utility": no_group,
                    "teacher_gain_over_no_group": best - no_group,
                    "top1_top2_gap": best - second,
                    "near_optimal_within_0.001": int(np.sum(utilities >= best - 0.001)),
                    "near_optimal_within_0.005": int(np.sum(utilities >= best - 0.005)),
                    "candidate_count": len(utilities),
                })
                for group_index, group in enumerate(groups):
                    group_rows.append({
                        "load_level": load,
                        "seed": seed,
                        "split": split,
                        "scenario_index": scenario_index,
                        "teacher_k": len(groups),
                        "group_index": group_index,
                        "group_size": len(group),
                    })

                raw_x = mvp.build_feature_matrix(scenario, "history_cost")
                x = (raw_x - train_mean) / train_std
                labels = mvp.group_ids_from_groups(groups, args.users)
                distances = np.linalg.norm(x[:, None, :] - x[None, :, :], axis=2)
                np.fill_diagonal(distances, np.inf)
                nearest = np.argmin(distances, axis=1)
                same_cqi_pairs, same_cqi_same_group, same_cqi_cost_dist = 0, 0, []
                costs = raw_x[:, 5:]
                for i, j in itertools.combinations(range(args.users), 2):
                    if scenario.cqi_now[i] == scenario.cqi_now[j]:
                        same_cqi_pairs += 1
                        same_cqi_same_group += int(labels[i] == labels[j])
                        same_cqi_cost_dist.append(float(np.linalg.norm(costs[i] - costs[j])))
                learnability_rows.append({
                    "load_level": load,
                    "seed": seed,
                    "split": split,
                    "scenario_index": scenario_index,
                    "nearest_neighbor_same_teacher_group": float(np.mean(labels == labels[nearest])),
                    "nearest_neighbor_mean_distance": float(np.mean(distances[np.arange(args.users), nearest])),
                    "same_cqi_pair_count": same_cqi_pairs,
                    "same_cqi_same_group_ratio": (
                        same_cqi_same_group / same_cqi_pairs if same_cqi_pairs else float("nan")
                    ),
                    "same_cqi_mean_cost_distance": (
                        float(np.mean(same_cqi_cost_dist)) if same_cqi_cost_dist else float("nan")
                    ),
                })

    outputs = {
        "feature_summary.csv": feature_rows,
        "train_test_shift.csv": shift_rows,
        "feature_correlations.csv": correlation_rows,
        "teacher_landscape.csv": teacher_rows,
        "teacher_group_sizes.csv": group_rows,
        "learnability.csv": learnability_rows,
    }
    for filename, rows in outputs.items():
        write_csv(args.out_dir / filename, rows)
        print(f"Saved {args.out_dir / filename}", flush=True)
    print(f"Audit complete in {time.perf_counter() - started:.1f}s", flush=True)


if __name__ == "__main__":
    main()
