# Real Simu5G scale pilot: does the regret-graph finding replicate at N=40?

Date: 2026-08-27

## Question

`REAL_SIMU5G_SCALE_PILOT.md` finalized a validated, QA-passed 10-seed
real-data batch at N=40 users (up from the original 24), after a
multi-stage investigation into why the original "at least 100" target
wasn't achievable at this pipeline. With that data in hand, the natural
next question: do this project's already-validated method-family findings
-- specifically the regret-graph's advantage over CQI+cost, and
switching's lack of contribution at snapshot level -- replicate at this
new scale, or was N=24 doing something special?

## Method

`run_real_multiseed_scale_pilot_comparison.py`, mirroring direction 1's
own snapshot-level (non-temporal, `previous_quality=0` each snapshot)
methodology exactly. Five methods, in the order this project's history
introduced them: CQI k-means, the paper's CQI+cost 2-way union, the
once-shipped CQI+cost+switching 3-way headline,
`cqi_cost_regret_graph_hybrid_grouping` (direction 1's regret-graph 3-way),
and `cqi_cost_switching_regret_graph_hybrid_grouping` (direction 2's
confirmatory-validated 4-way, the current best-evidenced method at the
original N=24 scale). Real Simu5G seeds 1..10 at N=40
(`real_simu5g_scale_pilot_multiseed_data/`), all three dispersions, all
three loads.

## Result 1: switching contributes exactly nothing here -- expected, not a bug

At every one of the 9 (dispersion, load) cells, the switching-3way headline
scores byte-for-byte identical to the plain 2-way union, and the 4-way
scores byte-for-byte identical to the regret-graph 3-way. This is the
correct, expected behavior at snapshot level: `previous_quality` is reset
to 0 for every user in every scenario here, so the switching family's
joint `[CQI, previous_quality]` coordinate carries zero real information --
`best_candidate_groups` never selects a switching candidate because it never
scores better than the same-information CQI-only candidate. This confirms
the candidate-union machinery is choosing correctly, not that switching is
broken.

## Result 2: the regret-graph's advantage over CQI+cost replicates -- and is *larger* at N=40, especially at high dispersion + heavy load

| Dispersion | Load | 2-way union vs CQI | Regret-graph 3-way vs CQI | Regret-graph vs 2-way union | Seed W/T/L (regret vs 2-way) |
|---|---|---:|---:|---:|---:|
| low | light | +0.0009 | +0.0009 | +0.0000 | 0/10/0 |
| low | medium | +0.0008 | +0.0008 | +0.0000 | 0/10/0 |
| low | heavy | +0.0094 | +0.0094 | +0.0000 | 0/10/0 |
| mid | light | +0.0095 | +0.0102 | +0.0008 | 0/6/4 |
| mid | medium | +0.0152 | +0.0168 | +0.0015 | 0/5/5 |
| mid | heavy | +0.0079 | +0.0146 | +0.0067 | 0/5/5 |
| high | light | +0.0122 | +0.0122 | +0.0000 | 0/10/0 |
| high | medium | +0.0041 | +0.0079 | +0.0038 | 0/4/6 |
| **high** | **heavy** | **+0.1067** | **+0.1807** | **+0.0740** | **0/2/8** |

(The "seed W/T/L" column is signed the same direction as the difference
column -- read it as 2-way's record against regret-graph, so a high
loss-count means regret-graph wins most seeds. Low dispersion is
saturated, as expected, matching every prior finding at N=24.)

At high dispersion + heavy load -- the regime direction 1's original
mechanism analysis identified as where regret-graph's outlier-isolation
matters most -- the margin over the 2-way union is **+0.074**, roughly
double-digit-percent of the base utility scale there, and regret-graph
wins 8 of 10 seeds outright (2 ties, 0 losses). At N=24, the equivalent
finding (`REAL_SIMU5G_RB_PROFILE_DIRECTION.md`) was a real but comparatively
modest edge. The scale pilot's own history predicted exactly this
direction: `dispersion-and-scale-calibration`'s synthetic-data finding is
that more users mechanically raises the probability that at least one
severely bad-channel outlier exists in a given snapshot, and that is
precisely the condition regret-graph's feasibility-aware edge weights
detect and CQI's linear-distance clustering misses. N=40 gives that
mechanism more raw material to work with than N=24 did, and the data bears
that out directly rather than just plausibly.

## Decision

This is a genuine, mechanistically-expected replication, not a
coincidence -- it ties together three separate findings from this
project's real-data track (regret-graph's mechanism from direction 1,
switching's lack of standalone value at snapshot level from direction 2's
early analysis, and the scale-effect prediction from the original
synthetic dispersion/scale calibration work) into one consistent picture at
a new, independently-generated scale. Still exploratory (10 seeds, the only
seeds this scale has ever had) -- no confirmatory claim is being made here,
consistent with the project's standing rule that these same 10 seeds
cannot later be reused as an untouched confirmatory set for this specific
comparison.

## Not yet done

- Confirmatory validation on a fresh, untouched seed range at N=40 (would
  need new Simu5G generation at this scale).
- Temporal closed-loop evaluation at N=40 (this pass was snapshot-level
  only, matching direction 1's own first pass at N=24) -- the
  5-consecutive-second usable windows this scale achieves are temporally
  contiguous, so this is plausible future work, but not attempted here.
- Direction 3's trend features have not been tested at this scale.

## Reproduction

```powershell
python .\run_real_multiseed_scale_pilot_comparison.py
```

Results: `real_multiseed_scale_pilot_comparison_results/`.
