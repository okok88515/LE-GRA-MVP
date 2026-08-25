# Real Simu5G temporal candidate-source regime analysis

Date: 2026-08-25

## Research question

The closed-loop experiment established that candidate union beats CQI in all
non-saturated cells, but it also showed that the third switching-aware source
adds only a small trajectory-level increment over CQI+cost.  This analysis
asks two narrower questions:

1. When does the switching family produce a grouping that CQI+cost cannot?
2. Does an immediate same-state improvement reliably survive into the future
   method-owned trajectory?

## Attribution protocol

For every transition on the final 3-way method's own real Simu5G trajectory,
the runner constructs the three candidate families separately:

- CQI k-means candidates
- resource-cost k-means candidates
- joint `[CQI, previous_quality]` switching candidates

Every candidate is scored with the same exact-DP allocator and utility.  The
strict marginal value of switching is

```text
best(CQI, cost, switching) - best(CQI, cost)
```

where both sides use the exact same pre-decision state.  This isolates source
value from the different states followed by the separately run 2-way and
3-way trajectories.

The attribution rerun reproduces all 1,350 production 3-way transition
utilities exactly (`max absolute error = 0`).

## How often switching is uniquely useful

There are 1,260 post-warm-up transitions: 420 low, 420 mid, and 420 high.

| Dispersion | Load | Strict switching wins | Rate | Mean marginal over all transitions |
|---|---|---:|---:|---:|
| low | light | 0 / 140 | 0.0% | 0.00000 |
| low | medium | 0 / 140 | 0.0% | 0.00000 |
| low | heavy | 0 / 140 | 0.0% | 0.00000 |
| mid | light | 12 / 140 | 8.6% | +0.00185 |
| mid | medium | 7 / 140 | 5.0% | +0.00396 |
| mid | heavy | 1 / 140 | 0.7% | +0.00012 |
| high | light | 22 / 140 | 15.7% | +0.00353 |
| high | medium | 17 / 140 | 12.1% | +0.00365 |
| high | heavy | 1 / 140 | 0.7% | +0.00157 |

Across the 840 mid/high transitions, switching is strictly best only 60 times
(7.1%).  It is a targeted source, not a generally dominant representation.
Heavy load contains only two strict wins in 280 transitions, and each heavy
cell's total gain is concentrated in one event.  The largest single event is
high/heavy seed 0002 step 6 (`+0.22033`), so the heavy-load mean should not be
described as a broad switching effect.

## Main regime variable: previous-quality heterogeneity

`previous_quality_std` is the dominant explanatory feature:

- in 404 mid/high transitions with nearly homogeneous previous quality, there
  are zero strict switching wins
- in the top previous-quality-dispersion quartile, switching wins 44/218
  transitions (20.2%) with mean marginal `+0.00720`
- the shallow descriptive tree assigns 89.9% of its total feature importance
  to `previous_quality_std`
- CQI standard deviation contributes 7.6%; immediate CQI temporal change
  contributes 2.5%

This matches the mechanism.  When every user has the same previous quality,
the switching representation's second axis is constant and cannot add a new
partition.  Once playback states diverge, it becomes a genuinely new source
of grouping information.

Two secondary patterns are useful:

1. Switching wins peak at moderate/high CQI dispersion, not at the absolute
   maximum CQI dispersion.
2. The lowest CQI-cost rank-disagreement quartile has the highest switching
   strict-win rate (12.9%, versus 2.9% in the highest-disagreement quartile).
   When CQI and cost already disagree, cost supplies an alternative partition;
   when they are redundant, previous quality is the more novel third axis.

## How predictable is the regime?

A depth-3 decision tree was evaluated with leave-one-simulator-seed-out CV.
All loads and radio-power variants sharing a mobility seed were held out
together.

- positive prevalence: 7.1%
- ROC AUC: 0.776
- average precision: 0.164 (2.3 times the 0.071 prevalence baseline)
- at threshold 0.5: precision 0.142, recall 0.750, balanced accuracy 0.700

The decision features contain real cross-seed signal, but precision is too low
to call this a deployment-ready selector.  It is presently a regime map and a
safe screening rule, not a replacement for exact candidate evaluation.

The simplest descriptive rule is:

```text
if previous_quality_std <= 0.238:
    switching candidate has no observed unique value
elif previous_quality_std is moderate:
    value appears mainly when cqi_std > 2.32
else:
    switching becomes materially more likely to help
```

The numerical thresholds are exploratory and must not be frozen from only ten
seeds without out-of-sample confirmation.

## Immediate gain versus trajectory value

The same-state switching marginal is always non-negative by construction, but
the independent 3-way trajectory may later enter a less favorable playback
state.  The clearest aggregate example is mid/light:

- immediate same-state switching marginal: `+0.00185`
- full 3-way trajectory minus independent 2-way trajectory: `-0.00010`

Among strict switching events that have a following transition, the next-step
3-way-versus-2-way gap falls below its pre-event level in:

- mid/light: 5/12
- mid/medium: 4/7
- high/light: 11/21
- high/medium: 6/15

This is descriptive rather than a causal counterfactual because the two
methods may already have different states before the event.  Nevertheless,
the repeated erosion explains why positive greedy candidate gains translate
into much smaller trajectory-level gains and why mid/light can reverse sign.

## Conclusion

The third source is scientifically justified, but its role is narrower than
the original 3-way headline suggested:

> CQI+cost is the robust core.  Switching is a temporal refinement whose
> unique value emerges when users already occupy heterogeneous playback
> states, especially at mid/high CQI dispersion and non-heavy load.

The next algorithmic test should not add another representation.  It should
compare the current greedy 3-way against a temporal gate or short lookahead:

- require a minimum switching marginal before accepting the third source;
- or score the current candidate plus a predicted next-step utility;
- always keep CQI+cost as the fallback.

The main target is to retain high-medium gains while preventing mid-light
path traps.  Thresholds or gates must be selected with simulator-seed-level
cross-validation, not on individual adjacent transitions.

This experiment has now been run.  See
`REAL_SIMU5G_CONDITIONAL_GATING.md`: the LOSO conditional gate improves over
the 2-way core on the pooled mid/high trajectories, but ten seeds do not yet
stabilize the threshold well enough to remove the mid/light seed-0006 path
trap in every fold.

## Reproduction

```powershell
python .\run_real_multiseed_temporal_regime_analysis.py
python .\analyze_real_multiseed_temporal_regimes.py
```

Outputs are in `real_multiseed_temporal_regime_results/`:

- `per_transition_attribution.csv`
- `cell_summary.csv`
- `feature_quartile_summary.csv`
- `regime_tree_cv_summary.csv`
- `regime_tree_feature_importance.csv`
- `regime_tree_rules.txt`
- `strict_event_path_summary.csv`
- `switching_gain_concentration.csv`
