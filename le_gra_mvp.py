"""Minimal LE-GRA prototype.

LE-GRA: Learning-based Embedding Grouping and Resource Allocation.

This first version generates synthetic vehicular MBS scenarios, creates
pseudo-labels with an offline utility-driven teacher, trains an MLP embedding
model with pairwise contrastive loss, and evaluates learned grouping against
simple baselines.

The implementation uses only NumPy so it is easy to run and modify.
"""

from __future__ import annotations

import argparse
import itertools
import math
import random
from dataclasses import dataclass
from typing import Callable

import numpy as np


VIDEO_BITRATES_KBPS = np.array([200, 550, 1500, 3000, 5800, 7500], dtype=float)
RB_BANDWIDTH_KHZ = 180.0

# 3GPP-like CQI spectral efficiencies in bits/s/Hz.
CQI_TO_EFF = np.array(
    [
        0.0,
        0.1523,
        0.2344,
        0.3770,
        0.6016,
        0.8770,
        1.1758,
        1.4766,
        1.9141,
        2.4063,
        2.7305,
        3.3223,
        3.9023,
        4.5234,
        5.1152,
        5.5547,
    ],
    dtype=float,
)


@dataclass
class Scenario:
    """One synthetic MBS allocation snapshot.

    Think of this as one allocation cycle: a set of VUs, their channel/RB
    conditions, the current RB budget, and their previous video quality.
    """

    features: np.ndarray
    cqi_history: np.ndarray
    cqi_now: np.ndarray
    rb_rates: np.ndarray
    rb_available: int
    previous_quality: np.ndarray
    distance: np.ndarray
    speed: np.ndarray
    direction_to_gnb: np.ndarray
    dispersion: str


@dataclass
class EvalResult:
    """Aggregated metrics after a grouping is allocated by the DP backend."""

    utility: float
    adr_kbps: float
    used_spectral_efficiency: float
    system_spectral_efficiency: float
    served_ratio: float
    unserved_ratio: float
    average_quality: float
    rb_utilization: float
    avg_switching: float
    fairness: float
    groups: int


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def cqi_to_rate_kbps(cqi: np.ndarray) -> np.ndarray:
    """Map CQI values to per-RB achievable rates.

    The output is simplified but keeps the important ordering: higher CQI gives
    higher spectral efficiency, hence higher rate on a 180 kHz RB.
    """

    cqi_int = np.clip(np.rint(cqi).astype(int), 1, 15)
    return CQI_TO_EFF[cqi_int] * RB_BANDWIDTH_KHZ


def rb_needed(sorted_rates_kbps: np.ndarray, target_kbps: float) -> int | None:
    """Return the minimum number of RBs needed to support a bitrate.

    `sorted_rates_kbps` should be sorted from high to low. If even all RBs
    cannot reach the requested bitrate, the video level is infeasible.
    """

    total = 0.0
    for idx, rate in enumerate(sorted_rates_kbps, 1):
        total += rate
        if total >= target_kbps:
            return idx
    return None


def user_resource_cost_vector(rb_rates: np.ndarray) -> np.ndarray:
    """Compute each VU's RB cost for every video quality level.

    This is the main feature that goes beyond raw CQI. A user can have the same
    wideband CQI as another user but require different RB counts because its
    RB-level rate profile is different.
    """

    costs = np.zeros((rb_rates.shape[0], len(VIDEO_BITRATES_KBPS)), dtype=float)
    for user_idx in range(rb_rates.shape[0]):
        sorted_rates = np.sort(rb_rates[user_idx])[::-1]
        for q_idx, bitrate in enumerate(VIDEO_BITRATES_KBPS):
            need = rb_needed(sorted_rates, bitrate)
            costs[user_idx, q_idx] = need if need is not None else rb_rates.shape[1] + 1
    return costs


def generate_scenario(
    n_users: int,
    n_rbs: int,
    dispersion: str,
    scenario_mode: str = "mixed",
    dynamic_rb: bool = True,
    rb_budget_ratio: float | None = None,
) -> Scenario:
    """Generate one synthetic vehicular MBS scenario.

    `dispersion` controls whether VUs have high/mid/low CQI spread.
    `scenario_mode` controls whether RB-level behavior is aligned with CQI or
    intentionally ambiguous so CQI-only grouping has blind spots.
    """

    if dispersion == "high":
        distance = np.random.uniform(50, 600, size=n_users)
        base_cqi = 15.5 - distance / 45.0 + np.random.normal(0, 1.6, size=n_users)
    elif dispersion == "mid":
        distance = np.random.uniform(50, 320, size=n_users)
        base_cqi = 15.0 - distance / 65.0 + np.random.normal(0, 1.1, size=n_users)
    elif dispersion == "low":
        distance = np.random.uniform(20, 120, size=n_users)
        base_cqi = 14.5 - distance / 160.0 + np.random.normal(0, 0.7, size=n_users)
    else:
        raise ValueError(f"Unknown dispersion: {dispersion}")

    speed = np.random.uniform(35, 45, size=n_users)
    direction_to_gnb = np.random.uniform(-1.0, 1.0, size=n_users)

    cqi_history = []
    for lag in range(4, -1, -1):
        # Positive direction_to_gNB means the user is moving toward the gNB,
        # so CQI tends to improve over time.
        trend = direction_to_gnb * (2 - lag) * 0.25
        noise = np.random.normal(0, 0.55, size=n_users)
        cqi_history.append(np.clip(base_cqi + trend + noise, 1, 15))
    cqi_history = np.stack(cqi_history, axis=1)
    cqi_now = np.clip(np.rint(cqi_history[:, -1]).astype(int), 1, 15)

    mode = scenario_mode
    if mode == "mixed":
        mode = "ambiguous" if np.random.rand() < 0.5 else "aligned"
    if mode not in {"aligned", "ambiguous"}:
        raise ValueError(f"Unknown scenario_mode: {scenario_mode}")

    if mode == "aligned":
        # Aligned mode: RB rates are mostly a noisy version of wideband CQI.
        # This is the friendly setting where CQI k-means tends to be strong.
        rb_cqi = np.clip(
            cqi_now[:, None] + np.random.normal(0, 1.15, size=(n_users, n_rbs)),
            1,
            15,
        )
    else:
        # Ambiguous mode: users can share the same wideband CQI while having
        # different frequency-selective RB profiles.
        rb_cqi = generate_cqi_ambiguous_rb_cqi(cqi_now, direction_to_gnb, n_rbs)
    rb_rates = cqi_to_rate_kbps(rb_cqi)

    rb_stats = np.column_stack(
        [
            rb_rates.mean(axis=1),
            rb_rates.min(axis=1),
            rb_rates.max(axis=1),
            rb_rates.std(axis=1),
        ]
    )
    cost_vec = user_resource_cost_vector(rb_rates)

    previous_quality = np.clip(cqi_now // 3, 0, len(VIDEO_BITRATES_KBPS) - 1)
    if mode == "ambiguous":
        # Same current CQI can still have different QoE history. This makes
        # switching penalty relevant in ways CQI-only grouping cannot see.
        previous_quality = np.clip(
            previous_quality + np.random.choice([-2, -1, 0, 1, 2], size=n_users, p=[0.12, 0.18, 0.40, 0.18, 0.12]),
            0,
            len(VIDEO_BITRATES_KBPS) - 1,
        )

    if rb_budget_ratio is not None:
        if not 0.0 < rb_budget_ratio <= 1.0:
            raise ValueError("rb_budget_ratio must be in the interval (0, 1]")
        rb_available = max(1, int(round(rb_budget_ratio * n_rbs)))
    elif dynamic_rb:
        rb_available = int(np.random.uniform(0.45, 0.85) * n_rbs)
    else:
        rb_available = int(0.65 * n_rbs)

    scenario = Scenario(
        features=np.empty((n_users, 0), dtype=np.float32),
        cqi_history=cqi_history,
        cqi_now=cqi_now,
        rb_rates=rb_rates,
        rb_available=rb_available,
        previous_quality=previous_quality,
        distance=distance,
        speed=speed,
        direction_to_gnb=direction_to_gnb,
        dispersion=dispersion,
    )
    scenario.features = build_feature_matrix(scenario, feature_mode="full")
    return scenario


def build_feature_matrix(scenario: Scenario, feature_mode: str) -> np.ndarray:
    """Build per-user feature vectors for the requested ablation setting."""

    rb_stats = np.column_stack(
        [
            scenario.rb_rates.mean(axis=1),
            scenario.rb_rates.min(axis=1),
            scenario.rb_rates.max(axis=1),
            scenario.rb_rates.std(axis=1),
        ]
    )
    cost_vec = user_resource_cost_vector(scenario.rb_rates) / scenario.rb_rates.shape[1]
    mobility = np.column_stack(
        [
            scenario.distance / 600.0,
            scenario.speed / 45.0,
            scenario.direction_to_gnb,
        ]
    )
    # Scenario context is repeated per user so the point-wise encoder can
    # condition its embedding on resource pressure and switching state.
    quality_context = (
        scenario.previous_quality / (len(VIDEO_BITRATES_KBPS) - 1)
    )[:, None]
    load_context = np.full(
        (len(scenario.cqi_now), 1),
        scenario.rb_available / scenario.rb_rates.shape[1],
        dtype=float,
    )
    context = np.column_stack([quality_context, load_context])

    if feature_mode == "history_only":
        features = [scenario.cqi_history]
    elif feature_mode == "history_cost":
        features = [scenario.cqi_history, cost_vec]
    elif feature_mode == "history_cost_quality":
        features = [scenario.cqi_history, cost_vec, quality_context]
    elif feature_mode == "history_cost_load":
        features = [scenario.cqi_history, cost_vec, load_context]
    elif feature_mode == "history_cost_context":
        features = [scenario.cqi_history, cost_vec, context]
    elif feature_mode == "full":
        features = [scenario.cqi_history, rb_stats, mobility, cost_vec]
    elif feature_mode == "full_context":
        features = [scenario.cqi_history, rb_stats, mobility, cost_vec, context]
    else:
        raise ValueError(f"Unknown feature_mode: {feature_mode}")
    return np.column_stack(features).astype(np.float32)


def apply_feature_mode(train: list[Scenario], test: list[Scenario], feature_mode: str) -> None:
    """Rebuild scenario features for one ablation setting before normalization."""

    for scenario in train + test:
        scenario.features = build_feature_matrix(scenario, feature_mode)


def generate_cqi_ambiguous_rb_cqi(cqi_now: np.ndarray, direction_to_gnb: np.ndarray, n_rbs: int) -> np.ndarray:
    """Generate RB CQI where wideband CQI is not enough to describe users.

    Users with the same wideband CQI can have different frequency-selective
    profiles: some are good in low-index RBs, some in high-index RBs, and some
    have bursty narrowband peaks. Mobility direction also slightly tilts the
    profile to make temporal context useful.
    """
    n_users = len(cqi_now)
    rb_axis = np.linspace(-1.0, 1.0, n_rbs)
    rb_cqi = np.zeros((n_users, n_rbs), dtype=float)
    for i in range(n_users):
        profile_type = np.random.choice(["left", "right", "flat", "bursty"], p=[0.30, 0.30, 0.20, 0.20])
        if profile_type == "left":
            shape = -1.6 * rb_axis
        elif profile_type == "right":
            shape = 1.6 * rb_axis
        elif profile_type == "bursty":
            center = np.random.uniform(-0.75, 0.75)
            width = np.random.uniform(0.12, 0.28)
            shape = 2.2 * np.exp(-((rb_axis - center) ** 2) / (2 * width**2)) - 0.7
        else:
            shape = np.zeros(n_rbs)
        mobility_tilt = 0.7 * direction_to_gnb[i] * rb_axis
        noise = np.random.normal(0, 0.85, size=n_rbs)
        raw = cqi_now[i] + shape + mobility_tilt + noise
        # Preserve the same approximate wideband CQI while changing RB profile.
        raw += cqi_now[i] - np.mean(raw)
        rb_cqi[i] = np.clip(raw, 1, 15)
    return rb_cqi


def normalize_features(train: list[Scenario], test: list[Scenario]) -> tuple[np.ndarray, np.ndarray]:
    """Normalize feature columns using train-set statistics.

    This keeps the MLP training stable. Test data uses the same mean/std so the
    evaluation does not leak test statistics into training.
    """

    all_features = np.vstack([s.features for s in train])
    mean = all_features.mean(axis=0)
    std = all_features.std(axis=0) + 1e-6
    for scenario in train + test:
        scenario.features = ((scenario.features - mean) / std).astype(np.float32)
    return mean, std


def jain_fairness(values: np.ndarray) -> float:
    """Jain's fairness index over received user bitrates."""

    denom = len(values) * np.sum(values**2)
    if denom <= 0:
        return 0.0
    return float(np.sum(values) ** 2 / denom)


def allocate_and_evaluate(
    groups: list[list[int]],
    scenario: Scenario,
    switch_beta: float,
) -> EvalResult:
    """Allocate video levels for a given grouping and return metrics.

    Important: this function does NOT decide the groups. It assumes groups are
    already given, then solves the per-group video-quality assignment exactly
    under the RB budget using dynamic programming.
    """

    group_options = []
    for group in groups:
        if not group:
            continue
        group_rates = scenario.rb_rates[group].min(axis=0)
        # Multicast worst-user constraint: for each RB, the group can only use
        # the rate supported by the weakest VU in that group on that RB.
        sorted_rates = np.sort(group_rates)[::-1]
        options = [(-1, 0)]
        for q_idx, bitrate in enumerate(VIDEO_BITRATES_KBPS):
            need = rb_needed(sorted_rates, bitrate)
            if need is not None and need <= scenario.rb_available:
                options.append((q_idx, need))
        group_options.append((group, options))

    if not group_options:
        return EvalResult(
            utility=-2.0,
            adr_kbps=0.0,
            used_spectral_efficiency=0.0,
            system_spectral_efficiency=0.0,
            served_ratio=0.0,
            unserved_ratio=1.0,
            average_quality=0.0,
            rb_utilization=0.0,
            avg_switching=0.0,
            fairness=0.0,
            groups=len(groups),
        )

    # Exact quality assignment via dynamic programming.
    #
    # DP state:
    #   used_rb -> (best_total_value_so_far, quality_choices_so_far)
    #
    # For each group, choose exactly one option:
    #   -1 means unserved, or one of the video quality levels.
    #
    # This is a multiple-choice knapsack problem: every group is an item class,
    # every video level is one choice, and RB_available is the capacity.
    n_users = len(scenario.cqi_now)
    dp: dict[int, tuple[float, list[int]]] = {0: (0.0, [])}
    for group, options in group_options:
        next_dp: dict[int, tuple[float, list[int]]] = {}
        for used_before, (value_before, choices_before) in dp.items():
            for quality, need in options:
                used_after = used_before + need
                if used_after > scenario.rb_available:
                    continue
                value_after = value_before + group_quality_value(group, quality, scenario, switch_beta)
                old = next_dp.get(used_after)
                if old is None or value_after > old[0]:
                    next_dp[used_after] = (value_after, choices_before + [quality])
        dp = next_dp

    best_used_rb, (best_total_value, best_choices) = max(dp.items(), key=lambda item: item[1][0])
    best_utility = float(best_total_value / n_users)
    best_user_quality = np.full(n_users, -1, dtype=int)
    for (group, _), quality in zip(group_options, best_choices):
        if quality >= 0:
            best_user_quality[group] = quality

    user_bitrate = np.zeros(len(scenario.cqi_now), dtype=float)
    served = best_user_quality >= 0
    user_bitrate[served] = VIDEO_BITRATES_KBPS[best_user_quality[served]]
    used_spectral_efficiency = (
        float(user_bitrate.sum() / (best_used_rb * RB_BANDWIDTH_KHZ))
        if best_used_rb > 0
        else 0.0
    )
    system_spectral_efficiency = float(
        user_bitrate.sum() / (scenario.rb_available * RB_BANDWIDTH_KHZ)
    )
    average_quality = float(best_user_quality[served].mean()) if np.any(served) else 0.0

    switching = np.zeros(len(scenario.cqi_now), dtype=float)
    switching[served] = np.abs(best_user_quality[served] - scenario.previous_quality[served]) / (
        len(VIDEO_BITRATES_KBPS) - 1
    )
    return EvalResult(
        utility=best_utility,
        adr_kbps=float(user_bitrate.mean()),
        used_spectral_efficiency=used_spectral_efficiency,
        system_spectral_efficiency=system_spectral_efficiency,
        served_ratio=float(served.mean()),
        unserved_ratio=float(1.0 - served.mean()),
        average_quality=average_quality,
        rb_utilization=float(best_used_rb / max(1, scenario.rb_available)),
        avg_switching=float(switching.mean()),
        fairness=jain_fairness(user_bitrate),
        groups=len(groups),
    )


def compute_qoe_utility(user_quality: np.ndarray, scenario: Scenario, switch_beta: float) -> float:
    """Compute the final QoE-style utility for one user-quality assignment."""

    served = user_quality >= 0
    bitrate_score = np.zeros(len(user_quality), dtype=float)
    bitrate_score[served] = [normalized_bitrate_score(q) for q in user_quality[served]]
    switching = np.zeros(len(user_quality), dtype=float)
    switching[served] = np.abs(user_quality[served] - scenario.previous_quality[served]) / (
        len(VIDEO_BITRATES_KBPS) - 1
    )
    unserved_ratio = 1.0 - float(served.mean())
    return float(np.mean(bitrate_score - switch_beta * switching) - 2.0 * unserved_ratio)


def group_quality_value(
    group: list[int],
    quality: int,
    scenario: Scenario,
    switch_beta: float,
) -> float:
    """Contribution of one group if it is assigned one quality level."""

    if quality < 0:
        return -2.0 * len(group)
    bitrate_score = normalized_bitrate_score(quality)
    switching = np.abs(quality - scenario.previous_quality[group]) / (len(VIDEO_BITRATES_KBPS) - 1)
    return float(np.sum(bitrate_score - switch_beta * switching))


def normalized_bitrate_score(quality_idx: int) -> float:
    """Map a video quality level to a 0..1 log-bitrate utility."""

    lo = math.log(VIDEO_BITRATES_KBPS[0])
    hi = math.log(VIDEO_BITRATES_KBPS[-1])
    return (math.log(VIDEO_BITRATES_KBPS[quality_idx]) - lo) / (hi - lo)


def groups_from_sorted_boundaries(order: np.ndarray, boundaries: tuple[int, ...]) -> list[list[int]]:
    """Convert boundary cuts over a sorted VU order into contiguous groups."""

    groups = []
    start = 0
    for boundary in boundaries:
        groups.append(order[start:boundary].tolist())
        start = boundary
    groups.append(order[start:].tolist())
    return [g for g in groups if g]


def offline_teacher_groups(
    scenario: Scenario,
    max_groups: int,
    switch_beta: float,
) -> list[list[int]]:
    """Generate pseudo-optimal teacher groups for one scenario.

    The teacher is not global exhaustive over all possible partitions. It uses
    the MBS contiguity assumption: after sorting users by service difficulty
    (resource cost), good multicast groups are likely contiguous segments.

    For every boundary-cut candidate, DP allocation gives an exact utility
    evaluation. The best candidate becomes the pseudo-label for learning.
    """

    cost_vec = user_resource_cost_vector(scenario.rb_rates)
    cost_score = cost_vec.mean(axis=1)
    order = np.argsort(cost_score)
    n_users = len(order)

    best_groups = [order.tolist()]
    best_utility = -1e9
    cut_positions = list(range(1, n_users))
    for k in range(1, max_groups + 1):
        for boundaries in itertools.combinations(cut_positions, k - 1):
            groups = groups_from_sorted_boundaries(order, boundaries)
            result = allocate_and_evaluate(groups, scenario, switch_beta)
            if result.utility > best_utility:
                best_utility = result.utility
                best_groups = groups
    return best_groups


def pairwise_labels(groups: list[list[int]], n_users: int) -> np.ndarray:
    """Turn teacher groups into same-group labels for contrastive learning."""

    group_id = np.full(n_users, -1, dtype=int)
    for idx, group in enumerate(groups):
        group_id[group] = idx
    return (group_id[:, None] == group_id[None, :]).astype(np.float32)


def teacher_group_difficulty_order(
    scenario: Scenario,
    groups: list[list[int]],
) -> list[int]:
    """Rank teacher groups from hardest to easiest using mean resource cost."""

    if not groups:
        return []
    cost_vec = user_resource_cost_vector(scenario.rb_rates)
    group_costs = [
        float(cost_vec[group].mean()) if group else -1.0
        for group in groups
    ]
    return sorted(
        range(len(groups)),
        key=lambda group_idx: group_costs[group_idx],
        reverse=True,
    )


def pairwise_supervision_weights(
    scenario: Scenario,
    groups: list[list[int]],
    mode: str = "uniform",
    hard_positive_scale: float = 2.5,
    hard_negative_scale: float = 1.5,
) -> np.ndarray:
    """Build pair weights that emphasize the hardest teacher group.

    `uniform` reproduces the previous learner behavior. `teacher_hard_group`
    upweights:

    - positive pairs inside the teacher's hardest group;
    - negative pairs between the hardest group and every other group.

    `teacher_candidate_boundary` further concentrates supervision on the
    hardest group's top resource-cost members, especially the secondary weak
    candidate that the learner tends to miss in dual-weak regimes.
    """

    n_users = len(scenario.cqi_now)
    weights = np.ones((n_users, n_users), dtype=np.float32)
    if mode == "uniform":
        return weights
    if mode not in {"teacher_hard_group", "teacher_candidate_boundary"}:
        raise ValueError(f"Unsupported supervision weight mode: {mode}")
    if not groups:
        return weights

    group_ids = group_ids_from_groups(groups, n_users)
    ordered_groups = teacher_group_difficulty_order(scenario, groups)
    if not ordered_groups:
        return weights
    hard_group_id = ordered_groups[0]
    hard_members = np.where(group_ids == hard_group_id)[0]
    if len(hard_members) >= 2:
        for i in hard_members:
            for j in hard_members:
                if i != j:
                    weights[i, j] = hard_positive_scale
    for i in hard_members:
        for j in range(n_users):
            if i == j:
                continue
            if group_ids[j] != hard_group_id:
                weights[i, j] = hard_negative_scale
                weights[j, i] = hard_negative_scale
    if mode == "teacher_candidate_boundary":
        candidate_target, candidate_target_weights = candidate_conditioned_membership_targets(
            scenario,
            groups,
            top_k=2,
            secondary_scale=hard_negative_scale,
        )
        candidate_members = np.where(candidate_target > 0.5)[0].tolist()
        if len(candidate_members) >= 2:
            primary_idx = candidate_members[0]
            secondary_idx = candidate_members[1]
            candidate_positive_scale = max(hard_positive_scale, hard_negative_scale * 2.0)
            candidate_negative_scale = max(hard_negative_scale * 2.0, hard_positive_scale)
            weights[primary_idx, secondary_idx] = candidate_positive_scale
            weights[secondary_idx, primary_idx] = candidate_positive_scale
            for other_idx in range(n_users):
                if other_idx in candidate_members:
                    continue
                if group_ids[other_idx] != hard_group_id:
                    weights[secondary_idx, other_idx] = candidate_negative_scale
                    weights[other_idx, secondary_idx] = candidate_negative_scale
                    weights[primary_idx, other_idx] = max(
                        weights[primary_idx, other_idx],
                        hard_negative_scale,
                    )
                    weights[other_idx, primary_idx] = max(
                        weights[other_idx, primary_idx],
                        hard_negative_scale,
                    )
    return weights


def hardest_group_membership(
    scenario: Scenario,
    groups: list[list[int]],
) -> np.ndarray:
    """Return a binary membership target for the teacher's hardest group."""

    mask = np.zeros(len(scenario.cqi_now), dtype=np.float32)
    ordered_groups = teacher_group_difficulty_order(scenario, groups)
    if not ordered_groups:
        return mask
    hard_group = groups[ordered_groups[0]]
    mask[hard_group] = 1.0
    return mask


def candidate_conditioned_membership_targets(
    scenario: Scenario,
    groups: list[list[int]],
    *,
    top_k: int = 2,
    secondary_scale: float = 2.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Return a sparse weak-candidate target/weight mask.

    This is a minimal learner-side refinement on top of hardest-group
    membership: instead of supervising every member of the hardest group
    equally, explicitly mark the top resource-cost users inside that hardest
    group as the most plausible weak-group candidates.

    The first candidate receives weight 1.0. The second candidate (the
    "secondary weak candidate") receives `secondary_scale`, which lets the
    caller emphasize the user that the current learner tends to miss.
    """

    n_users = len(scenario.cqi_now)
    target = np.zeros(n_users, dtype=np.float32)
    weights = np.zeros(n_users, dtype=np.float32)
    if top_k <= 0:
        return target, weights

    ordered_groups = teacher_group_difficulty_order(scenario, groups)
    if not ordered_groups:
        return target, weights
    hard_group = groups[ordered_groups[0]]
    if not hard_group:
        return target, weights

    user_costs = user_resource_cost_vector(scenario.rb_rates).mean(axis=1)
    ranked_members = sorted(
        hard_group,
        key=lambda idx: (float(user_costs[idx]), -idx),
        reverse=True,
    )
    for rank, user_idx in enumerate(ranked_members[:top_k]):
        target[user_idx] = 1.0
        weights[user_idx] = float(secondary_scale if rank == 1 else 1.0)
    return target, weights


def candidate_frontier_contrast_targets(
    scenario: Scenario,
    groups: list[list[int]],
    *,
    candidate_top_k: int = 2,
    negative_top_k: int = 2,
    secondary_scale: float = 2.0,
    negative_scale: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Build localized candidate-vs-confuser targets for weak-score ranking.

    Positives are the teacher hardest group's top resource-cost candidates.
    Negatives are the nearest plausible confusers:

    - first, non-candidate users inside the teacher hardest group;
    - then, highest-cost users outside the candidate set if more negatives are
      still needed.

    This gives the learner an explicit local ranking signal for
    `{primary, secondary}` vs nearby alternatives such as the old `ue15-only`
    frontier.
    """

    n_users = len(scenario.cqi_now)
    positive_weights = np.zeros(n_users, dtype=np.float32)
    negative_weights = np.zeros(n_users, dtype=np.float32)
    if candidate_top_k <= 0 or negative_top_k <= 0:
        return positive_weights, negative_weights

    ordered_groups = teacher_group_difficulty_order(scenario, groups)
    if not ordered_groups:
        return positive_weights, negative_weights
    hard_group = groups[ordered_groups[0]]
    if not hard_group:
        return positive_weights, negative_weights

    user_costs = user_resource_cost_vector(scenario.rb_rates).mean(axis=1)
    ranked_hard_members = sorted(
        hard_group,
        key=lambda idx: (float(user_costs[idx]), -idx),
        reverse=True,
    )
    candidate_members = ranked_hard_members[:candidate_top_k]
    for rank, user_idx in enumerate(candidate_members):
        positive_weights[user_idx] = float(secondary_scale if rank == 1 else 1.0)

    hard_non_candidates = [
        idx for idx in ranked_hard_members
        if idx not in candidate_members
    ]
    all_non_candidates = sorted(
        (
            idx for idx in range(n_users)
            if idx not in candidate_members and idx not in hard_non_candidates
        ),
        key=lambda idx: (float(user_costs[idx]), -idx),
        reverse=True,
    )
    negative_members = (hard_non_candidates + all_non_candidates)[:negative_top_k]
    for rank, user_idx in enumerate(negative_members):
        negative_weights[user_idx] = float(secondary_scale if rank == 0 else negative_scale)
    return positive_weights, negative_weights


def prioritize_pairs(
    priority_pairs: list[tuple[int, int]],
    fallback_pairs: list[tuple[int, int]],
    max_pairs: int,
) -> list[tuple[int, int]]:
    """Keep priority pairs first, then fill remaining slots from fallback pairs."""

    selected: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for pair in priority_pairs + fallback_pairs:
        if pair in seen:
            continue
        selected.append(pair)
        seen.add(pair)
        if len(selected) >= max_pairs:
            break
    return selected


def group_ids_from_groups(groups: list[list[int]], n_users: int) -> np.ndarray:
    """Convert grouping lists into one cluster-id label per user."""

    group_ids = np.full(n_users, -1, dtype=int)
    for group_idx, group in enumerate(groups):
        group_ids[group] = group_idx
    return group_ids


def pairwise_same_group_accuracy(true_group_ids: np.ndarray, pred_group_ids: np.ndarray) -> float:
    """Return pairwise same/different-group accuracy between two partitions."""

    true_same = true_group_ids[:, None] == true_group_ids[None, :]
    pred_same = pred_group_ids[:, None] == pred_group_ids[None, :]
    upper = np.triu_indices(len(true_group_ids), k=1)
    return float(np.mean(true_same[upper] == pred_same[upper]))


def _contingency_matrix(true_group_ids: np.ndarray, pred_group_ids: np.ndarray) -> np.ndarray:
    """Build the contingency matrix used by partition comparison metrics."""

    true_labels, true_inverse = np.unique(true_group_ids, return_inverse=True)
    pred_labels, pred_inverse = np.unique(pred_group_ids, return_inverse=True)
    contingency = np.zeros((len(true_labels), len(pred_labels)), dtype=np.int64)
    for true_idx, pred_idx in zip(true_inverse, pred_inverse):
        contingency[true_idx, pred_idx] += 1
    return contingency


def adjusted_rand_index(true_group_ids: np.ndarray, pred_group_ids: np.ndarray) -> float:
    """Compute the adjusted Rand index without relying on sklearn."""

    contingency = _contingency_matrix(true_group_ids, pred_group_ids)
    n = int(contingency.sum())
    if n <= 1:
        return 1.0

    def comb2(values: np.ndarray) -> float:
        return float(np.sum(values * (values - 1) / 2.0))

    sum_comb = comb2(contingency)
    sum_rows = comb2(contingency.sum(axis=1))
    sum_cols = comb2(contingency.sum(axis=0))
    total_pairs = n * (n - 1) / 2.0
    expected = (sum_rows * sum_cols) / total_pairs if total_pairs > 0 else 0.0
    max_index = 0.5 * (sum_rows + sum_cols)
    denom = max_index - expected
    if abs(denom) < 1e-12:
        return 1.0
    return float((sum_comb - expected) / denom)


def normalized_mutual_information(true_group_ids: np.ndarray, pred_group_ids: np.ndarray) -> float:
    """Compute NMI with geometric-mean normalization."""

    contingency = _contingency_matrix(true_group_ids, pred_group_ids).astype(float)
    n = contingency.sum()
    if n <= 0:
        return 0.0

    row_probs = contingency.sum(axis=1) / n
    col_probs = contingency.sum(axis=0) / n
    mutual_info = 0.0
    for i in range(contingency.shape[0]):
        for j in range(contingency.shape[1]):
            pij = contingency[i, j] / n
            if pij <= 0:
                continue
            expected = max(row_probs[i] * col_probs[j], 1e-12)
            mutual_info += pij * math.log(pij / expected)

    row_entropy = -float(np.sum(row_probs[row_probs > 0] * np.log(row_probs[row_probs > 0])))
    col_entropy = -float(np.sum(col_probs[col_probs > 0] * np.log(col_probs[col_probs > 0])))
    if row_entropy <= 1e-12 and col_entropy <= 1e-12:
        return 1.0
    denom = math.sqrt(max(row_entropy * col_entropy, 1e-12))
    score = float(mutual_info / denom)
    return float(np.clip(score, 0.0, 1.0))


class MLPEncoder:
    """Small NumPy MLP that maps VU features to learned embeddings.

    This is the MVP version. It is intentionally framework-free so the research
    pipeline is easy to trace. A portfolio-grade version should move this to
    PyTorch with Dataset/DataLoader and train/validation/test splits.
    """

    def __init__(self, input_dim: int, hidden_dim: int, embedding_dim: int, lr: float):
        self.lr = lr
        self.selected_epoch = 0
        self.selection_validation_loss = float("nan")
        self.pair_sampling = "random_balanced"
        self.last_pair_stats: dict[str, float] = {}
        self.training_pair_stats: dict[str, float] = {}
        self.w1 = np.random.normal(0, 0.10, size=(input_dim, hidden_dim))
        self.b1 = np.zeros(hidden_dim)
        self.w2 = np.random.normal(0, 0.10, size=(hidden_dim, hidden_dim))
        self.b2 = np.zeros(hidden_dim)
        self.w3 = np.random.normal(0, 0.10, size=(hidden_dim, embedding_dim))
        self.b3 = np.zeros(embedding_dim)
        self.w4 = np.random.normal(0, 0.10, size=(hidden_dim, 1))
        self.b4 = np.zeros(1)

    def forward(
        self, x: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Forward pass: features -> hidden layers -> embeddings + weak-group scores."""

        h1_pre = x @ self.w1 + self.b1
        h1 = np.maximum(0, h1_pre)
        h2_pre = h1 @ self.w2 + self.b2
        h2 = np.maximum(0, h2_pre)
        z_raw = h2 @ self.w3 + self.b3
        norms = np.linalg.norm(z_raw, axis=1, keepdims=True) + 1e-8
        z = z_raw / norms
        weak_logits = h2 @ self.w4 + self.b4
        weak_probs = 1.0 / (1.0 + np.exp(-np.clip(weak_logits, -30.0, 30.0)))
        return h1, h2, z_raw, z, weak_logits, weak_probs

    def embed(self, x: np.ndarray) -> np.ndarray:
        """Return only the embeddings used by k-means grouping."""

        _, _, _, z, _, _ = self.forward(x)
        return z

    def weak_group_scores(self, x: np.ndarray) -> np.ndarray:
        """Return per-user weakest-group membership scores in [0, 1]."""

        _, _, _, _, _, weak_probs = self.forward(x)
        return weak_probs[:, 0]

    def get_state(self) -> dict[str, np.ndarray]:
        """Return a detached copy of all trainable parameters."""

        return {
            "w1": self.w1.copy(),
            "b1": self.b1.copy(),
            "w2": self.w2.copy(),
            "b2": self.b2.copy(),
            "w3": self.w3.copy(),
            "b3": self.b3.copy(),
            "w4": self.w4.copy(),
            "b4": self.b4.copy(),
        }

    def set_state(self, state: dict[str, np.ndarray]) -> None:
        """Restore trainable parameters saved by :meth:`get_state`."""

        for name, value in state.items():
            setattr(self, name, value.copy())

    def contrastive_loss(
        self,
        x: np.ndarray,
        same_group: np.ndarray,
        margin: float = 1.0,
    ) -> float:
        """Evaluate deterministic all-pairs contrastive loss without updating."""

        z = self.embed(x)
        losses = []
        for i in range(len(x)):
            for j in range(i + 1, len(x)):
                dist = float(np.linalg.norm(z[i] - z[j]))
                if same_group[i, j] > 0.5:
                    losses.append(dist**2)
                else:
                    losses.append(max(0.0, margin - dist) ** 2)
        return float(np.mean(losses)) if losses else 0.0

    def train_step(
        self,
        x: np.ndarray,
        same_group: np.ndarray,
        pair_weights: np.ndarray | None = None,
        hard_group_target: np.ndarray | None = None,
        candidate_target: np.ndarray | None = None,
        candidate_target_weights: np.ndarray | None = None,
        frontier_positive_weights: np.ndarray | None = None,
        frontier_negative_weights: np.ndarray | None = None,
        margin: float = 1.0,
        pair_sampling: str = "random_balanced",
        max_pairs_per_class: int = 160,
        prototype_margin: float = 1.0,
        prototype_weight: float = 0.0,
        membership_weight: float = 0.0,
        candidate_membership_weight: float = 0.0,
        frontier_contrast_weight: float = 0.0,
        frontier_margin: float = 0.0,
    ) -> float:
        """One scenario-level contrastive training step.

        Positive pairs are VUs that the teacher placed in the same group.
        Negative pairs are VUs that the teacher placed in different groups.

        The loss pulls positive-pair embeddings together and pushes negative
        pairs at least `margin` apart.
        """

        h1, h2, z_raw, z, weak_logits, weak_probs = self.forward(x)
        n_users = len(x)
        dz = np.zeros_like(z)
        dweak_logits = np.zeros_like(weak_logits)
        loss = 0.0

        positive_pairs = []
        negative_pairs = []
        for i in range(n_users):
            for j in range(i + 1, n_users):
                if same_group[i, j] > 0.5:
                    positive_pairs.append((i, j))
                else:
                    negative_pairs.append((i, j))
        if pair_sampling not in {"random_balanced", "hard_negative", "teacher_boundary"}:
            raise ValueError(f"Unsupported pair_sampling: {pair_sampling}")
        random.shuffle(positive_pairs)
        priority_positive_pairs = []
        priority_negative_pairs = []
        if pair_weights is None:
            pair_weights = np.ones_like(same_group, dtype=np.float32)
        if pair_sampling == "teacher_boundary":
            priority_positive_pairs = [
                pair for pair in positive_pairs if pair_weights[pair[0], pair[1]] > 1.0
            ]
            priority_negative_pairs = [
                pair for pair in negative_pairs if pair_weights[pair[0], pair[1]] > 1.0
            ]
            random.shuffle(priority_positive_pairs)
            random.shuffle(priority_negative_pairs)
            selected_positive = prioritize_pairs(
                priority_positive_pairs,
                positive_pairs,
                max_pairs_per_class,
            )
        else:
            selected_positive = positive_pairs[:max_pairs_per_class]
        if pair_sampling == "hard_negative":
            # Teacher-negative pairs that are currently closest in embedding
            # space provide the strongest signal near/inside the margin.
            negative_pairs.sort(key=lambda pair: float(np.linalg.norm(z[pair[0]] - z[pair[1]])))
            selected_negative = negative_pairs[:max_pairs_per_class]
        elif pair_sampling == "teacher_boundary":
            random.shuffle(negative_pairs)
            selected_negative = prioritize_pairs(
                priority_negative_pairs,
                negative_pairs,
                max_pairs_per_class,
            )
        else:
            random.shuffle(negative_pairs)
            selected_negative = negative_pairs[:max_pairs_per_class]
        pairs = selected_positive + selected_negative
        random.shuffle(pairs)

        negative_distances = [
            float(np.linalg.norm(z[i] - z[j])) for i, j in selected_negative
        ]
        hard_group_positive_weights = [
            float(pair_weights[i, j]) for i, j in selected_positive
            if pair_weights[i, j] > 1.0
        ]
        hard_group_negative_weights = [
            float(pair_weights[i, j]) for i, j in selected_negative
            if pair_weights[i, j] > 1.0
        ]
        self.last_pair_stats = {
            "positive_pairs": float(len(selected_positive)),
            "negative_pairs": float(len(selected_negative)),
            "active_negative_ratio": (
                float(np.mean(np.asarray(negative_distances) < margin))
                if negative_distances else 0.0
            ),
            "mean_selected_negative_distance": (
                float(np.mean(negative_distances)) if negative_distances else float("nan")
            ),
            "mean_positive_weight": (
                float(np.mean([pair_weights[i, j] for i, j in selected_positive]))
                if selected_positive else float("nan")
            ),
            "mean_negative_weight": (
                float(np.mean([pair_weights[i, j] for i, j in selected_negative]))
                if selected_negative else float("nan")
            ),
            "hard_group_positive_pairs": float(len(hard_group_positive_weights)),
            "hard_group_negative_pairs": float(len(hard_group_negative_weights)),
            "priority_positive_pairs": float(
                len([1 for i, j in selected_positive if pair_weights[i, j] > 1.0])
            ),
            "priority_negative_pairs": float(
                len([1 for i, j in selected_negative if pair_weights[i, j] > 1.0])
            ),
        }

        for i, j in pairs:
            diff = z[i] - z[j]
            dist = np.linalg.norm(diff) + 1e-8
            pair_weight = float(pair_weights[i, j])
            if same_group[i, j] > 0.5:
                # Positive pair: make embeddings close.
                loss += pair_weight * dist**2
                grad = pair_weight * 2.0 * diff
                dz[i] += grad
                dz[j] -= grad
            elif dist < margin:
                # Negative pair: only penalize it if it is inside the margin.
                loss += pair_weight * (margin - dist) ** 2
                grad = pair_weight * -2.0 * (margin - dist) * diff / dist
                dz[i] += grad
                dz[j] -= grad

        prototype_positive_terms = 0
        prototype_negative_terms = 0
        if hard_group_target is not None and prototype_weight > 0.0:
            hard_indices = np.where(hard_group_target > 0.5)[0]
            other_indices = np.where(hard_group_target <= 0.5)[0]
            if len(hard_indices) > 0:
                # Treat the current hard-group centroid as a temporary target.
                # This is a lightweight group-identity signal layered on top
                # of the pairwise objective without changing the model head.
                prototype_center = z[hard_indices].mean(axis=0)
                for idx in hard_indices:
                    diff = z[idx] - prototype_center
                    loss += prototype_weight * float(np.dot(diff, diff))
                    dz[idx] += prototype_weight * 2.0 * diff
                    prototype_positive_terms += 1
                for idx in other_indices:
                    diff = z[idx] - prototype_center
                    dist = np.linalg.norm(diff) + 1e-8
                    if dist < prototype_margin:
                        loss += prototype_weight * (prototype_margin - dist) ** 2
                        dz[idx] += (
                            prototype_weight
                            * -2.0
                            * (prototype_margin - dist)
                            * diff
                            / dist
                        )
                        prototype_negative_terms += 1

        membership_terms = 0
        if hard_group_target is not None and membership_weight > 0.0:
            target = hard_group_target.reshape(-1, 1)
            probs = np.clip(weak_probs, 1e-6, 1.0 - 1e-6)
            loss += membership_weight * float(
                -np.sum(target * np.log(probs) + (1.0 - target) * np.log(1.0 - probs))
            )
            dweak_logits += membership_weight * (probs - target)
            membership_terms = len(target)

        candidate_membership_terms = 0
        if (
            candidate_target is not None
            and candidate_target_weights is not None
            and candidate_membership_weight > 0.0
        ):
            target = candidate_target.reshape(-1, 1)
            weight_mask = candidate_target_weights.reshape(-1, 1)
            active = weight_mask > 0.0
            if np.any(active):
                probs = np.clip(weak_probs, 1e-6, 1.0 - 1.0e-6)
                bce = -(
                    target * np.log(probs) + (1.0 - target) * np.log(1.0 - probs)
                )
                loss += candidate_membership_weight * float(np.sum(weight_mask * bce))
                dweak_logits += candidate_membership_weight * (weight_mask * (probs - target))
                candidate_membership_terms = int(np.sum(active))

        frontier_contrast_terms = 0
        if (
            frontier_positive_weights is not None
            and frontier_negative_weights is not None
            and frontier_contrast_weight > 0.0
        ):
            positive_indices = np.where(frontier_positive_weights > 0.0)[0]
            negative_indices = np.where(frontier_negative_weights > 0.0)[0]
            if len(positive_indices) > 0 and len(negative_indices) > 0:
                for pos_idx in positive_indices:
                    for neg_idx in negative_indices:
                        pair_weight = float(
                            frontier_positive_weights[pos_idx] * frontier_negative_weights[neg_idx]
                        )
                        gap = float(weak_logits[pos_idx, 0] - weak_logits[neg_idx, 0])
                        if gap < frontier_margin:
                            diff = frontier_margin - gap
                            loss += frontier_contrast_weight * pair_weight * diff**2
                            grad = frontier_contrast_weight * pair_weight * -2.0 * diff
                            dweak_logits[pos_idx, 0] += grad
                            dweak_logits[neg_idx, 0] -= grad
                        frontier_contrast_terms += 1

        if not pairs:
            return 0.0
        normalizer = (
            len(pairs)
            + prototype_positive_terms
            + prototype_negative_terms
            + membership_terms
            + candidate_membership_terms
            + frontier_contrast_terms
        )
        loss /= normalizer
        dz /= normalizer
        self.last_pair_stats["prototype_positive_terms"] = float(prototype_positive_terms)
        self.last_pair_stats["prototype_negative_terms"] = float(prototype_negative_terms)
        self.last_pair_stats["prototype_weight"] = float(prototype_weight)
        self.last_pair_stats["membership_terms"] = float(membership_terms)
        self.last_pair_stats["membership_weight"] = float(membership_weight)
        self.last_pair_stats["candidate_membership_terms"] = float(candidate_membership_terms)
        self.last_pair_stats["candidate_membership_weight"] = float(candidate_membership_weight)
        self.last_pair_stats["candidate_secondary_weight_mean"] = (
            float(np.mean(candidate_target_weights[candidate_target_weights > 0.0]))
            if candidate_target_weights is not None and np.any(candidate_target_weights > 0.0)
            else float("nan")
        )
        self.last_pair_stats["frontier_contrast_terms"] = float(frontier_contrast_terms)
        self.last_pair_stats["frontier_contrast_weight"] = float(frontier_contrast_weight)
        self.last_pair_stats["frontier_margin"] = float(frontier_margin)
        self.last_pair_stats["frontier_positive_count"] = (
            float(np.sum(frontier_positive_weights > 0.0))
            if frontier_positive_weights is not None
            else 0.0
        )
        self.last_pair_stats["frontier_negative_count"] = (
            float(np.sum(frontier_negative_weights > 0.0))
            if frontier_negative_weights is not None
            else 0.0
        )
        self.last_pair_stats["mean_weak_score"] = float(np.mean(weak_probs))

        # Backprop through L2 normalization:
        # y = x / ||x||, so dL/dx = (g - y * <y, g>) / ||x||
        norms = np.linalg.norm(z_raw, axis=1, keepdims=True) + 1e-8
        projection = np.sum(dz * z, axis=1, keepdims=True)
        dz_raw = (dz - z * projection) / norms

        dw3 = h2.T @ dz_raw
        db3 = dz_raw.sum(axis=0)
        dw4 = h2.T @ dweak_logits / normalizer
        db4 = dweak_logits.sum(axis=0) / normalizer
        dh2 = dz_raw @ self.w3.T + (dweak_logits / normalizer) @ self.w4.T
        dh2[h2 <= 0] = 0
        dw2 = h1.T @ dh2
        db2 = dh2.sum(axis=0)
        dh1 = dh2 @ self.w2.T
        dh1[h1 <= 0] = 0
        dw1 = x.T @ dh1
        db1 = dh1.sum(axis=0)

        self.w3 -= self.lr * dw3
        self.b3 -= self.lr * db3
        self.w4 -= self.lr * dw4
        self.b4 -= self.lr * db4
        self.w2 -= self.lr * dw2
        self.b2 -= self.lr * db2
        self.w1 -= self.lr * dw1
        self.b1 -= self.lr * db1
        return float(loss)


def best_membership_groups(
    scenario: Scenario,
    weak_scores: np.ndarray,
    max_groups: int,
    switch_beta: float,
) -> list[list[int]]:
    """Search contiguous split candidates after sorting by learned weak scores."""

    order = np.argsort(-weak_scores)
    n_users = len(order)
    best_groups = [list(range(n_users))]
    best_utility = -1e9
    cut_positions = list(range(1, n_users))
    for k in range(1, max_groups + 1):
        for boundaries in itertools.combinations(cut_positions, k - 1):
            groups = groups_from_sorted_boundaries(order, boundaries)
            result = allocate_and_evaluate(groups, scenario, switch_beta)
            if result.utility > best_utility:
                best_utility = result.utility
                best_groups = groups
    return best_groups


def membership_candidate_groups(
    weak_scores: np.ndarray,
    max_groups: int,
) -> list[list[list[int]]]:
    """Enumerate contiguous groups after sorting by learned weak scores."""

    order = np.argsort(-weak_scores)
    n_users = len(order)
    cut_positions = list(range(1, n_users))
    candidates: list[list[list[int]]] = []
    for k in range(1, max_groups + 1):
        for boundaries in itertools.combinations(cut_positions, k - 1):
            candidates.append(groups_from_sorted_boundaries(order, boundaries))
    return candidates


def _kmeans_once(
    x: np.ndarray,
    k: int,
    rng: np.random.Generator,
    max_iter: int,
) -> tuple[list[list[int]], float]:
    """Run one deterministic-from-RNG k-means initialization."""

    n = len(x)
    centers = x[rng.choice(n, size=k, replace=False)].copy()
    labels = np.zeros(n, dtype=int)
    for _ in range(max_iter):
        distances = ((x[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        new_labels = distances.argmin(axis=1)
        new_centers = centers.copy()
        for cluster_id in range(k):
            members = x[new_labels == cluster_id]
            if len(members) > 0:
                new_centers[cluster_id] = members.mean(axis=0)
        if np.array_equal(labels, new_labels):
            break
        labels = new_labels
        centers = new_centers
    final_distances = ((x[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
    inertia = float(np.sum(final_distances[np.arange(n), labels]))
    groups = [
        np.where(labels == cluster_id)[0].tolist()
        for cluster_id in range(k)
        if np.any(labels == cluster_id)
    ]
    return groups, inertia


def kmeans(
    x: np.ndarray,
    k: int,
    max_iter: int = 40,
    n_init: int = 10,
    seed: int = 0,
) -> list[list[int]]:
    """Deterministic multi-start k-means used as the clustering head.

    Every call with the same representation and arguments returns the same
    partition. Multiple initializations reduce sensitivity to a single random
    center choice; the partition with the lowest inertia is retained.
    """

    n = len(x)
    if k <= 1:
        return [list(range(n))]
    if not 1 <= k <= n:
        raise ValueError("k must be between 1 and the number of samples")
    if n_init < 1:
        raise ValueError("n_init must be at least 1")

    rng = np.random.default_rng(seed)
    best_groups: list[list[int]] | None = None
    best_inertia = float("inf")
    for _ in range(n_init):
        groups, inertia = _kmeans_once(x, k, rng, max_iter)
        if inertia < best_inertia:
            best_inertia = inertia
            best_groups = groups
    assert best_groups is not None
    return best_groups


def best_kmeans_groups(
    scenario: Scenario,
    representation: np.ndarray,
    max_groups: int,
    switch_beta: float,
    kmeans_n_init: int = 10,
    kmeans_seed: int = 0,
) -> list[list[int]]:
    """Try k=1..Kmax and choose the grouping with best DP-evaluated utility."""

    best_groups = [list(range(len(scenario.cqi_now)))]
    best_utility = -1e9
    for k in range(1, max_groups + 1):
        groups = kmeans(
            representation,
            k,
            n_init=kmeans_n_init,
            seed=kmeans_seed + k,
        )
        result = allocate_and_evaluate(groups, scenario, switch_beta)
        if result.utility > best_utility:
            best_utility = result.utility
            best_groups = groups
    return best_groups


def kmeans_candidate_groups(
    representation: np.ndarray,
    max_groups: int,
    *,
    kmeans_n_init: int = 10,
    kmeans_seed: int = 0,
) -> list[list[list[int]]]:
    """Enumerate one k-means partition for each k in 1..Kmax."""

    return [
        kmeans(
            representation,
            k,
            n_init=kmeans_n_init,
            seed=kmeans_seed + k,
        )
        for k in range(1, max_groups + 1)
    ]


def best_candidate_groups(
    scenario: Scenario,
    candidate_groupings: list[list[list[int]]],
    switch_beta: float,
) -> list[list[int]]:
    """Choose the highest-utility grouping from a candidate set."""

    best_groups = [list(range(len(scenario.cqi_now)))]
    best_utility = -1e9
    seen: set[tuple[tuple[int, ...], ...]] = set()
    for groups in candidate_groupings:
        normalized = tuple(sorted(tuple(sorted(group)) for group in groups))
        if normalized in seen:
            continue
        seen.add(normalized)
        result = allocate_and_evaluate(groups, scenario, switch_beta)
        if result.utility > best_utility:
            best_utility = result.utility
            best_groups = groups
    return best_groups


def best_hybrid_groups(
    scenario: Scenario,
    weak_scores: np.ndarray,
    embeddings: np.ndarray,
    max_groups: int,
    switch_beta: float,
    *,
    kmeans_n_init: int = 10,
    kmeans_seed: int = 0,
) -> list[list[int]]:
    """Union membership-order and embedding k-means candidates, then DP-select."""

    membership_candidates = membership_candidate_groups(weak_scores, max_groups)
    kmeans_candidates = kmeans_candidate_groups(
        embeddings,
        max_groups,
        kmeans_n_init=kmeans_n_init,
        kmeans_seed=kmeans_seed,
    )
    return best_candidate_groups(
        scenario,
        membership_candidates + kmeans_candidates,
        switch_beta,
    )


def no_grouping(scenario: Scenario, *_args) -> list[list[int]]:
    return [list(range(len(scenario.cqi_now)))]


def cqi_kmeans_grouping(
    scenario: Scenario,
    max_groups: int,
    switch_beta: float,
    kmeans_n_init: int = 10,
) -> list[list[int]]:
    """Baseline: k-means directly on raw current CQI."""

    return best_kmeans_groups(
        scenario,
        scenario.cqi_now.reshape(-1, 1).astype(float),
        max_groups,
        switch_beta,
        kmeans_n_init=kmeans_n_init,
    )


def resource_cost_kmeans_grouping(
    scenario: Scenario,
    max_groups: int,
    switch_beta: float,
    kmeans_n_init: int = 10,
) -> list[list[int]]:
    """Baseline: k-means on each VU's resource-cost vector."""

    cost_vec = user_resource_cost_vector(scenario.rb_rates)
    return best_kmeans_groups(
        scenario, cost_vec, max_groups, switch_beta,
        kmeans_n_init=kmeans_n_init,
    )


def multi_feature_kmeans_grouping(
    scenario: Scenario,
    max_groups: int,
    switch_beta: float,
    feature_mode: str = "full",
    kmeans_n_init: int = 10,
) -> list[list[int]]:
    """Baseline: k-means directly on the normalized full feature vector.

    This is an important sanity-check baseline. It answers:
    "Does LE-GRA help because it learns embeddings, or simply because it uses
    more features than CQI-only k-means?"
    """

    representation = build_feature_matrix(scenario, feature_mode)
    mean = representation.mean(axis=0)
    std = representation.std(axis=0) + 1e-6
    normalized = ((representation - mean) / std).astype(np.float32)
    return best_kmeans_groups(
        scenario, normalized, max_groups, switch_beta,
        kmeans_n_init=kmeans_n_init,
    )


def learned_grouping(
    scenario: Scenario,
    model: MLPEncoder,
    max_groups: int,
    switch_beta: float,
    kmeans_n_init: int = 10,
) -> list[list[int]]:
    """Proposed learner grouping.

    Default path: embedding -> k-means -> DP utility selection.
    Membership-head path: weak-group scores -> ordered boundary search -> DP.
    """

    if getattr(model, "grouping_mode", "kmeans_embedding") == "membership_order":
        weak_scores = model.weak_group_scores(scenario.features)
        return best_membership_groups(scenario, weak_scores, max_groups, switch_beta)
    if getattr(model, "grouping_mode", "kmeans_embedding") == "hybrid_membership_kmeans":
        weak_scores = model.weak_group_scores(scenario.features)
        embeddings = model.embed(scenario.features)
        return best_hybrid_groups(
            scenario,
            weak_scores,
            embeddings,
            max_groups,
            switch_beta,
            kmeans_n_init=kmeans_n_init,
        )
    embeddings = model.embed(scenario.features)
    return best_kmeans_groups(
        scenario, embeddings, max_groups, switch_beta,
        kmeans_n_init=kmeans_n_init,
    )


def aggregate_eval_results(results: list[EvalResult]) -> EvalResult:
    """Average a non-empty list of per-scenario evaluation results."""

    if not results:
        raise ValueError("results must not be empty")
    return EvalResult(
        utility=float(np.mean([r.utility for r in results])),
        adr_kbps=float(np.mean([r.adr_kbps for r in results])),
        used_spectral_efficiency=float(np.mean([r.used_spectral_efficiency for r in results])),
        system_spectral_efficiency=float(np.mean([r.system_spectral_efficiency for r in results])),
        served_ratio=float(np.mean([r.served_ratio for r in results])),
        unserved_ratio=float(np.mean([r.unserved_ratio for r in results])),
        average_quality=float(np.mean([r.average_quality for r in results])),
        rb_utilization=float(np.mean([r.rb_utilization for r in results])),
        avg_switching=float(np.mean([r.avg_switching for r in results])),
        fairness=float(np.mean([r.fairness for r in results])),
        groups=float(np.mean([r.groups for r in results])),
    )


def evaluate_method(
    scenarios: list[Scenario],
    grouping_fn: Callable[[Scenario], list[list[int]]],
    switch_beta: float,
) -> EvalResult:
    """Evaluate one grouping method over a list of scenarios."""

    results = [allocate_and_evaluate(grouping_fn(s), s, switch_beta) for s in scenarios]
    return aggregate_eval_results(results)


def default_methods(
    max_groups: int,
    switch_beta: float,
    model: MLPEncoder,
    include_multifeature_baseline: bool = False,
    multifeature_feature_mode: str = "full",
    kmeans_n_init: int = 10,
) -> dict[str, Callable[[Scenario], list[list[int]]]]:
    """Return the default comparison set for the main research storyline."""

    methods = {
        "No grouping": lambda s: no_grouping(s),
        "CQI k-means": lambda s: cqi_kmeans_grouping(
            s, max_groups, switch_beta, kmeans_n_init
        ),
        "Resource-cost k-means": lambda s: resource_cost_kmeans_grouping(
            s, max_groups, switch_beta, kmeans_n_init
        ),
        "Offline teacher": lambda s: offline_teacher_groups(s, max_groups, switch_beta),
        "LE-GRA MVP": lambda s: learned_grouping(
            s, model, max_groups, switch_beta, kmeans_n_init
        ),
    }
    if include_multifeature_baseline:
        methods["Multi-feature k-means"] = lambda s: multi_feature_kmeans_grouping(
            s, max_groups, switch_beta, feature_mode=multifeature_feature_mode,
            kmeans_n_init=kmeans_n_init,
        )
    return methods


def main() -> None:
    """CLI entry point.

    Trace order:
      1. Generate train/test scenarios.
      2. Build offline-teacher pseudo-labels for train scenarios.
      3. Train the MLP embedding model with pairwise contrastive loss.
      4. Compare baselines and LE-GRA on test scenarios with the same DP backend.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("--train-scenarios", type=int, default=160)
    parser.add_argument("--test-scenarios", type=int, default=60)
    parser.add_argument("--users", type=int, default=24)
    parser.add_argument("--rbs", type=int, default=100)
    parser.add_argument("--max-groups", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--switch-beta", type=float, default=0.5)
    parser.add_argument(
        "--pair-sampling",
        choices=["random_balanced", "hard_negative"],
        default="random_balanced",
    )
    parser.add_argument("--pairs-per-class", type=int, default=160)
    parser.add_argument(
        "--kmeans-n-init",
        type=int,
        default=10,
        help="Deterministic k-means initializations per candidate k.",
    )
    parser.add_argument(
        "--rb-budget-ratio",
        type=float,
        default=0.40,
        help="Available RBs as a fraction of total RBs (default: 0.40).",
    )
    parser.add_argument("--scenario-mode", choices=["aligned", "ambiguous", "mixed"], default="mixed")
    parser.add_argument(
        "--feature-mode",
        choices=["history_only", "history_cost", "history_cost_quality", "history_cost_load", "history_cost_context", "full", "full_context"],
        default="full",
        help="Feature ablation mode for the learned LE-GRA model.",
    )
    parser.add_argument(
        "--include-multifeature-baseline",
        action="store_true",
        help="Include the multi-feature k-means sanity-check baseline in addition to the core comparison set.",
    )
    parser.add_argument("--seed", type=int, default=9)
    args = parser.parse_args()

    if args.pairs_per_class <= 0:
        parser.error("--pairs-per-class must be positive")

    set_seed(args.seed)
    dispersions = ["high", "mid", "low"]
    train = [
        generate_scenario(
            args.users, args.rbs, random.choice(dispersions), args.scenario_mode,
            rb_budget_ratio=args.rb_budget_ratio,
        )
        for _ in range(args.train_scenarios)
    ]
    test = [
        generate_scenario(
            args.users, args.rbs, random.choice(dispersions), args.scenario_mode,
            rb_budget_ratio=args.rb_budget_ratio,
        )
        for _ in range(args.test_scenarios)
    ]
    apply_feature_mode(train, test, args.feature_mode)
    normalize_features(train, test)

    print("Generating offline-teacher pseudo-labels...")
    teacher_groups = [offline_teacher_groups(s, args.max_groups, args.switch_beta) for s in train]
    teacher_labels = [pairwise_labels(g, args.users) for g in teacher_groups]

    model = MLPEncoder(
        input_dim=train[0].features.shape[1],
        hidden_dim=48,
        embedding_dim=8,
        lr=0.01,
    )

    print("Training MLP embedding model...")
    for epoch in range(1, args.epochs + 1):
        order = list(range(len(train)))
        random.shuffle(order)
        losses = []
        for idx in order:
            losses.append(model.train_step(
                train[idx].features,
                teacher_labels[idx],
                pair_sampling=args.pair_sampling,
                max_pairs_per_class=args.pairs_per_class,
            ))
        print(f"epoch={epoch:02d} contrastive_loss={np.mean(losses):.4f}")

    methods = default_methods(
        args.max_groups,
        args.switch_beta,
        model,
        include_multifeature_baseline=args.include_multifeature_baseline,
        kmeans_n_init=args.kmeans_n_init,
    )

    print("\nEvaluation over synthetic test scenarios")
    print(f"feature_mode={args.feature_mode}")
    print(
        "method, utility, ADR(kbps), used_SE(bit/s/Hz), system_SE(bit/s/Hz), "
        "served_ratio, unserved_ratio, avg_quality, RB_util, avg_switching, "
        "fairness, avg_groups"
    )
    for name, fn in methods.items():
        result = evaluate_method(test, fn, args.switch_beta)
        print(
            f"{name}, "
            f"{result.utility:.4f}, "
            f"{result.adr_kbps:.1f}, "
            f"{result.used_spectral_efficiency:.3f}, "
            f"{result.system_spectral_efficiency:.3f}, "
            f"{result.served_ratio:.3f}, "
            f"{result.unserved_ratio:.3f}, "
            f"{result.average_quality:.2f}, "
            f"{result.rb_utilization:.3f}, "
            f"{result.avg_switching:.3f}, "
            f"{result.fairness:.3f}, "
            f"{result.groups:.2f}"
        )


if __name__ == "__main__":
    main()
