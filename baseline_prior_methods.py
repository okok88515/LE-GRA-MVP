"""Reimplementations of two prior-published CQI k-means multicast-grouping
baselines, described by the user as the points of comparison for their own
earlier publication (this project's `le_gra_mvp.cqi_kmeans_grouping`) --
NOT part of this project's own candidate-union method lineage. Built here
purely to quantify, on real Simu5G data, how much the published method
already improved over prior art.

Method A: identical k-means candidate generation to `cqi_kmeans_grouping`
(one partition per k=1..max_groups on raw wideband CQI), but selects among
candidates with a proxy score -- group-size-weighted minimum CQI -- instead
of real resource-allocation utility. The published method's advantage over
this baseline is purely in the scoring/selection step.

Method B: no k-means. Sorts users by CQI and searches only CONTIGUOUS
cut-point partitions of the sorted sequence into 1..max_groups groups (not
literal exhaustive search over all set partitions of n users, which is
combinatorially infeasible -- confirmed with the user this is the intended
reading of "brute-force search all configurations"). A partition is
admissible only if every one of its groups has raw-CQI standard deviation
below a threshold, starting at 0.5 and escalating by 0.5 per round until at
least one partition anywhere in the search is admissible. Among admissible
partitions, the real exact-DP resource-allocation utility (this project's
own `allocate_and_evaluate`) picks the winner -- unlike Method A, Method B's
own selection step already used real resource-allocation scoring, per the
user's correction. The published method's advantage over this baseline is
in candidate-generation efficiency (k-means vs. cut-point enumeration with
threshold escalation), not scoring.

Both are capped at this project's own `max_groups` convention (KMAX=3) for
a fair, apples-to-apples comparison against every other method in this
codebase; this is an assumption about scope made for this reimplementation,
not a detail confirmed from either original publication.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np

import le_gra_mvp as mvp


def cqi_min_weighted_kmeans_grouping(
    scenario: mvp.Scenario,
    max_groups: int,
    kmeans_n_init: int = 10,
    kmeans_seed: int = 0,
) -> list[list[int]]:
    """Method A: k-means on CQI for k=1..max_groups, selected by a
    group-size-weighted minimum-CQI proxy score instead of real
    resource-allocation utility."""

    cqi_rep = scenario.cqi_now.reshape(-1, 1).astype(float)
    candidates = mvp.kmeans_candidate_groups(
        cqi_rep, max_groups, kmeans_n_init=kmeans_n_init, kmeans_seed=kmeans_seed
    )
    n_users = len(scenario.cqi_now)

    best_groups = candidates[0]
    best_score = -np.inf
    for groups in candidates:
        score = sum(
            len(group) * scenario.cqi_now[group].min() for group in groups if group
        ) / n_users
        if score > best_score:
            best_score = score
            best_groups = groups
    return best_groups


def _contiguous_partitions(order: np.ndarray, max_groups: int):
    """Yield every partition of `order` into 1..max_groups CONTIGUOUS
    segments (cut points chosen among the sorted gaps) -- not every possible
    set partition, which would be combinatorially infeasible."""

    n_users = len(order)
    for m in range(1, max_groups + 1):
        if m == 1:
            yield [order.tolist()]
            continue
        if m - 1 > n_users - 1:
            continue
        for cuts in combinations(range(1, n_users), m - 1):
            bounds = (0,) + cuts + (n_users,)
            yield [order[bounds[i] : bounds[i + 1]].tolist() for i in range(m)]


def no_grouping_single_group(scenario: mvp.Scenario) -> list[list[int]]:
    """Pure multicast, no clustering at all: every user in one shared group.
    The most resource-efficient possible allocation and the worst possible
    per-user quality outcome, used as a lower reference point, not a method
    anyone would actually deploy."""

    return [list(range(len(scenario.cqi_now)))]


def optimal_sorted_cutpoint_partition(
    scenario: mvp.Scenario,
    switch_beta: float,
    value_fn=None,
) -> tuple[list[list[int]], float]:
    """Exact DP optimum within the CQI-sorted CONTIGUOUS-partition family --
    the same search family Method B explores heuristically via threshold
    escalation -- allowing any number of groups (not capped at KMAX) and
    with no standard-deviation admissibility filter at all, just direct
    maximization of the real exact-DP resource-allocation utility.

    This is NOT the true global optimum over all possible set partitions of
    n users, which is combinatorially infeasible to compute (the Bell
    number for n=24 is exactly 44,152,005,855,084,346 ~= 4.46e17, and even
    capping at 3 groups leaves ~4.7e10 partitions -- confirmed with the
    user this substitute upper bound, restricted to the sorted-contiguous
    family, is an acceptable stand-in). It IS the rigorous best achievable
    result
    within that restricted family, and quantifies exactly how much Method
    B's own threshold-escalation heuristic leaves on the table relative to
    a proper search of the same family.

    DP state: dp[i][r] = best total utility achievable by optimally
    partitioning the first i users (in CQI-sorted order) into any number of
    CONTIGUOUS groups, using at most r RBs. This is tractable because the
    RB budget is carried explicitly through the state, unlike a naive
    per-segment-independent formulation, which would ignore that groups
    share one RB pool.
    """

    value_fn = value_fn or mvp.group_quality_value
    order = np.argsort(scenario.cqi_now, kind="stable")
    n_users = len(order)
    rb_available = scenario.rb_available

    NEG = float("-inf")
    dp = [[NEG] * (rb_available + 1) for _ in range(n_users + 1)]
    choice: list[list[tuple[int, int, int] | None]] = [
        [None] * (rb_available + 1) for _ in range(n_users + 1)
    ]
    for r in range(rb_available + 1):
        dp[0][r] = 0.0

    for i in range(1, n_users + 1):
        for j in range(i):
            segment = order[j:i].tolist()
            group_rates = scenario.rb_rates[segment].min(axis=0)
            sorted_rates = np.sort(group_rates)[::-1]
            options = [(-1, 0)]
            for q_idx, bitrate in enumerate(mvp.VIDEO_BITRATES_KBPS):
                need = mvp.rb_needed(sorted_rates, bitrate)
                if need is not None and need <= rb_available:
                    options.append((q_idx, need))
            for quality, need in options:
                val = value_fn(segment, quality, scenario, switch_beta)
                for r in range(need, rb_available + 1):
                    prev = dp[j][r - need]
                    if prev == NEG:
                        continue
                    candidate = prev + val
                    if candidate > dp[i][r]:
                        dp[i][r] = candidate
                        choice[i][r] = (j, quality, need)
        for r in range(1, rb_available + 1):
            if dp[i][r - 1] > dp[i][r]:
                dp[i][r] = dp[i][r - 1]
                choice[i][r] = choice[i][r - 1]

    best_r = max(range(rb_available + 1), key=lambda r: dp[n_users][r])
    # `value_fn` returns each group's raw SUMMED contribution (matching
    # `group_quality_value`/`allocate_and_evaluate`'s own convention), so
    # dp[][] accumulates a total, not a per-user mean -- divide here to
    # match `EvalResult.utility`'s convention used everywhere else in this
    # project, so the returned number is directly comparable.
    best_utility = dp[n_users][best_r] / n_users

    groups: list[list[int]] = []
    i, r = n_users, best_r
    while i > 0:
        step = choice[i][r]
        if step is None:
            break
        j, _quality, need = step
        groups.append(order[j:i].tolist())
        i, r = j, r - need
    groups.reverse()
    return groups, best_utility


def sorted_cutpoint_stddev_threshold_grouping(
    scenario: mvp.Scenario,
    max_groups: int,
    switch_beta: float,
    threshold_start: float = 0.5,
    threshold_step: float = 0.5,
    max_rounds: int = 40,
    value_fn=None,
) -> list[list[int]]:
    """Method B: sort by CQI, search contiguous cut-point partitions into
    1..max_groups groups, admit those whose every group has CQI standard
    deviation below a threshold (starting at 0.5, escalating by 0.5 per
    round if nothing anywhere is admissible), then pick the admissible
    partition with the highest real exact-DP resource-allocation utility.
    `value_fn` is forwarded to `allocate_and_evaluate` (default None ->
    `group_quality_value`); pass `mvp.group_adr_value` to select among
    admissible partitions by raw ADR instead."""

    order = np.argsort(scenario.cqi_now, kind="stable")

    threshold = threshold_start
    admissible: list[list[list[int]]] = []
    for _round in range(max_rounds):
        admissible = [
            groups
            for groups in _contiguous_partitions(order, max_groups)
            if all(scenario.cqi_now[group].std() < threshold for group in groups)
        ]
        if admissible:
            break
        threshold += threshold_step
    if not admissible:
        admissible = [[order.tolist()]]

    best_groups = admissible[0]
    best_utility = -np.inf
    for groups in admissible:
        result = mvp.allocate_and_evaluate(groups, scenario, switch_beta, value_fn=value_fn)
        if result.utility > best_utility:
            best_utility = result.utility
            best_groups = groups
    return best_groups
