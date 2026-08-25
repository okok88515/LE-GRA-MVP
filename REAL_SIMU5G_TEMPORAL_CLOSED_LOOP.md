# Real Simu5G temporal closed-loop evaluation

Date: 2026-08-25

## Question

Does the candidate-union advantage survive when every method must live with
its own previous allocation decisions, instead of evaluating every snapshot
with `previous_quality = 0`?

## Protocol

- Input: `real_simu5g_multiseed_data/`
- 10 independent simulator seeds per CQI dispersion
- dispersions: low, mid, high
- loads: light, medium, heavy
- 15 adjacent snapshots per run
- snapshot 0: common warm-up from quality 0
- snapshots 1..14: primary closed-loop evaluation
- each method owns a separate `previous_quality` state
- served users advance to the exact DP allocation chosen at the current step
- unserved users retain their last delivered quality
- methods: CQI k-means, CQI+cost 2-way union, final
  CQI+cost+switching 3-way union
- the simulator seed/trajectory is the independent statistical unit
- 95% confidence intervals use 20,000 paired bootstrap resamples of the ten
  seed-level mean differences

The reported utility values are not directly comparable to the older
snapshot baseline's absolute values.  That baseline reset every snapshot to
quality zero; this experiment pays the warm-up transition once, then carries
the actual playback state forward.

Runner:

```powershell
python .\run_real_multiseed_temporal_closed_loop.py
```

## Final 3-way versus CQI k-means

| Dispersion | Load | Mean utility | Mean delta | Paired bootstrap 95% CI | Seed W/T/L |
|---|---|---:|---:|---:|---:|
| low | light | 0.92908 | 0.00000 | [0.00000, 0.00000] | 0/10/0 |
| low | medium | 0.74693 | 0.00000 | [0.00000, 0.00000] | 0/10/0 |
| low | heavy | 0.55518 | 0.00000 | [0.00000, 0.00000] | 0/10/0 |
| mid | light | 0.71681 | +0.02379 | [+0.01374, +0.03418] | 9/0/1 |
| mid | medium | 0.54371 | +0.02502 | [+0.01581, +0.03649] | 10/0/0 |
| mid | heavy | 0.26434 | +0.00280 | [+0.00060, +0.00548] | 5/5/0 |
| high | light | 0.40972 | +0.03406 | [+0.02614, +0.04167] | 10/0/0 |
| high | medium | 0.21465 | +0.01966 | [+0.01146, +0.03115] | 10/0/0 |
| high | heavy | -0.09817 | +0.04078 | [+0.02737, +0.05368] | 9/1/0 |

All six non-saturated mid/high cells have a positive seed-level bootstrap
interval.  High-heavy remains a poor absolute operating point (negative
utility because of the unserved penalty), but the union makes it materially
less poor than CQI alone.

## Temporal behavior

Compared with CQI k-means, the final 3-way reduces mean normalized quality
switch magnitude by approximately:

- mid: 35% (light), 41% (medium), 22% (heavy)
- high: 34% (light), 9% (medium), 20% (heavy)

It also reduces label-invariant pairwise group churn by approximately:

- mid: 47% (light), 40% (medium), 1% (heavy)
- high: 14% (light), 10% (medium), 10% (heavy)

The utility gain therefore is not merely a larger bitrate obtained by more
aggressive regrouping.  In most mid/high cells it coexists with smoother
quality and a more stable partition trajectory.

## What the third candidate adds beyond the 2-way union

The final 3-way minus 2-way mean utility differences are:

| Dispersion | Load | Mean delta | Paired bootstrap 95% CI | Seed W/T/L |
|---|---|---:|---:|---:|
| mid | light | -0.00010 | [-0.00359, +0.00250] | 5/4/1 |
| mid | medium | +0.00156 | [-0.00091, +0.00545] | 2/7/1 |
| mid | heavy | +0.00012 | [0.00000, +0.00036] | 1/9/0 |
| high | light | +0.00097 | [-0.00120, +0.00326] | 5/1/4 |
| high | medium | +0.00303 | [+0.00081, +0.00542] | 6/2/2 |
| high | heavy | +0.00187 | [0.00000, +0.00561] | 1/9/0 |

Only high-medium has a clearly positive 95% interval.  The main robust gain
over CQI comes from the CQI+cost candidate union; the switching-aware third
source is a smaller, regime-dependent refinement.

## Important closed-loop finding

Candidate-set containment guarantees that the 3-way cannot score below its
own CQI candidate when both are evaluated from the same state.  It does not
guarantee that a method-owned trajectory will dominate a separate CQI
trajectory, because different decisions create different future
`previous_quality` states.

That distinction is visible in mid/light seed 0006: the final 3-way's
post-warm-up mean is 0.70697 versus CQI's 0.71004 and the 2-way's 0.72052.
The final 3-way takes a different state path and suffers two later switching
events large enough to erase its earlier gain.  This is the one seed-level
loss versus CQI in the full experiment.

## Conclusion

The candidate-union result survives a real temporal closed loop: the final
3-way has a positive paired confidence interval against CQI in every
non-saturated dispersion/load cell, while usually reducing both quality
switching and group churn.  However, the stronger scientific conclusion is
not that the switching candidate is universally superior.  Most of the gain
comes from the 2-way CQI+cost union; the third source adds a statistically
clear increment only at high dispersion with medium load and can enter a
path-dependent trap on an individual seed.  A future temporal method should
therefore score short candidate trajectories or add hysteresis, not assume
that greedy per-step no-regret implies trajectory-level no-regret.

## Outputs

- `real_multiseed_temporal_closed_loop_results/per_transition_results.csv`
- `real_multiseed_temporal_closed_loop_results/per_seed_summary.csv`
- `real_multiseed_temporal_closed_loop_results/summary_across_seeds.csv`

Candidate-source attribution and the regime map are documented separately in
`REAL_SIMU5G_TEMPORAL_REGIME_ANALYSIS.md`.

The follow-up minimum-margin gate is documented in
`REAL_SIMU5G_CONDITIONAL_GATING.md`.
