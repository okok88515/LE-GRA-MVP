# Real Simu5G regret-graph under the temporal closed loop (research direction 2)

Date: 2026-08-26

## Question

`POST_CQI_RESEARCH_ROADMAP_ZH.md` direction 2: two users with the same
current CQI can be in very different playback states (`previous_quality`),
and forcing them into the same group can impose an uneven switching cost.
Rather than building a new switching-only regret metric from scratch, this
tests whether `pairwise_exact_regret_matrix` -- built for direction 1
(`REAL_SIMU5G_RB_PROFILE_DIRECTION.md`) to capture RB-feasibility regret --
already captures switching-state value once evaluated where it matters: the
temporal closed loop, where `previous_quality` genuinely diverges across
users over time. Direction 1's own evaluation never exercised this, since it
used snapshot-level scenarios with `previous_quality` reset to 0 for
everyone; `group_quality_value` (which the regret formula is built from)
already includes the `switch_beta`-weighted switching penalty against
`scenario.previous_quality`, so no new affinity metric was needed to ask
this question.

## Methods and protocol

Reuses `run_real_multiseed_temporal_closed_loop.py`'s validated closed-loop
machinery (imported, not copied -- its own output is untouched) with a new
method set, on real Simu5G seeds 1..10:

- `CQI k-means`, `CQI+cost 2-way union`, `CQI+cost+switching 3-way union`:
  the existing headline methods (`REAL_SIMU5G_TEMPORAL_CLOSED_LOOP.md`).
- `CQI+cost+regret-graph 3-way union` (`cqi_cost_regret_graph_hybrid_grouping`):
  direction 1's validated candidate family, tested here for the first time
  under real state divergence instead of snapshot-level `previous_quality=0`.
- `CQI+cost+switching+regret-graph 4-way union`
  (`cqi_cost_switching_regret_graph_hybrid_grouping`, new): both extra
  families unioned together, to test whether switching adds anything on top
  of the regret graph.

Reproduction:

```powershell
python .\run_real_multiseed_regret_temporal_direction.py
```

Exploratory only: seeds 1..10. Seeds 11..30 are already "used" by the
switching-gate confirmatory work (`REAL_SIMU5G_CONDITIONAL_GATING.md`).

## Result: the regret graph, without switching at all, beats the switching headline

Utility vs CQI k-means, and vs the existing `CQI+cost+switching 3-way union`
headline, seed-level paired 95% CI (20,000 bootstrap resamples):

| Dispersion | Load | Regret-3way vs CQI | Regret-3way vs switching-3way headline | Seed W/T/L vs headline |
|---|---|---:|---:|---:|
| low | all | +0.0000 | +0.0000 | tied |
| mid | light | +0.0271 `[+0.0168,+0.0380]` | +0.0034 `[-0.0005,+0.0075]` | 8/0/2 |
| mid | medium | +0.0257 `[+0.0181,+0.0359]` | +0.0007 `[-0.0039,+0.0036]` | 7/2/1 |
| mid | heavy | +0.0032 `[+0.0004,+0.0065]` | +0.0004 `[-0.0006,+0.0019]` | 1/7/2 |
| **high** | **light** | +0.0445 `[+0.0355,+0.0547]` | **+0.0105 `[+0.0047,+0.0164]`** | **9/0/1** |
| **high** | **medium** | +0.0414 `[+0.0298,+0.0547]` | **+0.0218 `[+0.0145,+0.0291]`** | **10/0/0** |
| **high** | **heavy** | +0.0840 `[+0.0587,+0.1077]` | **+0.0432 `[+0.0236,+0.0668]`** | **10/0/0** |

At every dispersion/load cell, `CQI+cost+regret-graph` (which has never seen
`previous_quality` do anything but sit at 0 in its only prior test) performs
at least as well against CQI as `CQI+cost+switching` does -- often with a
slightly higher point estimate even at mid dispersion, though those
mid-dispersion margins are not individually significant (the CIs overlap).
**At all three high-dispersion cells the improvement over the switching
headline is clearly significant**: the 95% CI on the head-to-head difference
is entirely positive in every one, and the seed win rate is 9-10 out of 10.

## Does adding switching on top of the regret graph help further? No, not meaningfully

`CQI+cost+switching+regret-graph 4-way union` vs the 3-way (regret-graph
only, no switching):

| Dispersion | Load | 3-way (regret only) | 4-way (regret + switching) | Difference |
|---|---|---:|---:|---:|
| high | light | +0.42018 | +0.42041 | +0.00023 |
| high | medium | +0.23643 | +0.23461 | -0.00182 |
| high | heavy | -0.05497 | -0.05437 | +0.00060 |

The 4-way's candidate pool is a strict superset of the 3-way (regret-only)'s
pool at every individual decision (same CQI/cost/regret-graph candidates,
same seeds, plus the switching family) -- but the 4-way scores *below* the
3-way at high/medium in this trajectory-level aggregate. This is not a
contradiction or a bug: `REAL_SIMU5G_TEMPORAL_CLOSED_LOOP.md` already
documents that per-step candidate-superset containment guarantees no regret
only from an *identical* prior state; two independently-run trajectories
accumulate different `previous_quality` histories from their different past
choices, so a wider candidate set at each step does not guarantee a better
whole trajectory. The practical read: switching's marginal value on top of
an already-present regret graph is negligible in both directions, consistent
with the mechanistic explanation that `group_quality_value`'s switching
penalty is already inside the regret computation -- the switching family is
not adding information the regret graph doesn't already have access to.

## Decision

**The evidence supports treating the regret graph as a replacement for the
switching-aware candidate family, not just an addition to it** -- at every
cell tested it matches or exceeds switching's own contribution, and clearly
beats it (not just ties it) at all three high-dispersion cells, while
`switching`'s marginal value on top of an already-present regret graph is
negligible.

**Not yet a final call**, for two reasons stated plainly:

1. This is still a 10-seed exploratory result. The switching gate itself
   (`eta=.020`) only became a trusted method after a dedicated confirmatory
   pass on 20 fresh, never-before-seen seeds
   (`REAL_SIMU5G_CONDITIONAL_GATING.md`). This result has not had that same
   scrutiny yet, and seeds 11..30 are already "used" for that other
   confirmatory purpose -- a genuine confirmatory pass for this claim needs
   its own untouched seed range.
2. The mid-dispersion advantage over the switching headline is directionally
   consistent but not individually statistically significant (all three
   mid-dispersion head-to-head CIs include zero) -- "at least as good, likely
   a bit better" is the honest claim there, not "clearly better."

**Recommended path, mirroring the precedent already set when the
joint[CQI,cost] family was dropped for negligible marginal contribution**
(`paper-hybrid-candidate-method` memory): keep `CQI+cost+switching 3-way
union` as the currently-shipped headline until this result is confirmatory-
validated, but record `CQI+cost+regret-graph 3-way union` as the leading
candidate to replace it, on the strength of a decisive, mechanistically
explained high-dispersion win and no observed downside anywhere. Do not
silently swap the shipped method on the strength of a 10-seed exploratory
result alone.

## Not yet done

- Confirmatory validation on a fresh, untouched seed range.
- A head-to-head cost comparison: the regret graph's spectral clustering
  (eigendecomposition of an n×n matrix per snapshot) is more expensive than
  switching's plain joint-coordinate k-means, though negligible in absolute
  terms at n=24 users.
- Testing whether combining the regret graph with direction 3 (short-term
  CQI trend) adds anything once switching-state and RB-feasibility are
  already both covered by one mechanism.
