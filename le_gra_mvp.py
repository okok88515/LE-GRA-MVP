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
    rb_bandwidth_khz = 180.0
    return CQI_TO_EFF[cqi_int] * rb_bandwidth_khz


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

    if dynamic_rb:
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

    if feature_mode == "history_only":
        features = [scenario.cqi_history]
    elif feature_mode == "history_cost":
        features = [scenario.cqi_history, cost_vec]
    elif feature_mode == "full":
        features = [scenario.cqi_history, rb_stats, mobility, cost_vec]
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

    switching = np.zeros(len(scenario.cqi_now), dtype=float)
    switching[served] = np.abs(best_user_quality[served] - scenario.previous_quality[served]) / (
        len(VIDEO_BITRATES_KBPS) - 1
    )
    return EvalResult(
        utility=best_utility,
        adr_kbps=float(user_bitrate.mean()),
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


class MLPEncoder:
    """Small NumPy MLP that maps VU features to learned embeddings.

    This is the MVP version. It is intentionally framework-free so the research
    pipeline is easy to trace. A portfolio-grade version should move this to
    PyTorch with Dataset/DataLoader and train/validation/test splits.
    """

    def __init__(self, input_dim: int, hidden_dim: int, embedding_dim: int, lr: float):
        self.lr = lr
        self.w1 = np.random.normal(0, 0.10, size=(input_dim, hidden_dim))
        self.b1 = np.zeros(hidden_dim)
        self.w2 = np.random.normal(0, 0.10, size=(hidden_dim, hidden_dim))
        self.b2 = np.zeros(hidden_dim)
        self.w3 = np.random.normal(0, 0.10, size=(hidden_dim, embedding_dim))
        self.b3 = np.zeros(embedding_dim)

    def forward(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Forward pass: features -> hidden layers -> normalized embedding."""

        h1_pre = x @ self.w1 + self.b1
        h1 = np.maximum(0, h1_pre)
        h2_pre = h1 @ self.w2 + self.b2
        h2 = np.maximum(0, h2_pre)
        z_raw = h2 @ self.w3 + self.b3
        z = z_raw / (np.linalg.norm(z_raw, axis=1, keepdims=True) + 1e-8)
        return h1, h2, z

    def embed(self, x: np.ndarray) -> np.ndarray:
        """Return only the embeddings used by k-means grouping."""

        _, _, z = self.forward(x)
        return z

    def train_step(self, x: np.ndarray, same_group: np.ndarray, margin: float = 1.0) -> float:
        """One scenario-level contrastive training step.

        Positive pairs are VUs that the teacher placed in the same group.
        Negative pairs are VUs that the teacher placed in different groups.

        The loss pulls positive-pair embeddings together and pushes negative
        pairs at least `margin` apart.
        """

        h1, h2, z = self.forward(x)
        n_users = len(x)
        dz = np.zeros_like(z)
        loss = 0.0

        positive_pairs = []
        negative_pairs = []
        for i in range(n_users):
            for j in range(i + 1, n_users):
                if same_group[i, j] > 0.5:
                    positive_pairs.append((i, j))
                else:
                    negative_pairs.append((i, j))
        random.shuffle(positive_pairs)
        random.shuffle(negative_pairs)
        pairs = positive_pairs[:160] + negative_pairs[:160]
        random.shuffle(pairs)

        for i, j in pairs:
            diff = z[i] - z[j]
            dist = np.linalg.norm(diff) + 1e-8
            if same_group[i, j] > 0.5:
                # Positive pair: make embeddings close.
                loss += dist**2
                grad = 2.0 * diff
                dz[i] += grad
                dz[j] -= grad
            elif dist < margin:
                # Negative pair: only penalize it if it is inside the margin.
                loss += (margin - dist) ** 2
                grad = -2.0 * (margin - dist) * diff / dist
                dz[i] += grad
                dz[j] -= grad

        if not pairs:
            return 0.0
        loss /= len(pairs)
        dz /= len(pairs)

        # Approximate backprop through L2 normalization. Good enough for MVP.
        dw3 = h2.T @ dz
        db3 = dz.sum(axis=0)
        dh2 = dz @ self.w3.T
        dh2[h2 <= 0] = 0
        dw2 = h1.T @ dh2
        db2 = dh2.sum(axis=0)
        dh1 = dh2 @ self.w2.T
        dh1[h1 <= 0] = 0
        dw1 = x.T @ dh1
        db1 = dh1.sum(axis=0)

        self.w3 -= self.lr * dw3
        self.b3 -= self.lr * db3
        self.w2 -= self.lr * dw2
        self.b2 -= self.lr * db2
        self.w1 -= self.lr * dw1
        self.b1 -= self.lr * db1
        return float(loss)


def kmeans(x: np.ndarray, k: int, max_iter: int = 40) -> list[list[int]]:
    """Minimal k-means used as the clustering head."""

    n = len(x)
    if k <= 1:
        return [list(range(n))]
    centers = x[np.random.choice(n, size=k, replace=False)].copy()
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
    return [np.where(labels == cluster_id)[0].tolist() for cluster_id in range(k) if np.any(labels == cluster_id)]


def best_kmeans_groups(
    scenario: Scenario,
    representation: np.ndarray,
    max_groups: int,
    switch_beta: float,
) -> list[list[int]]:
    """Try k=1..Kmax and choose the grouping with best DP-evaluated utility."""

    best_groups = [list(range(len(scenario.cqi_now)))]
    best_utility = -1e9
    for k in range(1, max_groups + 1):
        groups = kmeans(representation, k)
        result = allocate_and_evaluate(groups, scenario, switch_beta)
        if result.utility > best_utility:
            best_utility = result.utility
            best_groups = groups
    return best_groups


def no_grouping(scenario: Scenario, *_args) -> list[list[int]]:
    return [list(range(len(scenario.cqi_now)))]


def cqi_kmeans_grouping(scenario: Scenario, max_groups: int, switch_beta: float) -> list[list[int]]:
    """Baseline: k-means directly on raw current CQI."""

    return best_kmeans_groups(scenario, scenario.cqi_now.reshape(-1, 1).astype(float), max_groups, switch_beta)


def resource_cost_kmeans_grouping(scenario: Scenario, max_groups: int, switch_beta: float) -> list[list[int]]:
    """Baseline: k-means on each VU's resource-cost vector."""

    cost_vec = user_resource_cost_vector(scenario.rb_rates)
    return best_kmeans_groups(scenario, cost_vec, max_groups, switch_beta)


def multi_feature_kmeans_grouping(scenario: Scenario, max_groups: int, switch_beta: float) -> list[list[int]]:
    """Baseline: k-means directly on the normalized full feature vector.

    This is an important sanity-check baseline. It answers:
    "Does LE-GRA help because it learns embeddings, or simply because it uses
    more features than CQI-only k-means?"
    """

    return best_kmeans_groups(scenario, scenario.features, max_groups, switch_beta)


def learned_grouping(
    scenario: Scenario,
    model: MLPEncoder,
    max_groups: int,
    switch_beta: float,
) -> list[list[int]]:
    """Proposed MVP: MLP embedding -> k-means -> DP utility selection."""

    embeddings = model.embed(scenario.features)
    return best_kmeans_groups(scenario, embeddings, max_groups, switch_beta)


def evaluate_method(
    scenarios: list[Scenario],
    grouping_fn: Callable[[Scenario], list[list[int]]],
    switch_beta: float,
) -> EvalResult:
    """Evaluate one grouping method over a list of scenarios."""

    results = [allocate_and_evaluate(grouping_fn(s), s, switch_beta) for s in scenarios]
    return EvalResult(
        utility=float(np.mean([r.utility for r in results])),
        adr_kbps=float(np.mean([r.adr_kbps for r in results])),
        rb_utilization=float(np.mean([r.rb_utilization for r in results])),
        avg_switching=float(np.mean([r.avg_switching for r in results])),
        fairness=float(np.mean([r.fairness for r in results])),
        groups=float(np.mean([r.groups for r in results])),
    )


def default_methods(
    max_groups: int,
    switch_beta: float,
    model: MLPEncoder,
    include_multifeature_baseline: bool = False,
) -> dict[str, Callable[[Scenario], list[list[int]]]]:
    """Return the default comparison set for the main research storyline."""

    methods = {
        "No grouping": lambda s: no_grouping(s),
        "CQI k-means": lambda s: cqi_kmeans_grouping(s, max_groups, switch_beta),
        "Resource-cost k-means": lambda s: resource_cost_kmeans_grouping(s, max_groups, switch_beta),
        "Offline teacher": lambda s: offline_teacher_groups(s, max_groups, switch_beta),
        "LE-GRA MVP": lambda s: learned_grouping(s, model, max_groups, switch_beta),
    }
    if include_multifeature_baseline:
        methods["Multi-feature k-means"] = lambda s: multi_feature_kmeans_grouping(s, max_groups, switch_beta)
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
    parser.add_argument("--scenario-mode", choices=["aligned", "ambiguous", "mixed"], default="mixed")
    parser.add_argument(
        "--feature-mode",
        choices=["history_only", "history_cost", "full"],
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

    set_seed(args.seed)
    dispersions = ["high", "mid", "low"]
    train = [
        generate_scenario(args.users, args.rbs, random.choice(dispersions), args.scenario_mode)
        for _ in range(args.train_scenarios)
    ]
    test = [
        generate_scenario(args.users, args.rbs, random.choice(dispersions), args.scenario_mode)
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
            losses.append(model.train_step(train[idx].features, teacher_labels[idx]))
        print(f"epoch={epoch:02d} contrastive_loss={np.mean(losses):.4f}")

    methods = default_methods(
        args.max_groups,
        args.switch_beta,
        model,
        include_multifeature_baseline=args.include_multifeature_baseline,
    )

    print("\nEvaluation over synthetic test scenarios")
    print(f"feature_mode={args.feature_mode}")
    print("method, utility, ADR(kbps), RB_util, avg_switching, fairness, avg_groups")
    for name, fn in methods.items():
        result = evaluate_method(test, fn, args.switch_beta)
        print(
            f"{name}, "
            f"{result.utility:.4f}, "
            f"{result.adr_kbps:.1f}, "
            f"{result.rb_utilization:.3f}, "
            f"{result.avg_switching:.3f}, "
            f"{result.fairness:.3f}, "
            f"{result.groups:.2f}"
        )


if __name__ == "__main__":
    main()
