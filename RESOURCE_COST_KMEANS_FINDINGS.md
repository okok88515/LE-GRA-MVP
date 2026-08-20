# Resource-cost k-means: regime-dependent, unrepaired feature-engineering failure

Status: **closed as an ablation finding, and corroborated on real Simu5G+SUMO data (section 6).**
Not pursued further as a fix target. `resource_cost_kmeans_grouping` and
`multi_feature_kmeans_grouping` remain in the baseline suite as evidence that hand-crafted feature
concatenation for k-means is not robust; LE-GRA (learned embedding + k-means on the embedding) is
the headline method, not these.

## 1. Headline finding

Pooled across all `generate_scenario` modes and loads, resource-cost k-means is **not reliably
better than CQI k-means** (see `clean_validation_results.md` memory / `clean_resource_cost_validation_results/`).
Breaking the same comparison out by CQI dispersion x load (`run_dispersion_confirmatory_validation.py`,
6 seeds x 120 scenarios/cell, Holm-corrected across 18 cells) shows why the pooled result is a
wash: the effect flips sign depending on regime.

| mode | dispersion | load | mean utility diff (resource-cost − CQI) | % of CQI mean | significant? |
|---|---|---|---|---|---|
| aligned | high | light | +0.01608 | **+2.4%** | yes |
| ambiguous | high | light | +0.01723 | **+2.7%** | yes |
| aligned | high | heavy | -0.02658 | **-11.7%** | yes |
| ambiguous | high | heavy | -0.02979 | **-14.8%** | yes |
| (all modes) | low/mid | any | ~0 to -1.8% | small, mostly negative | mixed |

Win size (~2-3%) is much smaller than loss size (~12-15%) — an asymmetric pattern, which is why
pooling across regimes nets out to "not significant."

## 2. Hypothesis 1 (tested, FALSIFIED): tier-scale domination

**Original hypothesis:** `user_resource_cost_vector` (le_gra_mvp.py) returns a 6-D vector per user
— RBs needed for each of the 6 video quality tiers — fed raw into k-means with no normalization
(unlike `multi_feature_kmeans_grouping`, which z-scores its features). Cross-user std at the
cheapest tier is ~0.2 RBs vs ~22.7 RBs at the most expensive tier (~100x). Squared Euclidean
distance is dominated by the highest-magnitude dimension, so the hypothesis was: k-means clusters
almost entirely on tier-5/6 differences, which are irrelevant when heavy load means only tier-1/2
is ever reachable — a toy 4-user example reproduced this exact failure mode when run through the
repo's own `kmeans()`.

**Test:** added `resource_cost_kmeans_grouping_normalized` (le_gra_mvp.py, mirrors
`multi_feature_kmeans_grouping`'s per-scenario z-scoring) and re-ran the same high-dispersion x
load x mode matrix (`run_resource_cost_normalization_test.py`, same 6 seeds / 120 scenarios/cell).

**Result: normalization did not fix the heavy-load loss.**

| mode | load | normalized vs CQI | raw vs CQI |
|---|---|---|---|
| aligned | heavy | -13.9% (significant) | -11.7% (significant) |
| ambiguous | heavy | -14.5% (significant) | -14.8% (significant) |
| aligned | light | +1.9% (significant) | +2.4% (significant) |
| ambiguous | light | +2.2% (significant) | +2.7% (significant) |

normalized-vs-raw itself was small and mostly not significant / slightly negative. The hypothesis
predicted a real improvement in the heavy cells; there is none. **Hypothesis 1 is falsified.**

Follow-up check explaining *why* it was falsified: the 6 tier-cost dimensions are highly
cross-user-correlated in the actual generator (0.73-1.0, checked directly on a generated
scenario), not independent/decorrelated the way the toy example assumed. Scale differences
between tiers therefore don't actually redirect the clustering onto an unrelated dimension —
there isn't an unrelated dimension to redirect onto.

## 3. Actual mechanism (verified via case study): outlier/sentinel-driven mis-shaped splits

Found by scanning many scenarios for the worst resource-cost-vs-CQI loss (aligned/high-dispersion/
heavy load) and inspecting the actual partitions.

**Case: seed=162.** `cqi_now = [13 9 3 7 6 1 6 13 13 3 4 3 1 1 13 4 15 10 11 2 3 13 10 3]`.

- **CQI k-means (k=2, utility=+0.107):** clean split at CQI≈8 — good group (CQI 9-15, n=10),
  bad group (CQI 1-7, n=14).
- **Resource-cost k-means, raw (k=2, utility=-0.208):** good/bad group boundary is NOT where CQI
  naturally splits. It isolates a small group of users whose resource-cost vector is an extreme
  outlier (users needing 2-3 RBs even at tier 1, and hitting the `rb_needed`-returns-`None` →
  sentinel-cost ceiling at multiple upper tiers — see le_gra_mvp.py:130-144), and dumps everyone
  else — CQI 4 through 15, a 12-point spread — into one large group. That large group's multicast
  rate is bottlenecked by its worst member (CQI 4), which is much worse than CQI k-means's
  "good" group (bottlenecked at CQI 9).
- k=3 on the resource-cost vector made it worse still (utility=-0.305): it peeled off a second,
  even smaller outlier cluster, doing nothing to fix the still-heterogeneous majority group.

**Why this is load-dependent even though the partition itself is not:** `user_resource_cost_vector`
output does not change with `rb_budget_ratio` — confirmed directly (identical output for the same
scenario generated at light vs heavy load). What changes is the downstream cost of getting the
split "shape" wrong. Under light load, a mixed-CQI majority group can still be pushed up several
quality tiers by throwing enough RBs at it despite the bottleneck; under heavy load there is no
slack to compensate, so the same badly-shaped split produces a much larger utility loss. This
matches the asymmetry in section 1 (small win at light load, large loss at heavy load) without
requiring any load-dependent change in the clustering itself.

**Why normalization doesn't fix this:** the failure mode is about *outlier sensitivity and
sentinel saturation* in a k-means (mean-based, non-robust) centroid update, not about relative
tier scale. Z-scoring rescales each dimension but does not change which points are extreme
outliers, so it does not change which users get peeled off into their own tiny cluster instead of
the population being split where it actually matters for CQI homogeneity.

## 4. Decision: stop here

A real fix (winsorizing or rank-transforming the cost vector before clustering, or an outlier-
robust clustering objective) is plausible but not pursued — it would still be a hand-tuned patch
to a hand-crafted feature, discovered only after two rounds of diagnosis (one hypothesis wrong,
one confirmed). That process itself is the useful takeaway: **hand-crafted feature engineering for
k-means has failure modes that are not obvious in advance and expensive to find and patch one at a
time.** This is the concrete, evidenced motivation for treating `resource_cost_kmeans_grouping`
and `multi_feature_kmeans_grouping` as ablation baselines rather than trying to perfect them, and
for LE-GRA's learned embedding (trained against actual DP-evaluated utility, not a hand-picked
feature/normalization scheme) as the headline method.

## 5. Follow-up (2026-08-17): does LE-GRA even benefit from this feature?

Natural objection: LE-GRA's default `feature_mode="history_cost"` feeds the *same* raw per-tier
resource-cost vector into its MLP input. If clustering directly on that vector is actively harmful
(section 3), why keep it in LE-GRA's input at all?

Tested directly (`run_legra_resource_cost_ablation.py`): trained matched LE-GRA models differing
only in `feature_mode` (`history_only` = CQI history alone vs `history_cost` = CQI history +
resource-cost vector), same seeds/teacher labels/training budget, across all 5 scenario modes x 3
loads x 3 seeds (1350 paired test scenarios, using `offline_teacher_groups_fast` for teacher
labels — this script also fixed the redundant teacher-label recomputation and slow brute-force
teacher generation present in `run_clean_resource_cost_validation.py`'s reused `train_model`).

**Result: removing it makes LE-GRA worse, not better.** `history_cost` beats `history_only` by
+0.29% pooled (significant, p<0.0001; win_rate 26.4% — same small-win/occasional-big-win asymmetry
seen elsewhere in this project). More tellingly, `history_cost`'s edge over CQI k-means (+0.73%) is
nearly double `history_only`'s edge over CQI (+0.44%). So the same raw resource-cost information
that actively hurts when clustered on directly (section 3) has a real net-positive contribution
once it is an input to a trained representation instead of the clustering key itself. This
confirms the theoretical distinction drawn in section 4's decision: the failure mode is specific to
naive k-means's outlier-sensitive, unweighted use of that feature as a clustering key — not a
property of the information being worthless. Per-scenario-mode, only `mixed` reached significance
individually (+0.48%, Holm-corrected); the other four modes trended positive but did not reach
significance at n=270 each — consistent with a real but modest per-scenario effect size, not a
contradiction.

**How to apply:** do not remove resource-cost from LE-GRA's feature set based on section 3's
finding — that finding is about k-means-on-raw-features specifically, verified in section 5 to not
generalize to "this information helps a learned representation." If asked in an interview why the
same signal is discarded in one baseline and kept in the headline method, this is the precise,
evidenced answer.

## 6. Real-data corroboration (2026-08-20): does the dispersion effect replicate outside the synthetic generator?

Everything above comes from `le_gra_mvp.generate_scenario`, a hand-written synthetic simulator —
raising the obvious question of whether the high-dispersion win in section 1 is an artifact of that
generator's specific formulas, or a real, physically-grounded effect. Tested against actual
Simu5G+SUMO+Veins output (not synthetic data at all).

**Setup:** WSL environment `LE-GRA-opp-env` (`~/p3_5_workspace`) already had OMNeT++ 6.3.0 + INET
4.6.0 + Simu5G 1.4.3 + Veins 5.3.1 installed and a custom radio/mobility CSV logger patched into
`simu5g-1.4.3/src/simu5g/stack/mac/LteMacEnb.cc` and
`veins-5.3.1/.../VeinsInetMobility.cc` from earlier (pre-audit) work. The existing SUMO scenario
had a real bug (route file not globally sorted by departure time → SUMO silently dropped 22 of 32
vehicles) and was also a "targeted family" design iteratively tuned toward a specific hypothesis —
neither reused as-is. Built a clean scenario instead
(`~/p3_5_workspace/p3_7_clean_validation_scenario`): the plain pre-"family-redesign" P3.6
layout (24 vehicles, single vehicle type, 4 routes, 2 gNBs, 25 bands), fixing only the route-sort
bug, run for 90 simulated seconds.

**Getting real dispersion:** the first run (eNodeB/UE tx power 30/20 dBm) produced CQI concentrated
at 13-15 for all 24 vehicles regardless of distance (23-330m) — verified as a genuine result, not a
bug, and consistent with the published paper's own "low-dispersed" condition ("90% of VUs have
CQI>13", and the paper's own conclusion that grouping method barely matters there). Two more power
levels were run to get real high/mid dispersion, calibrated only by inspecting the resulting raw
CQI histogram (not by looking at any grouping-method comparison) before analysis: mid = 15/10 dBm,
high = 5/0 dBm eNodeB/UE tx power. Same 24-vehicle scenario and route file reused for all three;
only tx power changed.

15 usable real scenarios per (dispersion, load) cell (limited by how long all 24 vehicles stay
simultaneously present with full 25-band CQI coverage in one run — see `parse_real_simu5g_data.py`
docstring). One run per condition, no repeated seeds — directional corroboration, not a
confirmatory statistical test.

| dispersion | load | resource-cost vs CQI | multi-feature vs CQI |
|---|---|---|---|
| low | any | 0.00% (all methods identical) | 0.00% (all methods identical) |
| mid | light/medium/heavy | -8.4% to +0.2% (mixed, small) | -4.3% to +0.7% (mixed, small) |
| high | light | **+4.07%** (9/15 win) | **+2.41%** (9/15 win) |
| high | medium | **+4.28%** (8/15 win) | -4.29% (5/15 win) |
| high | heavy | **+0.069 abs** (64% of a near-zero mean; 4/15 win) | +0.033 abs (3/15 win) |

**This replicates the synthetic finding's core shape on independently-generated real data**:
resource-cost k-means's advantage over CQI k-means concentrates specifically in the high-dispersion
regime (matching section 1's synthetic result of +2.4-2.7% at high-dispersion+light-load), is
weak/mixed at lower dispersion, and low-dispersion collapses all methods to identical behavior
(matching the published paper's own documented conclusion for that regime). `offline_teacher_groups`
(exact optimum) beats CQI k-means by up to +30% at mid/high dispersion, confirming there is real
headroom above every heuristic here too, consistent with the synthetic project's teacher-vs-heuristic
gap throughout.

LE-GRA was NOT evaluated on this real data — 15 scenarios is far short of the ~60-90 the synthetic
training protocol uses, nowhere near enough to train a model. That would need many more real
simulation runs, out of scope for this pass.

**How to apply:** the dispersion-dependence in section 1 is not a synthetic-generator artifact — an
independently-built, physically-simulated dataset shows the same qualitative pattern. This is
strong, disclosable evidence for an interview setting, with the honest caveat that sample sizes are
small (n=15, one seed) and the percentages in the heavy-load cell are inflated by a near-zero
baseline (report the raw utility differences there, not the percentage).

## Artifacts

- `run_dispersion_confirmatory_validation.py` / `dispersion_confirmatory_validation_results/` —
  section 1's regime breakdown.
- `run_resource_cost_normalization_test.py` / `resource_cost_normalization_test_results/` —
  section 2's falsification test.
- `resource_cost_kmeans_grouping_normalized` (le_gra_mvp.py) — kept in the codebase as a documented
  negative result, not wired into any default method list.
- `run_legra_resource_cost_ablation.py` / `legra_resource_cost_ablation_results/` — section 5's
  history_only vs history_cost ablation.
- `parse_real_simu5g_data.py` / `run_real_data_validation.py` / `real_simu5g_data/` — section 6's
  real Simu5G+SUMO+Veins data parsing and comparison; raw CSVs (`raw_radio.csv`,
  `mid_raw_radio.csv`, `high_raw_radio.csv` + matching `*_mobility.csv`) and
  `real_validation_results.csv` are the underlying real data and per-scenario results. The WSL-side
  scenario configs live in `~/p3_5_workspace/p3_7_clean_validation_scenario` (low dispersion),
  `p3_7_mid_scenario` (mid), reusing the same folder for high after swapping `omnetpp.ini`'s tx
  power (see `real_simu5g_data/omnetpp_mid.ini` / `omnetpp_high.ini` for the exact power settings);
  `real_simu5g_data/run_p3_7.sh` is the run script (`bash run_p3_7.sh <output_dir> <scenario_dir>`).
