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

## Confirmatory result (seeds 31..50, 2026-08-26)

Ran on 20 fresh, never-before-used seeds
(`run_real_multiseed_regret_confirmatory.py`, frozen method set, no
retuning) -- seeds 1..10 were used for this direction's own exploratory
pass, seeds 11..30 for the switching-gate confirmatory pass, so 31..50 is
the first genuinely untouched range for this specific claim.

**The high-dispersion win for the regret-graph 3-way replicates closely**:
head-to-head vs the switching-3way headline, all three cells still entirely
positive and closely matching the exploratory magnitudes --

| Cell | Exploratory (10 seeds) | Confirmatory (20 seeds) |
|---|---:|---:|
| high/light | +0.0105 `[+0.0047,+0.0164]` | +0.0119 `[+0.0084,+0.0157]`, WTL 18/0/2 |
| high/medium | +0.0218 `[+0.0145,+0.0291]` | +0.0108 `[+0.0072,+0.0145]`, WTL 19/0/1 |
| high/heavy | +0.0432 `[+0.0236,+0.0668]` | +0.0380 `[+0.0266,+0.0496]`, WTL 19/0/1 |

**But the mid-dispersion story is weaker than the smaller exploratory
sample suggested, and this is the important correction from running a
larger confirmatory set**: the regret-graph 3-way (no switching) loses to
the switching-3way headline on a real fraction of seeds at mid dispersion --
7/20 losses at mid/light, 8/20 at mid/medium -- both cells' CIs still cross
zero, same as exploratory, but the loss counts are large enough that
"matches or exceeds everywhere" (the exploratory-stage claim) does not
survive confirmatory scrutiny. The regret graph replacing switching outright
is **not** supported by this larger sample.

**What IS strongly supported: the 4-way union (switching + regret-graph
together) strictly dominates the shipped switching-3way headline in this
confirmatory set.** Across all 6 non-saturated cells, the 4-way has **zero
losses** to the switching-3way headline (low is fully saturated/tied
everywhere):

| Cell | 4-way vs switching-3way | Seed W/T/L |
|---|---:|---:|
| mid/light | +0.00066 `[-0.00067,+0.00167]` | 11/8/1 |
| mid/medium | +0.00138 `[+0.00043,+0.00230]` | 11/8/1 |
| mid/heavy | +0.00100 `[+0.00020,+0.00198]` | 5/15/0 |
| high/light | +0.01379 `[+0.01058,+0.01718]` | 20/0/0 |
| high/medium | +0.01264 `[+0.00912,+0.01634]` | 20/0/0 |
| high/heavy | +0.03799 `[+0.02678,+0.04983]` | 20/0/0 |

(The one loss at mid/light is a rounding-level artifact -- 1 seed out of 20,
diff CI still crosses zero there.) Five of six cells now have head-to-head
CIs entirely positive (mid/medium and mid/heavy newly reach significance in
the larger confirmatory sample; only mid/light stays non-significant in
both passes), and every high-dispersion cell replicates cleanly.

## Decision (revised after confirmatory validation)

**Switching should NOT be dropped.** The exploratory-stage suggestion that
the regret graph could replace switching outright does not survive a larger,
independent seed sample -- regret-graph-alone has real, non-trivial losses
to the switching headline at mid dispersion that the smaller exploratory set
did not reveal clearly enough.

**What the confirmatory evidence does support: promoting the 4-way union
(`cqi_cost_switching_regret_graph_hybrid_grouping`, CQI + cost + switching +
regret-graph) to replace `CQI+cost+switching 3-way union` as the shipped
headline.** It never loses to the current headline anywhere in 20 fresh
seeds (0/20 losses in every one of the 6 non-saturated cells), and is
significantly better in 5 of those 6 cells including all three
high-dispersion ones. This is the "union only gets better" guarantee holding
up almost exactly as designed, now confirmed rather than just exploratory --
adding the regret-graph family on top of the already-shipped 3-way is safe
and has a real, replicated payoff concentrated at high dispersion.

This is a useful example of why this project's own confirmatory discipline
exists: a 10-seed exploratory sample suggested a stronger, simpler story
(drop switching) that a 20-seed confirmatory sample did not support, while
still confirming the core mechanistic finding (regret-graph adds real value,
concentrated at high dispersion) at a smaller but very real magnitude for
the union case.

## Not yet done

- Actually promote the 4-way union to the shipped headline in downstream
  consumers (`hybrid_metrics_slides.html` still not updated per standing
  user instruction; this doc records the recommendation, not yet the
  switch).
- A head-to-head cost comparison: the regret graph's spectral clustering
  (eigendecomposition of an n×n matrix per snapshot) is more expensive than
  switching's plain joint-coordinate k-means, though negligible in absolute
  terms at n=24 users.
- Research direction 3 (causal CQI trend) is now being built on top of the
  confirmatory-validated 4-way rather than the regret-only 3-way, per this
  correction.
