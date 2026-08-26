# Real Simu5G RB-profile compatibility direction (research direction 1)

Date: 2026-08-26

## Question

`POST_CQI_RESEARCH_ROADMAP_ZH.md` direction 1: two users can share the same
wideband CQI while having very different per-band rate profiles. If their
good bands don't overlap, multicasting them together bottlenecks on the
worse-of-both-shapes rate on every band -- information CQI k-means cannot
see. This experiment tests whether keeping the full per-band profile, or a
pairwise RB-profile-compatibility graph built from it, beats CQI k-means and
the already real-data-validated CQI+cost 2-way union.

## Methods tested

All methods use the same exact-DP allocation and log-utility as everywhere
else in this project (`le_gra_mvp.py`). Snapshot-level, non-temporal
evaluation (`previous_quality` reset to 0 each snapshot) -- deliberately not
the closed-loop protocol, to isolate the frequency-selectivity axis from the
switching/temporal axis (a separate, already-explored direction).

- `full_rb_profile_kmeans_grouping`: k-means on the complete 25-band rate
  profile (z-scored), not a mean/min/max/std summary.
- `block_rb_profile_kmeans_grouping`: k-means on the profile averaged into 5
  contiguous frequency blocks -- checks whether exact per-band position
  matters or only the coarse shape.
- `rb_overlap_affinity_matrix` + `overlap_graph_grouping`: pairwise Pearson
  correlation of per-band rate profiles as a graph affinity, then hand-rolled
  spectral clustering (`np.linalg.eigh` on the graph Laplacian, no
  scipy/sklearn dependency in this project).
- `pairwise_exact_regret_matrix` + `exact_regret_graph_grouping`: pairwise
  "how much utility is lost by forcing these two users into the same group"
  regret (`regret(i,j) = value_solo(i) + value_solo(j) - value_pair(i,j)`,
  each value computed under an RB-feasibility-checked, exclusive-budget
  approximation), converted to an affinity via `exp(-regret/scale)`, then the
  same spectral clustering.
- `cqi_cost_regret_graph_hybrid_grouping`: CQI ∪ resource-cost ∪ regret-graph
  candidate union (added after the standalone results below), exact-DP picks
  the winner per scenario -- same "union only gets better" design as every
  other hybrid method in this project.

Reproduction:

```powershell
python .\run_real_multiseed_rb_profile_direction.py
```

Exploratory only: uses seeds 1..10. Seeds 11..30 already confirmed the
`eta=.020` switching gate (`REAL_SIMU5G_CONDITIONAL_GATING.md`) and per the
roadmap's own rule cannot also be claimed as an untouched confirmatory set
for this direction.

## A real bug found and fixed mid-investigation

The first run's `exact_regret_graph_grouping` catastrophically underperformed
everywhere, worst at high dispersion + heavy load (`-0.2439` vs CQI k-means).
Root cause: `group_quality_value` -- the helper this project's exact-DP
allocator uses to score an already-feasibility-filtered `(group, quality)`
option -- does not itself check RB feasibility; it assumes the caller already
filtered infeasible options via `rb_needed`. `pairwise_exact_regret_matrix`'s
first version called it directly to search "which quality tier maximizes the
score," without that filter. Every user's "best solo value" therefore landed
on quality tier 4 (5800 kbps) with an identical score of `0.5291`,
**regardless of their actual channel** -- the regret matrix was silently
~0 everywhere. A near-uniform affinity matrix makes the graph Laplacian's
low-eigenvalue eigenspace numerically degenerate; spectral clustering on it
produces partitions driven by floating-point noise, not real structure.

Fixed by adding the same `rb_needed`-based feasibility check `group_options`
already uses downstream, to both the solo and pair value searches. See
`le_gra_mvp.py`'s `pairwise_exact_regret_matrix` docstring for the exact
fix and a comment noting why it was missing.

## Standalone method results (post-fix, seeds 1..10, mean utility diff vs CQI k-means)

| Dispersion | Load | Cost | Full-profile | Block-profile (5) | Overlap graph | Exact-regret graph |
|---|---|---:|---:|---:|---:|---:|
| low | all | ≈0 | ≈0 | ≈0 | ≈0 | ≈0 |
| mid | light | +0.0004 | +0.0012 | +0.0006 | -0.0241 | -0.0043 |
| mid | medium | +0.0001 | +0.0019 | +0.0004 | -0.0233 | -0.0032 |
| mid | heavy | -0.0092 | -0.0010 | -0.0012 | -0.0150 | -0.0097 |
| high | light | +0.0063 | -0.0073 | -0.0059 | -0.0646 | -0.0329 |
| high | medium | -0.0105 | -0.0005 | -0.0016 | -0.0416 | -0.0115 |
| **high** | **heavy** | +0.0273 | -0.0594 | -0.0461 | -0.1263 | **+0.0586 (8/10 seed win)** |

Low dispersion is saturated for every method (all near-identical to CQI),
consistent with every other real-data result in this project.

**Full-profile / block-profile k-means: the roadmap's hypothesis is NOT
supported.** Gains are tiny and inconsistent at mid dispersion and turn
negative at high dispersion -- the opposite of the roadmap's own go/no-go
criterion ("gains should concentrate at mid/high dispersion"). Keeping the
complete per-band shape as a k-means clustering key does not, by itself,
recover useful information CQI/cost miss.

**Overlap graph: consistently the worst method everywhere it isn't tied.**
Plausible mechanism (not exhaustively proven): Pearson correlation is
scale-invariant, so it can score two users with very different absolute
rate levels but similarly-shaped relative profiles as highly compatible
(observed directly: two users at CQI 12 and CQI 14 -- not an extreme gap --
had affinity 0.763), which is exactly backwards for a worst-case multicast
bottleneck that cares about absolute achievable rate, not profile shape.

**Exact-regret graph: after the fix, a real, narrow, mechanistically
understood win at high dispersion + heavy load.** Elsewhere it still loses
to CQI k-means (though by much smaller margins than the buggy version), so
the roadmap's "gains concentrate broadly at mid/high dispersion" criterion
is not met -- but a specific, well-diagnosed regime is.

## Mechanism, verified on 4 independent seed/snapshot cases

Case study (seed 4, snapshot 14, high dispersion, heavy load,
`rb_available=2` of 25 bands):

- CQI k-means groups `[2,5,6,6,6,7,7,7,7,8,8,8]` (12 users, CQI 2..8) into
  one group. Multicast rate is bottlenecked by the group's worst member (the
  single CQI=2 user), pushing the RBs needed for even the *lowest* video
  tier (200 kbps) to 5 -- over budget. The entire 12-person group goes
  unserved. Result: utility `-0.9104`, served ratio `50%`.
- The regret graph isolates the CQI=2 user into their own singleton group
  (they can't be served under this budget regardless of partner) and splits
  the remaining 23 users into two groups that are each independently
  feasible at the lowest tier. Result: utility `-0.0012`, served ratio
  `95.8%`.
- Reproduced with the same qualitative pattern (CQI k-means groups a
  low-CQI outlier with a "not obviously extreme" mid/low-CQI cluster; the
  regret graph isolates the outlier alone or in a minimal group) in three
  more independent seed/snapshot pairs: seed 10/snapshot 0, seed 3/snapshot
  10, seed 5/snapshot 13.

**Exact numbers behind the mechanism** (seed 4/snapshot 14's outlier):
`value_solo(outlier) = -2.0` (even alone, this user cannot reach the lowest
tier within the 2-RB budget). Paired with *any* other user `j`, `pair_value
= -4.0` regardless of `j`'s own channel (the pair's worst-case rate is
dominated by the outlier, so the whole pair goes unserved). Consequently
`regret(outlier, j) = value_solo(j) + 2.0` -- **the regret of pairing with
the outlier scales with how good the partner would have been alone**
(`2.1791` for CQI 5-8 partners, `2.3559` for CQI 10-14 partners). This
gives the outlier uniformly low graph affinity to nearly everyone, and
lowest affinity to the best-off users specifically -- exactly the structure
spectral clustering is designed to cut along, so it isolates the outlier at
near-zero cost to the rest of the partition.

**Why CQI k-means misses this and the regret graph doesn't:** CQI-to-
achievable-rate is highly nonlinear at the low end of the 3GPP CQI table
(`CQI_TO_EFF`: 0.1523 at CQI 1, still only ~0.6-1.9 by CQI 4-8). A gap of
2-6 CQI levels looks small on the linear 1-15 scale k-means clusters on, but
can be the difference between "needs 1 RB" and "needs 5+ RBs." k-means's
centroid-distance objective has no way to see this; the regret graph's edge
weights are built directly from `rb_needed`-checked feasibility, so they
encode the nonlinearity by construction. This is the concrete, empirical
version of the general point from this project's own methodology
discussion: k-means minimizes *average* distance to a centroid, but
multicast grouping's true objective is a *worst-case* (min-over-group)
bottleneck -- the two are not the same, and the mismatch is worst exactly
where a small linear-scale gap hides a large nonlinear feasibility cliff.

## Integrated as a third candidate family: CQI ∪ cost ∪ regret-graph union

`cqi_cost_regret_graph_hybrid_grouping` in `le_gra_mvp.py` unions the
existing real-data-validated CQI+cost 2-way union's candidates with the
regret graph's spectral-clustering candidates (k=1..Kmax each), and lets
`allocate_and_evaluate`'s exact-DP scoring pick the winner per scenario --
same design as every other hybrid method in this project.

| Dispersion | Load | 2-way (paper method) vs CQI | 3-way (+regret-graph) vs CQI | Regret-graph's own contribution |
|---|---|---:|---:|---:|
| low | all | +0.0000 | +0.0000 | +0.0000 |
| mid | light | +0.0055 | +0.0059 | +0.0004 |
| mid | medium | +0.0055 | +0.0060 | +0.0005 |
| mid | heavy | +0.0012 | +0.0021 | +0.0009 |
| high | light | +0.0121 | +0.0177 | +0.0056 |
| high | medium | +0.0088 | +0.0162 | +0.0074 |
| **high** | **heavy** | +0.0416 | **+0.0846** | **+0.0430** |

The 3-way union never scores below the 2-way union in any of the 9 cells --
the expected mathematical guarantee of a superset candidate pool, and a
useful sanity check that nothing regressed. High/heavy's margin over CQI
nearly doubles (`+0.0416` → `+0.0846`), and its seed-level win rate closes
from `9/10` to a clean `10/10`. Every other non-saturated cell also gets a
small additional gain, even ones where the regret graph *alone* lost to CQI
(high/light, high/medium) -- because the union only needs the regret graph
to win on the *specific scenarios* where it helps; elsewhere the pool falls
back to CQI/cost exactly as designed.

## Per-scenario attribution: which family the union actually picks, and where

Computed directly from the saved per-scenario CSV (which family's own
standalone utility matches the 3-way union's choice), 150 scenarios/cell
(10 seeds × 15 snapshots):

| Cell | CQI wins | Cost wins | Regret-graph wins | Tie |
|---|---:|---:|---:|---:|
| low (all) | 0% | 0% | 0% | 100% |
| mid/light | 37.3% | 16.0% | 8.0% | 38.7% |
| mid/medium | 28.0% | 11.3% | 6.0% | 54.7% |
| mid/heavy | 8.7% | 3.3% | 1.3% | 86.7% |
| high/light | 18.0% | **40.7%** | 26.7% | 14.7% |
| high/medium | 35.3% | 15.3% | 22.7% | 26.7% |
| **high/heavy** | 6.7% | 1.3% | **28.0%** | 64.0% |

Each family has a distinct, largely non-overlapping regime where it is the
single most-picked source: CQI is the general anchor and dominates at low
dispersion; resource-cost peaks at high dispersion + light load (matching
the mechanism already documented in project memory
`resource-cost-mechanism-finding`); the regret graph peaks specifically at
high dispersion + heavy load, where it is picked more often than CQI and
cost combined, and where its contribution accounts for over half of the
3-way union's total margin over CQI in that cell.

## Decision

Keep `cqi_cost_regret_graph_hybrid_grouping` as a validated third candidate
family for the real-data track's non-temporal (frequency-selectivity)
comparisons. Do not adopt `full_rb_profile_kmeans_grouping`,
`block_rb_profile_kmeans_grouping`, or `overlap_graph_grouping` -- none show
a defensible net benefit, and `overlap_graph_grouping` in particular has a
plausible, if not exhaustively proven, structural flaw (scale-invariant
correlation is the wrong notion of compatibility for an absolute-rate
bottleneck problem).

This is still a 10-seed exploratory result, not a confirmatory one -- no
fresh, untouched seed range has evaluated the 3-way regret-graph union yet
(seeds 11..30 are already "used" by the switching-gate confirmatory work).
Before treating this as a settled method, a confirmatory pass on a new seed
range, following the same freeze-then-test discipline as
`REAL_SIMU5G_CONDITIONAL_GATING.md`, is the natural next step -- not further
tuning on seeds 1..10.

Not yet done: combining this 3rd family with the switching-aware family
into a single non-temporal-and-temporal-aware union; testing whether the
regret graph's advantage holds under the full closed-loop protocol (this
whole investigation used snapshot-level, non-temporal evaluation to isolate
the frequency axis); confirmatory validation on new seeds.
