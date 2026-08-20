"""Does LE-GRA actually benefit from the resource-cost feature in its input,
given that raw resource-cost k-means (clustering directly on that same
vector) does NOT reliably beat CQI k-means (see
RESOURCE_COST_KMEANS_FINDINGS.md)?

Why this script exists
-----------------------
LE-GRA's default recipe uses `feature_mode="history_cost"`: 5-step CQI
history + the same per-tier resource-cost vector that
`resource_cost_kmeans_grouping` clusters on directly (and which was shown to
have a real, diagnosed failure mode -- outlier/sentinel-driven mis-shaped
k-means splits, worse under heavy load). That raw-feature-clustering failure
does not automatically mean the *information* is useless: LE-GRA feeds it
into a neural network first, which could in principle learn to use it more
robustly than naive k-means does. This has never been tested directly --
Phase 3's ablation (`legra_ablation_phase3.md`) compared feature_mode
"history_cost" vs "full" (richer features), but never against
"history_only" (CQI history alone, no cost vector at all).

This script runs that missing comparison directly: for the same generated
scenarios, same seeds, same training budget, train two LE-GRA variants that
differ ONLY in feature_mode ("history_only" vs "history_cost") and compare
their held-out utility, plus CQI k-means for context. The model is re-seeded
identically before each variant's training so weight init and pair-sampling
randomness are matched -- any difference is attributable to the feature
representation, not to unrelated RNG draws.

Protocol
--------
- scenario_modes: all 5 built-in modes (aligned, ambiguous, anti_cqi_hard,
  corridor_general, mixed) -- resource-cost's value is expected to differ
  most in anti_cqi_hard/corridor_general (designed CQI blind spots), so both
  "normal" and "hard" modes are included rather than cherry-picking.
- load_levels: light, medium, heavy (matches Phase 1).
- seeds: 9, 17, 23 (a subset of the standard 6, sized for a background run;
  can be extended to the full 6 if the result is close).
- users=24, rbs=100, kmax=3, switch_beta=0.5, epochs=6, pair_sampling=
  random_balanced, pairs_per_class=160, kmeans_n_init=10 -- all repo
  defaults, matching every other clean validation script in this project.
- train_scenarios=60, test_scenarios=30 per (mode, load, seed) job.
"""

from __future__ import annotations

import argparse
import csv
import random
import time
from pathlib import Path

import numpy as np

import le_gra_mvp as mvp
import run_clean_resource_cost_validation as v
from run_standard_matrix import LOAD_RATIOS

FEATURE_MODES = ["history_only", "history_cost"]
DEFAULT_SEEDS = [9, 17, 23]
DEFAULT_MODES = ["aligned", "ambiguous", "anti_cqi_hard", "corridor_general", "mixed"]


def progress(message: str) -> None:
    print(message, flush=True)


def train_model_with_labels(
    train: list[mvp.Scenario],
    test: list[mvp.Scenario],
    teacher_labels: list[np.ndarray],
    feature_mode: str,
    epochs: int,
    pair_sampling: str,
    pairs_per_class: int,
    progress_label: str = "",
) -> mvp.MLPEncoder:
    """Same training loop as `run_standard_matrix.train_model` with
    `validation_fraction=0.0`, but takes already-computed teacher pairwise
    labels instead of regenerating them -- the labels only depend on each
    scenario's CQI/RB data, not on `feature_mode`, so they are computed once
    per (mode, load, seed) job and reused across every feature_mode variant
    tested for that job, instead of being recomputed per variant."""

    prefix = f"[{progress_label}] " if progress_label else ""
    mvp.apply_feature_mode(train, test, feature_mode)
    mvp.normalize_features(train, test)

    model = mvp.MLPEncoder(input_dim=train[0].features.shape[1], hidden_dim=48, embedding_dim=8, lr=0.01)
    best_state = model.get_state()
    best_training_loss = float("inf")
    best_epoch = 0
    for epoch in range(1, epochs + 1):
        order = list(range(len(train)))
        random.shuffle(order)
        losses = [
            model.train_step(
                train[idx].features,
                teacher_labels[idx],
                pair_sampling=pair_sampling,
                max_pairs_per_class=pairs_per_class,
            )
            for idx in order
        ]
        training_loss = float(np.mean(losses))
        if training_loss < best_training_loss:
            best_training_loss = training_loss
            best_epoch = epoch
            best_state = model.get_state()
        progress(f"{prefix}Epoch {epoch}/{epochs}, train_loss={training_loss:.4f}, best_epoch={best_epoch}")
    model.set_state(best_state)
    model.selected_epoch = best_epoch
    model.selection_validation_loss = best_training_loss
    model.pair_sampling = pair_sampling
    return model


def run_matrix(args) -> list[dict]:
    rows = []
    total_jobs = len(args.scenario_modes) * len(args.load_levels) * len(args.seeds)
    job = 0
    started = time.perf_counter()
    for scenario_mode in args.scenario_modes:
        for load_level in args.load_levels:
            for seed in args.seeds:
                job += 1
                label = f"job {job}/{total_jobs} mode={scenario_mode} load={load_level} seed={seed}"
                progress(f"{label} ({time.perf_counter() - started:.1f}s elapsed)")

                mvp.set_seed(seed)
                random.seed(seed)
                train, test = v.generate_splits(args, scenario_mode, seed, load_level)

                cqi_utils = [
                    mvp.allocate_and_evaluate(
                        mvp.cqi_kmeans_grouping(s, args.kmax, args.switch_beta, args.kmeans_n_init),
                        s, args.switch_beta,
                    ).utility
                    for s in test
                ]

                # Teacher labels depend only on each scenario's CQI/RB data,
                # not on feature_mode -- compute once (fast exact DP) and
                # reuse across every feature_mode variant tested below.
                teacher_groups = [
                    mvp.offline_teacher_groups_fast(s, args.kmax, args.switch_beta) for s in train
                ]
                teacher_labels = [mvp.pairwise_labels(g, len(train[0].cqi_now)) for g in teacher_groups]

                for feature_mode in FEATURE_MODES:
                    mvp.set_seed(seed)
                    random.seed(seed)
                    model = train_model_with_labels(
                        train, test,
                        teacher_labels=teacher_labels,
                        feature_mode=feature_mode,
                        epochs=args.epochs,
                        pair_sampling=args.pair_sampling,
                        pairs_per_class=args.pairs_per_class,
                        progress_label=f"{label} {feature_mode}",
                    )
                    for test_index, scenario in enumerate(test):
                        groups = mvp.learned_grouping(scenario, model, args.kmax, args.switch_beta, args.kmeans_n_init)
                        result = mvp.allocate_and_evaluate(groups, scenario, args.switch_beta)
                        rows.append(
                            {
                                "scenario_mode": scenario_mode,
                                "load_level": load_level,
                                "seed": seed,
                                "test_index": test_index,
                                "feature_mode": feature_mode,
                                "legra_utility": result.utility,
                                "cqi_utility": cqi_utils[test_index],
                            }
                        )
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


def bootstrap_ci(diffs: np.ndarray, n_boot: int, rng: np.random.Generator) -> tuple[float, float, float, float]:
    if len(diffs) == 0:
        return float("nan"), float("nan"), float("nan"), float("nan")
    mean = float(diffs.mean())
    n = len(diffs)
    boot_means = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        boot_means[i] = diffs[rng.integers(0, n, size=n)].mean()
    lo, hi = np.percentile(boot_means, [2.5, 97.5])
    p_pos = float(np.mean(boot_means <= 0.0))
    p_neg = float(np.mean(boot_means >= 0.0))
    return mean, float(lo), float(hi), float(min(1.0, 2.0 * min(p_pos, p_neg)))


def holm_correction(p_values: list[float]) -> list[float]:
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    adjusted = [0.0] * len(p_values)
    running_max = 0.0
    for rank, idx in enumerate(order):
        adj = (len(p_values) - rank) * p_values[idx]
        running_max = max(running_max, adj)
        adjusted[idx] = min(1.0, running_max)
    return adjusted


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--train-scenarios", type=int, default=60)
    parser.add_argument("--test-scenarios", type=int, default=30)
    parser.add_argument("--users", type=int, default=24)
    parser.add_argument("--rbs", type=int, default=100)
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--kmax", type=int, default=3)
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument("--kmeans-n-init", type=int, default=10)
    parser.add_argument("--pair-sampling", default="random_balanced")
    parser.add_argument("--pairs-per-class", type=int, default=160)
    parser.add_argument("--scenario-modes", nargs="+", default=DEFAULT_MODES)
    parser.add_argument("--load-levels", nargs="+", choices=list(LOAD_RATIOS), default=["light", "medium", "heavy"])
    parser.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--n-boot", type=int, default=10000)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    parser.add_argument("--out-dir", type=Path, default=Path("legra_resource_cost_ablation_results"))
    args = parser.parse_args()

    started = time.perf_counter()
    progress(
        f"Protocol: modes={args.scenario_modes}, loads={args.load_levels}, seeds={args.seeds}, "
        f"feature_modes={FEATURE_MODES}, kmax={args.kmax}, epochs={args.epochs}"
    )
    rows = run_matrix(args)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "per_scenario_results.csv", rows)

    rng = np.random.default_rng(args.bootstrap_seed)

    by_unit: dict[tuple, dict] = {}
    for r in rows:
        unit = (r["scenario_mode"], r["load_level"], r["seed"], r["test_index"])
        by_unit.setdefault(unit, {})[r["feature_mode"]] = r["legra_utility"]
        by_unit[unit]["cqi"] = r["cqi_utility"]

    print("\n=== PRIMARY: LE-GRA(history_cost) minus LE-GRA(history_only), by scenario_mode (Holm-corrected) ===")
    modes = sorted({r["scenario_mode"] for r in rows})
    p_values = []
    records = []
    for mode in modes:
        diffs = np.array(
            [
                v["history_cost"] - v["history_only"]
                for (m, l, s, t), v in by_unit.items()
                if m == mode and "history_cost" in v and "history_only" in v
            ],
            dtype=float,
        )
        mean, lo, hi, p = bootstrap_ci(diffs, args.n_boot, rng)
        win_rate = float(np.mean(diffs > 0)) if len(diffs) else float("nan")
        records.append((mode, mean, lo, hi, p, win_rate, len(diffs)))
        p_values.append(p)
    adjusted = holm_correction(p_values)
    for (mode, mean, lo, hi, p, win_rate, n), adj in zip(records, adjusted):
        sig = "significant" if adj < 0.05 else "not significant"
        print(
            f"{mode:16s}: mean(cost-only)={mean:+.5f} 95% CI=[{lo:+.5f},{hi:+.5f}] "
            f"holm_p={adj:.4f} ({sig}) win_rate={win_rate:.3f} n={n}"
        )

    print("\n=== Pooled: LE-GRA(history_cost) minus LE-GRA(history_only) ===")
    all_diffs = np.array(
        [
            v["history_cost"] - v["history_only"]
            for v in by_unit.values()
            if "history_cost" in v and "history_only" in v
        ],
        dtype=float,
    )
    mean, lo, hi, p = bootstrap_ci(all_diffs, args.n_boot, rng)
    print(f"mean={mean:+.5f} 95% CI=[{lo:+.5f},{hi:+.5f}] p={p:.5f} win_rate={float(np.mean(all_diffs>0)):.3f} n={len(all_diffs)}")

    print("\n=== Context: both variants vs CQI k-means, pooled ===")
    for feature_mode in FEATURE_MODES:
        diffs = np.array(
            [v[feature_mode] - v["cqi"] for v in by_unit.values() if feature_mode in v],
            dtype=float,
        )
        mean, lo, hi, p = bootstrap_ci(diffs, args.n_boot, rng)
        print(
            f"LE-GRA({feature_mode}) vs CQI: mean={mean:+.5f} 95% CI=[{lo:+.5f},{hi:+.5f}] "
            f"p={p:.5f} win_rate={float(np.mean(diffs>0)):.3f} n={len(diffs)}"
        )

    progress(f"Done in {time.perf_counter() - started:.1f}s. Wrote {args.out_dir}/")


if __name__ == "__main__":
    main()
