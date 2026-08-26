# Real Simu5G conditional switching-gate experiment

Date: 2026-08-26

## Question

The temporal attribution study found that the switching-aware candidate is
strictly useful in only a small subset of transitions and that a positive
same-state gain can create a worse future playback-quality path.  This
experiment tests whether switching should be retained conditionally rather
than included in every candidate pool.

## Gate and fair protocol

CQI+resource-cost is always the fallback.  At each decision state, the exact
DP allocator separately scores the best 2-way candidate and the best
switching candidate.  Switching is selected only if

```text
U(best switching candidate) - U(best CQI/cost candidate) > eta
```

Every eta follows its own closed-loop `previous_quality` state; the gate is
not retroactively applied to the always-on trajectory.  The evaluated grid is
`eta = {0, .005, .010, .020, .030, .050, infinity}`.  `eta=0` is always-on
3-way selection and `eta=infinity` is the 2-way fallback.

The deployment eta is selected with leave-one-seed-out cross-validation.  A
seed number is held out jointly across all three dispersions and all three
loads, and one global eta is chosen from the other nine seeds.  Therefore no
dispersion/load cell or adjacent transition receives its own tuned threshold.

Endpoint validation passed exactly over all 1,350 transitions per endpoint:

- `eta=0` versus the production 3-way: maximum absolute utility error 0
- `eta=infinity` versus the production 2-way: maximum absolute utility error 0

## Primary out-of-seed result

The LOSO conditional gate versus the 2-way fallback is:

| Dispersion | Load | Mean delta | Paired bootstrap 95% CI | Seed W/T/L | Gate rate |
|---|---|---:|---:|---:|---:|
| low | light | 0.000000 | [0.000000, 0.000000] | 0/10/0 | 0.0% |
| low | medium | 0.000000 | [0.000000, 0.000000] | 0/10/0 | 0.0% |
| low | heavy | 0.000000 | [0.000000, 0.000000] | 0/10/0 | 0.0% |
| mid | light | -0.000569 | [-0.003894, +0.001847] | 2/7/1 | 5.0% |
| mid | medium | +0.001419 | [-0.001053, +0.005311] | 1/8/1 | 4.3% |
| mid | heavy | 0.000000 | [0.000000, 0.000000] | 0/10/0 | 0.0% |
| high | light | +0.002668 | [+0.000382, +0.005488] | 5/4/1 | 7.1% |
| high | medium | +0.002418 | [+0.000807, +0.004328] | 6/4/0 | 6.4% |
| high | heavy | +0.001871 | [0.000000, +0.005614] | 1/9/0 | 0.7% |

Pooling the six mid/high cells at the seed level, conditional gating improves
over 2-way by `+0.001301`, with paired 95% CI
`[+0.000542, +0.002176]` and seed W/T/L `9/1/0`.  It also continues to beat
CQI k-means: pooled mid/high delta `+0.024411`, CI
`[+0.020382, +0.028432]`, W/T/L `10/0/0`.

Against always-on 3-way, the pooled mid/high delta is only `+0.000060`, with
CI `[-0.000110, +0.000241]`.  The experiment therefore establishes that a
small conditional switching contribution improves the 2-way core, but it
does not establish a statistically clear overall advantage of gating over
always-on 3-way.

The gate admitted switching on 33/1,260 post-warm-up decisions (2.62%), versus
61/1,260 (4.84%) strict admissions at `eta=0`.  Thus about half the greedy
switching activations can be removed without reducing pooled utility.

## Threshold stability and the remaining failure

Nine of ten LOSO folds select `eta=.020`.  The fold holding out seed 0006
selects `.005`; its training advantage over `.020` is only `0.000021`.  On the
held-out mid/light seed 0006, `.005` reproduces the always-on path trap and
loses `-0.013543` to 2-way.  This single fold causes the LOSO mid/light mean to
remain slightly negative.

This is important rather than an implementation defect: exact argmax
threshold selection is sensitive when the training utilities differ only in
the fifth decimal place.  Ten seeds are enough to detect a useful pooled gate
but not enough to estimate the threshold robustly.

For interpretation only, fixing `.020` after seeing all ten seeds gives:

- 27/1,260 switching admissions (2.14%)
- mid/light versus 2-way `+0.000785`, CI `[0.000000, +0.002016]`, W/T/L `2/8/0`
- high/light versus 2-way `+0.002882`, CI `[+0.000742, +0.005591]`
- high/medium versus 2-way `+0.002418`, CI `[+0.000766, +0.004326]`

It removes the observed mid/light loss and improves high/light over always-on
3-way, but this fixed-threshold result is exploratory because `.020` was
chosen using the full dataset.  It must not replace the LOSO estimate in a
paper table.

## Decision

Do not delete the switching candidate, but do not keep it as an unconditional
third source either.  The evidence supports this narrower method statement:

> CQI+cost is the stable core; switching is admitted only when its immediate
> utility advantage is large enough to justify changing the future playback
> state.

The strongest result is at high dispersion: the LOSO gate has a clearly
positive interval over 2-way at both light and medium load.  The unresolved
issue is threshold stability around seed 0006, not absence of switching
value.  The next confirmatory experiment should freeze `eta=.020` before
running additional independent seeds.  Those new seeds, rather than the
current ten, should decide whether conditional switching becomes the final
algorithm or remains an ablation.

## Confirmatory result (seeds 11..30, 2026-08-26)

`eta=.020` was frozen before generating or looking at any of these 20 seeds.
They were never used for threshold selection. Reproduction:

```powershell
python .\run_real_multiseed_confirmatory_gate.py --seeds 11-30
```

Pooled mid/high (six cells, seed-level paired bootstrap CI), confirmatory
vs. the original exploratory LOSO estimate:

| Comparison | Exploratory (LOSO, seeds 1..10) | Confirmatory (frozen eta=.020, seeds 11..30) |
|---|---:|---:|
| gated vs CQI k-means | `+0.024411` CI `[+0.020382, +0.028432]` | `+0.022815` CI `[+0.019373, +0.026127]` |
| gated vs 2-way | `+0.001301` CI `[+0.000542, +0.002176]` | `+0.001785` CI `[+0.001279, +0.002298]` |
| gated vs always-on 3-way | `+0.000060` CI `[-0.000110, +0.000241]` | `+0.000185` CI `[-0.000255, +0.000628]` |

All five pre-registered judging criteria from the confirmatory protocol pass:

1. Pooled mid/high gated-vs-2way CI is entirely positive: confirmed above.
2. high/light and high/medium gains reproduce: `+0.002386` CI
   `[+0.001379, +0.003431]` and `+0.005361` CI `[+0.002770, +0.008176]`
   respectively (high/medium is even stronger than the exploratory
   fixed-`.020` estimate of `+0.002418`).
3. mid/light is no longer systematically negative: `+0.001732` CI
   `[+0.000658, +0.003005]`, cleanly positive. This is the cell that carried
   the unresolved seed-0006 path trap in the LOSO estimate; it does not
   reappear across 20 fresh independent seeds.
4. The fixed gate clearly beats CQI k-means: confirmed above, matching the
   exploratory magnitude closely.
5. This confirmatory result is reported on its own 20 seeds, kept separate
   from the original 10 exploratory seeds (`real_multiseed_confirmatory_gating_results/`
   vs `real_multiseed_conditional_gating_results/`). A combined 30-seed
   sensitivity analysis may be reported in addition, but does not replace
   either estimate on its own.

One caveat carried forward honestly: mid/medium's own cell-level interval
still crosses zero (`+0.000598` CI `[-0.000350, +0.001697]`, 2/20 seed
losses) — the pooled mid/high statistic is robust, but this individual cell
is not yet independently conclusive. The gate's advantage over always-on
3-way also remains statistically inconclusive on the confirmatory seeds too
(CI crosses zero, same as the exploratory result) — conditional gating's
demonstrated value is specifically "beats the 2-way core, matches or
slightly exceeds always-on 3-way," not "clearly beats always-on 3-way."

## Reproduction

```powershell
python .\run_real_multiseed_conditional_gating.py
```

Outputs are in `real_multiseed_conditional_gating_results/`:

- `fixed_eta_per_transition.csv`
- `endpoint_validation.csv`
- `loso_eta_selection.csv`
- `cv_gated_per_transition.csv`
- `comparison_per_seed.csv`
- `comparison_across_seeds.csv`
- `pooled_summary.csv`
