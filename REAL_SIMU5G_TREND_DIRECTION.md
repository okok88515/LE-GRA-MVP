# Real Simu5G causal CQI-trend features (research direction 3, step 1)

Date: 2026-08-26

## Question

`POST_CQI_RESEARCH_ROADMAP_ZH.md` direction 3: two users at the same
current CQI can have opposite trajectories -- one improving (`[4,5,6,7,8]`),
one degrading (`[12,11,10,9,8]`). Snapshot CQI k-means treats them as
identical. This is step 1 of the roadmap's three-step plan for this
direction ("causal hand-crafted trend baseline") -- not the later next-step
predictor or multi-step teacher objective, which are separate, more
involved follow-ups not attempted here.

## Method

Three causal features computed only from the 5-step `cqi_history` already
present in every real Simu5G scenario, never looking past `cqi_now`
(`le_gra_mvp.py`):

- `cqi_trend_slope_vector`: least-squares slope over the history window.
- `cqi_trend_volatility_vector`: std of the history window.
- `cqi_trend_downside_deviation_vector`: semi-deviation of only the
  negative step-to-step diffs (distinguishes a symmetric oscillator from a
  user whose swings are mostly drops).

Tested standalone (each its own k-means candidate family), as a trend-only
union (CQI + all three, no cost/regret-graph/switching), and unioned on top
of the confirmatory-validated base from direction 2
(`cqi_cost_switching_regret_graph_hybrid_grouping`, the 4-way union that
strictly dominates the previous switching-only headline, see
`REAL_SIMU5G_REGRET_GRAPH_TEMPORAL_DIRECTION.md`). Snapshot-level,
non-temporal (`previous_quality` reset to 0 each snapshot), matching
direction 1's own first pass, since these are per-snapshot causal features,
not a temporal-closed-loop question.

Reproduction:

```powershell
python .\run_real_multiseed_trend_direction.py
```

Exploratory only: seeds 1..10. Seeds 11..30 and 31..50 are already used for
the switching-gate and direction-2 confirmatory passes respectively.

## Result 1: trend features alone are much worse than CQI k-means

Standalone trend k-means throws away current channel quality entirely, and
it shows -- a user "trending up" or "trending down" says nothing about
whether they're feasible *right now*. The damage grows with how tight the
RB budget is:

| Cell | Trend-slope k-means dCQI | Trend-volatility k-means dCQI |
|---|---:|---:|
| mid/light | -0.0190 | -0.0158 |
| mid/heavy | -0.0078 | -0.0079 |
| high/light | -0.0540 | -0.0695 |
| high/medium | -0.0378 | -0.0454 |
| **high/heavy** | **-0.0937** | **-0.0920** |

## Result 2: unioned with CQI, trend recovers to roughly matching CQI k-means, with one real standalone gain

`Trend-only union` (CQI + slope + volatility + downside, no cost/regret-
graph) never scores below CQI k-means by more than rounding noise anywhere,
and at high/heavy shows a genuine standalone gain: `dCQI=+0.0272`. This is
the one cell where trend information alone, combined with current CQI,
outperforms CQI alone -- the same regime (tightest RB budget) where
resource-cost and the regret graph also do their best work.

## Result 3: on top of the confirmatory-validated 4-way base, trend adds a small but real gain, concentrated in the same regime

`CQI+cost+switching+regret-graph+trend union` vs the 4-way base
(`cqi_cost_switching_regret_graph_hybrid_grouping`), seed-level:

| Cell | 5-way vs 4-way base | Seed W/T/L |
|---|---:|---:|
| mid/light | +0.0001 | 3/7/0 |
| mid/medium | +0.0006 | 4/6/0 |
| mid/heavy | +0.0001 | 2/8/0 |
| high/light | +0.0000 | 1/9/0 |
| high/medium | +0.0004 | 3/7/0 |
| **high/heavy** | **+0.0046** | **6/4/0** |

Zero losses anywhere -- this is snapshot-level evaluation, so unlike the
temporal closed loop the candidate-superset "union only gets better"
guarantee holds *exactly*, not just approximately. But the absolute gain is
small: the largest cell, high/heavy, is +0.0046 against a base utility
around -0.05, a real but minor effect. The gain concentrates in the same
cell where trend's own standalone contribution (Result 2) and the regret
graph's own strongest win (`REAL_SIMU5G_RB_PROFILE_DIRECTION.md`) both
concentrate.

## Interpretation

The pattern across all three results points to trend information being
largely redundant with what cost and the regret graph already capture, not
orthogonal to it. All three signals get strongest at the same regime (high
dispersion + heavy load, i.e. the tightest RB budget), and the mechanism
plausibly overlaps: a user with a degrading CQI trend is often *also* a user
whose current channel is already marginal (that's usually *why* it's
degrading), which cost and the regret graph already detect from the current
snapshot alone. Trend may be adding an early-warning version of the same
signal rather than new information the current-snapshot features miss
entirely -- consistent with the small but non-zero, same-regime-concentrated
gain observed here.

## Decision

**Not promoted to the recommended method.** The gain is real (never
negative, matches the union guarantee exactly at snapshot level) but small
(+0.0046 max) and exploratory (10 seeds, snapshot-level only). Per the
roadmap's own three-step plan for this direction, this causal
hand-crafted-feature baseline was always expected to be the weakest of the
three steps -- the next-step predictor and the multi-step
discounted-cumulative-utility teacher objective (steps 2-3) are more likely
to extract real value from temporal information, since they can use trend
to anticipate *future* infeasibility rather than only describing the past.
Whether to pursue those follow-ups, given the modest step-1 result, is an
open question for a future session.

## Not yet done

- Step 2: a causal next-step CQI/RB-profile predictor, reported separately
  from an oracle lookahead upper bound that uses real future CQI (not
  deployable, ceiling only).
- Step 3: reformulating the teacher objective as multi-step discounted
  cumulative utility with a regrouping penalty, rather than single-snapshot
  greedy.
- Testing trend under the real temporal closed loop (this pass was
  snapshot-level only, matching direction 1's own first pass) -- the union
  guarantee would no longer be exact there, per the trajectory-divergence
  caveat already documented for direction 2.
- Confirmatory validation on a fresh, untouched seed range, if step 1's
  modest result is judged worth carrying forward.
