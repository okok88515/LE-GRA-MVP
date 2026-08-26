# MBS Grouping Research Session Handoff

Last updated: 2026-08-26 (direction 2 confirmatory validation + direction 3 step 1 result)

## CURRENT HANDOFF — 2026-08-26 UPDATE 5 (AUTHORITATIVE; READ THIS FIRST)

This section supersedes "UPDATE 4" immediately below it (kept for
provenance) and every older handoff.

### Direction 2's confirmatory validation corrected the exploratory conclusion

Full writeup: `REAL_SIMU5G_REGRET_GRAPH_TEMPORAL_DIRECTION.md`'s
"Confirmatory result" and "Decision (revised after confirmatory
validation)" sections. Generated seeds 31..50 (20 fresh, never-before-used
Simu5G seeds -- 1..10 used for direction 1/2 exploratory, 11..30 for the
switching-gate confirmatory pass), QA-validated (60/60 pass), ran
`run_real_multiseed_regret_confirmatory.py` (new script, frozen method set,
no retuning). Summary:

- The high-dispersion win for `CQI+cost+regret-graph 3-way union` (no
  switching) vs the switching-3way headline replicates cleanly: all three
  cells still entirely-positive 95% CIs, closely matching exploratory
  magnitudes (high/light +0.0119 vs exploratory +0.0105; high/medium
  +0.0108 vs +0.0218; high/heavy +0.0380 vs +0.0432).
- **Correction**: at mid dispersion, the larger 20-seed sample reveals the
  regret-graph-only 3-way has real losses to the switching headline (7/20 at
  mid/light, 8/20 at mid/medium) that the smaller 10-seed exploratory
  sample did not show clearly. The exploratory-stage suggestion that
  switching could be dropped outright does not survive confirmatory
  scrutiny -- **switching should NOT be removed**.
- **What the confirmatory pass does support**: the 4-way union
  (`cqi_cost_switching_regret_graph_hybrid_grouping`, switching AND
  regret-graph together) strictly dominates the previous switching-3way
  headline -- **zero seed-level losses** across all 6 non-saturated cells in
  20 fresh seeds, and significantly better in 5 of those 6 (all three
  high-dispersion cells, plus mid/medium and mid/heavy newly reaching
  significance at this larger sample size). This is the "union only gets
  better" guarantee holding up almost exactly as designed, now with
  confirmatory backing.
- **Recommendation**: promote the 4-way union to the shipped headline,
  replacing the 3-way switching-only method. Not yet propagated to
  `hybrid_metrics_slides.html` (still not updated per standing user
  instruction).
- This is a good illustration of why this project's confirmatory discipline
  exists: a plausible, simpler exploratory-stage story (drop switching)
  did not hold up against a larger independent sample, while the core
  mechanistic finding (regret-graph adds real value at high dispersion)
  still replicated.

### Direction 3 (causal CQI trend) code written and running

Per the user's request to prepare direction 3 while direction 2's
confirmatory batch used the WSL/CPU budget: added causal trend-feature
extraction (`cqi_trend_slope_vector`, `cqi_trend_volatility_vector`,
`cqi_trend_downside_deviation_vector`, all computed only from the 5-step
`cqi_history` already in every real scenario, never looking past
`cqi_now`), standalone k-means grouping functions per feature, a trend-only
union, and two combined-union functions to `le_gra_mvp.py`. Smoke-tested on
real data before running the full experiment (`run_real_multiseed_trend_direction.py`,
seeds 1..10, snapshot-level). Originally built the trend-plus-existing-work
union on top of the regret-only 3-way (the exploratory-stage "leading
candidate" at the time of writing); corrected to build on the
confirmatory-validated 4-way instead
(`cqi_cost_switching_regret_trend_hybrid_grouping`) once direction 2's
confirmatory result landed, keeping the regret-only-plus-trend version
(`cqi_cost_regret_trend_hybrid_grouping`) as a deliberate ablation.

**Results (full writeup: `REAL_SIMU5G_TREND_DIRECTION.md`)**: standalone
trend k-means is much worse than CQI k-means (throws away current channel
quality entirely; high/heavy dCQI=-0.094). Unioned with CQI alone, it
recovers to roughly matching CQI k-means, with one real standalone gain at
high/heavy (dCQI=+0.027). Unioned on top of the confirmatory-validated
4-way base, trend adds a small, real, zero-loss gain (exact union guarantee
holds at snapshot level) concentrated in the same high/heavy cell
(+0.0046, 6/10 seed wins, 0 losses) where the regret graph and resource-
cost already do their best work -- suggesting trend is capturing a similar,
largely redundant signal (early warning of the same infeasibility cost/
regret-graph detect from the current snapshot) rather than orthogonal new
information. Not promoted to the recommended method; step 2 (next-step
predictor) and step 3 (multi-step teacher objective) in the roadmap are
more likely to extract real value from temporal information than this
causal hand-crafted baseline did.

## CURRENT HANDOFF — 2026-08-26 UPDATE 4 (SUPERSEDED BY THE UPDATE ABOVE)

This section supersedes "UPDATE 3" immediately below it (kept for
provenance) and every older handoff.

### Research direction 2 (QoE pairwise switching regret) has a first exploratory result

Full writeup: `REAL_SIMU5G_REGRET_GRAPH_TEMPORAL_DIRECTION.md`. Summary:

- Question: does direction 1's exact-utility-regret graph (validated as a
  candidate family under snapshot-level, non-temporal evaluation) also
  capture switching-state value once run under the real temporal closed
  loop, where `previous_quality` genuinely diverges across users? No new
  metric needed to be built -- `pairwise_exact_regret_matrix`'s regret
  formula already includes `group_quality_value`'s switching penalty
  against `scenario.previous_quality`; direction 1 just never exercised
  that term (its scenarios reset `previous_quality` to 0 for everyone).
- Ran `run_real_multiseed_regret_temporal_direction.py` (real Simu5G seeds
  1..10, method-owned `previous_quality` state, reusing
  `run_real_multiseed_temporal_closed_loop.py`'s validated closed-loop
  machinery unmodified) comparing 5 methods, most importantly
  `CQI+cost+regret-graph 3-way union` (no switching family at all) against
  the existing shipped headline `CQI+cost+switching 3-way union`.
- Result: at every dispersion/load cell tested, the regret-graph 3-way
  matches or exceeds the switching headline's own margin over CQI k-means
  (never worse anywhere). At all three high-dispersion cells the head-to-
  head improvement over the switching headline is clearly significant (95%
  CI entirely positive: light `+0.0105 [+0.0047,+0.0164]`, medium `+0.0218
  [+0.0145,+0.0291]`, heavy `+0.0432 [+0.0236,+0.0668]`; seed win rate
  9-10/10). Mid-dispersion cells trend the same direction but are not
  individually significant (CIs include zero).
- Adding switching on top of the regret graph (a new 4-way union,
  `cqi_cost_switching_regret_graph_hybrid_grouping`, added to
  `le_gra_mvp.py`) gives negligible additional benefit and is occasionally
  slightly negative at the trajectory level -- explained by the same
  candidate-superset-doesn't-guarantee-trajectory-dominance caveat already
  documented in `REAL_SIMU5G_TEMPORAL_CLOSED_LOOP.md` (per-step containment
  holds only from an identical prior state; independent trajectories
  diverge in `previous_quality` history).
- Bottom line / decision: evidence supports the regret graph as a
  *replacement* for the switching-aware candidate family, not just an
  addition -- but this is still a 10-seed exploratory result. The switching
  gate itself only became trusted after a dedicated 20-seed confirmatory
  pass (`REAL_SIMU5G_CONDITIONAL_GATING.md`); this finding has not had that
  scrutiny yet, and seeds 11..30 are already "used" for that other
  confirmatory purpose. **Do not swap the shipped headline method yet** --
  keep `CQI+cost+switching 3-way union` shipped, record the regret-graph
  3-way as the leading candidate to replace it pending confirmatory
  validation on a fresh seed range.

### What is next

Per the user's standing instruction, the interview slide deck
(`hybrid_metrics_slides.html`) still does NOT need updating for this
finding. Options for continuing, not yet decided:

1. Confirmatory validation of both direction 1 and direction 2's findings
   on a fresh, untouched seed range (needs new Simu5G generation).
2. Move on to direction 3 (short-term CQI trend) per
   `POST_CQI_RESEARCH_ROADMAP_ZH.md` -- user was told this is lower
   priority than direction 2 and has not been started.
3. "Direction 4" (24-vehicle -> larger-scale real Simu5G validation),
   recorded in the roadmap per explicit user instruction, not yet
   implemented -- separate from the numbered research directions, a scale
   validation the user wants addressed eventually.

## CURRENT HANDOFF — 2026-08-26 UPDATE 3 (SUPERSEDED BY THE UPDATE ABOVE)

This section supersedes "UPDATE 2" immediately below it (kept for
provenance) and every older handoff.

### Research direction 1 (frequency-selectivity) has a first exploratory result

Full writeup: `REAL_SIMU5G_RB_PROFILE_DIRECTION.md`. Summary:

- Tested 4 methods on real Simu5G seeds 1..10, snapshot-level (non-temporal):
  full-profile k-means, block-profile k-means, an overlap-correlation graph,
  and an exact-utility-regret graph (all new, in `le_gra_mvp.py`; spectral
  clustering hand-rolled with `np.linalg.eigh`, no scipy/sklearn in this
  project).
- Found and fixed a real bug: `pairwise_exact_regret_matrix`'s first version
  never checked RB feasibility, making every user's "solo value" identical
  regardless of channel -- the regret graph degenerated to spectral
  clustering on numerical noise. Fixed by adding the same `rb_needed`
  feasibility filter `group_options` already uses. High/heavy went from
  `-0.2439` (buggy) to `+0.0586` (fixed) vs CQI k-means.
- Full-profile/block-profile k-means and the overlap graph do not pass the
  roadmap's go/no-go bar; abandoned. The regret graph, once fixed, has a
  narrow but mechanistically well-understood win specifically at high
  dispersion + heavy load (verified on 4 independent seed/snapshot cases:
  CQI k-means groups a low-CQI outlier with a not-obviously-extreme
  mid/low-CQI cluster, dragging the whole group below RB feasibility; the
  regret graph correctly isolates the outlier because its edge weights are
  feasibility-aware where CQI's linear-scale distance is not).
- Integrated as a third candidate family, `cqi_cost_regret_graph_hybrid_grouping`
  (CQI ∪ cost ∪ regret-graph union). Never scores below the existing 2-way
  union in any of 9 (dispersion, load) cells (the expected union guarantee);
  high/heavy's margin over CQI nearly doubles (`+0.0416` → `+0.0846`, seed
  win rate `9/10` → `10/10`); every other non-saturated cell gets a small
  additional gain too.
- Per-scenario attribution (which family the union actually picks): CQI is
  the general anchor, resource-cost peaks at high dispersion + light load
  (40.7% pick rate, matching `resource-cost-mechanism-finding`), the regret
  graph peaks at high dispersion + heavy load (28.0% pick rate, more than
  CQI and cost combined there).
- Still exploratory (seeds 1..10 only) -- not yet confirmatory. Seeds 11..30
  are already "used" for the switching-gate confirmatory result and per the
  roadmap's own rule cannot double as an untouched confirmatory set here.

### What is next

Per the user's explicit instruction, the interview slide deck
(`hybrid_metrics_slides.html`) does NOT need updating for this finding yet.
Options for continuing, not yet decided:

1. Confirmatory validation of `cqi_cost_regret_graph_hybrid_grouping` on a
   fresh seed range (would need new Simu5G generation, same discipline as
   the switching-gate confirmatory pass).
2. Move on to direction 2 (QoE pairwise switching regret) or direction 3
   (short-term CQI trend), per `POST_CQI_RESEARCH_ROADMAP_ZH.md`.
3. Test whether the regret-graph family's advantage survives under the full
   temporal closed-loop protocol (this investigation used snapshot-level,
   non-temporal evaluation specifically to isolate the frequency axis from
   the switching axis).

## CURRENT HANDOFF — 2026-08-26 UPDATE 2 (SUPERSEDED BY THE UPDATE ABOVE)

This section is kept for provenance.

### The confirmatory experiment planned in the section below is DONE

Seeds `seed_0011`..`seed_0030` (20 new independent Simu5G runs x 3
dispersions = 60 new simulator runs) were generated, QA-validated, and
evaluated against the frozen `eta=.020` gate on a different machine than
the one that produced seeds 1..10 (this machine's WSL environment was
missing the `p3_7_recovery/scenarios/{low,mid,high}` templates -- they were
WSL-local state on the original machine, never tracked by git -- so they
were reconstructed byte-exact from the committed seed_0001 scenario files
and verified by re-deriving seed 1's own patched files from the
reconstruction and diffing against the committed originals: zero content
differences). A CRLF line-ending bug in `run_p3_7_seed.sh`/
`run_p3_7_multiseed_batch.sh` (Windows `core.autocrlf=true` corrupting the
bash scripts on checkout) was also found and fixed via `.gitattributes`
(`*.sh text eol=lf`).

All five pre-registered judging criteria pass. Full results and tables are
in `REAL_SIMU5G_CONDITIONAL_GATING.md`'s "Confirmatory result" section.
Headline pooled mid/high numbers (seed-level paired bootstrap CI):

- gated vs CQI k-means: `+0.022815` CI `[+0.019373, +0.026127]` (exploratory
  LOSO was `+0.024411` CI `[+0.020382, +0.028432]` -- closely reproduced)
- gated vs 2-way: `+0.001785` CI `[+0.001279, +0.002298]` (exploratory LOSO
  was `+0.001301` CI `[+0.000542, +0.002176]` -- closely reproduced, and the
  confirmatory CI is entirely positive with more margin)
- gated vs always-on 3-way: `+0.000185` CI `[-0.000255, +0.000628]` (still
  crosses zero, same as exploratory -- gating is not yet shown to clearly
  beat always-on 3-way, only to clearly beat the 2-way core)
- mid/light, the cell carrying the unresolved seed-0006 path trap in the
  LOSO estimate, is now cleanly positive on 20 fresh seeds: `+0.001732` CI
  `[+0.000658, +0.003005]`
- one honest caveat: mid/medium's own cell-level CI still crosses zero
  (`+0.000598` CI `[-0.000350, +0.001697]`, 2/20 seed losses) even though
  the pooled mid/high statistic is robust

New/changed files this update:

- `validate_real_simu5g_multiseed.py`: `EXPECTED_SEEDS` constant replaced
  with a `--seeds`/`--label` CLI (so a non-`1-10` run never overwrites the
  original QA artifacts)
- `run_real_multiseed_confirmatory_gate.py`: new, evaluates the frozen
  `eta=.020` gate on an explicit `--seeds` argument without any LOSO
  retuning (reuses `run_real_multiseed_conditional_gating.select_gated_candidate`
  and `run_real_multiseed_temporal_closed_loop` baselines directly, so the
  gating logic itself is not duplicated)
- `.gitattributes`: added `*.sh text eol=lf`
- `real_simu5g_multiseed_data/{low,mid,high}/seed_0011`..`seed_0030/`: the
  new confirmatory data (git-lfs), plus `*_confirmatory` QA manifest/CSV
- `real_multiseed_confirmatory_gating_results/`: the confirmatory analysis
  outputs, kept separate from `real_multiseed_conditional_gating_results/`
  (the original 10-seed exploratory results, untouched)

### What is next

Per the roadmap in `POST_CQI_RESEARCH_ROADMAP_ZH.md`, now that the fixed
gate is confirmed: pursue the three CQI-information-gap directions (RB
profile graph partitioning, pairwise switching-regret modeling, short-term
CQI trend/forecast) as separate ablations before combining them. Seeds
11..30 have now been inspected for this confirmatory purpose; per the
already-stated rule, they cannot also be described as an untouched
confirmatory set for whichever of those three methods is tried next -- that
would need its own fresh seed range or must be reported as exploratory/
nested-CV if reusing 11..30.

## CURRENT HANDOFF — 2026-08-26 (SUPERSEDED BY THE UPDATE ABOVE)

This section supersedes the 2026-08-25 handoff and every older next-step
recommendation below. Older sections remain only as research provenance.

### Current research conclusion

The real 10-seed Simu5G experiment is now temporal and closed-loop. Each
method owns its `previous_quality` state, served users advance to the exact-DP
assigned quality, unserved users retain their last delivered quality, and the
first of 15 usable snapshots is a common warm-up. The simulator seed is the
independent statistical unit.

The robust algorithmic core is CQI+resource-cost 2-way candidate union.
Switching `[CQI, previous_quality]` is useful only in a small regime-dependent
subset and should be treated as a conditional refinement, not an
unconditionally active third source.

The implemented conditional gate admits the best switching candidate only if

```text
U(best switching candidate) - U(best CQI/cost candidate) > eta
```

Every eta follows a separate closed-loop trajectory. The tested grid was
`{0, .005, .010, .020, .030, .050, infinity}`. Leave-one-seed-out selection
holds the same seed number out jointly across low/mid/high and all loads.

Primary LOSO result over the six mid/high cells:

- gated minus CQI k-means: `+0.024411`, 95% CI
  `[+0.020382, +0.028432]`, seed W/T/L `10/0/0`
- gated minus 2-way: `+0.001301`, 95% CI
  `[+0.000542, +0.002176]`, seed W/T/L `9/1/0`
- gated minus always-on 3-way: `+0.000060`, 95% CI
  `[-0.000110, +0.000241]`; no statistically clear overall difference
- switching admission rate falls from 4.84% at `eta=0` to 2.62% under LOSO
- high/light and high/medium both have clearly positive cell-level intervals
  versus 2-way

Nine of ten folds select `eta=.020`. The fold holding out seed 0006 selects
`.005` by only `0.000021` training utility and reproduces the known mid/light
path trap. A full-data exploratory `.020` run removes that observed mid/light
loss, but it is not independent evidence.

Therefore the next experiment must freeze `eta=.020` before observing new
results. Do not retune utility, features, eta, or grouping constraints on the
confirmatory seeds.

### New files completed and validated

- `le_gra_mvp.py`: exact allocation now returns optional per-user quality for
  closed-loop state feedback
- `run_real_multiseed_temporal_closed_loop.py`
- `run_real_multiseed_temporal_regime_analysis.py`
- `analyze_real_multiseed_temporal_regimes.py`
- `run_real_multiseed_conditional_gating.py`
- `REAL_SIMU5G_TEMPORAL_CLOSED_LOOP.md`
- `REAL_SIMU5G_TEMPORAL_REGIME_ANALYSIS.md`
- `REAL_SIMU5G_CONDITIONAL_GATING.md`
- `real_multiseed_temporal_closed_loop_results/`
- `real_multiseed_temporal_regime_results/`
- `real_multiseed_conditional_gating_results/`

Validation completed:

- 4,050 closed-loop baseline transition rows
- 1,350 attribution rows; production 3-way reproduction max error 0
- 9,450 fixed-eta transition rows and 1,350 LOSO gated rows
- `eta=0` exactly reproduces always-on 3-way over all 1,350 transitions
- `eta=infinity` exactly reproduces 2-way over all 1,350 transitions
- Python compilation and `git diff --check` pass

### Tomorrow on the other computer

Start with:

```powershell
git pull origin main
git lfs pull
git status
```

Then read, in order:

1. this 2026-08-26 section
2. `REAL_SIMU5G_CONDITIONAL_GATING.md`
3. `REAL_SIMU5G_TEMPORAL_REGIME_ANALYSIS.md`
4. `REAL_SIMU5G_MULTISEED.md`

Confirmatory target:

- generate real Simu5G `seed_0011` through `seed_0030`
- retain low/mid/high with identical scenario settings
- three application loads continue to be derived from each radio trace; they
  are not extra Simu5G runs
- total new simulator runs: `20 seeds x 3 dispersions = 60`
- freeze conditional gate at `eta=.020`
- preserve the new 20 seeds as a confirmatory set; do not use them to retune
  eta

Measured timing from the existing batch: seeds 1..10 across all three
dispersions ran from 15:38:41 to 15:54:55 UTC, about 16.2 minutes wall time.
At the same serial-run speed, 20 new seeds should need 32--36 minutes for raw
generation and about 45--50 minutes including copy, QA, parsing, and fixed-gate
evaluation. Budget one hour. Expected additional compressed dataset size is
about 0.8--0.9 GB.

Before running the confirmatory analysis, update the current hard-coded
`1..10` seed constants in `validate_real_simu5g_multiseed.py` and the temporal
evaluation entry point, or add explicit train/test seed-range arguments. Do
not change the gate or utility while making this plumbing change. The raw
batch command is:

```powershell
python .\run_real_simu5g_multiseed.py --seeds 11-30
```

The batch writes under WSL by default to
`/home/opp_env/p3_5_workspace/p3_7_multiseed_v3_outputs`. It is resumable and
does not overwrite completed runs.

The three legacy mobility CSVs may still appear modified on Windows solely
because of line-ending detection. Their content was not changed and they
must not be committed:

- `real_simu5g_data/raw_mobility.csv`
- `real_simu5g_data/mid_raw_mobility.csv`
- `real_simu5g_data/high_raw_mobility.csv`

### Longer research roadmap: pursue all three CQI-information gaps

After the fixed-gate confirmatory run, pursue all three directions recorded
in `POST_CQI_RESEARCH_ROADMAP_ZH.md`:

1. same wideband CQI but different frequency-selective RB profiles: build
   pairwise RB-overlap/utility-regret graphs and compare graph partitioning
   against full-profile k-means using identical inputs
2. same CQI but different QoE switching states: move from a joint-coordinate
   switching candidate to pairwise load-aware utility regret
3. opposite short-term CQI trends: change the objective from a single
   snapshot to causal predicted or windowed cumulative utility with group
   persistence cost

All three are intended research branches. Isolate each mechanism first and
combine them only after separate ablations succeed. The new seeds 11..30 are
the untouched confirmatory set for the already-frozen `.020` gate; after they
are inspected, they cannot also be described as untouched confirmation for
methods designed later.

## Historical handoff — 2026-08-25

This section supersedes every older "recommended next step" in the historical
log below. The old sections remain only as research provenance.

### Current objective

The goal is not to minimize computation. The goal is to find a useful,
defensible grouping insight that can beat the published CQI k-means baseline.
The comparison must remain fair: all methods may access the same predeclared
input variables and use the same utility, RB budgets, group-count constraints,
and downstream allocation. Only the grouping algorithm may differ.

Do not change utility weights or method inputs after seeing the result of one
method. Freeze the protocol first.

### Data completed this session

1. The missing original P3.7 Simu5G radio exports were reconstructed and
   versioned through Git LFS.
2. The reproducible fair-input benchmark pipeline is complete:
   - generated locally as `fair_input_dataset_v1/`
   - 16,200 scenarios in 9 compressed NumPy shards
   - intentionally ignored because fixed seeds can rebuild it
3. The real Simu5G protocol-v3 multi-seed dataset is complete:
   - path: `real_simu5g_multiseed_data/`
   - seeds: `1..10`
   - dispersions: `low`, `mid`, `high`
   - 30 separately preserved simulator runs
   - 15 complete snapshots per run
   - 450 learner-facing scenarios total
   - 24 users, 25 bands, 5 CQI history steps
   - 10 distinct mobility trajectories
   - for each seed, low/mid/high share the same mobility input and differ only
     in radio power
4. Full QA passed:
   - `MULTISEED_QA_PASS runs=30 scenarios=450`
   - gzip hashes and run manifests verified
   - 10 unique mobility hashes across seeds
   - one shared mobility hash across dispersions within each seed

Authoritative machine-readable summaries:

- `real_simu5g_multiseed_data/aggregate_manifest.json`
- `real_simu5g_multiseed_data/multiseed_qa.csv`
- `REAL_SIMU5G_MULTISEED.md`
- `REAL_SIMU5G_DATA_COMPLETION.md`

Aggregate CQI mean / mean within-run standard deviation:

- low: `14.761 / 0.602` (still strongly saturated near CQI 15)
- mid: `12.583 / 2.182`
- high: `9.188 / 3.010`

### Git state at handoff

Everything above is committed and pushed to `origin/main`:

- `4dd6dd2` — Add reproducible Simu5G multi-seed protocol
- `9906a6e` — Add validated 10-seed Simu5G dataset

The three legacy mobility CSVs may appear as modified on Windows because of
line-ending detection. Their Git object hash and file-content hash are
unchanged; do not commit those false-positive modifications.

### Tomorrow: exact startup on the other computer

```powershell
git pull
git lfs install
python .\prepare_project_data.py
python .\validate_real_simu5g_multiseed.py
```

`prepare_project_data.py` hydrates both the original real Simu5G inputs and
the protocol-v3 multi-seed LFS archive, verifies the original hashes, and
builds/validates `fair_input_dataset_v1` when absent. The full multi-seed
validator takes several minutes because it parses all 30 runs.

If cloning from scratch, follow `OTHER_MACHINE_QUICKSTART.md` first.

### Next implementation task

Build `run_real_multiseed_baseline.py` and run the non-learned fair comparison
before training LE-GRA.

Required matrix:

- methods: CQI k-means, resource-cost k-means, multi-feature k-means
- dispersions: low, mid, high
- loads: light, medium, heavy
- simulation seeds: 1..10
- same utility, variables, K constraints, RB budget, and allocation for all
  methods

Required output and statistical unit:

1. Average the 15 adjacent snapshots within each run first.
2. Treat the simulation seed/trajectory as the independent unit (`n=10` per
   dispersion), never the 450 adjacent snapshots.
3. Report paired
   `delta_utility = method_utility - cqi_kmeans_utility` per seed.
4. Report mean, median, seed-level bootstrap 95% CI, win rate, and worst case.
5. Break utility into its declared components so any improvement can be
   explained as a real insight rather than only a scalar score.

Decision order:

1. Determine whether resource-cost or multi-feature grouping consistently
   beats CQI k-means on real multi-seed data.
2. Identify the dispersion/load regime and utility component causing the gain.
3. Only then train LE-GRA to reproduce or improve that signal.
4. If neither non-learned method wins, inspect the frozen utility and feature
   sufficiency before redesigning the learner.

### Remaining limitations — do not overclaim

- Ten seeds complete the exploratory target; 20 seeds remain the target for a
  confirmatory statistical claim.
- `previous_quality` is still not a measured application-layer state.
- Native wideband CQI is unavailable; the parser uses the disclosed mean
  per-band CQI proxy.
- RSRP, RSRQ, SINR, and MCS remain unavailable for this dataset.
- Low dispersion has a ceiling effect and should eventually gain a
  low-dispersion but non-saturated companion condition.

## READ THIS FIRST (2026-08-21 correction -- supersedes the TL;DR below)

Everything from "Quick Restart For Another Agent" through the August 11
entries below was written during an earlier research phase whose narrative
had temporarily reframed the project as "resource-cost / multi-feature are
the mainline methods, LE-GRA is a secondary exploratory line." **That framing
was reversed again after 2026-08-11 and is no longer current.** Do not trust
the "Current method positioning" / "Do not do these first" bullets a few
lines down -- they are historical, not current guidance.

Current, authoritative status as of 2026-08-21:

- **The project's actual purpose is interview preparation**: the user is
  interviewing about their own published paper ("Resource Allocation for 5G
  Vehicular Users' MBS using a CQI-based k-means Grouping Method," Huang &
  Liao, IEEE MSWiM 2025). Everything in this repo beyond the paper itself is
  honest post-publication personal extension work, framed explicitly as such
  -- never as part of the published paper.
- **LE-GRA (learned embedding + k-means + a CQI-fallback ensemble) is the
  headline post-publication extension again** (reversed back from the Aug 11
  reframing above). `resource-cost k-means` and `multi-feature k-means` are
  ablation baselines under it, not competing mainline methods. `Offline
  teacher + exact DP` is a pseudo-optimal reference baseline -- see the
  contiguity caveat below, it is NOT a true global optimum.
- **This repo now has a second, actively-maintained continuity mechanism**:
  a Claude Code memory store at
  `C:\Users\Weber\.claude\projects\c--Users-Weber-Documents-LE-GRA-MVP\memory\`
  (indexed by `MEMORY.md` in that same folder). That memory store is more
  current and more granular than this file for anything after 2026-08-11 --
  if you are an agent picking this repo back up, read `MEMORY.md` there
  first, then treat this file's August 21 section (at the very bottom) as
  the connecting summary between that memory and the pre-08-11 research log
  above.
- **The single most important recent finding**: `offline_teacher_groups`/
  `offline_teacher_groups_fast` are NOT true global optima -- by their own
  docstring, they only search contiguous-by-resource-cost partitions. At low
  CQI dispersion this is lossy (confirmed: teacher loses on its own utility
  metric in 100% of 600 n=150 low-dispersion test scenarios). A validated
  fix (`offline_teacher_groups_multikey`, added 2026-08-21) closes this gap
  to 0% at n=150. See the "August 21" section at the end of this file and
  the `teacher-contiguity-limitation` memory entry for full detail.

See the new section titled "## August 21 update: interview-prep pivot,
dispersion-stratified benchmark suite, and offline-teacher contiguity fix"
at the very end of this file for what actually happened this session.

Artifact hygiene update (2026-08-11):

- The repo now has a dedicated artifact policy note:
  - `REPO_ARTIFACT_GUIDE_ZH.md`
- `.gitignore` has been extended to hide clearly reproducible local outputs:
  - `_tmp_*`
  - corridor mining batch outputs
  - large local variant-search directories
  - auto-generated `p3_6r5s_* / p3_6r7_* / p3_6r8s_*` variant bundles
- If resuming on a new machine, read `REPO_ARTIFACT_GUIDE_ZH.md` before
  deciding to commit any new large search output.

Repo evidence update (2026-08-11):

- The repo is now intentionally layered into:
  1. main showcase artifacts
  2. control / support artifacts
  3. focused subset evidence
- Main showcase now committed:
  - `p3_6r4_q10_history_conflict_bundle`
  - `p3_6r8_q10_temporal_decoy_flicker_bundle`
  - `p3_6q27_*_radio_coverage.csv`
- Supporting control / subset artifacts now committed:
  - `p3_6r2b_*`
  - `p3_6r2c_*`
  - `p3_6i2_focused_teacher_subset`
  - `p3_6q10_focused_teacher_subset`
- The remaining untracked assets are now mostly exploratory side branches
  rather than core narrative evidence.

This document is the continuity note for resuming the MBS grouping discussion in a
new Codex task or on another computer. After pulling the repository, ask Codex
to read this file together with `medium_matrix_results/*.csv` before proposing
the next experiment.

## Quick Restart For Another Agent

**(Historical -- see "READ THIS FIRST (2026-08-21 correction)" at the top of
this file before trusting anything below; the mainline-vs-LE-GRA positioning
here was reversed again after 2026-08-11.)**

If you are Claude / Codex / another agent resuming this repo, start from this
summary before reading the detailed sections below.

### TL;DR

- The project narrative has been reset:
  - the main story is no longer "prove LE-GRA is the universal winner"
  - the main story is now "CQI-only grouping is too shallow, and
    `resource-cost` / `multi-feature` grouping are better aligned with the
    true multicast allocation problem"
- Current method positioning:
  - `Offline teacher + exact DP` = validated research backbone
  - `resource-cost k-means` = strongest practical mainline method
  - `multi-feature k-means` = richer mainline feature-based method
  - `LE-GRA` = exploratory / appendix line, still useful but no longer the
    headline contribution

- The current best showcase corridor is now:
  - `1|2|3|4|5|6 @ gnb_2`
  - bundle: `p3_6r4_q10_history_conflict_bundle`
  - corridor: `28.0s ~ 28.2s` with train support `27.7s ~ 27.9s`
- On that corridor, we now have a larger clean gap:
  - `Offline teacher = LE-GRA = 0.5694`
  - `resource-cost k-means = 0.5426`
  - `teacher - resource-cost = 0.0268`
- This is stronger than the original `q10` showcase:
  - old `q10` gap was `0.01276`
  - `r4` roughly doubles the teacher-vs-resource-cost separation
- A direct follow-up variant `r4b` was also tested:
  - idea: reduce `ue6` instantaneous cost distinctiveness even further while
    keeping its history-side weakness
  - result:
    - `Offline teacher = LE-GRA = 0.5694`
    - `resource-cost k-means = 0.5525`
    - gap shrinks to `0.0169`
  - interpretation:
    - the `r4` corridor is better balanced; pushing cost separation even lower
      starts to help the baselines again instead of widening the gap
- A stable control corridor still exists:
  - `0|1|2|3|4 @ gnb_2`
  - bundle: `p3_6r2c_five_user_dualweak_plateau_plus_bundle`
  - corridor: `18.7s ~ 19.2s`
- But `r2c` is still only a control:
  - `Offline teacher = LE-GRA = resource-cost k-means`
  - it proves stable split demand, but not a wider method gap

### Current bottleneck in one sentence

The main unsolved problem is no longer "can we make teacher split?"; it is
"can we find or synthesize more corridors where richer grouping methods beat
the strong `resource-cost` baseline instead of merely tying it."

### What has already been proven

0. The biggest research-level conclusion is now representation-focused:
   - `CQI-only` is too weak to describe the real grouping problem
   - `resource-cost` is the clearest practical improvement over pure CQI
   - `multi-feature` is a credible mainline direction
   - `LE-GRA` is not a robust universal solution, even though it remains
     valuable as an exploratory line

1. The old UE-holdout evaluation was hiding good corridors by breaking the
   exact family in test; family-preserving temporal evaluation is required.
2. Under the correct protocol, the original `p3_6q10` is a real success case:
   - `No grouping = 0.6139`
   - `CQI = 0.6245`
   - `resource-cost = 0.6298`
   - `Offline teacher = LE-GRA = 0.6458`
3. A stronger `q10` derivative now exists:
   - bundle: `p3_6r4_q10_history_conflict_bundle`
   - focused split:
     - train `27.7 ~ 27.9`
     - test `28.0 ~ 28.2`
   - result:
     - `No grouping = 0.4059`
     - `CQI = 0.5437`
     - `resource-cost = 0.5426`
     - `Offline teacher = LE-GRA = 0.5694`
   - key meaning:
     - lower instantaneous cost dispersion plus stronger history-side conflict
       can widen the teacher-vs-resource-cost gap
4. A global miner plus batch evaluator now exists:
   - `mine_family_corridors.py`
   - `run_family_corridor_batch.py`
5. Many positive corridors are still too easy:
   - teacher splits
   - but `resource-cost k-means` already matches teacher
6. `p3_6r2c` proves we can now synthesize a stable split-demand plateau:
   - family: `0|1|2|3|4 @ gnb_2`
   - window: `18.7s ~ 19.2s`
   - teacher split: `[[0, 1, 2, 4], [3]]`
   - gain per snapshot: `0.12181`
7. However, `r2c` still ties on the strong baseline:
   - `No grouping = 0.3959`
   - `CQI = 0.5174`
   - `resource-cost = Offline teacher = LE-GRA = 0.5177`

### Do not do these first

- do not jump to bigger matrices / more seeds / larger `Kmax`
- do not go back to learner-side micro-tuning before picking a better corridor
- do not assume "teacher splits" automatically means "resource-cost will fail"
- do not assume the project still uses only raw CQI
- do not write the report as if LE-GRA is still the only main character

### Important interpretation

- Pure `CQI k-means` is only the weakest baseline.
- The main learner already uses richer signals:
  - `cqi_history`
  - `rb_rates`-derived `cost_vec`
  - RB stats
  - mobility
  - quality/load context
- So the current failure is not explained simply by
  "CQI is quantized to `1..15`".
- However, the repo's radio schema already reserves continuous radio fields
  such as `RSRP` / `RSRQ` / `SINR`, and the exporter still leaves them empty.

### Best next step

The most promising next move is corridor selection plus feature-centric
mainline consolidation, not learner redesign.

Recommended order:

1. keep using the automated pipeline:
   - `mine_family_corridors.py`
   - `run_family_corridor_batch.py`
   - `run_focused_family_temporal_learner.py`
2. search for families where:
   - teacher needs a stable split for at least `>= 3` snapshots
   - and `resource-cost k-means` does **not** already match teacher
3. use synthetic family-window transforms only when they widen the
   `teacher - resource-cost` gap, not just the `teacher - no-grouping` gap
4. treat `p3_6q10` as the primary showcase and `p3_6r2c` as a useful control:
   - `q10`: genuine method separation
   - `r2c`: stable split-demand without additional separation
5. when writing reports or summaries:
   - present `Offline teacher + DP`, `resource-cost k-means`, and
     `multi-feature k-means` as the mainline methods
   - keep LE-GRA as a secondary exploratory branch

### August 10 update: `r4` local sweep plateau is now explicit, and `n3` is the next source-family probe

- We added a local automated sweep around the current best `r4` corridor:
  - `search_q10_history_conflict_variants.py`
  - output: `q10_history_conflict_variant_search/leaderboard.csv`
- This sweep tested mild `ue4` / `ue5` decoy-history and weak-pair rebalancing
  around the successful `p3_6r4_q10_history_conflict_bundle`.
- Main result:
  - none of the small local variants beats the current `r4` gap
  - best variants only tie the existing result:
    - `teacher - resource-cost = 0.0268`
  - some variants raise teacher utility slightly, but also help the
    `resource-cost` baseline rise with it
- Interpretation:
  - `r4` is not just "any nearby perturbation works"
  - the current `q10/r4` line already sits on a local plateau
  - more tiny local knob-turning is unlikely to create a new breakthrough

- We then pivoted to the strongest alternative source family discovered by
  `mine_source_family_candidates.py`:
  - `3|4|5|6 @ gnb_2`
  - source audit winner:
    - `p3_6n3_teacher_audit`
  - positive corridor length:
    - `42` snapshots (`25.8s ~ 29.9s`)
- Important baseline reality on the original `n3` family:
  - teacher always uses the same easy split:
    - `[[0, 1, 3], [2]]`
  - which means the regime is abundant but too easy

- New source-shift probe implemented:
  - spec:
    - `p3_6r5_n3_dualweak_history_conflict_spec.json`
  - bundle:
    - `p3_6r5_n3_dualweak_history_conflict_bundle`
- Goal of `r5`:
  - convert the easy `ue5` singleton regime into a harder dual-weak
    `{ue4, ue5}` history-conflict corridor

- `r5` first split (`25.8 ~ 27.3` train, `27.4 ~ 28.8` test):
  - output:
    - `_tmp_r5_family_temporal_hcq/main_comparison.csv`
  - result:
    - `train_positive_gain_count = 0`
    - `test_positive_gain_count = 9`
    - `Offline teacher = Resource-cost = 0.4044`
    - `LE-GRA = 0.2914`
  - meaning:
    - the redesign did create a harder late test corridor
    - but positive teacher supervision arrived too late for the chosen train
      window

- `r5` later split (`27.4 ~ 28.0` train, `28.1 ~ 28.8` test):
  - output:
    - `_tmp_r5b_family_temporal_hcq/main_comparison.csv`
  - result:
    - `train_positive_gain_count = 1`
    - `test_positive_gain_count = 8`
    - `Offline teacher = Resource-cost = LE-GRA = 0.3867`
  - meaning:
    - once positive support is present, LE-GRA transfers
    - but `resource-cost` still fully catches the teacher

- Updated interpretation after `r4` sweep + `r5` probe:
  1. local `r4` perturbations are plateaued
  2. source-family shift is the right direction
  3. `n3` can be turned into a harder late corridor, so the source is usable
  4. but the present `r5` transform still does not break the strong baseline
  5. the next source-side redesign should target:
     - earlier positive onset in train
     - and dual-weak ambiguity that is *not* instantly recoverable by
       resource-cost ranking

### August 10 update: fast source-bank triage says the current positive-family bank is nearly exhausted

- We ran a broad local search on the strongest alternative source family:
  - script:
    - `search_n3_dualweak_variants.py`
  - results:
    - `n3_dualweak_variant_search/leaderboard.csv`
- This sweep completed `360` variants around `3|4|5|6 @ gnb_2`.
- Hard result:
  - `positive_gap_variants = 0`
  - many variants create positive teacher corridors
  - but none produce `teacher - resource-cost > 0`
- Meaning:
  - `n3` is not the next fast breakthrough source
  - it behaves like a source where teacher split can be synthesized, but
    `resource-cost` still follows too easily

- We also re-checked the seemingly remaining five-user family candidate:
  - `1|2|3|4|5 @ gnb_2`
  - repo source investigated:
    - `p3_6e2_budget_sweep/rb_032/teacher_audit/full_bundle/scenario_teacher_decisions.csv`
- Result:
  - actual positive snapshot count there is `0`
  - so this family is not a live positive source under the current audited data
- Interpretation:
  - the old source-family ranking should not be treated as a fresh
    "available next-family" list without revalidation
  - after revalidation, the current positive-source bank is effectively:
    1. `q10/r4` style six-user family
    2. `r2c` style control family
    3. `n3` style easy-singleton family that remains baseline-solvable

- Updated fast conclusion:
  - if the goal is specifically "find a larger gap quickly",
    the highest-yield next move is no longer more local mining inside the
    current source bank
  - the next meaningful step should be:
    - create a genuinely new source-family generation rule
    - or introduce a new data-generation axis that makes dual-weak ambiguity
      appear without instantly exposing the answer to resource-cost ranking

### August 10 update: even `q10/r4` decoy-collision search does not beat the current best gap

- We ran a new focused search on the only currently successful source line:
  - script:
    - `search_q10_decoy_collision_variants.py`
  - output:
    - `q10_decoy_collision_search/leaderboard.csv`
- Search idea:
  - keep the proven true weak pair `{ue2, ue6}`
  - make `ue4` look more similar in instantaneous cost
  - hope `resource-cost` would over-group the decoy while teacher still keeps
    `{ue2, ue6}` as the real weak pair
- Search scale:
  - `288` variants
- Hard result:
  - best `teacher - resource-cost = 0.0`
  - many variants still preserve positive teacher corridors
  - but once the decoy gets strong enough, `resource-cost` catches up to
    teacher completely
- Meaning:
  - the present `q10/r4` line is not just locally plateaued under tiny manual
    tweaks
  - it is also robustly plateaued under this larger decoy-collision sweep
- Updated very short conclusion:
  - current best gap remains:
    - `0.0268` on `_tmp_r4_family_temporal_hcq/main_comparison.csv`
  - if we want a larger gap quickly, the next move must be a new structural
    data-generation axis rather than more local search around the current
    positive-family bank

### August 10 update: first new structural regime after the plateau is `r8`

- We then stopped local static sweeps and built a more structural variant:
  - spec:
    - `p3_6r8_q10_temporal_decoy_flicker_spec.json`
  - bundle:
    - `p3_6r8_q10_temporal_decoy_flicker_bundle`
- New idea:
  - keep the train corridor aligned with the successful `r4` weak pair
    `{ue2, ue6}`
  - but introduce a *flickering* test-side instantaneous decoy on `ue4`
  - this is different from the failed static decoy-collision sweep:
    - the decoy is temporal, not constant
    - so the test corridor is structurally harder instead of just being a
      slightly different static ranking

- Important teacher-side change:
  - train `27.7 ~ 27.9` still uses the stable weak pair:
    - `1|3|4|5 / 2|6`
  - but test `28.0 ~ 28.2` now alternates:
    - `28.0`: `1|3|4|5|6 / 2`
    - `28.1`: `1|3|4|5 / 2|6`
    - `28.2`: `1|3|4|5|6 / 2`
  - this means the new corridor is not just another copy of `r4`
  - it is the first post-plateau regime where the target structure itself
    changes over time inside the focused test window

- Focused learner result:
  - output:
    - `_tmp_r8_family_temporal_hcq/main_comparison.csv`
  - numbers:
    - `Offline teacher = 0.5748`
    - `Resource-cost = 0.5692`
    - `Multi-feature = 0.5577`
    - `LE-GRA = 0.5089`
    - `CQI = 0.5322`
    - `No grouping = 0.3893`

- Immediate meaning:
  1. This is the first new structural regime after the long plateau that
     re-opens a nonzero `teacher - resource-cost` gap:
     - about `0.0056`
  2. But LE-GRA does **not** transfer here yet:
     - it drops below both `teacher` and `resource-cost`
  3. So `r8` is not a better final showcase than `r4`
  4. However, it is a real breakthrough in *benchmark construction*:
     - we now have a new hard regime where the old learner no longer rides
       the teacher automatically

- Updated interpretation:
  - `r4` remains the best current showcase because:
    - `LE-GRA = teacher`
    - and `teacher - resource-cost = 0.0268`
  - `r8` is different:
    - smaller teacher-vs-resource-cost gap
    - but far more valuable as the next learner-improvement target
  - in other words:
    - `r4` is still the best success case
    - `r8` is now the best genuinely new challenge case

### Minimum files to read next

1. `SESSION_HANDOFF.md`
2. `P3_6Q_24_DUAL_BOUNDARY_CROSSOVER_REGIME_ZH.md`
3. `P3_6Q_25_SINGLE_SUPPORT_CROSSOVER_TRANSFER_ZH.md`
4. `P3_6Q_26_EARLIEST_ONSET_FAILURE_ZH.md`
5. `P3_6Q_27_RADIO_SIGNAL_READINESS_ZH.md`
6. `P3_6Q_28_SOURCE_HOOK_AUDIT_ZH.md`
7. `SIMU5G_RADIO_SCHEMA.md`
8. `simu5g_raw_radio_export.py`
9. `le_gra_mvp.py`

### August 10 update: source hook is now working

- `q29` and `q30` proved that PHY-level outer hooks were not reliable enough:
  - `LtePhyEnb::requestFeedback()` did not emit a usable sidecar in the
    `Multiple-UEs` smoke path
  - `LtePhyUe::handleAirFrame()` also failed to produce a stable sidecar
- `q31` moved the recorder down to the true measurement source:
  - `simu5g/stack/phy/channelmodel/LteRealisticChannelModel.cc`
  - function: `LteRealisticChannelModel::getSINR(...)`
- This finally produced `raw_radio_diag.csv` successfully in the focused smoke
  test.
- Important alignment result:
  - diag rows contain multiple contexts
  - the subset `frame_type=2` and `direction=1`
    (`FEEDBACKPKT` + `UL`) matches the main raw-radio row count exactly
  - the exporter now prefers this subset when those columns are present

Read `P3_6Q_31_CHANNELMODEL_DIAG_SUCCESS_ZH.md` before attempting the next
radio-aware learner step.

### August 10 update: focused teacher-positive subset is now reproducible

- A reusable focused-subset builder now exists:
  - `build_focused_teacher_subset_bundle.py`
- It scans a coupled bundle with the current offline teacher and keeps only
  scenarios that satisfy:
  - `teacher_gain_vs_single >= min_gain`
  - `teacher_group_count >= min_group_count`
- It filters all three coupled views together:
  - `bundle/`
  - `radio/`
  - `mobility/`
- First validation target:
  - source bundle: `p3_6i2_coupled_bundle`
  - focused output: `p3_6i2_focused_teacher_subset`
- Result:
  - full bundle had `830` multi-user audited scenarios
  - only `9` were positive-gain multi-group teacher windows
  - they belong to just `2` families:
    - `0|1|2|3|4 @ gnb_2` on `18.7s ~ 19.2s`
    - `0|1|15|2|3|4|5 @ gnb_1` on `43.7s ~ 43.9s`
- This confirms the previous dilution hypothesis:
  - the full `p3_6i2` bundle is mostly non-splitting context
  - broad averages hide the actual teacher-positive windows
- But the focused rerun also revealed a second bottleneck:
  - these `9` windows are mostly easy one-weak-user separations
  - `CQI k-means`, `Multi-feature k-means`, and `Offline teacher`
    all collapse to the same average utility on this subset
  - `history_cost_quality` LE-GRA matches them exactly
  - `history_cost_radio` LE-GRA is slightly worse, not better
- Interpretation:
  - radio export is no longer the blocker
  - focused extraction is now solved
  - the current `p3_6i2` positive windows are too easy to create a
    meaningful method gap
  - the next real need is a harder focused regime with genuine crossover /
    multi-weak-user ambiguity, not just isolated single-outlier splits

### August 10 update: q10 confirms the real issue was the evaluation protocol, not the regime itself

- We tested a harder focused regime:
  - source bundle: `p3_6q10_six_user_transition_extension_bundle`
  - focused subset: `p3_6q10_focused_teacher_subset`
  - strongest family: `1|2|3|4|5|6 @ gnb_2`
  - teacher-positive corridor: `27.3s ~ 28.2s`
- First result with the existing `run_p3_6_coupled_learner.py` looked flat again,
  but that turned out to be a protocol artifact:
  - the default split is UE-holdout
  - it broke the six-user family into test scenarios like `3|4`
  - once that happens, the teacher itself no longer needs to split
  - so every method trivially ties
- To verify this, we added:
  - `run_focused_family_temporal_learner.py`
- This new script preserves the exact family and only splits by time window.
- On the preserved `1|2|3|4|5|6 @ gnb_2` family:
  - train: `27.3s ~ 27.6s`
  - test: `27.7s ~ 28.2s`
  - both train and test have positive-gain teacher splits in every scenario
- Result on that family-preserving temporal protocol:
  - `No grouping`: `0.6139`
  - `CQI k-means`: `0.6245`
  - `Resource-cost k-means`: `0.6298`
  - `Multi-feature k-means`: `0.6139`
  - `Offline teacher`: `0.6458`
  - `LE-GRA MVP`: `0.6458`
- Interpretation:
  - the project does now have a real, stable gap when the regime and protocol
    are aligned correctly
  - LE-GRA can fully recover the teacher on this family
  - the main remaining gap is no longer "teacher vs LE-GRA"
  - it is now:
    1. finding more such family-preserving hard corridors
    2. deciding whether radio features can improve robustness or transfer
       beyond the already-solved quality/cost path
  - `history_cost_radio` did not improve over `history_cost_quality` here;
    both matched the teacher on the preserved family

## Research Goal

The project studies grouping and resource allocation for vehicular 5G MBS.
The current prototype, LE-GRA (Learning-based Embedding Grouping and Resource
Allocation), learns a user embedding from channel-history and resource-cost
features, applies k-means to the embedding, and uses an exact DP backend to
select group video qualities under an RB budget.

The immediate research question is not whether more methods can be added. It
is whether resource-cost features and learned embeddings provide a stable
advantage over CQI k-means, particularly under channel ambiguity and resource
pressure.

## Current Comparison Methods

1. No grouping: all users belong to one MBS group.
2. CQI k-means: k-means on current CQI.
3. Resource-cost k-means: k-means on per-quality RB cost vectors.
4. Multi-feature k-means: k-means directly on normalized hand-crafted features.
5. Offline teacher: users are sorted by resource cost; contiguous partition
   boundaries up to `Kmax` are searched and evaluated by exact DP.
6. LE-GRA MVP: NumPy MLP embedding, k-means, then the same DP evaluator.

## Implemented During This Session

### Reproducible resource pressure

The standard experiment matrix now uses fixed RB-budget ratios:

- `light`: 0.50 of configured RBs,
- `medium`: 0.25,
- `heavy`: 0.10.

This replaced the old random 0.45-0.85 RB availability in standard experiments.
Single runs can use `--rb-budget-ratio`.

### Evaluation metrics

The evaluator and CSV files now report:

- `utility`: normalized log-bitrate utility minus switching and unserved
  penalties;
- `adr_kbps`: mean delivered user bitrate;
- `used_spectral_efficiency`: total successfully delivered user bitrate divided
  by the bandwidth of RBs actually used;
- `system_spectral_efficiency`: the same delivered bitrate divided by all
  currently available RB bandwidth; use this as the primary SE metric for
  comparisons within a fixed load level;
- `served_ratio` and `unserved_ratio`;
- `average_quality`: mean assigned quality index among served users (0-5);
- RB utilization, average switching, Jain fairness, and group count.

Do not compare the absolute value of `system_spectral_efficiency` across load
levels without qualification because its denominator changes with available
bandwidth. Compare methods within the same scenario and load.

### Progress reporting

`run_standard_matrix.py` now prints the current matrix job, teacher-label
progress, elapsed time, training epoch/loss, and evaluation method with
immediate flushing. Use `python -u` in PowerShell for unbuffered output.

### Feature ablation modes

- `history_only`: CQI history only;
- `history_cost`: CQI history plus resource-cost vector;
- `full`: CQI history, RB statistics, mobility, and resource-cost vector.

The standard matrix now uses `history_cost` as the main LE-GRA training mode.
`full` remains in the ablation matrix rather than being assumed to be better.

### Teacher-imitation diagnostics

`run_standard_matrix.py` now writes `teacher_imitation_diagnostics.csv` with:

- `pairwise_accuracy`: same/different-group accuracy against teacher groups;
- `ari`: adjusted Rand index;
- `nmi`: normalized mutual information.

These diagnostics are computed on held-out test scenarios for:

- `Multi-feature k-means`
- `LE-GRA MVP`

### Learner update before the latest rerun

After the `v2` medium run, the NumPy MLP was updated to backpropagate through
embedding L2 normalization with the correct analytic gradient instead of the
earlier approximation. This is a small but meaningful learner-side fix. A tiny
smoke test (`small_validation_results_after_grad_fix`) showed improved utility
for LE-GRA in one ambiguous/medium validation slice, but teacher-imitation
metrics did not yet improve consistently. Treat this as a correctness-oriented
learner fix, not as evidence that the learner bottleneck is solved.

## Latest Medium Experiment

Command used:

```powershell
.\run_standard_matrix.cmd `
  --train-scenarios 40 `
  --test-scenarios 20 `
  --epochs 5 `
  --scenario-modes aligned ambiguous `
  --load-levels light medium heavy `
  --kmax-values 3 `
  --seeds 9 17 23 `
  --feature-modes history_only history_cost full `
  --ablation-kmax 3 `
  --out-dir medium_matrix_results_v2_after_grad_fix
```

Raw results:

- `medium_matrix_results_v2_after_grad_fix/main_comparison_matrix.csv`
- `medium_matrix_results_v2_after_grad_fix/feature_ablation.csv`
- `medium_matrix_results_v2_after_grad_fix/teacher_imitation_diagnostics.csv`

### Main conclusions

The corrected normalization gradient materially improved LE-GRA. In the main
utility comparison, LE-GRA now beats CQI k-means, resource-cost k-means, and
multi-feature k-means in:

- `aligned/light`
- `aligned/medium`

Mean utility by scenario/load:

| Scenario/load | CQI | Resource-cost | Multi-feature | Teacher | LE-GRA |
|---|---:|---:|---:|---:|---:|
| aligned/light | 0.8337 | 0.8300 | 0.8349 | **0.8421** | **0.8357** |
| aligned/medium | 0.7905 | 0.7855 | 0.7928 | **0.8059** | **0.7950** |
| aligned/heavy | **0.5928** | 0.5914 | 0.5914 | **0.6211** | 0.5901 |
| ambiguous/light | 0.8089 | **0.8183** | 0.8120 | **0.8280** | 0.8126 |
| ambiguous/medium | **0.7704** | **0.7716** | 0.7700 | **0.7872** | 0.7698 |
| ambiguous/heavy | **0.5793** | 0.5639 | 0.5747 | **0.5964** | 0.5750 |

Across the 18 scenario/load/seed slices, LE-GRA beat:

- `CQI k-means` in `10/18`
- `Multi-feature k-means` in `11/18`
- `Resource-cost k-means` in `13/18`
- `Offline teacher` in `0/18`

This is a meaningful step up from the earlier `v2` conclusion. However, the
result is still not strong enough to claim a stable learned-embedding win in
the most important ambiguous settings or under heavy load. The teacher remains
the clear upper bound.

### Strongest current result: resource-cost features

Resource-cost features still matter, but the learner fix makes the ablation
story slightly more nuanced than before. Mean ablation utilities are:

| Scenario/load | History only | History + cost | Full |
|---|---:|---:|---:|
| Aligned/light | 0.8330 | **0.8364** | 0.8321 |
| Aligned/medium | 0.7889 | 0.7914 | **0.7930** |
| Aligned/heavy | 0.5916 | **0.5929** | 0.5925 |
| Ambiguous/light | 0.8069 | 0.8153 | **0.8157** |
| Ambiguous/medium | 0.7668 | **0.7699** | 0.7690 |
| Ambiguous/heavy | 0.5770 | 0.5770 | **0.5777** |

Interpretation:

- `history_only` is still the weakest input and should no longer be treated as
  a serious main candidate.
- `history_cost` remains a strong compact default.
- `full` is now competitive again after the learner fix, so richer inputs may
  not be inherently harmful; the earlier weakness likely reflected learner
  limitations as much as feature design.

### Teacher-imitation diagnostics

The diagnostics now show that the learner fix helped especially in aligned
scenarios.

Mean agreement with the teacher:

| Scenario/load | Method | Pairwise | ARI | NMI |
|---|---|---:|---:|---:|
| aligned/light | Multi-feature | 0.6425 | 0.2506 | 0.3443 |
| aligned/light | LE-GRA | **0.6787** | **0.3353** | **0.3831** |
| aligned/medium | Multi-feature | **0.6758** | 0.2860 | **0.3374** |
| aligned/medium | LE-GRA | 0.6638 | **0.2866** | 0.3353 |
| aligned/heavy | Multi-feature | 0.9152 | 0.8175 | **0.8383** |
| aligned/heavy | LE-GRA | **0.9175** | **0.8264** | 0.8365 |
| ambiguous/light | Multi-feature | **0.6326** | 0.2513 | **0.3495** |
| ambiguous/light | LE-GRA | 0.6281 | **0.2685** | 0.3324 |
| ambiguous/medium | Multi-feature | **0.7178** | **0.3104** | **0.3483** |
| ambiguous/medium | LE-GRA | 0.7115 | 0.3081 | 0.3383 |
| ambiguous/heavy | Multi-feature | **0.9436** | **0.8730** | **0.8744** |
| ambiguous/heavy | LE-GRA | 0.9385 | 0.8635 | 0.8680 |

The updated interpretation is that the learner is now clearly more credible in
aligned settings, but ambiguous scenarios still expose a real gap between the
current embedding learner and the best hand-crafted clustering baselines.

## Interpretation and Important Caveats

- The new pressure levels work. Quality falls substantially under heavy load;
  served ratio often remains near one because the optimizer can lower quality
  instead of dropping users.
- Used-bandwidth SE naturally favors large multicast groups because one
  transmission serves many users. This is expected and is why system SE,
  utility, quality, and served ratio must be reported together.
- The teacher optimizes QoE utility, not spectral efficiency directly. A method
  can therefore have the highest utility without the highest used-bandwidth SE.
- Current results now establish two things at once:
  - resource-cost features are valuable;
  - learner correctness mattered, because fixing the normalization gradient
    visibly improved LE-GRA.
- The learned embedding still does not dominate ambiguous settings. The
  remaining bottleneck is now better described as learner design and training
  quality, not a missing feature ablation.

## Recommended Next Steps

Do not immediately expand to `Kmax=5` or a much larger experiment matrix. The
next bottleneck is still learner diagnosis rather than more runs.

1. Treat `medium_matrix_results_v2_after_grad_fix` as the new reference result
   set. Do not keep citing the old `v2` matrix as the main conclusion.
2. Keep the focus on ambiguous scenarios. That is where LE-GRA still needs to
   prove value beyond hand-crafted clustering.
3. Run learner-focused improvements next:
   - validation-based model selection,
   - pair sampling / label construction refinements,
   - small sweeps over margin, epochs, hidden size, and learning rate.
4. Keep `history_cost` and `full` as the meaningful feature candidates. Treat
   `history_only` mainly as a weaker ablation baseline.
5. Only after learner quality stabilizes should you expand `Kmax`, seeds, or
   total scenario counts.

## P0 Validation-selection Update (2026-08-05)

A focused ambiguous-only study compared fixed training against validation-based
epoch selection with select-then-refit:

- loads: light and medium,
- seeds: 9, 17, 23,
- train/test: 40/20,
- Kmax: 3,
- epochs: 12,
- feature mode: `history_cost`,
- validation fraction: 0 versus 0.2.

Validation selection improved LE-GRA utility in only 1/6 load/seed slices. It
slightly increased mean pairwise accuracy and ARI but decreased mean NMI, and
the teacher utility gap improved in only one slice. The current contrastive
validation loss is therefore not a reliable selection criterion for final
utility or partition quality.

See `P0_VALIDATION_STUDY_ZH.md`, `p0_validation_comparison.csv`, and the two
`p0_validation_fraction_*` result directories. Validation support remains in
the code as an experimental option, but its CLI default is 0.0 so the formal
baseline is unchanged.

The next priority is P1: deterministic multi-start k-means, reuse of groupings
between evaluation and diagnostics, and explicit `test_index`/selected-group
logging. Do not expand the formal experiment matrix before P1 is complete.

## P1 Deterministic k-means Update (2026-08-05)

P1 is complete and passed. The clustering head now uses deterministic
multi-start k-means (`n_init=10` by default), main evaluation and diagnostics
reuse the exact same cached groupings, and diagnostics include `test_index`.

In the ambiguous light/medium study, `n_init=10` improved LE-GRA utility in 5/6
load/seed slices. Mean utility increased from 0.8139 to 0.8163 on light load and
from 0.7645 to 0.7702 on medium load. The improvement also benefited strong
baselines, so ambiguous/medium remains unresolved: LE-GRA reached 0.7702 versus
0.7740 for Multi-feature k-means.

See `P1_DETERMINISTIC_KMEANS_STUDY_ZH.md`, `p1_kmeans_comparison.csv`, and the
two `p1_kmeans_n_init_*` result directories. The next priority is P2:
learner-focused hard-negative/group-balanced pair sampling with explicit pair
statistics. Do not expand the formal matrix before P2.

Interpretation: P1 separates clustering noise from learner quality. Multi-start
tries several seeded centroid initializations and keeps the lowest-inertia
partition; deterministic seeding makes repeated runs reproducible. Its 5/6
slice improvement validates the measurement fix, but because Multi-feature
k-means also improved and still leads on ambiguous/medium, P1 is not evidence
that the learner bottleneck is solved.

## P2 Hard-negative Sampling Update (2026-08-05)

P2 implemented `random_balanced` and `hard_negative` pair sampling plus explicit
pair diagnostics. A pilot exposed that the old cap of 160 pairs/class selected
nearly every negative pair for 24 users, so the valid controlled comparison uses
64 pairs/class while leaving the formal default at 160.

On ambiguous/light, hard-negative reduced mean LE-GRA utility by 0.00199. On
ambiguous/medium it increased mean utility by 0.00343, but this was driven by
seed 23 (+0.01049) and was not stable across seeds. In contrast, all six mean
teacher-imitation comparisons (pairwise accuracy, ARI, NMI across light and
medium) improved. P2 therefore partially passes as a learner mechanism, but it
does not become the default: better partition imitation is still not reliably
turning into downstream utility.

See `P2_HARD_NEGATIVE_STUDY_ZH.md`, `p2_hard_negative_comparison.csv`,
`p2_random_balanced_64/`, and `p2_hard_negative_64/`. The next learner-focused
step should test semi-hard/mixed sampling or utility-aware pair weighting on the
same bounded matrix, not expand Kmax or seed count.

## P2.5 Data Audit Update (2026-08-05)

Before further learner tuning, a bounded audit was run on 360 ambiguous
scenarios (light/medium, seeds 9/17/23, train/test 40/20, Kmax=3). It found a
more fundamental input-sufficiency problem: no feature mode includes
`rb_available`, although teacher grouping depends on resource pressure, and no
feature mode includes `previous_quality`, although teacher utility directly
uses it for switching penalty. Ambiguous generation also adds random variation
to previous quality, creating target information the learner cannot observe.

For identical user/channel draws under light versus medium load, teacher K is
the same only 58.3% of the time and the exact partition only 18.3% of the time.
Teacher labels are also often non-unique in utility: the mean top-1/top-2 gap is
0.00185 on light and 0.00325 on medium; light has an average of 85/277 candidate
partitions within 0.005 of the optimum. High-dispersion scenarios drive nearly
all meaningful grouping gain, while many mid/low-dispersion partitions differ
very little in utility.

See `P2_5_DATA_AUDIT_ZH.md`, `p2_5_data_audit_summary.csv`, and the six detailed
CSVs under `p2_5_data_audit/`. The next priority is to add normalized load and
previous-quality context, then run a bounded mixed-load learner comparison.
After input sufficiency is fixed, investigate regret-aware/soft supervision and
then calibrate the generator with real channel and mobility traces.

## P2.6 Decision-context Update (2026-08-05)

P2.6 trained one learner jointly on paired light+medium ambiguous scenarios and
ablated the two missing context variables. Adding normalized previous quality
was the decisive change: it improved LE-GRA utility in all 6 load/seed slices,
raising light mean from 0.81549 to 0.82602 and medium from 0.76881 to 0.77569.
This beats Multi-feature k-means (0.81467 light, 0.77400 medium) and
Resource-cost k-means (0.81858 light, 0.77201 medium) in the bounded study.

Load context alone was nearly neutral (light -0.00001, medium +0.00173), while
adding both contexts was positive but weaker than previous quality alone. The
likely reason is architectural: previous quality is user-specific and directly
enters teacher switching utility, whereas RB budget is a scenario-wide scalar
repeated for every user and has little direct effect on k-means relative
geometry. It may require scenario-level conditioning or a separate K head.

See `P2_6_CONTEXT_STUDY_ZH.md`, `p2_6_context_comparison.csv`,
`p2_6_context_study/`, and `p2_6_context_ablation/`. Treat
`history_cost_quality` as the leading learner feature candidate, but retain the
old baseline and do not overwrite the formal matrix yet.

## P3.0 Trace-interface Update (2026-08-05)

P3.0 defines the versioned three-table contract for future SUMO/Simu5G traces:
`scenarios.csv`, `users.csv`, and `rb_rates.csv`. See `TRACE_SCHEMA.md` for
columns, units, sources, invariants, and trajectory-aware split requirements.
`trace_io.py` exports and validates/loads the bundle without serializing derived
learner features or fabricating unavailable Simu5G measurements.

The acceptance test in `run_trace_roundtrip.py` passed on six mixed light/medium
ambiguous scenarios. All allocation-relevant arrays had max absolute error 0.0,
and offline-teacher K, exact partition, and utility were identical before and
after CSV round-trip for all 6/6 scenarios. A deliberately removed RB row was
also rejected by the loader. See `P3_0_TRACE_INTERFACE_ZH.md` and the example
`p3_0_roundtrip_bundle/`.

Next is P3.1: implement a SUMO mobility exporter that populates stable UE IDs,
timestamps, positions, speed, distance, and direction in this schema. P3.2 then
adds Simu5G radio and per-RB/subband output. Do not alter the learner interface
to accommodate simulator-specific formats.

## P3.1 SUMO Mobility Adapter Update (2026-08-05)

P3.1 is implemented as a dependency-free parser for official SUMO FCD XML.
`sumo_mobility_io.py` assigns each UE to the nearest configured gNB, creates
synchronized `(timestamp, gNB)` snapshots, preserves stable vehicle IDs and
trajectory steps, and computes distance and direction-to-gNB. Deterministic
min/max user filtering supports fixed-size 24-UE studies.

The local machine does not currently have SUMO, TraCI, or sumolib installed, so
the acceptance claim is deliberately limited to format-level integration. The
fixture test passed FCD parsing, nearest-gNB assignment, stable trajectories,
approaching/receding/stopped direction cases, and deterministic filtering. See
`SUMO_MOBILITY_SCHEMA.md`, `P3_1_SUMO_MOBILITY_ADAPTER_ZH.md`,
`sumo_fcd_to_mobility.py`, and `p3_1_fixture/`.

P3.2 must add actual Simu5G serving-cell/radio state and must not fabricate CQI,
SINR, RB rates, RB budget, or previous quality in the mobility adapter.

## P3.2 Simu5G Radio Join Update (2026-08-05)

P3.2 defines normalized `radio_users.csv` and `radio_rbs.csv` contracts in
`SIMU5G_RADIO_SCHEMA.md`. `simu5g_trace_io.py` joins these tables with P3.1
mobility by exact simulation timestamp and stable UE ID, uses Simu5G serving
association, creates five-step CQI histories, validates scenario-level RB
configuration and complete per-UE RB vectors, and emits a P3.0 full bundle.

The deterministic fixture passed end-to-end: two post-warmup scenarios, four
user rows, sixteen RB rows, correct CQI histories, time-varying RB budget,
`history_cost_quality` reconstruction, P3.0 loading, and offline-teacher
execution. Removing one RB observation was correctly rejected.

This remains format-level integration because OMNeT++/INET/Simu5G are not
installed locally. See `P3_2_SIMU5G_RADIO_JOIN_ZH.md`, `p3_2_fixture/`,
`p3_2_trace_bundle/`, and `run_simu5g_join_test.py`. Next is P3.3 environment
bring-up and inspection of actual Simu5G `.vec/.sca` signals before choosing
configuration-only extraction versus a custom recorder.

## P3.3 Simu5G Environment Bring-up Update (2026-08-05)

The local environment is now real rather than format-only. The official
`opp_env` WSL image was imported as `LE-GRA-opp-env`, and
`opp_env install simu5g-1.4.3` built OMNeT++ 6.4.0, INET 4.6.0, and Simu5G
1.4.3. The official NR `Single-UE` tutorial completed its 10-second simulation
(92,628 events) and produced non-empty `.sca`, `.vec`, and `.vci` files.

Actual signal inspection found standard vectors for `averageCqiDl/Ul`,
`measuredSinrDl/Ul`, `rcvdSinrDl/Ul`, `avgServedBlocksDl/Ul`, HARQ, and MAC/RLC
throughput. This is enough for wideband CQI history and diagnostics, but not for
the complete per-UE/per-RB counterfactual achievable-rate matrix required by
the P3.2 schema and offline teacher. `avgServedBlocks` only reports realized
allocation and must not be used as a substitute.

See `P3_3_ENVIRONMENT_BRINGUP_ZH.md` and `p3_3_*.sh`. Next is P3.4: implement a
minimal Simu5G recorder/exporter for stable UE identity, serving gNB, RB budget,
and per-UE/per-logical-band achievable rate, then validate a tiny single-cell
trace through the existing P3.2 joiner. Do not expand seeds, Kmax, or the
experiment matrix yet.

## P3.4 Simu5G Per-Band Radio Exporter Update (2026-08-06)

P3.4 patches `LteMacEnb::macHandleFeedbackPkt` at the point where the serving
gNB receives ALLBANDS CQI. For every UE and logical band, the recorder calls
Simu5G's NR AMC `computeBitsPerRbBackground` and writes CQI plus transport-block
bits per slot. This is counterfactual channel capacity available before actual
scheduler allocation, not realized throughput. The source modification is
versioned as `simu5g_p3_4_radio_recorder.patch` and can be reapplied/rebuilt with
`p3_4_apply_and_build.sh`.

Both actual tests passed. The 2-second Single-UE case produced 2,004 complete
raw rows. The official 5-UE case with background interference produced 10,020
raw rows, 1,670 complete six-band UE snapshots, CQIs 9/13/14/15, and distinct
NR TBS values 608/984/1128/1160 bits per slot. The Python exporter binned the
feedback at 0.1 seconds and produced 105 normalized user rows plus 630 RB rows.

All assumptions are written to `export_metadata.json`: 1 ms slot for the
numerology-0 tutorial, 50% study RB budget, logical-band RB abstraction, and
constant previous quality 3 explicitly marked as an experiment control rather
than a measured video state. See `P3_4_SIMU5G_RADIO_EXPORTER_ZH.md` and
`p3_4_actual_radio/`.

Next is P3.5, not a larger learner matrix: build a tiny coupled SUMO+Simu5G
scenario, establish stable vehicle-to-node IDs and one timestamp source, then
export measured video quality. Only after the coupled bundle passes the P3.2
joiner and teacher should learner training use it.

## P3.5 One-Clock SUMO + Simu5G Coupling Update (2026-08-06)

P3.5 created a separate compatible workspace with OMNeT++ 6.3.0, INET 4.6.0,
Veins 5.3.1/veins_inet, Simu5G 1.4.3, and SUMO 1.22.0. The official Simu5G NR
cars `VoIP-DL` scenario completed a six-second TraCI-coupled run. SUMO vehicle
creation/mobility and Simu5G radio therefore share one OMNeT event timeline.

Two versioned recorder extensions join state by OMNeT module full path instead
of assuming insertion order. The observed mappings were SUMO `0` ->
`Highway.car[0]` -> Simu5G `2049` and SUMO `1` -> `Highway.car[1]` -> Simu5G
`2050`. Final bundle UE IDs are only `0` and `1`.

The run produced 67 mobility rows and 27,950 radio rows, all radio observations
having complete 25-band vectors. Common 0.1-second bins yielded 67 normalized
radio users and 1,675 RB rows. After five-step CQI warm-up, the unchanged P3.2
joiner produced 55 scenarios, 59 user rows, and 1,475 RB rows; all 55 scenarios
ran through the offline teacher. `run_p3_5_coupled_test.py` verifies mapping,
timestamps, band completeness, join counts, metadata, and teacher execution.

This remains an integration artifact, not training evidence: only two cars are
present, CQI is always 15, and previous quality is still an explicit constant
control rather than measured video state. See `P3_5_SUMO_SIMU5G_COUPLING_ZH.md`.
P3.6 should first create informative channel/resource variation and record real
video quality, audit those data, and only then run a learner-focused real-trace
experiment. Do not expand Kmax, seeds, or the whole matrix yet.

## Suggested Prompt on the Next Computer

Use the complete Traditional-Chinese prompt in `NEXT_SESSION_PROMPT.md`. The
next phase is P3.6 coupled-data audit, informative scenario design, and measured
video quality. It is no longer appropriate to begin by modifying the learner or
expanding the synthetic standard matrix.

## P3.6 Coupled Trace Audit and Focused Learner Update (2026-08-06)

P3.6 is no longer a placeholder. The project now has an informative coupled
trace line built on top of the P3.5 pipeline.

### P3.6a-P3.6d: audit first, not learner expansion

The first coupled audit confirmed that the original small coupled bundle was too
easy: CQI saturation was high, teacher split cases were almost absent, and the
first learner slice contained no meaningful grouping supervision. This was a
data-regime problem rather than evidence about learner quality.

See:

- `P3_6_COUPLED_AUDIT_ZH.md`
- `P3_6A_INFORMATIVE_SCENARIO_ZH.md`
- `P3_6B_VIDEO_STATE_ZH.md`
- `P3_6C_COUPLED_LEARNER_ZH.md`
- `P3_6D_TEACHER_DECISION_AUDIT_ZH.md`

### P3.6e: create actual split pressure

The coupled scenario was redesigned with a wider geometry, lower transmit
power, heterogeneous traffic/mobility, longer runtime, and later a tighter
RB-budget sweep. The key result is that `rb_budget_ratio = 0.32` is the first
setting that produces real positive-gain teacher split decisions rather than
numerical ties.

Important coupled artifacts:

- `p3_6e_coupled_output/`
- `p3_6e_coupled_bundle/`
- `p3_6e2_budget_sweep/`
- `p3_6e3_coupled_bundle/`
- `p3_6e3_teacher_audit/`

Important conclusions:

- `rb_budget_ratio = 0.40` was still effectively too loose.
- `rb_budget_ratio = 0.32` produced 24 positive-gain teacher split scenarios.
- Those positive-gain cases concentrated on one focused UE set: `0|1|2|3`.
- Adding heterogeneous video-state control increased quality variation, but did
  not by itself create more teacher split gain; the main bottleneck remained
  resource pressure.

See:

- `P3_6E_SPLIT_PRESSURE_DESIGN_ZH.md`
- `P3_6E_1_IMPLEMENTATION_ZH.md`
- `P3_6E_2_BUDGET_SWEEP_RESULTS_ZH.md`

### P3.6f: focused learner test exposed a supervision mismatch

P3.6f moved the positive-gain UE set `0|1|2|3` entirely into the learner test
slice. This succeeded as an evaluation design because the learner-facing test
set finally contained informative split cases, but it also exposed the real
training bottleneck: the train split then contained essentially no positive-gain
split supervision.

On that focused test slice:

- Offline teacher utility: `0.7127`
- Multi-feature / Resource-cost k-means: `0.7127`
- LE-GRA MVP: `0.7117`

Teacher-imitation diagnostics showed Multi-feature exactly matching the teacher
and LE-GRA nearly matching it, but train-side pair statistics still showed
almost no informative negative pairs. The fair interpretation is not that the
learner cannot work on real traces; it is that the supervision protocol was
misaligned.

See `P3_6F_FOCUSED_SPLIT_RESULTS_ZH.md`.

### P3.6g: train-side supervision redesign works

P3.6g answered the next critical question: if train data actually contains
positive-gain split supervision, can LE-GRA learn the coupled teacher decision?

The answer is yes.

`run_p3_6g_temporal_learner.py` builds a focused temporal split for UE set
`0|1|2|3`:

- focus-train window: `<= 15.9s`
- focus-test window: `16.0s` to `18.0s`
- background train scenarios are retained

This gives:

- `focus_train_positive_gain_count = 12`
- `focus_test_positive_gain_count = 12`

On the 21-scenario focused future window:

- No grouping utility: `0.6402`
- Offline teacher utility: `0.6622`
- Multi-feature k-means utility: `0.6622`
- LE-GRA MVP utility: `0.6622`

Both Multi-feature k-means and LE-GRA achieved perfect teacher imitation on the
test window (`pairwise_accuracy = ARI = NMI = 1.0`).

This is an important protocol-level result. The earlier coupled learner failure
was not simply "the learner is too weak"; it was largely that the train split
did not actually expose the learner to informative split-gain supervision. Once
train and test are aligned around a real split regime, LE-GRA can reproduce the
teacher decision on a future time window of the same focused slice.

See:

- `P3_6G_TRAIN_SIDE_SUPERVISION_REDESIGN_ZH.md`
- `p3_6g_temporal_learner/`
- `run_p3_6g_temporal_learner.py`

### What should happen next

Do not jump straight to a larger coupled learner matrix yet. The immediate next
step is to test whether the P3.6g conclusion generalizes beyond one focused UE
set and one temporal window.

Recommended order:

1. Build more focused temporal slices that contain positive-gain teacher split
   supervision in both train and test.
2. Check whether the same conclusion holds beyond UE set `0|1|2|3`.
3. Compare whether LE-GRA remains as stable as Multi-feature k-means across
   those slices.
4. Only after that should the project consider expanding coupled seeds, Kmax,
   or a broader learner matrix.

## P3.6h-P3.6i2 Pressure Sweep and Conservative Redesign Update (2026-08-06)

After P3.6g, the project did not expand the learner matrix. It first searched
for additional real split regimes in the coupled trace and then tested whether
scenario redesign could create or preserve those regimes.

### P3.6h: near-miss pressure sweep

`run_p3_6h_near_miss_pressure_sweep.py` replayed the same coupled raw trace at
several tighter RB-budget ratios. This showed that the split regime is highly
localized rather than monotonic:

- `rb_032`: 24 positive snapshots, 1 positive family
- `rb_028`: 9 positive snapshots, 3 positive families
- `rb_024`: 3 positive snapshots, 2 positive families
- `rb_020`: 0 positive snapshots

The important interpretation is that "more pressure" is not always better. If
the budget is too loose, the teacher stays single-group; if it is too tight,
everyone is uniformly constrained and split gain disappears again.

At `rb_028`, one new family became especially important:

- `1|2|3|4|5|6 @ gnb_2`
  - time: `27.3s` to `27.6s`
  - 4 positive snapshots
  - max teacher gain vs single: `0.0530`

See:

- `P3_6H_NEAR_MISS_PRESSURE_SWEEP_ZH.md`
- `P3_6H_2_RB028_FAMILY_FOLLOWUP_ZH.md`
- `p3_6h_pressure_sweep/`

### P3.6h follow-up learner result

A focused learner follow-up on the `rb_028` family was partially encouraging
but not yet decisive.

For the stronger `1|2|3|4|5|6 @ gnb_2` slice:

- Offline teacher utility: `0.5714`
- LE-GRA utility: `0.5708`
- Strong baselines matched LE-GRA

This means the family is real and learnable enough to matter, but the learner
did not clearly separate from strong hand-crafted clustering there.

### P3.6i: aggressive targeted redesign failed

The first targeted redesign (`p3_6i`) aggressively changed northbound spacing
and speeds to try to amplify split pressure around the discovered family.

That redesign failed. Teacher audit on the rebuilt coupled bundle produced:

- `positive_segment_count = 0`
- `candidate_temporal_slice_count = 0`

The critical diagnosis is structural. The rebuilt bundle retained only eight
vehicles:

- `0,1,2,3,4,5,6,7`

By contrast, the earlier informative bundles retained ten:

- `0,1,2,3,4,5,6,7,15,31`

This strongly suggests that the informative split regime depends not only on
the northbound group but also on cross-traffic participants such as `15` and
`31`. Over-aggressive redesign destroyed the interaction pattern that made the
teacher prefer splitting.

See `P3_6I_TARGETED_REDESIGN_ZH.md` and `p3_6i_focus_mining/`.

### P3.6i-2: conservative redesign recovered positive split regimes

P3.6i-2 reversed the design philosophy. Instead of stretching vehicles apart,
it preserved the original northbound departure rhythm and applied only mild
speed differences to the suspected key users.

Artifacts:

- `p3_6i2_coupled_scenario/`
- `p3_6i2_coupled_output/`
- `p3_6i2_coupled_bundle/`
- `p3_6i2_teacher_audit/`
- `p3_6i2_focus_mining/`
- `P3_6I_2_CONSERVATIVE_REDESIGN_ZH.md`

Key rebuilt-trace facts:

- raw radio rows: `1,353,826`
- raw mobility rows: `3,249`
- retained UE IDs: `0,1,2,3,4,5,6,7,15,31`
- teacher scenarios: `875`

Teacher audit on the full bundle recovered real split gain:

- `scenario_count = 830`
- `positive_gain_count = 9`
- `multi_group_count = 9`
- `max_teacher_gain_vs_single = 0.05716`

Focused mining found two positive segments and seven candidate temporal slices.
The two positive segments are:

1. `0|1|2|3|4 @ gnb_2`
   - `18.7s` to `19.2s`
   - 6 positive snapshots
   - teacher split isolates one user: `[[0,1,2,4],[3]]`
   - gain: `0.01190`
2. `0|1|15|2|3|4|5 @ gnb_1`
   - `43.7s` to `43.9s`
   - 3 positive snapshots
   - teacher split isolates one user: `[[0,1,3,4,5,6],[2]]`
   - gain: `0.05716`

This is an important scenario-design result. It shows that positive split
regimes are not gone; they are highly sensitive to preserving the original
traffic overlap and cross-traffic structure.

### Recommended next step after P3.6i-2

The best immediate next experiment is not a broad matrix. It is a focused
temporal learner on the recovered conservative-redesign slices:

1. First run the `seg_02` family `0|1|2|3|4 @ gnb_2` around `18.8s-19.0s`
   because it has the longer positive window (`6` snapshots).
2. Then run the higher-gain but shorter `seg_01` family
   `0|1|15|2|3|4|5 @ gnb_1`.
3. Compare LE-GRA against Multi-feature and the offline teacher on both slices.

If LE-GRA reproduces the teacher on both recovered slices, the project can make
a stronger claim that the P3.6g supervision result generalizes beyond one
focused UE set and one time window.

### P3.6i-2 seg_02 learner result

The first recovered conservative-redesign slice has already been tested:

- family: `0|1|2|3|4 @ gnb_2`
- train window end: `18.9s`
- test window: `19.0s` to `19.2s`
- output: `p3_6i2_seg02_temporal_learner/`

This slice had:

- `focus_train_positive_gain_count = 3`
- `focus_test_positive_gain_count = 3`

On the three-snapshot test window:

- No grouping utility: `0.6072`
- Offline teacher utility: `0.6191`
- Multi-feature k-means utility: `0.6191`
- LE-GRA MVP utility: `0.6191`

Teacher-imitation diagnostics were perfect for both Multi-feature and LE-GRA:

- pairwise accuracy: `1.0`
- ARI: `1.0`
- NMI: `1.0`

Interpretation: this is another successful protocol-level result. It confirms
that after conservative redesign, the recovered `seg_02` slice is a real split
regime and that LE-GRA can again reproduce the teacher when train/test are
aligned to that regime. However, the test window is still only three snapshots
and Multi-feature also matches the teacher exactly, so this should be treated
as a generalization of the supervision conclusion, not yet as evidence that
LE-GRA clearly surpasses strong hand-crafted clustering.

### P3.6i-2 seg_01 learner result

The second recovered conservative-redesign slice has also been tested, and it
was evaluated with both plausible split points because the positive window is
only three snapshots long:

- family: `0|1|15|2|3|4|5 @ gnb_1`
- positive window: `43.7s` to `43.9s`
- outputs:
  - `p3_6i2_seg01_split437_temporal_learner/`
  - `p3_6i2_seg01_split438_temporal_learner/`

Results were identical across both split variants:

- No grouping utility: `0.5472`
- Offline teacher utility: `0.6043`
- Multi-feature k-means utility: `0.6043`
- LE-GRA MVP utility: `0.6043`

The more balanced split (`43.7s` train end, `43.8s-43.9s` test) had:

- `focus_train_positive_gain_count = 7`
- `focus_test_positive_gain_count = 2`

The later split (`43.8s` train end, `43.9s` test) had:

- `focus_train_positive_gain_count = 8`
- `focus_test_positive_gain_count = 1`

Teacher-imitation diagnostics were perfect in both runs for both Multi-feature
and LE-GRA:

- pairwise accuracy: `1.0`
- ARI: `1.0`
- NMI: `1.0`

Interpretation: this is the strongest conservative-redesign learner result so
far. Unlike `seg_02`, this family includes cross-traffic user `15`, occurs on
`gnb_1`, and has a much larger teacher gain (`0.05716` versus `0.01190` on
`seg_02`). LE-GRA still reproduces the teacher exactly. The evidence now spans
multiple focused temporal slices and more than one family structure.

The careful conclusion remains the same: the key bottleneck in P3.6 is not that
LE-GRA categorically fails on coupled traces, but that the research pipeline
must preserve and expose informative split-supervision regimes. Multi-feature
still matches the teacher on these focused slices, so this is a strong
supervision/protocol result rather than final proof of learner superiority.

## P3.6j Scenario-Redesign Direction (2026-08-06)

After recovering and validating `seg_02` and `seg_01`, the next priority is no
longer "can LE-GRA reproduce the teacher at all?" That has already been shown.
The more important question is how to widen the gap among:

- Offline teacher
- LE-GRA
- Multi-feature k-means
- No grouping

The recommended direction is a new targeted scenario redesign line, documented
in `P3_6J_TARGETED_SCENARIO_DESIGN_V2_ZH.md`.

Core logic:

1. The current focused slices already show real split gain, because
   `teacher > no-group`.
2. However, `LE-GRA` and `Multi-feature` still often tie the teacher exactly,
   which means the current split regimes are still simple enough to be captured
   by strong hand-crafted snapshot features.
3. Therefore the next step should not first change the learner. It should make
   the decision regime more dependent on temporal context and previous-quality
   divergence while preserving the informative traffic interaction structure.

The proposed P3.6j design has three escalating mechanisms:

1. `P3.6j-1`: quality-divergence variant
   - preserve the `p3_6i2` traffic structure
   - enlarge `previous_quality` differences inside the active family
   - keep `rb_budget_ratio = 0.28`
2. `P3.6j-2`: cost-order mismatch variant
   - keep wideband CQI relatively close
   - increase per-band TBS / resource-cost dispersion
3. `P3.6j-3`: temporal-flip variant
   - create short windows where the best isolated user changes over time

The most recommended immediate implementation is `P3.6j-1`, because it has the
lowest structural risk and is most consistent with the earlier P2.6 finding
that previous quality is an important learner input.

Success should be judged not only by more positive split families, but by a
more discriminative ranking:

- `teacher` stays clearly above `no-group`
- `Multi-feature` no longer always matches the teacher perfectly
- `LE-GRA` becomes more stable than `Multi-feature` on at least part of the
  recovered temporal slices

### P3.6j-1 implementation result

`P3.6j-1` has now been implemented as a first quality-divergence variant. It
adds a new `previous_quality_mode` in `simu5g_raw_radio_export.py`:

- `deterministic_controller_family_divergence`

and a dedicated builder:

- `build_p3_6j1_coupled_bundle.py`

This variant keeps the `p3_6i2` raw trace fixed and only changes the
deterministic quality-state controller. It assigns:

- high-anchor profiles to `0`, `1`, `15`, `31`
- low-anchor profiles to `2`, `3`, `4`, `5`, `6`, `7`
- bridge profiles to the rest

The controller also applies explicit quality bands, so this is a stronger
intervention than simple heterogeneous EWMA parameters.

Important result:

- global `previous_quality` divergence did increase
- but the key positive-gain families did not change at all

Teacher audit remained identical to `p3_6i2`:

- `positive_gain_count = 9`
- `positive_segment_count = 2`
- `candidate_temporal_slice_count = 7`
- `max_teacher_gain_vs_single = 0.057159`

The reason is now better understood. In the crucial positive windows:

- `seg_01` family `0|1|15|2|3|4|5 @ gnb_1` still had
  `previous_quality_range = 0`
- `seg_02` family `0|1|2|3|4 @ gnb_2` still had only
  `previous_quality_range = 1`

So `P3.6j-1` is a useful negative result: enlarging quality divergence at the
global trace level is not enough. If the project wants larger teacher-vs-baseline
gaps, the divergence must persist specifically inside the positive-gain family
and time window, not just in the dataset overall.

This narrows the next redesign step further. The most promising follow-up is a
family/time-window targeted state divergence variant rather than another global
heterogeneity sweep.

### P3.6j-1b targeted-window result

`P3.6j-1b` has also been implemented as the next refinement after `j-1`. It
adds a new mode in `simu5g_raw_radio_export.py`:

- `deterministic_controller_seg01_targeted`

and a dedicated builder:

- `build_p3_6j1b_coupled_bundle.py`

This variant keeps the same raw trace and directly targets the strongest known
positive-gain family:

- `0|1|15|2|3|4|5 @ gnb_1`
- time window: `43.7s` to `43.9s`

Inside that window it forces:

- high group `0,1,15` to remain at quality `3`
- low group `2,3,4,5` to remain at quality `0`

So unlike `j-1`, this is a true family/time-window intervention rather than a
global profile change.

Important result:

- the targeted state divergence worked exactly as intended
- `seg_01` previous-quality range increased from `0` to `3`
- but teacher gain *decreased* from `0.057159` to `0.028588`

Global summary after `j-1b`:

- `positive_gain_count = 9` (unchanged)
- `positive_segment_count = 2` (unchanged)
- `candidate_temporal_slice_count = 7` (unchanged)
- `max_teacher_gain_vs_single = 0.028588` (down from `0.057159`)

This is an important negative result. It shows that even correctly targeted
previous-quality divergence does not automatically enlarge teacher gain. In
fact, if the divergence is too extreme relative to the CQI/resource-cost
structure, it can weaken the original split advantage.

The next redesign should therefore not simply make state differences larger. It
should seek a more moderate divergence that is structurally aligned with the
family's split economics.

### P3.6j-1c mild targeted-window result

`P3.6j-1c` has now been run as the milder counterpart to `j-1b`. It adds:

- `deterministic_controller_seg01_targeted_mild`
- `build_p3_6j1c_coupled_bundle.py`

Inside the same `seg_01` window (`43.7s` to `43.9s`), it enforces:

- high group `0,1,15` at quality `2`
- low group `2,3,4,5` at quality `1`

This targeted divergence worked as intended:

- `seg_01 previous_quality_range = 1`

But the key result is that `j-1c` simply returned the trace to the original
teacher-gain level rather than improving it:

- `p3_6i2 seg_01 gain = 0.057159`
- `p3_6j1b seg_01 gain = 0.028588`
- `p3_6j1c seg_01 gain = 0.057159`

Global summary after `j-1c` is effectively identical to `p3_6i2`:

- `positive_gain_count = 9`
- `positive_segment_count = 2`
- `candidate_temporal_slice_count = 7`
- `max_teacher_gain_vs_single = 0.057159`

Interpretation: the project now has a useful three-point conclusion:

1. global quality divergence (`j-1`) is insufficient
2. overly strong targeted divergence (`j-1b`) weakens the split advantage
3. mild targeted divergence (`j-1c`) preserves the original regime but does not
   enlarge it

This strongly suggests that the next promising redesign should move away from
quality-state manipulation alone and focus instead on CQI/resource-cost
misalignment or other ambiguity structures that change the economics of the
teacher split decision itself.

### P3.6j-2 cost-mismatch result

`P3.6j-2` has now been implemented as the first cost-side redesign variant. It
uses:

- `build_p3_6j2_cost_mismatch_bundle.py`

and creates:

- `p3_6j2_cost_mismatch_bundle/`

This variant does not rerun the simulator. It copies `p3_6i2_coupled_bundle`
and modifies only the per-band RB rate profile of the teacher-isolated user in
the strongest family:

- family: `0|1|15|2|3|4|5 @ gnb_1`
- timestamps: `43.7s`, `43.8s`, `43.9s`
- targeted user: `15`

The intervention scales `ue 15` RB rates by band range:

- RB `0-7`: `0.62`
- RB `8-15`: `0.76`
- RB `16-24`: `0.88`

This increases resource-cost dispersion while leaving mobility, CQI, and
previous-quality unchanged.

Important result:

- `seg_01 resource_cost_range` increased to `4.0`
- but `seg_01 teacher_gain_vs_single` dropped from `0.057159` to `0.031899`

Global summary after `j-2`:

- `positive_gain_count = 9` (unchanged)
- `positive_segment_count = 2` (unchanged)
- `candidate_temporal_slice_count = 7` (unchanged)
- `max_teacher_gain_vs_single = 0.031899` (down from `0.057159`)

Interpretation: cost-mismatch is still a plausible direction, but this first
version shows that simply making the already-isolated user uniformly more
expensive is not enough. It increases cost range but does not improve the
relative split advantage. The next variant should change the *shape* of the
resource-cost profile or create misaligned candidate users, not just apply a
stronger penalty to one user.

### P3.6j-2b shape-mismatch result

`P3.6j-2b` has now been fully formalized beyond the earlier probe. It uses:

- `build_p3_6j2b_shape_mismatch_bundle.py`

and targets the same strongest family:

- `0|1|15|2|3|4|5 @ gnb_1`
- timestamps: `43.7s`, `43.8s`, `43.9s`

But unlike `j-2`, it does **not** further penalize the already-isolated
`ue 15`. Instead it targets a strong main-group user:

- targeted user: `4`

It weakens that user's high-end RB rates so the sorted per-band rate multiset
becomes worse even though mobility, CQI metadata, and previous-quality remain
unchanged.

This is important because `le_gra_mvp.py` sorts RB rates before computing user
resource cost, so `j-2b` must change the sorted rate multiset itself, not just
permute band indices.

Formal outputs now exist in:

- `p3_6j2b_shape_mismatch_bundle/`
- `p3_6j2b_teacher_audit/`
- `p3_6j2b_focus_mining/`

Observed result:

- teacher grouping in `seg_01` changed structurally
- but teacher gain still did not increase

Measured effect:

- `p3_6i2 seg_01 gain = 0.057159`
- `p3_6j2 seg_01 gain = 0.031899`
- `p3_6j2b seg_01 gain = 0.032425`

Formal `j-2b` summary:

- `positive_gain_count = 9`
- `positive_segment_count = 2`
- `candidate_temporal_slice_count = 7`
- `max_teacher_gain_vs_single = 0.032425`

So `j-2b` is slightly better than `j-2`, and unlike `j-2` it genuinely changes
the grouping structure, but it still remains well below the original `p3_6i2`
teacher gain.

Interpretation: this is the first cost-side variant that looks directionally
closer to the real target. Pure penalty on the isolated user is not enough;
shape mismatch on a competing high-CQI user can move the teacher decision, but
the current one-user version still does not enlarge the split-vs-single gain.
The next promising step is a dual-candidate mismatch variant rather than a
stronger single-user penalty.

### P3.6j-2c dual-candidate mismatch result

`P3.6j-2c` has now been implemented as the first formal dual-candidate
cost-shape variant. It uses:

- `build_p3_6j2c_dual_candidate_mismatch_bundle.py`

and creates:

- `p3_6j2c_dual_candidate_mismatch_bundle/`
- `p3_6j2c_teacher_audit/`
- `p3_6j2c_focus_mining/`

Design:

- family: `0|1|15|2|3|4|5 @ gnb_1`
- timestamp: `43.8s` only
- targeted users: `4` and `5`

The intervention deliberately keeps `43.7s` and `43.9s` unchanged so the
original high-gain teacher split remains on both sides of the segment, while the
middle snapshot is perturbed into a dual-candidate split state.

Rate transforms:

- `ue 4`: strong top-end compression (`0.70 / 0.84 / 0.94`)
- `ue 5`: lighter broad compression (`0.92 / 0.95 / 0.98`)

Observed result:

- `43.7s`: teacher remains `[[0,1,3,4,5,6],[2]]`
- `43.8s`: teacher becomes `[[0,1,3,4],[2,5,6]]`
- `43.9s`: teacher returns to `[[0,1,3,4,5,6],[2]]`

So `j-2c` does **not** enlarge the global teacher gap, but it does produce a
clean snapshot-level split-identity flip within the same positive-gain family.

Measured effect:

- `seg_01 mean gain = 0.040669714529`
- `seg_01 max gain = 0.057159402144`
- `max_teacher_gain_vs_single = 0.057159402144`
- `positive_gain_count = 9`
- `positive_segment_count = 2`
- `candidate_temporal_slice_count = 7`

Interpretation:

- `j-2c` is better than `j-2b` if the goal is to create temporal ambiguity
  inside a still-positive teacher regime
- it is **not** better than `p3_6i2` if the goal is to maximize raw teacher
  advantage

Most important new insight:

> cost-side redesign can create a local teacher identity flip without rerunning
> mobility, CQI, or previous-quality generation, but preserving that flip while
> also increasing `teacher - no-group` remains unsolved.

This suggests the next promising continuation is not a stronger one-user
penalty, but a follow-up around `j-2d`:

- preserve the `43.7s` / `43.9s` high-gain endpoints
- widen the middle flip window
- add one more ambiguous candidate or a mild quality-state offset only inside
  the flipped snapshots

### P3.6j-2d extended flip-window result

`P3.6j-2d` has now been implemented as the first multi-snapshot follow-up to
`j-2c`. It uses:

- `build_p3_6j2d_extended_flip_window_bundle.py`

and creates:

- `p3_6j2d_extended_flip_window_bundle/`
- `p3_6j2d_teacher_audit/`
- `p3_6j2d_focus_mining/`

Design:

- family: `0|1|15|2|3|4|5 @ gnb_1`
- timestamps: `43.8s` and `43.9s`
- targeted users: `4` and `5`

Key result:

- `43.7s`: teacher remains `[[0,1,3,4,5,6],[2]]`
- `43.8s`: teacher becomes `[[0,1,3,4],[2,5,6]]`
- `43.9s`: teacher stays `[[0,1,3,4],[2,5,6]]`

So unlike `j-2c`, which produced only a one-snapshot flip, `j-2d` creates a
two-snapshot flipped window inside the same positive-gain family.

Measured effect:

- `43.7s gain = 0.057159402144`
- `43.8s gain = 0.007690339299`
- `43.9s gain = 0.007690339299`
- `seg_01 mean gain = 0.024180026914`
- `max_teacher_gain_vs_single = 0.057159402144`
- `positive_gain_count = 9`
- `positive_segment_count = 2`
- `candidate_temporal_slice_count = 7`

Interpretation:

- `j-2d` is better than `j-2c` if the objective is to lengthen the temporal
  ambiguity window
- `j-2d` is worse than `j-2c` if the objective is to preserve average teacher
  advantage inside `seg_01`

This cleanly separates two research directions:

1. higher-gain but shorter ambiguity (`j-2c`)
2. lower-gain but longer ambiguity (`j-2d`)

### Three-group status

This thread also checked whether teacher decisions ever split into three or
more groups.

Current status as of August 6, 2026:

- every formal audit still has `max_teacher_group_count = 2`
- no `scenario_teacher_decisions.csv` row has `teacher_group_count >= 3`
- an extra 144-combination local probe on `seg_01` also found zero 3-group
  cases

So there is currently no evidence that the existing offline teacher naturally
prefers 3-way partitions in the present coupled regimes; its behavior remains
strongly biased toward single-cut / two-group structure.

### P3.6j-2e symmetric flip-window result

`P3.6j-2e` has now been implemented as a validation step after `j-2d`. It uses:

- `build_p3_6j2e_symmetric_flip_window_bundle.py`

and creates:

- `p3_6j2e_symmetric_flip_window_bundle/`
- `p3_6j2e_teacher_audit/`
- `p3_6j2e_focus_mining/`

Design:

- family: `0|1|15|2|3|4|5 @ gnb_1`
- timestamps: `43.8s` and `43.9s`
- targeted users: `4` and `5`

Unlike `j-2d`, which used asymmetric transforms between the two flipped
snapshots, `j-2e` applies the original `j-2c` dual-candidate transform
symmetrically to both `43.8s` and `43.9s`.

Observed result:

- `43.7s`: teacher remains `[[0,1,3,4,5,6],[2]]`
- `43.8s`: teacher becomes `[[0,1,3,4],[2,5,6]]`
- `43.9s`: teacher stays `[[0,1,3,4],[2,5,6]]`

Measured effect:

- `43.7s gain = 0.057159402144`
- `43.8s gain = 0.007690339299`
- `43.9s gain = 0.007690339299`
- `seg_01 mean gain = 0.024180026914`
- `max_teacher_gain_vs_single = 0.057159402144`
- `positive_gain_count = 9`
- `positive_segment_count = 2`
- `candidate_temporal_slice_count = 7`

Most important conclusion:

`j-2e` is numerically equivalent to `j-2d`. This means the two-snapshot flipped
regime is not a fragile one-off caused by a particular asymmetric tuning; it is
instead a reproducible plateau under a broader class of dual-candidate
cost-shape perturbations.

Interpretation:

- further gain improvement is unlikely to come from small in-family rescaling of
  the same `ue 4 / ue 5` cost-shape pattern
- if we want larger `teacher / LE-GRA / multi-feature / no-group` separation,
  we likely need to leave this local plateau by introducing a third candidate,
  a local previous-quality offset, or a changed family composition rather than
  more micro-tuning of the same two-user regime

### P3.6j-2f third-candidate collapse result

`P3.6j-2f` has now been implemented as the first explicit plateau-boundary
challenge after `j-2d/j-2e`. It uses:

- `build_p3_6j2f_third_candidate_collapse_bundle.py`

and creates:

- `p3_6j2f_third_candidate_collapse_bundle/`
- `p3_6j2f_teacher_audit/`
- `p3_6j2f_focus_mining/`

Design:

- family: `0|1|15|2|3|4|5 @ gnb_1`
- timestamps: `43.8s` and `43.9s`
- retained the `ue 4 / ue 5` dual-candidate cost-shape changes
- added a third cost-side candidate on `ue 0`
- added a local previous-quality offset:
  - `ue 15 -> 2`
  - `ue 4 -> 0`
  - `ue 5 -> 0`

Observed result:

- `43.7s`: teacher remains `[[0,1,3,4,5,6],[2]]`
- `43.8s`: teacher collapses to `[[0,1,2,3,4,5,6]]`
- `43.9s`: teacher collapses to `[[0,1,2,3,4,5,6]]`

Measured effect:

- `multi_group_count = 7` (down from `9`)
- `positive_gain_count = 7` (down from `9`)
- `candidate_temporal_slice_count = 5` (down from `7`)
- `43.7s gain = 0.057159402144`
- `43.8s gain = 0.0`
- `43.9s gain = 0.0`

Interpretation:

`j-2f` is the clearest boundary test so far. When the current `seg_01`
two-candidate plateau is pushed with a third cost-side candidate plus a local
quality-state offset, teacher behavior does **not** expand to 3-way partitions
or richer positive splits. Instead, the split incentive disappears and the
system collapses back to single-group allocation on the flipped snapshots.

This strengthens two emerging conclusions:

1. the current offline teacher is strongly biased toward single-cut / two-group
   structure rather than natural 3-way partitioning
2. within this family, moving away from the narrow `j-2d/j-2e` plateau appears
   more likely to destroy the positive split regime than to create a stronger
   one

### P3.6k family-switch decision

After `j-2f`, the workflow explicitly stopped investing in the old
`seg_01 = 0|1|15|2|3|4|5 @ gnb_1` family and switched to a new family-search
stage.

New script:

- `rank_family_redesign_candidates.py`

It ranks near-miss families from a teacher audit using:

- `max_cqi_range`
- `max_resource_cost_range`
- `max_previous_quality_range`
- `user_count`
- `scenario_count`
- `duration`

Formal output:

- `p3_6k_family_ranking/family_redesign_ranking.csv`
- `p3_6k_family_ranking/top10_family_redesign_ranking.csv`
- `p3_6k_family_ranking/summary.txt`

Current top redesign target:

- `3|4|5|6 @ gnb_2`

Why this family won:

- `scenario_count = 42`
- `user_count = 4`
- `max_cqi_range = 6.0`
- `max_resource_cost_range = 0.833333`
- `max_previous_quality_range = 1.0`
- time support = `25.8s ~ 29.9s`

Most important interpretation:

- this family is a better next source than `seg_01` because it is not dominated
  by one obvious weak outlier versus an otherwise uniform strong group
- `ue 4` looks like a meaningful weak candidate, while `ue 3 / 5 / 6` provide a
  richer competitive structure than the old `gnb_1` plateau family
- the longer time window (`42` snapshots) makes it much more suitable for fresh
  focused slice mining, redesign, and later learner train/test slicing

Recommended next stage:

- `P3.6k-1`: focused audit and redesign on `3|4|5|6 @ gnb_2`

### P3.6k-1 focused audit result

`P3.6k-1` has now been completed on the new top-ranked family:

- `3|4|5|6 @ gnb_2`

New script:

- `build_p3_6k1_family_focus.py`

Formal output:

- `p3_6k1_family_focus/summary.txt`
- `p3_6k1_family_focus/family_timeline.csv`
- `p3_6k1_family_focus/family_user_snapshot_metrics.csv`
- `p3_6k1_family_focus/family_user_summary.csv`
- `p3_6k1_family_focus/peak_snapshots.csv`

Measured family profile:

- `scenario_count = 42`
- `time_window = 25.8s ~ 29.9s`
- `max_teacher_gain_vs_single = 0.0`
- `max_cqi_range = 6.0`
- `max_resource_cost_range = 0.833333`
- `max_previous_quality_range = 1.0`

Most important per-user finding:

- `ue 5` becomes the real late-window weak candidate
  - `cqi = 9~10`
  - `cost = 4.0`
- while `ue 3 / 4 / 6` stay much tighter
  - mostly `cost = 3.167~3.333`

Crucial insight:

- the late window already has strong CQI/cost separation
- but `previous_quality` is almost completely flat there (`range = 0`)
- so the family looks less like “no signal exists” and more like “the signal is
  not aligned with the continuity dimension the teacher needs to justify a split”

Interpretation:

`3|4|5|6 @ gnb_2` is fundamentally different from the old `seg_01` plateau. It
is not a flip-driven family. Instead it is a monotonic near-miss family whose
late window (`29.2s ~ 29.9s`) increasingly isolates `ue 5` on CQI and cost, but
still never crosses the teacher split threshold because the quality-history side
remains too static.

Recommended next stage after `k-1`:

- `P3.6k-2`
- keep the same family
- focus only on the late window (`29.2s ~ 29.9s`)
- prioritize localized previous-quality divergence around `ue 5`
- use cost-side changes only as a light auxiliary signal if needed

### P3.6k-2 hybrid breakthrough

`P3.6k-2` has now been completed and is the most important post-`j` research
breakthrough so far.

New builder:

- `build_p3_6k2_hybrid_bundle.py`

Formal output:

- `p3_6k2_hybrid_bundle/`
- `p3_6k2_teacher_audit/`
- `p3_6k2_focus_mining/`

Target:

- family: `3|4|5|6 @ gnb_2`
- time window: `29.2s ~ 29.9s`

Design:

- strong cost-side penalty on `ue 5`
  - `0.84 / 0.80 / 0.90`
- localized previous-quality divergence
  - `ue 5 -> 0`
  - `ue 3/4/6 -> 2`

Observed result:

- before `29.2s`: teacher stays single-group
- from `29.2s` through `29.9s`: teacher becomes `[[0,1,3],[2]]`
- teacher now stably isolates `ue 5`

Measured effect:

- new positive segment:
  - `seg_03 = 3|4|5|6 @ gnb_2`
  - `29.2s ~ 29.9s`
  - `snapshot_count = 8`
  - `mean_gain_vs_single = 0.038608503577`
- bundle-level summary improved:
  - `multi_group_count = 17` (up from `9`)
  - `positive_gain_count = 17` (up from `9`)
  - `positive_segment_count = 3` (up from `2`)
  - `candidate_temporal_slice_count = 14` (up from `7`)

Interpretation:

- this is the first successful new positive-gain family outside the old
  `seg_01` plateau line
- pure quality-side was insufficient
- hybrid alignment of `ue 5` cost weakness plus quality-history weakness was
  enough to push the family across the teacher split threshold

Most important next-step recommendation:

- run a focused learner study on the new `seg_03` regime before doing more
  family expansion
- this is currently the best candidate for a fresh `teacher / LE-GRA /
  multi-feature / no-group` comparison outside the exhausted `seg_01` family

### P3.6k-3 focused learner result on `seg_03`

`P3.6k-3` has now completed the first focused learner evaluation on the new
post-`j` family:

- `3|4|5|6 @ gnb_2`
- positive-gain segment: `seg_03`
- test window: `29.6s ~ 29.9s`

New result directory:

- `p3_6k2_seg03_temporal_learner/`

Formal command:

```powershell
python run_p3_6g_temporal_learner.py `
  --bundle-dir p3_6k2_hybrid_bundle/bundle `
  --out-dir p3_6k2_seg03_temporal_learner `
  --focus-ue-ids 3 4 5 6 `
  --train-window-end 29.5 `
  --test-window-start 29.6 `
  --test-window-end 29.9 `
  --max-groups 3 `
  --epochs 12 `
  --seed 9 `
  --min-users 2
```

Split summary:

- `background_train_scenarios = 721`
- `focus_train_scenarios = 130`
- `focus_test_scenarios = 4`
- `focus_train_positive_gain_count = 4`
- `focus_test_positive_gain_count = 4`
- `selected_epoch = 11`
- `selection_validation_loss = 0.0011118897958436505`

Main comparison result:

| Method | Utility | Avg groups |
|---|---:|---:|
| No grouping | 0.597184 | 1.0 |
| CQI k-means | 0.635793 | 2.0 |
| Resource-cost k-means | 0.635793 | 2.0 |
| Multi-feature k-means | 0.635793 | 2.0 |
| Offline teacher | 0.635793 | 2.0 |
| LE-GRA MVP | 0.635793 | 2.0 |

Teacher-imitation diagnostics on all 4 test snapshots:

- `Multi-feature k-means`
  - `pairwise_accuracy = 1.0`
  - `ARI = 1.0`
  - `NMI = 1.0`
- `LE-GRA MVP`
  - `pairwise_accuracy = 1.0`
  - `ARI = 1.0`
  - `NMI = 1.0`

Most important interpretation:

- this confirms that the new `seg_03` family is a real positive-gain split
  regime rather than a fragile artifact
- but it also shows that the current regime is still too easy
- once the split exists, every grouping-aware method matches the teacher
  exactly, including static `Multi-feature k-means`

So `P3.6k-2` solved:

- "can we make a new family where teacher stably wants to split?"

But `P3.6k-3` shows we still have not solved:

- "can we make a regime where temporal learning beats strong snapshot
  hand-crafted clustering?"

This is now the main bottleneck.

Recommended next direction:

- stop optimizing for "more split" alone
- search for families where snapshot CQI/cost look similar, but temporal trend
  or quality-history continuity separates the truly weak user
- the desired regime is one where teacher still needs the split, but static
  multi-feature clustering is no longer sufficient to recover it perfectly

### P3.6k-4 history-decoy result

`P3.6k-4` tested the first explicit attempt to confuse static clustering inside
the new `seg_03` regime without changing teacher economics.

New builder:

- `build_p3_6k4_decoy_history_bundle.py`

Formal outputs:

- `p3_6k4_decoy_history_bundle/`
- `p3_6k4_teacher_audit/`
- `p3_6k4_focus_mining/`
- `p3_6k4_seg03_temporal_learner/`

Design:

- base: `p3_6k2_hybrid_bundle`
- family: `3|4|5|6 @ gnb_2`
- window: `29.2s ~ 29.9s`
- change only bundle-side `cqi_history`
  - `ue 4`: strong recent-decline decoy history
  - `ue 5`: mild recovery history

Important result:

- the teacher regime was fully preserved
- `seg_03` remained unchanged with the same split and the same
  `teacher_gain_vs_single = 0.038608503576809006`

But the focused learner result was still:

- `No grouping < all grouping-aware methods`
- `CQI = Resource-cost = Multi-feature = Teacher = LE-GRA`

And diagnostics were still perfect on all 4 test snapshots:

- `Multi-feature k-means`: pairwise/ARI/NMI = `1.0 / 1.0 / 1.0`
- `LE-GRA MVP`: pairwise/ARI/NMI = `1.0 / 1.0 / 1.0`

Interpretation:

- history-only decoy structure is not enough to separate `LE-GRA` from
  `Multi-feature`
- in this family, the raw feature geometry is still dominated by the true
  `ue 5` weakness on cost and previous quality

### P3.6k-5 dual-weak collapse result

`P3.6k-5` tested whether adding a second plausible weak candidate could create
the desired regime where static clustering becomes confused but teacher still
prefers isolating only `ue 5`.

New builder:

- `build_p3_6k5_dualweak_decoy_bundle.py`

Formal outputs:

- `p3_6k5_dualweak_decoy_bundle/`
- `p3_6k5_teacher_audit/`
- `p3_6k5_focus_mining/`

Design:

- base: `p3_6k4_decoy_history_bundle`
- retained the history decoy on `ue 4`
- added a moderate secondary weakness on `ue 4`
  - RB-rate transform:
    - `>=1128 kbps -> 0.95`
    - `>=984 kbps -> 0.92`
    - else `0.97`
  - `ue 4 previous_quality -> 1`

Critical result:

- the entire `seg_03` positive-gain regime collapsed
- from `29.2s` through `29.9s`, teacher returned to single-group:
  - `teacher_groups = [[0,1,2,3]]`
  - `teacher_gain_vs_single = 0.0`

So this variant did **not** produce a richer ambiguous split regime. Instead it
destroyed the split incentive entirely.

Most important interpretation:

- the current `seg_03` family can support one clearly isolated weak user
- but it is structurally too narrow to support a second plausible weak
  candidate while keeping the teacher split alive
- this is now the clearest post-`k-2` bottleneck

Recommended next direction after `k-5`:

- do not keep micro-tuning the same `3|4|5|6 @ gnb_2` family
- either switch family source again, or design a broader targeted scenario that
  naturally contains two competing weak candidates while teacher still stably
  prefers one split
- the real target is no longer "make teacher split" but "make teacher split
  stay stable under decoy competition while static raw-feature clustering
  becomes insufficient"

### P3.6l dual-candidate family search

After `k-5`, the workflow explicitly shifted from micro-tuning one existing
family to mining new family sources that naturally contain *two plausible weak
candidates*.

New script:

- `rank_dual_candidate_families.py`

This ranks near-miss families by:

- dual-candidate weakness closeness
- gap over the third-weakest user
- minimum viable family CQI/resource-cost signal

Formal outputs:

- `p3_6l_dual_candidate_ranking/`
- `p3_6l_dual_candidate_ranking_v2/`

The corrected `v2` ranking promoted a new top family:

- `1|2|4|5 @ gnb_2`

This is important because `3|4|5|6 @ gnb_2` was best for one-clear-weak-user
redesign, but `1|2|4|5 @ gnb_2` is a better source for *dual-candidate*
competition.

### P3.6l-2 focused audit on `1|2|4|5 @ gnb_2`

Formal output:

- `p3_6l2_family_focus/`

Measured profile:

- `scenario_count = 10`
- `time_window = 23.0s ~ 23.9s`
- `max_teacher_gain_vs_single = 0.0`
- `max_cqi_range = 4.0`
- `max_resource_cost_range = 0.5`
- `max_previous_quality_range = 1.0`

Most important per-user finding:

- `ue 2`
  - `cqi = 12~14`
  - `cost = 3.166667~3.500000`
- `ue 4`
  - `cqi = 11~14`
  - `cost = 3.166667~3.666667`

So unlike `3|4|5|6`, this family already contains two plausible weak
candidates rather than one overwhelmingly obvious weak outlier.

### P3.6l-3 first dual-candidate generator prototype

New builder:

- `build_p3_6l3_dual_candidate_bundle.py`

Formal outputs:

- `p3_6l3_dual_candidate_bundle/`
- `p3_6l3_teacher_audit/`
- `p3_6l3_focus_mining/`

Design:

- family: `1|2|4|5 @ gnb_2`
- window: `23.0s ~ 23.9s`
- `ue 4`: primary weak user
  - stronger RB-rate penalty
  - `previous_quality -> 0`
  - recent-decline history
- `ue 2`: competing decoy weak user
  - milder RB-rate penalty
  - `previous_quality -> 1`
  - mild-recovery history
- `ue 1 / ue 5`: `previous_quality -> 2`

Critical result:

- this first dual-candidate prototype did **not** create a positive-gain split
- `1|2|4|5 @ gnb_2` remained single-group throughout `23.0s ~ 23.9s`
- no new positive segment appeared in `p3_6l3_focus_mining/positive_segments.csv`

Interpretation:

- the new family-search direction is valid
- but the first generator rule is still too coarse
- simply weakening both candidates is not enough; teacher still prefers
  single-group instead of isolating one candidate

Most important updated bottleneck:

- we now need a regime where one candidate is *economically split-worthy*
  while the second remains only a *decoy competitor* for static clustering

Recommended next direction:

- continue on `1|2|4|5 @ gnb_2`
- move from "two weakened candidates" to "one strong primary weak + one light
  temporal decoy"
- reduce the secondary candidate's cost penalty and shift more of its signal
  into history shape rather than direct cost weakness

### P3.6l-4 first split-structure success

`P3.6l-4` is the first follow-up that made the new dual-candidate family
actually split, even though it did not yet produce positive gain.

New builder:

- `build_p3_6l4_primary_weak_bundle.py`

Formal outputs:

- `p3_6l4_primary_weak_bundle/`
- `p3_6l4_teacher_audit/`
- `p3_6l4_focus_mining/`

Design:

- family: `1|2|4|5 @ gnb_2`
- `ue 4`: clear primary weak user
- `ue 2`: light temporal decoy with very small direct cost penalty

Critical result:

- from `23.7s` through `23.9s`, teacher split became:
  - `[[0,3],[1,2]]`
  - original UEs: `{1,5}` versus `{2,4}`

But the split was still only a *tie-utility* split:

- `teacher_gain_vs_single ≈ 0`

Interpretation:

- this is the first successful proof that the new family can support the
  desired dual-candidate split *structure*
- but it is not yet a real positive-gain regime

### P3.6l-5 positive-gain attempt and collapse

`P3.6l-5` tried to push the `l-4` split into a positive-gain regime.

New builder:

- `build_p3_6l5_positive_gain_bundle.py`

Formal outputs:

- `p3_6l5_positive_gain_bundle/`
- `p3_6l5_teacher_audit/`
- `p3_6l5_focus_mining/`

Design:

- kept the `l-4` family and split structure target
- weakened `ue 4` further
- raised `ue 1 / ue 5` previous-quality continuity to `3`
- kept `ue 2` as a very light decoy

Critical result:

- the `l-4` split structure disappeared
- `1|2|4|5 @ gnb_2` returned to single-group throughout `23.0s ~ 23.9s`
- `teacher_gain_vs_single = 0`

Interpretation:

- increasing strong-pair QoE continuity is the wrong direction
- it makes single-group allocation too attractive and removes the marginal
  benefit of isolating `ue 4`

Most important updated conclusion:

- `l-4` is the first genuine structural success on the new family
- `l-5` proves the next gain-improvement step must come from increasing the
  *primary weak user's isolation value*, not from helping the strong pair more

Recommended next direction after `l-5`:

- treat `l-4` as the new reference redesign on `1|2|4|5`
- if continuing to `P3.6l-6`, keep the `l-4` previous-quality setup
- only deepen `ue 4` locally or more selectively
- keep `ue 2` as a very light decoy rather than a second true weak user

### P3.6m family-bank batch search

After `l-6`, the workflow moved from single-family micro-tuning to a batch
family-bank search built from the successful `l-4` template.

New script:

- `run_p3_6m_family_bank.py`

This script applies a generic transform across ranked candidate families:

- `candidate_1 -> primary weak`
- `candidate_2 -> light temporal decoy`
- then runs:
  - `run_p3_6_teacher_decision_audit.py`
  - `mine_focus_slices.py`

Formal output:

- `p3_6m_family_bank/`

Initial batch tested these ranked families:

- rank 1: `1|2|4|5 @ gnb_2`
- rank 2: `0|1|15|2|3|4|5 @ gnb_1`
- rank 4: `0|1|15|2|3|4 @ gnb_1`
- rank 5: `31|4|5|6|7 @ gnb_2`
- rank 9: `0|1|2|3|4 @ gnb_2`

Most important result:

- the only family that produced a meaningful *window-local* multi-group
  structure under the batch template was still:
  - `1|2|4|5 @ gnb_2`
  - `23.0s ~ 23.9s`
  - `window_multi_group_count = 6`
  - `window_positive_gain_count = 0`

Teacher behavior on that family:

- `23.3s ~ 23.8s`
- split `[[0,3],[1,2]]`
- original UEs: `{1,5}` vs `{2,4}`
- but still *zero gain*

So `1|2|4|5` remains the strongest current source for a dual-candidate
*structural* split, but it is still trapped on a tie-utility plateau.

Important clarification on `0|1|15|2|3|4|5 @ gnb_1`:

- the batch summary still shows:
  - `target_positive_gain_count = 3`
  - `target_max_gain_vs_single = 0.057159402144`
- but these are **not** new `P3.6m` gains inside the modified window
- they are the pre-existing base-bundle positive rows at:
  - `43.7s ~ 43.9s`
  - split `[[0,1,3,4,5,6],[2]]`
  - isolated local index `2` = `ue 15`

Inside the actual modified window:

- `38.0s ~ 43.6s`
- `window_multi_group_count = 0`
- `window_positive_gain_count = 0`

The other tested families were effectively unresponsive:

- `0|1|15|2|3|4 @ gnb_1`
- `31|4|5|6|7 @ gnb_2`
- `0|1|2|3|4 @ gnb_2`

All stayed:

- single-group in the modified window
- `window_positive_gain_count = 0`

Most important interpretation from `P3.6m`:

- the generic `primary weak + light decoy` template can reproduce split
  *structure* in the right family
- but it does **not** reliably create split *economics*
- and it does not transfer cleanly across most near-miss families

Updated research picture:

- `1|2|4|5 @ gnb_2`
  - best current family for ambiguity / structural dual-candidate split
  - still no positive gain
- `0|1|15|2|3|4|5 @ gnb_1`
  - best current family for real positive-gain isolation
  - but not yet a true dual-candidate ambiguous regime

Recommended next direction after `P3.6m`:

- do **not** keep applying the same generic template to more near-miss families
- instead move to a `P3.6m-2` style redesign:
  - start from a family that already has a real positive-gain split
  - inject a second plausible weak decoy *without destroying* the original
    gain basin
- the clearest current source for that is:
  - `0|1|15|2|3|4|5 @ gnb_1`

### P3.6m-2 positive-family decoy injection

`P3.6m-2` executed that redesign directly on the strongest positive-gain source:

- target family: `0|1|15|2|3|4|5 @ gnb_1`
- target window: `43.4s ~ 43.9s`

New builder:

- `build_p3_6m2_positive_family_decoy_bundle.py`

Formal outputs:

- `p3_6m2_positive_family_decoy_bundle/`
- `p3_6m2_teacher_audit/`
- `p3_6m2_family_focus/`
- `p3_6m2_focus_mining/`

Design:

- keep `ue 15` as the real primary weak user
- inject `ue 4` as a lighter decoy
- use mostly history shaping plus a very small RB-rate penalty on `ue 4`
- reinforce `ue 15` history shape without further deepening its resource cost

Critical result:

- the positive-gain split survived
- but the split structure changed

Original base-bundle split at `43.7s ~ 43.9s`:

- `[[0,1,3,4,5,6],[2]]`
- isolated local index `2 = ue 15`
- `teacher_gain_vs_single = 0.057159402144`

New `P3.6m-2` split at `43.7s ~ 43.9s`:

- `[[0,1,3,4,6],[2,5]]`
- weak group became `{ue 15, ue 4}`
- `teacher_gain_vs_single = 0.032424870721`

So `P3.6m-2` achieved an important new regime:

- positive gain still exists
- but the teacher no longer isolates only one obvious weak user
- a second plausible weak candidate has been injected directly into the
  teacher's split structure

Most important interpretation:

- this is the first current regime that combines:
  - real positive-gain split economics
  - nontrivial weak-user ambiguity
- it is therefore a stronger learner-side challenge than either:
  - the old single-weak positive family
  - or the gainless `1|2|4|5` structural plateau

Updated best next direction:

- promote `P3.6m-2` as the current best learner-side evaluation target
- next step should be a focused learner / ablation run on this new segment
- the key question is whether `LE-GRA`, `multi-feature`, and `no-group`
  finally separate on a regime that has both:
  - positive gain
  - injected decoy ambiguity

### P3.6m-3 focused learner / ablation on the new positive regime

That focused learner run has now been completed on the `P3.6m-2` regime.

Formal output:

- `p3_6m2_seg01_split437_temporal_learner/`

Protocol:

- bundle: `p3_6m2_positive_family_decoy_bundle/bundle`
- focus UEs: `0|1|15|2|3|4|5`
- `train_window_end = 43.7`
- `test_window = 43.8s ~ 43.9s`
- same protocol as the old `p3_6i2_seg01_split437_temporal_learner`
  for direct comparability

Main comparison:

- `Offline teacher`
  - utility: `0.579609048805`
- `LE-GRA MVP`
  - utility: `0.579083105194`
- `Multi-feature k-means`
  - utility: `0.579083105194`
- `CQI k-means`
  - utility: `0.579083105194`
- `Resource-cost k-means`
  - utility: `0.579083105194`
- `No grouping`
  - utility: `0.547184178084`

So the ordering is now:

- `teacher > LE-GRA = multi-feature = CQI = resource-cost > no-group`

This is the first current positive-gain regime where the teacher is **not**
exactly reproduced by either:

- `LE-GRA`
- `Multi-feature`

Most important structural finding:

- all grouping-aware baselines still predict 2 groups
- but they choose the *wrong* weak group identity

Teacher on both test snapshots (`43.8s`, `43.9s`):

- `[[0,1,3,4,6],[5,2]]`
- original UEs: strong `{0,1,2,3,5}` vs weak `{4,15}`

LE-GRA / Multi-feature / CQI / Resource-cost on both test snapshots:

- `[[0,1,3,4,5,6],[2]]`
- original UEs: strong `{0,1,2,3,4,5}` vs weak `{15}`

So the current learner failure mode is now very clear:

- the learner has no problem deciding to split
- but it still fails to include the injected decoy `ue 4` in the weak group
- it collapses back to the old single-isolated-user solution

Teacher-imitation diagnostics for both `LE-GRA` and `Multi-feature`:

- `pairwise_accuracy = 0.714285714286`
- `ARI = 0.416666666667`
- `NMI = 0.428140178120`

Most important interpretation:

- `P3.6m-2` successfully created the first positive-gain regime where
  teacher split identity is no longer perfectly matched by static clustering
  or the current learner
- this is currently the strongest learner-side evidence point in the project

Updated best next direction after `P3.6m-3`:

- keep this regime as the current primary evaluation slice
- next work should either:
  - replicate this decoy-positive pattern into more nearby slices / families
  - or redesign learner supervision so `LE-GRA` can recover the secondary weak
    candidate and finally beat `Multi-feature`

### P3.6m-4 slice replication around the positive-family decoy regime

`P3.6m-4` first tested whether the current regime could be extended by changing
only the decoy side.

New sweep script:

- `run_p3_6m4_positive_slice_sweep.py`

Formal output:

- `p3_6m4_slice_sweep/`

This sweep varied:

- decoy activation start time
- `ue 4` rate-penalty strength
- `ue 4` recent-drop history shape

Critical result from the sweep:

- every tested variant stayed identical on the target family
- `positive_gain_count = 3`
- `positive_dualweak_count = 3`
- `first_positive_time_s = 43.7`

So decoy-only changes do **not** move the regime boundary earlier. That is an
important negative result: the bottleneck is still on the primary weak user
side (`ue 15`), not on the injected decoy (`ue 4`) side.

### P3.6m-4b threshold nudge

After that negative sweep result, `P3.6m-4b` directly nudged the primary weak
user only at `43.6s`.

New builder:

- `build_p3_6m4b_threshold_nudge_bundle.py`

Formal outputs:

- `p3_6m4b_threshold_nudge_bundle/`
- `p3_6m4b_teacher_audit/`
- `p3_6m4b_family_focus/`
- `p3_6m4b_focus_mining/`

Design:

- start from `p3_6m2_positive_family_decoy_bundle`
- modify only:
  - family `0|1|15|2|3|4|5 @ gnb_1`
  - timestamp `43.6s`
  - user `ue 15`
- deepen `ue 15` rate penalty and lower `cqi_now_raw`

Critical result:

- `43.6s` crossed into positive gain
- but with the old single-weak-user split:
  - `[[0,1,3,4,5,6],[2]]`
  - `teacher_gain_vs_single = 0.031898927110`
- `43.7s ~ 43.9s` kept the newer dual-weak split:
  - `[[0,1,3,4,6],[2,5]]`
  - `teacher_gain_vs_single = 0.032424870721`

So the positive segment is now:

- `43.6s ~ 43.9s`
- `snapshot_count = 4`

This is an important partial success:

- the regime is longer now
- but only the last three snapshots (`43.7s ~ 43.9s`) are the true
  dual-weak ambiguity regime
- `43.6s` is better understood as a threshold-bridge snapshot

### Focused learner on the extended slice

New focused learner output:

- `p3_6m4b_seg01_split436_temporal_learner/`

Protocol:

- `train_window_end = 43.6`
- `test_window = 43.7s ~ 43.9s`

This increased the learner test set from:

- 2 dual-weak positive snapshots (`43.8s ~ 43.9s`)

to:

- 3 dual-weak positive snapshots (`43.7s ~ 43.9s`)

Main comparison remained unchanged:

- `teacher > LE-GRA = multi-feature = CQI = resource-cost > no-group`

Utilities:

- `Offline teacher = 0.579609048805`
- `LE-GRA = 0.579083105194`
- `Multi-feature = 0.579083105194`
- `No grouping = 0.547184178084`

Teacher-imitation diagnostics also stayed identical across all 3 test rows:

- `pairwise_accuracy = 0.714285714286`
- `ARI = 0.416666666667`
- `NMI = 0.428140178120`

Most important interpretation from `P3.6m-4`:

- the learner-side separation found in `P3.6m-3` is now supported by a longer,
  cleaner test slice
- the regime has become more reproducible temporally
- but the current learner still collapses to the old `ue 15`-only isolation
  pattern instead of including the injected `ue 4` decoy

Updated best next direction after `P3.6m-4`:

- stop spending time on further local temporal extension (for example trying to
  force `43.5s`)
- keep `43.7s ~ 43.9s` as the main dual-weak evaluation regime
- move to `P3.6m-5`:
  - learner-side supervision redesign so `LE-GRA` can learn the secondary weak
  candidate and finally separate from `Multi-feature`

### P3.6m-5 learner-side supervision redesign v1

`P3.6m-5` has now started with the first bounded supervision-only change.

Formal note:

- `P3_6M_5_SUPERVISION_REDESIGN_V1_ZH.md`

Formal output:

- `p3_6m5_teacher_hard_group_v1/`

Design:

- keep the existing learner architecture unchanged
- keep the same main regime and protocol as `P3.6m-4b`
  - bundle: `p3_6m4b_threshold_nudge_bundle/bundle`
  - train window end: `43.6s`
  - test window: `43.7s ~ 43.9s`
- change only the supervision
  - new mode: `teacher_hard_group`
  - upweight positive pairs inside the teacher's hardest group
  - upweight negative pairs between the hardest group and other groups

Purpose:

- not just "teach split"
- explicitly emphasize the weak-group identity that should contain
  `{ue15, ue4}`

Critical result:

- the main comparison did **not** move
- ordering remains:
  - `teacher > LE-GRA = multi-feature = CQI = resource-cost > no-group`
- utilities remain:
  - `Offline teacher = 0.579609048805`
  - `LE-GRA = 0.579083105194`

Teacher-imitation diagnostics also remain unchanged on all 3 test snapshots:

- `pairwise_accuracy = 0.714285714286`
- `ARI = 0.416666666667`
- `NMI = 0.428140178120`

So `LE-GRA` still collapses to the old `ue15`-only isolation pattern and does
not yet recover the teacher's dual-weak weak-group identity `{ue15, ue4}`.

Most important new evidence from `v1`:

- train-side hardest-group positive supervision is present
- hardest-group negative supervision is almost absent

Measured train statistics:

- `train_positive_pairs = 6.2219`
- `train_negative_pairs = 0.0444`
- `train_mean_positive_weight = 2.4845`
- `train_mean_negative_weight = 1.5`
- `train_hard_group_positive_pairs = 6.1464`
- `train_hard_group_negative_pairs = 0.0444`

Interpretation:

- weighting alone is not enough
- the more precise bottleneck is now supervision coverage, especially
  cross-boundary negatives around the secondary weak candidate

Updated best next direction after `P3.6m-5 v1`:

- do not expand Kmax, seeds, or the matrix
- keep the same `43.7s ~ 43.9s` regime
- move to `P3.6m-5 v2` with:
  - boundary-aware pair construction / guaranteed hard-group negatives
  - or positive-gain / dual-weak scenario weighting

### P3.6m-5 learner-side supervision redesign v2

`P3.6m-5 v2` has now been completed on the same main regime.

Formal note:

- `P3_6M_5_SUPERVISION_REDESIGN_V2_ZH.md`

Formal output:

- `p3_6m5_teacher_boundary_v2/`

Design:

- keep the learner architecture unchanged
- keep the same main regime and temporal protocol as `P3.6m-4b`
- change supervision coverage in two ways:
  - new pair sampling mode: `teacher_boundary`
    - prioritizes weighted positives inside the hardest teacher group
    - prioritizes weighted negatives across the hardest-group boundary
  - new scenario weighting mode: `positive_multigroup_focus`
    - repeats multi-group train scenarios
    - repeats positive-gain train scenarios more strongly

Purpose:

- fix the specific `v1` issue where the learner almost never saw enough
  hardest-group boundary negatives
- test whether better coverage alone is sufficient to recover the dual-weak
  teacher identity `{ue15, ue4}`

Critical result:

- the main comparison still did **not** move
- ordering remains:
  - `teacher > LE-GRA = multi-feature = CQI = resource-cost > no-group`
- utilities remain:
  - `Offline teacher = 0.579609048805`
  - `LE-GRA = 0.579083105194`

Teacher-imitation diagnostics also remain unchanged on all 3 test snapshots:

- `pairwise_accuracy = 0.714285714286`
- `ARI = 0.416666666667`
- `NMI = 0.428140178120`

So even after explicitly improving boundary coverage, `LE-GRA` still collapses
to the old `ue15`-only isolation pattern and does not recover the teacher's
dual-weak weak-group identity `{ue15, ue4}`.

Most important new evidence from `v2`:

- supervision coverage really did improve
- but improved coverage still did not change the final partition

Measured train statistics:

- `train_negative_pairs = 0.1722` versus `0.0444` in `v1`
- `train_hard_group_negative_pairs = 0.1722`
- `train_priority_negative_pairs = 0.1722`
- `train_schedule_examples = 697.0`
- `train_boosted_scenarios = 7.0`

Interpretation:

- `v1` could still be criticized as "not enough boundary signal"
- `v2` removes much of that objection
- the more precise bottleneck is now the supervision form itself:
  pairwise contrastive supervision appears insufficient to encode the
  teacher's weak-group identity in a way that changes downstream k-means
  grouping

Updated best next direction after `P3.6m-5 v2`:

- do not expand Kmax, seeds, or the matrix
- keep the same `43.7s ~ 43.9s` regime
- move to `P3.6m-5 v3` with a supervision-form redesign, not another small
  pair-sampling tweak:
  - weak-group membership / group-identity supervision
  - group-prototype supervision
  - or regret-aware soft supervision over near-best teacher partitions

### P3.6m-5 learner-side supervision redesign v3

`P3.6m-5 v3` has now been completed on the same main regime.

Formal note:

- `P3_6M_5_SUPERVISION_REDESIGN_V3_ZH.md`

Formal output:

- `p3_6m5_group_identity_v3/`

Design:

- keep all `v2` coverage improvements:
  - `teacher_boundary` pair sampling
  - `positive_multigroup_focus` scenario weighting
- add weakest-group identity supervision:
  - derive a hardest-group membership target from the teacher partition
  - add a prototype-style loss that pulls hardest-group members toward a
    shared center and repels non-members inside a prototype margin

Purpose:

- test whether the real issue is still missing group-identity signal
- move beyond pure pairwise supervision without replacing the current learner
  architecture or k-means output stage

Critical result:

- the main comparison still did **not** move
- ordering remains:
  - `teacher > LE-GRA = multi-feature = CQI = resource-cost > no-group`
- utilities remain:
  - `Offline teacher = 0.579609048805`
  - `LE-GRA = 0.579083105194`

Teacher-imitation diagnostics also remain unchanged on all 3 test snapshots:

- `pairwise_accuracy = 0.714285714286`
- `ARI = 0.416666666667`
- `NMI = 0.428140178120`

So even after directly adding hardest-group identity supervision, `LE-GRA`
still collapses to the old `ue15`-only isolation pattern and does not recover
the teacher's dual-weak weak-group identity `{ue15, ue4}`.

Most important new evidence from `v3`:

- the prototype-style identity supervision really did fire during training
- but it still did not change the final grouping

Measured train statistics:

- `train_prototype_positive_terms = 3.6069`
- `train_prototype_negative_terms = 0.0488`
- `prototype_weight = 0.5`

Interpretation:

- this is no longer just a sampling or coverage problem
- this is no longer just a missing weak-group identity signal problem
- the more precise bottleneck is now the learner output form itself:
  the current embedding + k-means pipeline appears unable to stably express
  the teacher's dual-weak weak-group identity in downstream partitions

Updated best next direction after `P3.6m-5 v3`:

- do not expand Kmax, seeds, or the matrix
- keep the same `43.7s ~ 43.9s` regime
- stop spending more time on bounded pairwise/prototype supervision tweaks
- move to a new learner form:
  - weak-group membership head
  - direct split-structure prediction
  - or soft / near-best partition supervision

### P3.6m-6 weak-group membership head (prototype-style MVP)

`P3.6m-6` has now been started and its first MVP evidence point is complete.

Formal note:

- `P3_6M_6_WEAK_GROUP_MEMBERSHIP_HEAD_ZH.md`

Evidence output:

- `p3_6m5_group_identity_v3/`

Research interpretation:

- this run should now be read as the first `P3.6m-6` MVP, even though the
  directory name still reflects its original `v3` naming

Design:

- keep the bounded `P3.6m-5 v2` supervision-coverage improvements
  - `teacher_boundary` pair sampling
  - `positive_multigroup_focus` scenario weighting
- add explicit weakest-group identity supervision
  - derive a hardest-group membership target from the teacher partition
  - add a prototype-style loss around that target

Purpose:

- test whether directly injecting hardest weak-group identity is enough to
  move `LE-GRA` beyond `multi-feature`

Critical result:

- the main comparison still did **not** move
- ordering remains:
  - `teacher > LE-GRA = multi-feature = CQI = resource-cost > no-group`
- utilities remain:
  - `Offline teacher = 0.579609048805`
  - `LE-GRA = 0.579083105194`

Teacher-imitation diagnostics also remain unchanged on all 3 test snapshots:

- `pairwise_accuracy = 0.714285714286`
- `ARI = 0.416666666667`
- `NMI = 0.428140178120`

Train-side evidence confirms the new identity signal was active:

- `train_prototype_positive_terms = 3.6069`
- `train_prototype_negative_terms = 0.0488`
- `prototype_weight = 0.5`

Interpretation:

- this is no longer just a pair-sampling problem
- this is no longer just a supervision-coverage problem
- this is no longer just a missing weak-group-identity signal problem
- the current embedding + k-means output form itself appears unable to turn
  the teacher's dual-weak identity `{ue15, ue4}` into the downstream grouping

Updated best next direction after `P3.6m-6`:

- do not expand Kmax, seeds, or the matrix
- keep the same `43.7s ~ 43.9s` regime
- move to `P3.6m-7` with an actual output-form change:
  - direct weak-group membership head
  - direct split-structure prediction
  - or soft / near-best partition supervision without forcing k-means as the
    only output layer

### P3.6m-7 direct weak-group membership output

`P3.6m-7` has now been completed with the first real post-k-means output-form
change.

Formal note:

- `P3_6M_7_DIRECT_MEMBERSHIP_OUTPUT_ZH.md`

Formal output:

- `p3_6m7_membership_head_v1/`

Design:

- keep the bounded supervision improvements from `P3.6m-5/6`
  - `teacher_boundary` pair sampling
  - `positive_multigroup_focus` scenario weighting
  - teacher hardest-group targets
- add a direct weakest-group membership head on top of the MLP
- change the learner output path:
  - instead of `embedding -> k-means -> DP`
  - use `membership score -> weak-score order -> boundary search -> DP`

Purpose:

- remove the explicit dependence on k-means as the final learner output layer
- test whether a direct learned weak-group ordering can recover the teacher's
  dual-weak weak-group identity `{ue15, ue4}`

Critical result:

- the main comparison still did **not** move
- ordering remains:
  - `teacher > LE-GRA = multi-feature = CQI = resource-cost > no-group`
- utilities remain:
  - `Offline teacher = 0.579609048805`
  - `LE-GRA = 0.579083105194`

Teacher-imitation diagnostics also remain unchanged on all 3 test snapshots:

- `pairwise_accuracy = 0.714285714286`
- `ARI = 0.416666666667`
- `NMI = 0.428140178120`

So even after removing k-means from the learner's final output path, `LE-GRA`
still does not recover the teacher's dual-weak weak-group identity
`{ue15, ue4}`.

Most important new evidence from `P3.6m-7`:

- the direct membership head was active during training
- the learner really did use `membership_order` rather than the old k-means
  path
- yet the final grouping still did not change

Measured train statistics:

- `membership_weight = 1.0`
- `train_membership_terms = 3.7791`
- `train_mean_weak_score = 0.9707`

Interpretation:

- this is no longer just a k-means bottleneck
- the problem is now better described as target/evidence insufficiency for
  learning a transferable rule for the secondary weak candidate

Updated best next direction after `P3.6m-7`:

- do not expand Kmax, seeds, or the matrix
- keep the same `43.7s ~ 43.9s` regime
- stop spending more time on small head/loss/output-form tweaks within the same
  learner family
- move to `P3.6m-8` with:
  - richer supervision targets (for example soft / near-best partitions)
  - or regime-focused train-evidence redesign that increases the density of
    true secondary-weak examples

## Latest Regime-Focused Result: `P3.6m-8`

Formal write-up:

- `P3_6M_8_TRAIN_EVIDENCE_REPLAY_ZH.md`

Main finding:

- the original focused learner protocol had a train-evidence hole
- in `focus_train <= 43.6s`, the number of exact teacher dual-weak slices
  `{ue15, ue4}` was **zero**
- in `focus_test = 43.7s ~ 43.9s`, all 3 evaluation slices were exact
  dual-weak `{ue15, ue4}`

This means the learner was not merely facing ordinary temporal drift. The
teacher target form itself changed between train and test:

- `43.6s`: bridge snapshot, teacher isolates only `{ue15}`
- `43.7s ~ 43.9s`: true dual-weak split `{ue15, ue4}`

Protocol changes added in `run_p3_6g_temporal_learner.py`:

- `--train-window-start`
- `--background-train-repeat`
- `--focus-train-repeat`
- `teacher_group_evidence_audit.csv`

Two key `P3.6m-8` experiments were run:

1. `p3_6m8_support_train437_438_test439/`
   - train includes only 2 exact dual-weak support slices (`43.7`, `43.8`)
   - test is `43.9`
   - result: still not enough; direct inspection shows LE-GRA still predicts
     `{ue15}` as the weak group

2. `p3_6m8_support_replay80_train437_438_test439/`
   - same support slices, but replayed to reach evidence density comparable to
     the 150 background slices
   - result: LE-GRA exactly matches teacher on the `43.9` holdout
   - diagnostics:
     - `pairwise_accuracy = 1.0`
     - `ARI = 1.0`
     - `NMI = 1.0`
   - direct grouping:
     - teacher: `[['0','1','2','3','5'], ['4','15']]`
     - LE-GRA: `[['15','4'], ['0','5','3','1','2']]`

Important interpretation:

- this is the strongest evidence so far that the bottleneck is now
  evidence-density / curriculum design rather than a simple inability of the
  learner family to represent the dual-weak rule
- do **not** jump straight to bigger matrices or seed sweeps
- do **not** assume a new external dataset is immediately required
- the best next step is a controlled evidence-density or support/holdout sweep
  around this same regime

Implementation note:

- the first replay attempt exposed a protocol bug: repeating Python lists of
  `Scenario` objects caused shared references and repeated in-place feature
  normalization, producing `NaN`
- this was fixed by replaying deep-copied scenarios instead
- treat the fixed `p3_6m8_support_replay80_train437_438_test439/` result as the
  valid one

## Latest Threshold Result: `P3.6m-9`

Formal write-up:

- `P3_6M_9_EVIDENCE_DENSITY_SWEEP_ZH.md`

Formal output:

- `p3_6m9_evidence_density_sweep/`
- `p3_6m9_evidence_density_sweep/sweep_summary.csv`

Purpose:

- quantify how much exact dual-weak support density is required before LE-GRA
  stops isolating only `ue15` and starts recovering the full
  `{ue15, ue4}` weak group

Protocol:

- keep the same regime and learner recipe as `P3.6m-8`
- support window: `43.7s ~ 43.8s`
- holdout test: `43.9s`
- sweep `focus_train_repeat` over:
  - `1, 2, 4, 8, 16, 40, 80`
- keep background training fixed at 150 effective scenarios

Critical result:

- `repeat = 1, 2`
  - LE-GRA remains stuck at the old behavior
  - utility stays at `0.579083105194`
  - diagnostics stay at:
    - `pairwise_accuracy = 0.714285714286`
    - `ARI = 0.416666666667`
    - `NMI = 0.428140178120`

- `repeat >= 4`
  - LE-GRA exactly matches the teacher
  - utility becomes `0.579609048805`
  - diagnostics become:
    - `pairwise_accuracy = 1.0`
    - `ARI = 1.0`
    - `NMI = 1.0`

Most important interpretation:

- the bottleneck is now best described as a support-density threshold
- in this regime, the threshold is surprisingly sharp and not very large
- effective focus support moves from:
  - `4` exact support slices at `repeat = 2`
  - to `8` exact support slices at `repeat = 4`
- the phase transition happens between those two points

Practical implication:

- do not jump to larger matrices or broader dataset generation yet
- the most valuable next step is not more scale but better curriculum / support
  efficiency
- the next experiment should try to recover the `repeat = 4` win while using
  only `repeat = 1` or `2` worth of exact support, for example through smarter
  weighting or scheduling rather than brute-force replay

## Latest Support-Efficiency Result: `P3.6m-10`

Formal write-up:

- `P3_6M_10_BACKGROUND_DILUTION_ZH.md`

Formal output:

- `p3_6m10_background_dilution_sweep/`

Purpose:

- test whether `repeat = 2` fails because exact support is inherently too weak,
  or because the exact support is diluted by too many irrelevant background
  scenarios

Protocol:

- keep the same exact support window (`43.7s ~ 43.8s`) and same holdout test
  (`43.9s`)
- keep `focus_train_repeat = 2`
- sweep `background_train_limit` over:
  - `150, 100, 50, 20, 10, 5, 0`

Critical result:

- `background_limit = 150` or `100`
  - LE-GRA still fails
  - utility stays at `0.579083105194`
  - diagnostics stay at:
    - `pairwise_accuracy = 0.714285714286`
    - `ARI = 0.416666666667`
    - `NMI = 0.428140178120`

- `background_limit <= 50`
  - LE-GRA exactly matches the teacher
  - utility becomes `0.579609048805`
  - diagnostics become:
    - `pairwise_accuracy = 1.0`
    - `ARI = 1.0`
    - `NMI = 1.0`

Boundary refinement:

- `p3_6m11_repeat3_bg150/`
  - `repeat = 3`, `background = 150`
  - success

- `p3_6m11_repeat2_bg080/`
  - fail

- `p3_6m11_repeat2_bg075/`
  - fail

- `p3_6m11_repeat2_bg060/`
  - success

Most important interpretation:

- `repeat = 2` is not inherently insufficient
- the failure of the original protocol is partly caused by background dilution
- the bottleneck is now best understood as a combination of:
  - exact dual-weak support density
  - support-to-background ratio
  - schedule frequency of those exact support slices

Current best next direction:

- do not regenerate a new dataset yet
- do not broaden the matrix
- move to a schedule-aware learner protocol that enforces stronger exposure to
  exact support slices without brute-force scaling of the whole train set

## Latest Curriculum Result: `P3.6m-11`

Formal write-up:

- `P3_6M_11_SUPPORT_WARMUP_CURRICULUM_ZH.md`

Purpose:

- test whether the original `repeat = 2`, `background = 150` failure can be
  fixed by changing only the timing of support exposure, not the amount of
  data

Implementation:

- `train_trace_model(...)` now supports:
  - `focus_support_indices`
  - `focus_only_warmup_epochs`
- in the temporal protocol, this creates a support-only warmup phase before the
  full mixed schedule begins

Key experiment family:

- `p3_6m12_repeat2_bg150_warmup1/`
- `p3_6m12_repeat2_bg150_warmup2/`
- `p3_6m12_repeat2_bg150_warmup3/`
- `p3_6m12_repeat2_bg150_warmup4/`
- `p3_6m12_repeat2_bg150_warmup6/`

Critical result:

- `warmup = 1, 2, 3`
  - all succeed
  - LE-GRA exactly matches teacher again
  - utility = `0.579609048805`

- `warmup = 4, 6`
  - both fail
  - LE-GRA falls back to the old solution
  - utility = `0.579083105194`

Most important interpretation:

- the bottleneck is now clearly not just support quantity
- a short support-only warmup is sufficient to unlock the correct dual-weak
  rule even when:
  - `background = 150`
  - `focus_train_repeat = 2`
- but longer support-only warmup is harmful, suggesting a narrow curriculum
  sweet spot rather than a monotonic “more support first is always better”

Updated best next direction after `P3.6m-11`:

- keep the same regime
- do not regenerate data yet
- formalize a schedule-aware curriculum protocol
- then test whether the short-warmup win transfers to nearby slices or nearby
  families rather than only to the exact `43.9s` holdout

## Latest Transfer Check: `P3.6m-12`

Formal write-up:

- `P3_6M_12_SINGLE_SUPPORT_TRANSFER_ZH.md`

Purpose:

- check whether the short-warmup win transfers when support is reduced to only
  one exact dual-weak snapshot

Protocol:

- train support uses only `43.7s`
- holdout test uses `43.8s ~ 43.9s`
- keep:
  - `background = 150`
  - `focus_train_repeat = 2`
- compare:
  - no warmup
  - warmup `1`
  - warmup `2`

Key experiment family:

- `p3_6m13_support437_test438_439_baseline/`
- `p3_6m13_support437_test438_439_warmup1/`
- `p3_6m13_support437_test438_439_warmup2/`

Critical result:

- all three runs fail
- LE-GRA remains at:
  - `0.579083105194`
- so short warmup alone is not enough when support diversity collapses to a
  single exact dual-weak snapshot

Most important interpretation:

- warmup is helpful, but not magical
- it does not replace the need for at least a minimally sufficient support set
- current evidence suggests the successful recipe requires both:
  - more than one exact dual-weak support snapshot
  - and the correct curriculum timing

Updated best next direction after `P3.6m-12`:

- stay on the same regime
- do not regenerate data yet
- identify the minimum successful support set
- the next best experiments are two-support transfer checks such as:
  - `43.7 + 43.8 -> 43.9`
  - `43.8 + 43.9 -> 43.7`
  - `43.7 + 43.9 -> 43.8`

## Repository State at Handoff

Git contains all source patches, reproducible scripts, raw evidence, normalized
radio output, and the final P3.5 coupled bundle. It does not contain the WSL/Nix
simulator installations. On a new computer, first run the pure-Python
`run_p3_5_coupled_test.py` against committed evidence; only install the P3.5
runtime when a new coupled simulation must be generated. The current primary
research artifacts are `medium_matrix_results_v2_after_grad_fix/`,
`p3_4_actual_radio/`, and `p3_5_coupled_bundle/`.

## Latest Focused Robustness Check: `P3.6m-15`

Purpose:

- verify whether the new two-support warmup recipe is a one-seed accident
- keep the same family/regime and avoid expanding the overall matrix

Protocol:

- same family:
  - `0|1|15|2|3|4|5 @ gnb_1`
- same training recipe:
  - `background_train_limit = 150`
  - `focus_train_repeat = 2`
  - `focus_only_warmup_epochs = 1`
- run the three minimum-support transfer tasks with seeds:
  - `7`
  - `9`
  - `11`

Transfer tasks:

- `43.7 + 43.8 -> 43.9`
- `43.8 + 43.9 -> 43.7`
- `43.7 + 43.9 -> 43.8`

Key experiment family:

- `p3_6m15_seed7_support437_438_test439/`
- `p3_6m15_seed9_support437_438_test439/`
- `p3_6m15_seed11_support437_438_test439/`
- `p3_6m15_seed7_support438_439_test437/`
- `p3_6m15_seed9_support438_439_test437/`
- `p3_6m15_seed11_support438_439_test437/`
- `p3_6m15_seed7_support437_439_test438/`
- `p3_6m15_seed9_support437_439_test438/`
- `p3_6m15_seed11_support437_439_test438/`

Critical result:

- seed `7`: all three transfer tasks succeed
- seed `11`: all three transfer tasks succeed
- seed `9`: all three transfer tasks fail in the same way

Most important interpretation:

- the earlier warmup result is real, not a one-off direction artifact
- but the learner is still initialization-sensitive
- the bottleneck has moved from:
  - “can it ever learn the dual-weak rule?”
- to:
  - “can we select or stabilize the good training trajectory?”

## Latest Selection Fix: `P3.6m-16`

Formal write-up:

- `P3_6M_16_FOCUSED_MULTISTART_TIEBREAK_ZH.md`

Purpose:

- add the smallest possible learner-side stabilization without changing the
  main architecture
- test whether deterministic restart selection can recover the seed-9 failures

Implementation:

- `run_p3_6g_temporal_learner.py` now supports:
  - `--restart-seeds`
- for each restart seed:
  - train one candidate model
  - score it on the exact support slices
  - record candidate metrics in `restart_candidates.csv`
- selection rule:
  - higher support pairwise accuracy
  - then higher support ARI
  - then higher support NMI
  - then higher support utility
  - then smaller support utility gap to teacher
  - then lower training selection loss as deterministic tie-break

Key experiment family:

- `p3_6m16_multistart_support437_438_test439/`
- `p3_6m16_multistart_support438_439_test437/`
- `p3_6m16_multistart_support437_439_test438/`
- `p3_6m16b_multistart_tiebreak_support437_438_test439/`
- `p3_6m16b_multistart_tiebreak_support438_439_test437/`
- `p3_6m16b_multistart_tiebreak_support437_439_test438/`

Critical result:

- with `--restart-seeds 7 9 11`, all three transfer tasks again match teacher
- after adding the loss-based tie-break, all three cases consistently select
  seed `11`
- all three final outputs recover:
  - `LE-GRA utility = teacher utility = 0.579609048805`

Important nuance:

- support-side imitation metrics remain tied at:
  - `pairwise = 0.714285714286`
  - `ARI = 0.416666666667`
  - `NMI = 0.428140178120`
- so exact support imitation is still not a sufficient selector by itself
- the useful discriminator is currently the lower training selection loss

Current best interpretation:

- the focused supervision/curriculum line is still alive
- the current learner can represent the right local rule
- but its local validation signal is still weak
- the most sensible next step is no longer “more tiny loss hacks”
- it is either:
  - formalize restart selection as the focused protocol, or
  - design a better support-side validation signal that correlates with the
    true dual-weak transfer target

Current stop-loss recommendation:

- this is a reasonable temporary stop point for the current micro-loop
- we have already shown:
  - minimum two-support transfer works in all three directions
  - the success is seed-sensitive
  - deterministic focused multi-start can recover the failures
- do not expand the full experiment matrix yet
- next work should be a cleaner validation/selection signal, not another long
  chain of ad-hoc learner-head variants

## Latest Validation-Signal Fix: `P3.6m-17`

Formal write-up:

- `P3_6M_17_NORMALIZED_SUPPORT_SELECTOR_ZH.md`

Purpose:

- test whether the selector problem is really “no useful local signal exists”
- or whether the previous restart scorer was simply evaluating candidates in the
  wrong feature space

What was wrong in `P3.6m-16`:

- `_score_restart_candidate(...)` evaluated restart candidates on
  `focus_train` slices before the training-time normalization used by
  `train_trace_model(...)`
- this collapsed the apparent differences between restart seeds and made the
  support selector look much weaker than it really was

Fix:

- keep the same restart protocol
- but score each candidate on the normalized support slices that live inside the
  actual training copy after feature-mode application and normalization

Additional candidate diagnostics now recorded in `restart_candidates.csv`:

- `support_contrastive_loss`
- `support_weak_bce`
- `support_weak_margin_min`
- `support_weak_margin_mean`
- `support_proto_sep_margin`

Key experiment family:

- `p3_6m17_selector_fix_support437_438_test439/`
- `p3_6m17_selector_fix_support438_439_test437/`
- `p3_6m17_selector_fix_support437_439_test438/`

Critical result:

- after the normalization fix, support-side teacher imitation becomes strongly
  discriminative:
  - seeds `7` and `11`:
    - `support_pairwise = 1.0`
    - `support_ari = 1.0`
    - `support_nmi = 1.0`
    - `support_utility_gap = 0.0`
  - seed `9`:
    - `support_pairwise = 0.714285714286`
    - `support_ari = 0.416666666667`
    - `support_nmi = 0.428140178120`
    - `support_utility_gap = -0.000525943612`
- all three cases now select seed `11` cleanly for the right reason, not just
  by fallback tie-break

Most important interpretation:

- the local validation problem is materially improved
- the main issue in `P3.6m-16` was not the absence of a selector signal
- it was a support-evaluation mismatch between:
  - pre-normalization candidate scoring
  - and post-normalization learner behavior

Updated best next direction:

- treat normalized-support restart scoring as the current best focused protocol
- only after that, decide whether more selector engineering is still needed
- do not jump back to new learner-head redesigns unless this normalized
  selector later proves insufficient on broader nearby regimes

## Latest External Check on Sibling Bundle: `P3.6m-18`

Formal write-up:

- `P3_6M_18_SIBLING_BUNDLE_PROTOCOL_CHECK_ZH.md`

Purpose:

- test whether the normalized-support restart protocol transfers to a nearby
  sibling bundle rather than only the `P3.6m-4b` threshold-nudge regime
- choose the most informative sibling:
  - `p3_6m2_positive_family_decoy_bundle`
  - same family `0|1|15|2|3|4|5 @ gnb_1`
  - earlier positive dual-weak source that originally produced
    `teacher > LE-GRA = static baselines`

Protocol:

- rerun the original `P3.6m-3` focused temporal learner with:
  - `--restart-seeds 7 9 11`
  - normalized support scoring enabled by `P3.6m-17`
- output:
  - `p3_6m18_m2_normalized_selector_multistart/`

Critical result:

- the protocol does **not** recover the teacher on this sibling bundle
- final selected restart seed is still `9`
- final test result remains:
  - `teacher utility = 0.579609048805`
  - `LE-GRA utility = 0.579083105194`
- so this is not a case where restart selection was the missing ingredient

Why this is important:

- all three restart seeds collapse to essentially the same support-side score
  on `m2`
- candidate summary:
  - `support_pairwise_accuracy = 0.999457847655`
  - `support_utility_gap ≈ -9.98e-07`
  - nearly identical across seeds `7/9/11`
- boundary-focused post-check on the normalized support train set also shows
  no separation:
  - all-support pairwise: `0.999457847655`
  - positive-gain support pairwise: `0.959183673469`
  - boundary-support pairwise: `0.928571428571`
  - identical for seeds `7/9/11`
- holdout remains wrong for all three:
  - holdout pairwise: `0.714285714286`

Most important interpretation:

- `P3.6m-17` fixed a **selector-space mismatch**
- but `P3.6m-18` shows that not every failure is a selector problem
- on `m2`, the current learner recipe itself converges to the same wrong local
  rule across seeds
- therefore:
  - restart selection is enough for the narrow `m4b` dual-weak regime
  - but insufficient for the broader `m2` sibling bundle

Updated best next direction:

- do **not** spend more time on restart/tie-break engineering alone
- the next meaningful improvement must change the learner's effective training
  signal on broader mixed support sets, for example:
  - boundary-aware support weighting
  - positive-gain-window-focused curriculum
  - regime-local training subset selection

## Latest Boundary-Aware Support Weighting: `P3.6m-19`

Formal write-up:

- `P3_6M_19_BOUNDARY_SUPPORT_WEIGHTING_ZH.md`

Purpose:

- implement the smallest possible learner-side change that alters the effective
  support-train signal on `m2` without redesigning the learner head
- specifically test whether replaying a tiny number of late, positive-gain,
  boundary-near support slices can move `LE-GRA` toward the teacher

Implementation:

- keep the current `run_p3_6g_temporal_learner.py` training loop and model
  architecture unchanged
- add a minimal temporal protocol on top of existing support replay:
  - `--boundary-support-start`
  - `--boundary-support-repeat`
  - `--boundary-support-positive-only`
- select support examples whose timestamp is later than
  `boundary_support_start`
- optionally restrict them to positive-gain support slices only
- replay those selected support slices `boundary_support_repeat - 1` extra
  times on top of the normal support train set
- record in `split_summary.json`:
  - `boundary_support_selected_scenarios`
  - `effective_boundary_support_scenarios`
  - the chosen boundary replay arguments

Main test family:

- `p3_6m19b_m2_boundary_weighting_r1/`
- `p3_6m19b_m2_boundary_weighting_r4/`
- `p3_6m19b_m2_boundary_weighting_r8/`
- `p3_6m19b_m2_boundary_weighting_r16/`

Common regime:

- bundle: `p3_6m2_positive_family_decoy_bundle/bundle`
- family: `0|1|15|2|3|4|5 @ gnb_1`
- train window end: `43.7 s`
- test window: `43.8 s ~ 43.9 s`
- boundary filter:
  - `--boundary-support-start 43.4`
  - `--boundary-support-positive-only`
- selected boundary support slices:
  - exactly `1`

Critical sweep result:

- `r1` (baseline, no extra replay):
  - selected seed `9`
  - `LE-GRA utility = 0.579083105194`
  - gap to teacher: `-0.000525943612`
- `r4`:
  - selected seed `11`
  - utility still `0.579083105194`
  - selector changes first, holdout utility does not move yet
- `r8`:
  - selected seed `11`
  - support selection becomes perfect:
    - `support_pairwise = 1.0`
  - `LE-GRA utility = 0.579346076999`
  - gap to teacher shrinks to `-0.000262971806`
- `r16`:
  - selected seed `7`
  - support selection remains perfect:
    - `support_pairwise = 1.0`
  - `LE-GRA utility = 0.579609048805`
  - exactly matches teacher utility on this `43.8 ~ 43.9 s` holdout

Most important interpretation:

- this is the first clean evidence on `m2` that a tiny amount of
  boundary-focused support replay can materially change learner behavior
- unlike `P3.6m-18`, the learner is no longer locked to the old
  `LE-GRA = static baseline` plateau once we reweight the right support slice
- the effect is not just random seed luck:
  - replay changes the selected restart seed
  - stronger replay also improves holdout utility
- the behavior looks like a genuine replay-strength threshold:
  - `r4` is not enough
  - `r8` is partially effective
  - `r16` reaches teacher-level utility on this slice pair

Current practical conclusion:

- boundary-aware support weighting is now the strongest low-risk learner-side
  direction after the selector fixes
- this should be treated as a focused protocol success on `m2`
- but it is still a narrow proof:
  - one selected boundary-positive support slice
  - one sibling regime
  - one short holdout window

Updated best next direction:

- keep the learner architecture stable for now
- next work should test whether this boundary replay signal generalizes beyond
  this exact `m2` slice pair, for example:
  - small nearby holdout shifts
  - nearby support-start thresholds
  - slightly richer boundary subset definitions
- do **not** jump to large matrix expansion yet
- first verify whether the gain is robust or only a single-slice resonance

## Latest Robustness Check on Boundary Replay: `P3.6m-20`

Formal write-up:

- `P3_6M_20_BOUNDARY_WEIGHTING_ROBUSTNESS_ZH.md`

Purpose:

- test whether the `P3.6m-19` success at `m2` is fragile
- specifically check two low-cost robustness questions:
  - does the gain depend on one exact `boundary_support_start` value?
  - does it survive small holdout shifts around the same late regime?

Protocol:

- keep the same focused regime and learner recipe as `P3.6m-19`
- bundle:
  - `p3_6m2_positive_family_decoy_bundle/bundle`
- fixed settings:
  - `train_window_end = 43.7`
  - `boundary_support_repeat = 16`
  - `boundary_support_positive_only = true`
  - `restart_seeds = 7 9 11`
- run two tiny sweeps:
  - boundary-start sweep:
    - `43.3 / 43.4 / 43.5`
    - common holdout: `43.8 ~ 43.9`
  - holdout sweep:
    - `43.8 only`
    - `43.9 only`
    - `44.0 only`
    - common boundary start: `43.4`

Result summary:

- boundary-start sweep:
  - `p3_6m20_m2_boundary_start_433_r16/`
  - `p3_6m20_m2_boundary_start_434_r16/`
  - `p3_6m20_m2_boundary_start_435_r16/`
  - all three produce:
    - selected restart seed `7`
    - `support_pairwise = 1.0`
    - `LE-GRA utility = 0.579609048805`
    - exact teacher match on `43.8 ~ 43.9`
- holdout sweep:
  - `p3_6m20_m2_holdout_438_only_r16/`
  - `p3_6m20_m2_holdout_439_only_r16/`
  - `p3_6m20_m2_holdout_440_only_r16/`
  - `43.8 only`:
    - exact teacher match
  - `43.9 only`:
    - exact teacher match
  - `44.0 only`:
    - `LE-GRA = CQI = teacher`
    - so the boundary replay advantage is no longer needed there because this
      slice already lies in an easier/equal regime for the static baseline

Most important interpretation:

- the `P3.6m-19` improvement is **not** a one-point artifact of choosing
  exactly `boundary_support_start = 43.4`
- with `repeat = 16`, the same replay protocol is stable across
  `43.3 / 43.4 / 43.5`
- the gain also survives the immediate holdout decomposition:
  - it works on `43.8` alone
  - it works on `43.9` alone
- however the benefit is still regime-local:
  - by `44.0`, the static CQI baseline already matches the teacher
  - so `44.0` should not be treated as additional evidence that the learner has
    solved a harder boundary case

Current practical conclusion:

- `boundary-aware support weighting` has now passed the first meaningful
  robustness check on `m2`
- the evidence is strong enough to say this is a real focused learner-side
  mechanism, not just accidental noise
- the remaining open question is no longer:
  - "does replay help at all?"
- it is now:
  - "how far does this mechanism transfer before the regime changes?"

Updated best next direction:

- do not expand to a broad matrix yet
- first reuse this minimal replay protocol on one nearby but still informative
  sibling regime, or on a slightly harder late-window variant where
  `teacher > CQI` still holds
- if that transfer fails, then move to the next learner-side refinement rather
  than returning to selector debugging

## Latest Transfer Check on `m4b`: `P3.6m-21`

Formal write-up:

- `P3_6M_21_M4B_BOUNDARY_TRANSFER_CHECK_ZH.md`

Purpose:

- test whether the exact minimal replay protocol that succeeded on `m2`
  transfers to the nearest difficult sibling regime
- target:
  - `p3_6m4b_threshold_nudge_bundle/bundle`
  - same family `0|1|15|2|3|4|5 @ gnb_1`
  - same dual-weak bottleneck
  - harder evaluation window `43.7s ~ 43.9s`

Protocol:

- keep the `P3.6m-20` best boundary replay recipe unchanged:
  - `boundary_support_start = 43.4`
  - `boundary_support_repeat = 16`
  - `boundary_support_positive_only = true`
- keep focused learner settings otherwise unchanged:
  - `train_window_end = 43.6`
  - `test_window = 43.7 ~ 43.9`
  - `restart_seeds = 7 9 11`
- output:
  - `p3_6m21_m4b_boundary_weighting_transfer_r16/`

Critical result:

- transfer **fails**
- main comparison remains unchanged:
  - `teacher = 0.579609048805`
  - `CQI = 0.579083105194`
  - `LE-GRA = 0.579083105194`
- so `LE-GRA` still ties the static baselines and does not recover the teacher

Important support-side detail:

- support replay is definitely active:
  - `boundary_support_selected_scenarios = 1`
  - `effective_boundary_support_scenarios = 15`
- support-side selection also becomes perfect:
  - `support_pairwise = 1.0`
  - `support_ari = 1.0`
  - `support_nmi = 1.0`
  - `support_utility_gap = 0.0`
- yet final selected restart seed remains `9`
- and the holdout utility does not move at all

Most important interpretation:

- this is the clearest evidence so far that:
  - `m2` success was real
  - but `boundary-aware support weighting` is **not** yet a same-family
    universal fix
- the current bottleneck is therefore more specific than:
  - "late positive boundary support is underweighted"
- on `m4b`, even perfect support-side imitation under replay is still
  insufficient to make the learner adopt the teacher's dual-weak grouping on
  the harder holdout

Current practical conclusion:

- we now have a meaningful stop-loss boundary for the replay-only idea
- replay-only learner-side weighting is worth keeping as a successful focused
  mechanism for `m2`
- but replay-only is not enough to declare the broader dual-weak problem solved

Updated best next direction:

- stop expanding replay sweeps for now
- do not go back to selector-only debugging
- the next useful learner-side step should add a more explicit mechanism for
  the secondary weak candidate itself, for example:
  - boundary-aware pair construction around the secondary weak candidate
  - candidate-conditioned weak-group supervision
  - localized hard-negative generation that directly separates
    `{ue15, ue4}` from the old `ue15`-only split

## Latest Candidate-Conditioned Weak-Group Supervision v1: `P3.6m-22`

Formal write-up:

- `P3_6M_22_CANDIDATE_CONDITIONED_WEAK_GROUP_V1_ZH.md`

Purpose:

- implement the smallest possible version of
  `candidate-conditioned weak-group supervision`
- keep the learner architecture unchanged
- add explicit supervision pressure on the likely weak-group candidates inside
  the teacher's hardest group, especially the secondary candidate that the
  learner keeps missing on `m4b`

Implementation:

- `le_gra_mvp.py`
  - added `candidate_conditioned_membership_targets(...)`
  - inside the teacher's hardest group:
    - rank members by mean resource-cost
    - mark the top `k` users as weak-group candidates
    - assign the second candidate an extra supervision scale
- `MLPEncoder.train_step(...)`
  - added optional sparse candidate-membership BCE on top of the existing
    contrastive / prototype / hardest-group membership losses
- `run_p3_6_coupled_learner.py`
  - threaded new candidate-supervision parameters through
    `train_trace_model(...)`
- `run_p3_6g_temporal_learner.py`
  - added CLI knobs:
    - `--candidate-membership-weight`
    - `--candidate-top-k`
    - `--candidate-secondary-scale`
  - recorded them in `split_summary.json`

First focused test:

- output:
  - `p3_6m22_m4b_candidate_conditioned_v1/`
- regime:
  - bundle: `p3_6m4b_threshold_nudge_bundle/bundle`
  - train end: `43.6`
  - test: `43.7 ~ 43.9`
  - boundary replay kept on:
    - `boundary_support_start = 43.4`
    - `boundary_support_repeat = 16`
    - `boundary_support_positive_only = true`
- new candidate-supervision settings:
  - `candidate_membership_weight = 1.0`
  - `candidate_top_k = 2`
  - `candidate_secondary_scale = 2.0`

Critical result:

- implementation works, but the first `m4b` run does **not** move the holdout
- main comparison remains:
  - `teacher = 0.579609048805`
  - `LE-GRA = 0.579083105194`
  - `CQI = 0.579083105194`
- support-side metrics remain perfect:
  - `support_pairwise = 1.0`
  - `support_ari = 1.0`
  - `support_nmi = 1.0`
  - `support_utility_gap = 0.0`

Most important interpretation:

- this confirms the new supervision path is now available for further learner
  studies
- but the first minimal weight setting is not yet enough to break the `m4b`
  plateau
- so the next useful move is not another replay sweep
- it is a very small candidate-supervision calibration, for example:
  - increase `candidate_membership_weight`
  - increase `candidate_secondary_scale`
  - combine candidate supervision with explicit boundary pair construction

## Latest Minimal Calibration on Candidate Supervision: `P3.6m-23`

Formal write-up:

- `P3_6M_23_CANDIDATE_CONDITIONED_CALIBRATION_ZH.md`

Purpose:

- test whether the new candidate-conditioned weak-group supervision from
  `P3.6m-22` was simply too weak
- keep everything else fixed and run the smallest useful 2x2 calibration over:
  - `candidate_membership_weight`
  - `candidate_secondary_scale`

Protocol:

- same regime as `P3.6m-22`:
  - bundle: `p3_6m4b_threshold_nudge_bundle/bundle`
  - train end: `43.6`
  - test: `43.7 ~ 43.9`
  - replay:
    - `boundary_support_start = 43.4`
    - `boundary_support_repeat = 16`
    - `boundary_support_positive_only = true`
- fixed:
  - `candidate_top_k = 2`
- sweep:
  - `w2_s2`
  - `w4_s2`
  - `w2_s4`
  - `w4_s4`

Outputs:

- `p3_6m23_m4b_candidate_calib_w2_s2/`
- `p3_6m23_m4b_candidate_calib_w4_s2/`
- `p3_6m23_m4b_candidate_calib_w2_s4/`
- `p3_6m23_m4b_candidate_calib_w4_s4/`

Critical result:

- all four runs are identical on the holdout
- in every case:
  - selected restart seed stays `9`
  - `support_pairwise = 1.0`
  - `LE-GRA = 0.579083105194`
  - `teacher = 0.579609048805`
  - `CQI = 0.579083105194`
- so the 2x2 minimal calibration produces **no movement at all**

Most important interpretation:

- this is a clean stop-loss point for the current
  candidate-membership-BCE-only idea
- the issue is not merely that `P3.6m-22` used weights that were too small
- even after increasing:
  - overall candidate-membership weight
  - and secondary-candidate emphasis
- the learner still remains exactly on the old plateau

Current practical conclusion:

- keep the candidate-conditioned supervision path in the codebase
- but stop spending time on weight-only calibration
- the next meaningful learner-side step must change supervision structure, not
  just its coefficient magnitude

Updated best next direction:

- combine candidate supervision with explicit boundary-aware pair construction
- or directly generate localized hard negatives that separate:
  - the correct dual-weak grouping `{ue15, ue4}`
  - from the old `ue15`-only solution

## Latest Boundary-Aware Pair Construction v1: `P3.6m-24`

Formal write-up:

- `P3_6M_24_BOUNDARY_AWARE_PAIR_CONSTRUCTION_V1_ZH.md`

Purpose:

- move beyond weight-only candidate BCE tuning
- implement the smallest possible pair-structure refinement aimed directly at
  the secondary weak candidate boundary

Implementation:

- `le_gra_mvp.py`
  - extended `pairwise_supervision_weights(...)` with:
    - `teacher_candidate_boundary`
- logic:
  - keep existing hardest-group emphasis
  - additionally identify the top-2 hardest-group members by resource-cost
  - explicitly upweight:
    - the positive pair between primary and secondary weak candidates
    - negative pairs from the secondary candidate to users outside the hardest
      group
    - keep primary-candidate boundary negatives at least at hardest-group level
- no model-architecture change
- no extra membership BCE in this first test

First focused test:

- output:
  - `p3_6m24_m4b_candidate_boundary_pairs_v1/`
- regime:
  - bundle: `p3_6m4b_threshold_nudge_bundle/bundle`
  - train end: `43.6`
  - test: `43.7 ~ 43.9`
  - replay still on:
    - `boundary_support_start = 43.4`
    - `boundary_support_repeat = 16`
    - `boundary_support_positive_only = true`
- pair setup:
  - `pair_sampling = teacher_boundary`
  - `supervision_weight_mode = teacher_candidate_boundary`

Critical result:

- the new pair structure is implemented correctly
- but the first `m4b` run still does **not** move the holdout
- result remains:
  - `teacher = 0.579609048805`
  - `LE-GRA = 0.579083105194`
  - `CQI = 0.579083105194`
- support-side selection remains perfect:
  - `support_pairwise = 1.0`
  - `support_ari = 1.0`
  - `support_nmi = 1.0`

Most important interpretation:

- this gives us a stronger stop-loss boundary:
  - replay-only was insufficient
  - candidate-BCE-only was insufficient
  - first localized boundary-pair construction is also insufficient
- so the remaining bottleneck is unlikely to be solvable by one more small
  coefficient or pair-priority tweak alone

Current practical conclusion:

- the codebase now contains all three minimal learner-side hooks:
  - replay weighting
  - candidate membership supervision
  - boundary-aware pair construction
- none of the minimal `m4b` variants has yet broken the plateau

Updated best next direction:

- if continuing this line, the next step should combine structure, not just add
  another tiny isolated tweak, for example:
  - boundary-aware pair construction + candidate membership together
  - or localized hard negatives that explicitly contrast
    `{ue15, ue4}` vs `ue15-only`
- if imposing a research stop-loss, this is now a reasonable point to summarize
  that minimal learner-side local tweaks are insufficient on `m4b`

## Latest Minimal Joint Supervision on `m4b`: `P3.6m-25`

Formal write-up:

- `P3_6M_25_MINIMAL_JOINT_SUPERVISION_ZH.md`

Purpose:

- stop testing the three learner-side hooks in isolation
- combine the currently available minimal mechanisms into one focused protocol:
  - boundary-aware replay
  - candidate-conditioned weak-group supervision
  - boundary-aware pair construction
- test only the main `m4b` dual-weak regime, not a larger matrix

Implementation:

- `run_p3_6g_temporal_learner.py`
  - added `--joint-supervision-mode`
  - added preset:
    - `m4b_minimal_joint_v1`
  - this preset applies:
    - `pair_sampling = teacher_boundary`
    - `supervision_weight_mode = teacher_candidate_boundary`
    - `candidate_top_k = 2`
    - `candidate_membership_weight >= 4.0`
    - `candidate_secondary_scale >= 4.0`
    - `boundary_support_repeat >= 16`
    - `boundary_support_positive_only = true`
    - default `boundary_support_start = 43.4` if unset
- also added:
  - `weak_group_prediction_audit.csv`
- this audit records:
  - teacher hardest-group signature
  - teacher candidate signature
  - learner weak-score top-k
  - secondary weak candidate rank
  - candidate hit count

Focused run:

- output:
  - `p3_6m25_m4b_minimal_joint_supervision_v1/`
- regime:
  - bundle: `p3_6m4b_threshold_nudge_bundle/bundle`
  - family: `0|1|15|2|3|4|5 @ gnb_1`
  - train end: `43.6`
  - test: `43.7 ~ 43.9`
  - restart seeds: `7 9 11`
  - background train limit: `150`

Critical result:

- the minimal joint version still does **not** move the holdout
- main comparison remains:
  - `teacher = 0.579609048805`
  - `LE-GRA = 0.579083105194`
  - `CQI = 0.579083105194`
- selected restart seed remains `9`
- support-side remains perfect:
  - `support_pairwise = 1.0`
  - `support_ari = 1.0`
  - `support_nmi = 1.0`
  - `support_utility_gap = 0.0`

Most important new insight:

- the new weak-group audit localizes the failure more precisely
- on the real holdout points `43.7 / 43.8 / 43.9`:
  - teacher candidate signature is `15|4`
  - learner predicted top-2 is `15|1`
  - `ue4` falls to `predicted_secondary_rank = 7`
- so this is **not** a case where the learner already ranks `ue4` correctly but
  loses later in grouping/DP
- the failure is earlier:
  - the current representation/supervision still does not pull `ue4` into the
    weak-candidate frontier at all

Current practical conclusion:

- this is a stronger stop-loss point than `P3.6m-24`
- replay-only was insufficient
- candidate-BCE-only was insufficient
- pair-only was insufficient
- and even the minimal joint combination is still insufficient on `m4b`

Updated best next direction:

- do **not** continue with more replay-only / weight-only / pair-only micro-tweaks
- the next meaningful step should move to:
  - stronger localized hard negatives that explicitly contrast
    `{ue15, ue4}` vs `ue15-only`
  - or a more structural redesign of the learner-side supervision / representation

## Latest Localized Hard Negatives + Inference Bridge: `P3.6m-26`

Formal write-up:

- `P3_6M_26_LOCALIZED_HARD_NEGATIVE_AND_INFERENCE_BRIDGE_ZH.md`

Purpose:

- move beyond minimal joint weighting and add a stronger local ranking signal
- explicitly force the teacher weak candidates to outrank nearby confusers
- immediately test whether the remaining bottleneck is actually learner quality
  or an inference mismatch between the trained weak head and the final grouping path

Implementation:

- `le_gra_mvp.py`
  - added `candidate_frontier_contrast_targets(...)`
  - added a localized frontier contrast loss inside `MLPEncoder.train_step(...)`
  - this loss pushes teacher candidates above local confusers in weak-logit space
- `run_p3_6_coupled_learner.py`
  - threaded:
    - `frontier_contrast_weight`
    - `frontier_negative_top_k`
    - `frontier_margin`
  - recorded frontier diagnostics into output CSVs
- `run_p3_6g_temporal_learner.py`
  - added joint mode:
    - `m4b_localized_hard_negative_v1`

Phase A: localized hard negatives with the old inference path

- output:
  - `p3_6m26_m4b_localized_hard_negative_v1/`
- regime:
  - same `m4b` focused setup
  - grouping still:
    - `kmeans_embedding`

Critical result from Phase A:

- main utility still does **not** move:
  - `teacher = 0.579609048805`
  - `LE-GRA = 0.579083105194`
- however the new weak-group audit changes dramatically:
  - on `43.7 / 43.8 / 43.9`
  - teacher candidate signature = `15|4`
  - learner predicted top-2 also becomes `15|4`
  - `ue4` rank improves from `7` to `2`

Most important interpretation from Phase A:

- this is the first strong evidence that the learner can now recover the correct
  dual-weak frontier
- therefore the remaining failure is no longer well-described as
  "the learner still cannot identify `ue4`"

Phase B: inference-bridge check

- output:
  - `p3_6m26b_m4b_localized_hard_negative_membership_order/`
- identical training setup, but evaluation switches to:
  - `grouping_mode = membership_order`

Critical result from Phase B:

- `LE-GRA` now matches teacher on the focused `m4b` holdout:
  - `teacher = 0.579609048805`
  - `LE-GRA = 0.579609048805`

Most important new conclusion:

- the bottleneck is now much more specifically localized:
  - localized hard-negative supervision can fix the weak ranking
  - but the old `embedding -> kmeans` inference path does not automatically use
    that repaired weak-boundary signal
- in other words, a major part of the previous plateau was an
  **inference mismatch**, not purely a supervision failure

Current practical conclusion:

- this is a real breakthrough, not just another null result
- the project now has a concrete path that reaches teacher-level behavior on the
  hardest current `m4b` regime:
  - localized hard negatives
  - plus `membership_order` inference

Updated best next direction:

- stop treating the problem as "more local learner-side loss tweaks needed"
- the next priority should be inference bridging:
  - compare `membership_order` vs `kmeans_embedding` systematically
  - test whether the bridge transfers beyond this one regime
  - if staying with embeddings, investigate hybrid bridging so the weak-head
    signal influences final group construction

## Latest `membership_order` Focused Transfer Check: `P3.6m-27`

Formal write-up:

- `P3_6M_27_MEMBERSHIP_ORDER_TRANSFER_CHECK_ZH.md`

Purpose:

- verify that the `P3.6m-26` bridge success on `m4b` is not just a
  3-snapshot average artifact
- keep the same localized hard-negative training
- split the main holdout into single-point tests:
  - `43.7 only`
  - `43.8 only`
  - `43.9 only`

Protocol:

- same focused `m4b` regime:
  - bundle: `p3_6m4b_threshold_nudge_bundle/bundle`
  - family: `0|1|15|2|3|4|5 @ gnb_1`
  - train end: `43.6`
- same training mode:
  - `joint_supervision_mode = m4b_localized_hard_negative_v1`
- same inference bridge:
  - `grouping_mode = membership_order`
- outputs:
  - `p3_6m27a_m4b_localized_membership_437_only/`
  - `p3_6m27b_m4b_localized_membership_438_only/`
  - `p3_6m27c_m4b_localized_membership_439_only/`

Critical result:

- all three single-point focused checks match the teacher individually
- so on:
  - `43.7`
  - `43.8`
  - `43.9`
- `LE-GRA = teacher`

Most important interpretation:

- the `membership_order` breakthrough on `m4b` is not a pooled-average accident
- it is stable across the full main holdout segment, point by point
- this substantially strengthens the inference-bridge conclusion from
  `P3.6m-26`

Current practical conclusion:

- the project now has a focused, repeatable teacher-matching path on the
  hardest current `m4b` regime
- the next question is no longer "does this work at all on `m4b`?"
- it is:
  - how far does the bridge transfer beyond this focused regime?

## Latest Cross-Regime Transfer Check: `P3.6m-28`

Formal write-up:

- `P3_6M_28_CROSS_REGIME_TRANSFER_TO_M2_ZH.md`

Purpose:

- begin the real phase-2 transfer check beyond the `m4b` main regime
- test whether the new successful path:
  - localized hard negatives
  - plus `membership_order`
- is stable outside `m4b`, or is only a regime-specific fix

Protocol:

- bundle:
  - `p3_6m2_positive_family_decoy_bundle/bundle`
- focus family:
  - `0|1|15|2|3|4|5 @ gnb_1`
- train end:
  - `43.7`
- test window:
  - `43.8 ~ 43.9`
- training mode:
  - `joint_supervision_mode = m4b_localized_hard_negative_v1`
- inference bridge:
  - `grouping_mode = membership_order`
- output:
  - `p3_6m28_m2_localized_hard_negative_membership_order/`

Critical result:

- on `m2`, `LE-GRA` still matches the teacher exactly:
  - `teacher = 0.579609048805`
  - `LE-GRA = 0.579609048805`
- baselines remain slightly below:
  - `CQI / resource-cost / multi-feature = 0.579083105194`

Weak-group audit result:

- on both focused holdout points:
  - `43.8`
  - `43.9`
- the audit shows:
  - `teacher_candidate_signature = 15|4`
  - `predicted_topk_signature = 15|4`
  - full candidate hit count = `2`

Most important interpretation:

- the `m4b` breakthrough is not isolated to one regime
- the new supervision + bridge path transfers cleanly to at least one sibling
  focused regime without regression
- this strengthens the view that:
  - localized hard negatives repair the weak frontier
  - `membership_order` can reliably expose that repaired signal at inference

Current practical conclusion:

- we now have evidence for:
  - regime-specific success on `m4b`
  - plus first cross-regime stability on `m2`
- the next phase-2 question should no longer be "does it transfer at all?"
- it should be:
  - which regimes are already easy
  - which regimes specifically need the bridge
  - and where the next genuinely unsolved mismatch still lives

## Latest Focused Regime Classification: `P3.6m-29`

Formal write-up:

- `P3_6M_29_REGIME_CLASSIFICATION_ZH.md`

Purpose:

- convert the current phase-2 transfer results into a cleaner regime taxonomy
- avoid continuing to over-tune already-solved regimes
- identify whether the project's next bottleneck is:
  - more learner tweaks
  - more inference bridging
  - or simply missing regime discovery

Classification summary:

- `m2`:
  - easy / already-solvable
  - old `kmeans_embedding` already matches teacher on focused holdouts
  - new localized-hard-negative + `membership_order` path also transfers there
    without regression
- `m4b`:
  - bridge-needed
  - old `kmeans_embedding` remains stuck at the baseline plateau
  - localized hard negatives repair the weak frontier
  - `membership_order` is required to expose that repaired signal and recover
    teacher-level utility
- current status of a third class:
  - no additional focused family has yet been validated as a new genuinely
    unsolved regime

Most important interpretation:

- the project now has at least two clearly distinct regime types:
  - already-solvable
  - bridge-needed
- but the next major gap is not better tuning inside `m2` or `m4b`
- it is finding the next informative family that is neither trivially easy nor
  already resolved by the current bridge path

Current best next step:

- move into focused regime mining / family discovery
- for each candidate family, do a minimal triage:
  - does old `kmeans_embedding` already solve it?
  - if not, does `membership_order` solve it?
  - if still not, then elevate it as the next genuinely unsolved regime

## Latest Family-Bank Filter Fix And Triage: `P3.6m-30`

Formal write-up:

- `P3_6M_30_FAMILY_BANK_FILTER_FIX_AND_TRIAGE_ZH.md`

Bug found:

- the original `p3_6m_family_bank/` focus-mining outputs were polluted because
  `run_p3_6m_family_bank.py` called `mine_focus_slices.py` on the full audit CSV
  without filtering to the target family
- consequence:
  - several different family outputs shared identical
    `candidate_temporal_slices.csv`
  - and identical `positive_segments.csv`

Fix implemented:

- `mine_focus_slices.py`
  - now accepts:
    - `--target-ue-ids`
    - `--target-serving-gnb`
  - and filters rows before segment mining
- `run_p3_6m_family_bank.py`
  - now passes the target family filter through to `mine_focus_slices.py`

Validation:

- reran the batch to:
  - `p3_6m_family_bank_filtered/`

Critical result after the fix:

- among the filtered top-5 family bank candidates, only the known
  `0|1|15|2|3|4|5 @ gnb_1` family still has:
  - nonzero `target_positive_gain_count`
  - nonempty focused temporal slices
- the other candidate families collapse to:
  - zero target-positive gain
  - empty `candidate_temporal_slices.csv`

Most important interpretation:

- the current family bank does **not** yet provide a third informative focused
  regime beyond the already-known `m4b`
- this means the next bottleneck is no longer learner tweaking inside the
  existing bank
- it is finding or generating a new scenario/ranking source with genuinely new
  informative families

Current best next step:

- do not keep mining the same bank blindly
- instead move to one of:
  - new scenario-source generation
  - stronger near-miss mining
  - ranking criteria that explicitly reward sustained target-positive gain

## Latest `gnb_2` Regime-Generation Breakthrough: `P3.6n-1 ~ P3.6n-3`

Formal write-up:

- `P3_6N_1_TO_3_GNB2_UE5_ISOLATION_REDESIGN_ZH.md`

Purpose:

- stop relying only on already-existing positive regimes
- turn a high-structure near-miss family into a new teacher-positive focused
  regime
- use the top redesign target:
  - `3|4|5|6 @ gnb_2`

Variants built:

- `build_p3_6n1_quality_gap_bundle.py`
  - output:
    - `p3_6n1_quality_gap_bundle/`
  - continuity / previous-quality gap only
- `build_p3_6n2_quality_gap_pressure_bundle.py`
  - output:
    - `p3_6n2_quality_gap_pressure_bundle/`
  - continuity gap + moderate pressure + extra `ue5` weakening
- `build_p3_6n3_isolate_ue5_bundle.py`
  - output:
    - `p3_6n3_isolate_ue5_bundle/`
  - stronger `ue5` isolation pressure

Critical progression:

- `n1`:
  - still no positive segment
- `n2`:
  - still no positive segment
  - but best non-single split gap improves strongly toward zero
  - and the preferred split stabilizes as:
    - `[[0,1,3],[2]]`
    - i.e. isolate `ue5`
- `n3`:
  - breakthrough
  - on `25.8s ~ 29.9s`, teacher now consistently chooses:
    - `teacher_group_count = 2`
    - `teacher_groups = [[0,1,3],[2]]`
  - with stable positive gain:
    - `teacher_gain_vs_single = 0.079451741871`

Focused mining result on `n3`:

- `p3_6n3_focus_mining/`
- `positive_segment_count = 1`
- `candidate_temporal_slice_count = 41`
- `near_miss_family_count = 0`

Most important interpretation:

- this is the first confirmed new teacher-positive focused regime source beyond
  the old `m4b` line
- it was not found by passive mining alone; it was created through targeted
  regime redesign
- the resulting split structure is clean and stable:
  - isolate `ue5`
  - group the rest together

Current best next step:

- treat `p3_6n3_isolate_ue5_bundle` as the next focused learner target
- run learner-side focused validation there first:
  - old `kmeans_embedding`
  - `membership_order`
  - compare whether this new regime is:
    - easy
    - bridge-needed
    - or a new genuinely unsolved learner regime

## Latest Focused Learner Triage On `n3`: `P3.6n-4`

Formal write-up:

- `P3_6N_4_FOCUSED_LEARNER_TRIAGE_ON_N3_ZH.md`

Protocol:

- bundle:
  - `p3_6n3_isolate_ue5_bundle/bundle`
- focus family:
  - `3|4|5|6 @ gnb_2`
- balanced split:
  - `train end = 27.8`
  - `test = 27.9 ~ 29.9`
- compared:
  - old `kmeans_embedding`
  - `membership_order`

Outputs:

- `p3_6n3a_baseline_kmeans/`
- `p3_6n3b_baseline_membership_order/`

Critical result:

- both runs give the same final outcome:
  - `Offline teacher = 0.460388133563`
  - `LE-GRA MVP = 0.460388133563`
  - `Resource-cost = Multi-feature = 0.460388133563`
  - `CQI = 0.456624985427`

Interpretation:

- `n3` is a successful new teacher-positive regime source
- but it is **not** a new learner-hard regime
- old `kmeans_embedding` already solves it
- `membership_order` is not additionally required

Updated regime taxonomy:

- `m2`:
  - easy / already-solvable
- `m4b`:
  - bridge-needed
- `n3`:
  - newly generated positive regime
  - but still easy

Current best next step:

- do not spend more learner-tweak budget on `n3` as-is
- instead redesign beyond one-vs-rest isolation:
  - introduce a second near-weak user
  - create ambiguous weak ordering
  - or otherwise make the positive regime less trivially separable
- the goal should be turning `n3` from:
  - positive-but-easy
  into:
  - positive-and-bridge-needed

## Latest Temporal-Swap Regime: `P3.6n-5`

Formal write-up:

- `P3_6N_5_TEMPORAL_SWAP_TRIAGE_ZH.md`

Bundle / outputs:

- bundle:
  - `p3_6n5_temporal_swap_bundle/bundle`
- teacher audit:
  - `p3_6n5_teacher_audit/`
- focus mining:
  - `p3_6n5_focus_mining/`
- focused learner holdout:
  - `p3_6n5a_kmeans_swap_holdout/`
  - `p3_6n5b_membership_swap_holdout/`

What changed:

- started from `n3`
- kept the early `ue5-only` weak regime
- from `27.9s` onward, weakened `ue4` and partially recovered `ue5`
- intent:
  - create temporal weak-order ambiguity
  - make teacher switch from `ue5-only` to `{ue4, ue5}`

Teacher result:

- `25.8s ~ 27.8s`:
  - teacher split = `[[0, 1, 3], [2]]`
  - semantic meaning:
    - isolate `ue5`
  - `teacher_gain_vs_single = 0.07945174187052606`
- `27.9s ~ 28.3s`:
  - teacher split = `[[0, 3], [1, 2]]`
  - semantic meaning:
    - weak pair becomes `{ue4, ue5}`
  - `teacher_gain_vs_single = 0.007212230576617407`
- `28.4s ~ 29.9s`:
  - teacher falls back to single-group

Interpretation:

- this is the first focused regime in this line where teacher grouping clearly
  changes across time inside the same family
- however, the late weak-pair regime is still:
  - short
  - weak-gain
  - and too easy for simple baselines

Focused learner triage:

- holdout protocol:
  - train end = `27.8`
  - test = `27.9 ~ 28.3`
- both `kmeans_embedding` and `membership_order` produce the same result:
  - No grouping = `0.43093639169248765`
  - CQI = `0.438148622269105`
  - Resource-cost = `0.438148622269105`
  - Multi-feature = `0.438148622269105`
  - Offline teacher = `0.438148622269105`
  - LE-GRA MVP = `0.438148622269105`

Bottom line:

- `n5` is structurally more interesting than `n3`
- but it is still not a new bridge-needed regime
- the next redesign should preserve the temporal/pair structure while making
  the weak pair less trivially separable from simple features

## Latest Failure Boundary: `P3.6n-6`

Formal write-up:

- `P3_6N_6_MASKED_PAIR_FAILURE_ZH.md`

Bundle / outputs:

- bundle:
  - `p3_6n6_masked_pair_bundle/bundle`
- teacher audit:
  - `p3_6n6_teacher_audit/`
- focus mining:
  - `p3_6n6_focus_mining/`

What changed:

- started from `n5`
- forced late-window `rb_available = 3`
- kept `ue4` / `ue5` as rate-weakened pair
- but compressed simple feature separability by:
  - setting all four target UEs to `previous_quality = 3`
  - pulling `ue4` / `ue5` CQI back toward the middle

Critical result:

- overall audit still shows positive scenarios because the early `ue5-only`
  segment from `n5` remains
- but on the actual late target window `27.9s ~ 29.9s`:
  - teacher returns to single-group for all 21 target scenarios
  - positive count = `0 / 21`

Interpretation:

- this gives us an important boundary condition:
  - if we mask the late weak pair too aggressively, teacher no longer wants to
    split
- therefore this family's positive regime still depends on a visible quality
  gap, not just hidden rate / resource pressure

Current best next step:

- do not keep pushing fully masked variants
- move to a partial-masking redesign:
  - keep some visible quality gap
  - extend late weak-pair duration
  - increase late positive gain
  - only then test whether baseline separability starts to break

## Latest O-Series Family Search And Positive-Family Redesign

Formal write-up:

- `P3_6O_1_TO_7_POSITIVE_FAMILY_REDESIGN_ZH.md`

### O1 ~ O2: new family `2|3|4|5 @ gnb_2`

Outputs:

- `p3_6o1_family_focus/`
- `build_p3_6o2_primary_weak_bundle.py`
- `p3_6o2_primary_weak_bundle/`
- `p3_6o2_teacher_audit/`
- `p3_6o2_focus_mining/`

Critical result:

- `2|3|4|5 @ gnb_2` on `24.0s ~ 24.9s` did not produce any split structure
- `o2` remained single-group throughout
- so this family is currently too weak to justify more local tweaking

### O3 ~ O5: positive family `0|1|2|3|4 @ gnb_2`

Focused audit:

- `p3_6o3_family_focus/`

Base regime:

- `18.7s ~ 19.2s`
- teacher split = `[[0, 1, 2, 4], [3]]`
- semantic meaning:
  - isolate `ue3`
- `teacher_gain_vs_single = 0.011900924527038947`

Decoy injection results:

- `o4`:
  - `build_p3_6o4_positive_family_decoy_bundle.py`
  - light `ue4` decoy
- `o5`:
  - `build_p3_6o5_stronger_decoy_bundle.py`
  - stronger `ue4` boundary decoy

Critical result:

- both `o4` and `o5` preserved the positive-gain basin perfectly
- but neither changed teacher structure at all
- the split remained:
  - `[[0, 1, 2, 4], [3]]`

Interpretation:

- this family has a stable positive-gain basin
- but weak decoy injection alone is not enough to perturb the structure

### O6: pair-candidate breakthrough with tie-only structure shift

Outputs:

- `build_p3_6o6_pair_candidate_bundle.py`
- `p3_6o6_pair_candidate_bundle/`
- `p3_6o6_teacher_audit/`
- `p3_6o6_focus_mining/`

Critical result:

- `o6` is the first run that actually moved this family away from the old
  `ue3-only` split
- teacher switched to tie-utility multigroup structures:
  - `18.7s ~ 19.1s`: `[[1, 2], [0, 3, 4]]`
  - `19.2s`: `[[0, 2], [1, 3, 4]]`
- but:
  - `teacher_gain_vs_single ≈ 0`
  - `positive count = 0 / 6`
  - `multigroup count = 6 / 6`

Interpretation:

- this is an important structural boundary:
  - the family *can* be perturbed out of `ue3-only`
  - but the first successful perturbation lands on an arbitrary tie split,
    not on a useful positive-gain weak pair

### O7: true dual-weak attempt reverts to base positive regime

Outputs:

- `build_p3_6o7_dual_weak_pair_bundle.py`
- `p3_6o7_dual_weak_pair_bundle/`
- `p3_6o7_teacher_audit/`
- `p3_6o7_focus_mining/`

Critical result:

- explicitly turning `ue3` and `ue4` into a dual-weak pair did **not**
  preserve the `o6` structure shift
- teacher returned to the original positive-gain split:
  - `[[0, 1, 2, 4], [3]]`
- `positive count = 6 / 6`

Bottom line:

- `0|1|2|3|4 @ gnb_2` is now a high-value family because it exposes a clean
  gain/structure tension:
  - `o4 / o5 / o7`:
    - preserve positive gain
    - but structure stays at `ue3-only`
  - `o6`:
    - structure moves
    - but gain collapses to tie-utility

Current best next step:

- do not go back to broad family search yet
- stay on `0|1|2|3|4 @ gnb_2`
- the latest work after `o7` is:
  - `o8`:
    - first true `{ue3, ue4}` positive split
    - but only at `18.7s`
  - `o9`:
    - attempted stabilization
    - did not extend beyond the same single timestamp
- therefore the new best next step is:
  - timestamp-neighborhood stabilization around `o8`
  - not another broad family jump

### O8: localized gain recovery breakthrough

Outputs:

- `build_p3_6o8_gain_recovery_bundle.py`
- `p3_6o8_gain_recovery_bundle/`
- `p3_6o8_teacher_audit/`
- `p3_6o8_focus_mining/`

Critical result:

- `18.7s`:
  - teacher split = `[[0, 1, 2], [3, 4]]`
  - semantic meaning:
    - first true `{ue3, ue4}` weak pair
  - `teacher_gain_vs_single = 0.012637245583141055`
- `18.8s ~ 19.2s`:
  - teacher returns to single-group

Interpretation:

- `o8` is the first successful gain-recovery run after `o6`
- it proves that the desired `{ue3, ue4}` positive split is reachable on this
  family
- but only as a single timestamp seed point so far

### O9: pair stabilization attempt

Outputs:

- `build_p3_6o9_pair_stabilization_bundle.py`
- `p3_6o9_pair_stabilization_bundle/`
- `p3_6o9_teacher_audit/`
- `p3_6o9_focus_mining/`

Critical result:

- `o9` preserved the `o8` breakthrough
- but did not extend it:
  - still only `18.7s`
  - still only one positive target scenario in the `18.7s ~ 19.2s` window

Updated bottleneck:

- we now have a real positive `{ue3, ue4}` split seed
- but not yet a trainable multi-scenario segment
- the immediate goal is no longer "find any new structure"
- it is now:
  - turn the `o8` seed point into a short stable positive segment

### O10: local smoothing did not extend the seed

Outputs:

- `build_p3_6o10_local_smoothing_bundle.py`
- `p3_6o10_local_smoothing_bundle/`
- `p3_6o10_teacher_audit/`
- `p3_6o10_focus_mining/`

Critical result:

- `18.7s` still gives:
  - `[[0, 1, 2], [3, 4]]`
  - `teacher_gain_vs_single = 0.012637245583141055`
- `18.8s ~ 19.2s` still all collapse to single-group
- `positive_segment_count = 1`
- `segment = 18.7s ~ 18.7s`

Interpretation:

- ordinary local smoothing around `o8` is not enough to create a short stable
  segment
- the `{ue3, ue4}` positive split is currently a real but very narrow local
  seed point

Current best next step:

- choose between two tight follow-ups only:
  - more aggressive timestamp-local shaping around `18.8s`
  - or accept `o8` as a single-point regime and do ultra-short-window
    learner-side validation

### O8 ultra-short-window learner validation: signal exists, bridge differs

Ran two focused learner validations on Friday, August 7, 2026:

- bundle:
  - `p3_6o8_gain_recovery_bundle/bundle`
- train end:
  - `18.6`
- test:
  - `18.7 ~ 18.7`
- focus UEs:
  - `0 1 2 3 4`
- restart seeds:
  - `7 9 11`

Outputs:

- `p3_6o8a_ultrashort_kmeans/`
- `p3_6o8b_ultrashort_membership/`

Observed utility at `18.7s`:

- no-group:
  - `0.6071841780840183`
- offline teacher:
  - `0.6198214236671593`
- `kmeans_embedding` LE-GRA:
  - `0.6071841780840183`
- `membership_order` LE-GRA:
  - `0.6198214236671593`

Key audit fact:

- both runs hit the correct weak-group candidate signature in
  `weak_group_prediction_audit.csv`:
  - teacher:
    - `3|4`
  - predicted top-k:
    - `3|4`
- but only `membership_order` converted that signal into the correct final
  multigroup split

Research meaning:

- `o8 @ 18.7s` is now confirmed as a valid single-point positive probe
- the current bottleneck is not total absence of weak-group signal
- the sharper bottleneck is the bridge from predicted weak-pair evidence to the
  final grouping decision
- this means we should treat `kmeans_embedding` vs `membership_order` as the
  main focused learner-side contrast before going back to broader teacher-side
  stabilization work

Suggested immediate next step:

- keep `o8 @ 18.7s` as the main focused probe
- inspect why k-means style final grouping collapses to no-group even when the
  correct `3|4` weak pair is already present in top-k predictions

### O8 bridge diagnosis refinement: k-means collapses to single-group

Follow-up diagnostic runs on Friday, August 7, 2026:

- `p3_6o8c_ultrashort_kmeans_diag/`
- `p3_6o8d_ultrashort_membership_diag/`

What was added:

- `run_p3_6_coupled_learner.py`
- `run_p3_6g_temporal_learner.py`

The per-scenario `teacher_imitation_diagnostics.csv` now records:

- `teacher_group_signature`
- `predicted_group_signature`
- `teacher_group_json`
- `predicted_group_json`
- `teacher_utility`
- `predicted_utility`
- `utility_gap_vs_teacher`

Critical focused result on `o8 @ 18.7s`:

- teacher:
  - `0|1|2 / 3|4`
- `membership_order` LE-GRA:
  - `3|4 / 0|1|2`
  - exact teacher-equivalent split
  - utility gap = `0.0`
- `kmeans_embedding` LE-GRA:
  - `0|1|2|3|4`
  - collapses to single-group
  - utility gap = `-0.012637245583141055`

Most important interpretation:

- this is sharper than the previous statement "the bridge differs"
- the failure mode is not:
  - "LE-GRA predicts the wrong weak pair"
- and not even:
  - "LE-GRA finds a wrong 2-group split"
- it is specifically:
  - the embedding -> k-means path fails to preserve the weak-pair structure
    strongly enough, so DP selection falls all the way back to no-group

Updated immediate next step:

- stay on `o8 @ 18.7s`
- inspect / redesign the embedding-to-grouping bridge itself
- likely directions:
  - hybrid grouping that seeds k-means from weak-pair order
  - boundary-aware clustering constraints
  - or direct weak-head-conditioned group construction

### O8 minimal hybrid bridge: immediate recovery on the single-point probe

Follow-up run on Friday, August 7, 2026:

- `p3_6o8e_ultrashort_hybrid_bridge/`

What changed:

- `le_gra_mvp.py`
  - added:
    - `membership_candidate_groups(...)`
    - `kmeans_candidate_groups(...)`
    - `best_candidate_groups(...)`
    - `best_hybrid_groups(...)`
- new grouping mode:
  - `hybrid_membership_kmeans`
- meaning:
  - generate candidate groupings from both:
    - weak-score contiguous boundary search
    - embedding k-means
  - then let the same DP utility selector choose the best candidate

Focused result on `o8 @ 18.7s`:

- `LE-GRA MVP = 0.6198214236671593`
- matches:
  - offline teacher
  - CQI
  - resource-cost
  - multi-feature
- per-scenario diagnostic:
  - teacher:
    - `0|1|2 / 3|4`
  - hybrid LE-GRA:
    - `3|4 / 0|1|2`
  - utility gap vs teacher:
    - `0.0`

Most important interpretation:

- this is the first direct evidence that a minimal bridge-level fix is already
  enough to recover the correct grouping on the `o8` single-point regime
- we did **not** change training
- we only widened the candidate grouping bridge
- so the previous `kmeans_embedding` failure was indeed a candidate-bridge
  bottleneck, not a missing weak-pair signal bottleneck

Updated immediate next step:

- do not go back to teacher-side local shaping yet
- keep `o8 @ 18.7s` as the main bridge probe
- next best follow-up is:
  - transfer check for `hybrid_membership_kmeans`
  - first on the current hard focused regimes
  - then decide whether this should become:
    - a diagnostic-only bridge
    - or the new default learner-side inference path

### P3.6p-1 / P3.6p-2: hybrid bridge transfer succeeds on both `m4b` and `m2`

Follow-up runs on Friday, August 7, 2026:

- `p3_6p1_m4b_hybrid_bridge/`
- `p3_6p2_m2_hybrid_bridge/`

Protocol:

- kept the existing successful train-side setup:
  - `joint_supervision_mode = m4b_localized_hard_negative_v1`
- changed only the inference bridge:
  - `grouping_mode = hybrid_membership_kmeans`

Focused result on `m4b`:

- test window:
  - `43.7 ~ 43.9`
- main comparison:
  - `Offline teacher = 0.5796090488051922`
  - `LE-GRA MVP = 0.5796090488051922`
- per-scenario diagnostic:
  - teacher:
    - `0|1|2|3|5 / 15|4`
  - hybrid LE-GRA:
    - `15|4 / 0|1|2|3|5`
  - pairwise / ARI / NMI:
    - all `1.0`

Focused result on `m2`:

- test window:
  - `43.8 ~ 43.9`
- main comparison:
  - `Offline teacher = 0.5796090488051922`
  - `LE-GRA MVP = 0.5796090488051922`
- per-scenario diagnostic:
  - teacher:
    - `0|1|2|3|5 / 15|4`
  - hybrid LE-GRA:
    - `15|4 / 0|1|2|3|5`
  - pairwise / ARI / NMI:
    - all `1.0`

Most important interpretation:

- the minimal hybrid bridge is not just an `o8` single-point trick
- it already transfers cleanly to:
  - the hardest current `m4b` focused regime
  - and the sibling `m2` regime
- this is now strong evidence that:
  - the current train-side supervision is already sufficient when the bridge
    exposes the right candidate set
  - the main remaining research question has shifted from
    "how do we force better weak-pair learning?"
    to
    "what inference bridge should become the project's default?"

Updated immediate next step:

- stop prioritizing more learner-loss micro-tweaks
- compare bridge candidates directly:
  - `kmeans_embedding`
  - `membership_order`
  - `hybrid_membership_kmeans`
- then decide whether `hybrid_membership_kmeans` should be promoted from:
  - focused repair
  to:
  - the new default LE-GRA inference path

### P3.6p-3: bridge comparison matrix and current regime taxonomy

Formal bridge comparison artifact added on Friday, August 7, 2026:

- `P3_6P_3_BRIDGE_COMPARISON_ZH.md`
- `p3_6p3_bridge_comparison_matrix.csv`

Purpose:

- convert the scattered focused-bridge results into a single comparison artifact
- answer the practical question:
  - is the current bottleneck still train-side supervision?
  - or is it now mainly the default inference bridge?

Matrix summary:

- `o8 @ 18.7s`:
  - teacher utility:
    - `0.6198214236671593`
  - old `kmeans_embedding` LE-GRA:
    - `0.6071841780840183`
  - `membership_order` LE-GRA:
    - `0.6198214236671593`
  - `hybrid_membership_kmeans` LE-GRA:
    - `0.6198214236671593`
- `m4b @ 43.7 ~ 43.9`:
  - teacher utility:
    - `0.5796090488051922`
  - old `kmeans_embedding` LE-GRA:
    - `0.5790831051936908`
  - `membership_order` LE-GRA:
    - `0.5796090488051922`
  - `hybrid_membership_kmeans` LE-GRA:
    - `0.5796090488051922`
- `m2 @ 43.8 ~ 43.9`:
  - teacher utility:
    - `0.5796090488051922`
  - focused old `kmeans_embedding` reference:
    - `0.5790831051936908`
  - `membership_order` LE-GRA:
    - `0.5796090488051922`
  - `hybrid_membership_kmeans` LE-GRA:
    - `0.5796090488051922`

Important interpretation:

- the cleanest single-point evidence still comes from `o8 @ 18.7s`
  - the learner already surfaces the correct weak pair
  - but old `kmeans_embedding` collapses that candidate into a worse final grouping
- `m4b` now provides cross-time evidence that:
  - train-side localized supervision is already sufficient to repair the frontier
  - but old `kmeans_embedding` still fails at the final bridge step
  - both `membership_order` and `hybrid_membership_kmeans` recover the teacher
- `m2` should currently be treated as an already-solvable sibling regime
  - it is not the strongest evidence for a hard bridge bottleneck
  - but it confirms the newer bridge does not regress there

Current regime taxonomy is now clearer:

- already-solvable:
  - `m2`
  - `n3`
- bridge-needed:
  - `o8 @ 18.7s`
  - `m4b`

Current bottleneck shift:

- we should stop behaving as if every miss is a learner-loss failure
- the main near-term decision is now:
  - should `hybrid_membership_kmeans` become the default LE-GRA inference path?

Recommended next step:

- do one minimal sanity check of `hybrid_membership_kmeans` on an
  already-solvable regime such as `n3`
- if no regression appears, promote hybrid bridge as the default path for the
  next focused learner validations
- move the main research effort toward discovering a genuinely new
  learner-hard family, rather than continuing micro-tweaks around the same old
  `m4b` plateau

### P3.6p-4: `n3` hybrid sanity check confirms no regression

Follow-up run on Friday, August 7, 2026:

- `p3_6p4_n3_hybrid_sanity/`

Protocol:

- reused the existing focused `n3` learner setup
  - `bundle = p3_6n3_isolate_ue5_bundle/bundle`
  - `focus_ue_ids = 3 4 5 6`
  - `train end = 27.8`
  - `test = 27.9 ~ 29.9`
- kept:
  - `joint_supervision_mode = none`
- changed only:
  - `grouping_mode = hybrid_membership_kmeans`

Result:

- `Offline teacher = 0.4603881335630136`
- `LE-GRA MVP = 0.4603881335630136`
- mean pairwise / ARI / NMI:
  - all `1.0`

Interpretation:

- hybrid bridge is not only a repair for bridge-needed regimes such as `o8`
  and `m4b`
- it also stays stable on an already-solvable regime
- this materially strengthens the case for treating
  `hybrid_membership_kmeans` as the candidate default inference path for the
  next focused learner validations

Updated immediate next step:

- stop spending more budget on bridge-choice uncertainty
- treat `hybrid_membership_kmeans` as the working default for the next round of
  focused learner probes
- shift the main research effort to finding a new genuinely learner-hard family
  beyond the current `m4b` / `o8` bridge-needed class

### P3.6n-9 / P3.6n-10: extending the `n5` late weak-pair segment

Formal write-up:

- `P3_6N_9_10_LATE_PAIR_SEGMENT_EXTENSION_ZH.md`

New artifacts:

- `build_p3_6n9_late_cliff_smoothing_bundle.py`
- `p3_6n9_late_cliff_smoothing_bundle/`
- `p3_6n9_teacher_audit/`
- `p3_6n9_focus_mining/`
- `build_p3_6n10_late_state_hold_bundle.py`
- `p3_6n10_late_state_hold_bundle/`
- `p3_6n10_teacher_audit/`
- `p3_6n10_focus_mining/`
- `p3_6n10a_baseline_kmeans/`
- `p3_6n10b_hybrid_bridge/`

What was tested:

- `n9`:
  - mild late-cliff smoothing after `28.4s`
  - goal:
    - see whether the short `n5` late pair can be extended with only a small
      local repair
- `n10`:
  - stronger late-state hold
  - copied the last positive `28.3s` weak-pair state into `28.4s ~ 28.8s`
  - goal:
    - first answer whether this family can support a longer teacher-positive
      segment at all

Critical `n9` result:

- no improvement over `n5`
- late positive count stayed:
  - `5 / 21`
- still only positive at:
  - `27.9 ~ 28.3`

Critical `n10` result:

- late positive count became:
  - `10 / 21`
- positive timestamps became:
  - `27.9 ~ 28.8`
- teacher split stayed stable on all 10 late positive snapshots:
  - `[[0, 3], [1, 2]]`

Most important interpretation:

- `n10` is the first successful proof that the `n5` line can be turned into a
  longer trainable late weak-pair segment
- but focused learner validation shows this new segment is still
  already-solvable:
  - old `kmeans_embedding` LE-GRA already matches the teacher
  - `hybrid_membership_kmeans` also matches, but is not required

Focused learner result on `n10`:

- bundle:
  - `p3_6n10_late_state_hold_bundle/bundle`
- focus:
  - `3 4 5 6`
- train end:
  - `27.8`
- test:
  - `27.9 ~ 28.8`
- main comparison:
  - `Offline teacher = 0.43814862226910506`
  - old `kmeans_embedding` LE-GRA = `0.43814862226910506`
  - `hybrid_membership_kmeans` LE-GRA = `0.43814862226910506`

Current status shift:

- `n10` is not the new learner-hard regime we ultimately want
- but it is now a much better source family than raw `n5`
  because it provides a controllable, longer positive pair segment

Updated immediate next step:

- stop pushing raw `n5` / `n9` local cliff tweaks
- treat `n10` as the new source family on this line
- next redesign should preserve the `27.9 ~ 28.8` pair segment while gradually
  reducing simple separability
- the target is to find the boundary where:
  - teacher still splits
  - but old `kmeans_embedding` or simple baselines begin to fail

### P3.6n-11: mild compression immediately kills the `n10` late segment

Formal write-up:

- `P3_6N_11_MILD_COMPRESSION_COLLAPSE_ZH.md`

New artifacts:

- `build_p3_6n11_state_hold_mild_compression_bundle.py`
- `p3_6n11_state_hold_mild_compression_bundle/`
- `p3_6n11_teacher_audit/`
- `p3_6n11_focus_mining/`

What changed:

- started from `n10`
- kept the successful late state-hold structure
- applied only mild simple-feature compression on `27.9 ~ 28.8`:
  - slightly raised `ue4` / `ue5` CQI
  - slightly lowered `ue3` / `ue6` CQI
  - compressed `previous_quality` gap

Critical result:

- late window `27.9 ~ 28.8`:
  - positive scenario count = `0 / 10`
  - teacher returns to single-group for all snapshots
- focus mining shows the only surviving positive segment is again just the old
  early one:
  - `25.8 ~ 27.8`

Interpretation:

- `n10` is a valid positive-segment source
- but that source is extremely fragile to even mild simple-feature compression
- this is now a clean boundary result:
  - `n10` = longer segment but still easy
  - `n11` = mild compression already kills the late segment entirely

Updated immediate next step:

- do not jump back to learner-side work on `n11`
- do not treat `n11` as a new hard regime; it is a collapse case
- the right next move on this line is an interpolation sweep around `n10`
  rather than another big discrete redesign:
  - smaller CQI uplift steps
  - smaller strong-side downshift steps
  - smaller previous-quality compression steps
- the real target is to locate the threshold where:
  - teacher still keeps the late pair
  - but old `kmeans_embedding` first stops matching

### P3.6n-12: interpolation sweep narrows the `n10 -> n11` boundary

Formal write-up:

- `P3_6N_12_INTERPOLATION_SWEEP_ZH.md`

New artifacts:

- `build_p3_6n12_interpolation_bundle.py`
- `p3_6n12a_interp_light/`
- `p3_6n12b_interp_mid/`
- `p3_6n12c_interp_uppermid/`
- `p3_6n12a_teacher_audit/`
- `p3_6n12b_teacher_audit/`
- `p3_6n12c_teacher_audit/`
- `p3_6n12a_focus_mining/`
- `p3_6n12b_focus_mining/`
- `p3_6n12c_focus_mining/`
- `p3_6n12b_kmeans_learner/`
- `p3_6n12b_hybrid_learner/`

What was tested:

- instead of one more big redesign, we interpolated between:
  - `n10` (alive)
  - `n11` (collapsed)
- three variants were checked:
  - `n12a`: light compression
  - `n12b`: mid compression
  - `n12c`: upper-mid compression

Teacher-side result:

- `n12a`:
  - late positive count = `10 / 10`
- `n12b`:
  - late positive count = `10 / 10`
- `n12c`:
  - late positive count = `0 / 10`

Interpretation:

- the collapse boundary is now much tighter:
  - `n12b` still fully alive
  - `n12c` fully dead
- so the true threshold is now approximately between:
  - `n12b -> n12c`

Focused learner result on the strongest surviving point `n12b`:

- `Offline teacher = 0.463148622269105`
- old `kmeans_embedding` LE-GRA = `0.463148622269105`
- `hybrid_membership_kmeans` LE-GRA = `0.463148622269105`

Meaning:

- even near the current collapse boundary, the surviving regime is still
  already-solvable
- the old bridge is still enough there

Updated immediate next step:

- stop treating the boundary as one-dimensional
- split the next probe by axis:
  - `previous_quality` compression only
  - CQI / strong-side compression only
- identify which axis kills the late pair first
- then refine only around that axis-specific threshold

### P3.6n-13 ~ P3.6n-16: axis split identifies the real kill switch, but
surviving regimes are still too easy

Formal write-up:

- `P3_6N_13_16_AXIS_SPLIT_AND_ASYMMETRY_ZH.md`

New artifacts:

- `p3_6n13a_prevq_only/`
- `p3_6n13b_cqi_only/`
- `p3_6n14a_weak_prevq_only/`
- `p3_6n14b_strong_prevq_only/`
- `p3_6n15a_cqi_stronger/`
- `p3_6n15b_cqi_heavy/`
- `p3_6n15c_cqi_extreme/`
- `p3_6n16a_weak_asym_light/`
- `p3_6n16b_weak_asym_mid/`
- `p3_6n16c_weak_asym_strong/`
- `p3_6n13b_kmeans_learner/`
- `p3_6n13b_hybrid_learner/`

What was learned:

- `n13a_prevq_only`:
  - late positive `0 / 10`
- `n13b_cqi_only`:
  - late positive `10 / 10`
- `n14a_weak_prevq_only`:
  - late positive `0 / 10`
- `n14b_strong_prevq_only`:
  - late positive `10 / 10`

So the real kill switch is now very clear:

- raising the weak-side `previous_quality` kills the late split
- CQI-only compression is not the first-order killer
- lowering strong-side `previous_quality` does not kill the segment

But preserving the split is still not enough:

- focused learner on `n13b_cqi_only`:
  - `Offline teacher = 0.463148622269105`
  - old `kmeans_embedding` LE-GRA = `0.463148622269105`
  - `hybrid_membership_kmeans` LE-GRA = `0.463148622269105`

This means:

- teacher-side survival and learner-side hardness are different questions
- the surviving corridor is still already-solvable for simple clustering /
  hybrid bridge inference

Additional stop-loss checks:

- `n15a/b/c` tried stronger CQI-only sweeps while keeping:
  - `weak_prevq = 1`
  - `strong_prevq = 4`
- all three collapse at the learner-test late window:
  - late positive `0 / 10`
  - `teacher_group_count = 1`
  - `teacher_gain_vs_single = 0`

- `n16a/b/c` tried weak-pair internal asymmetry to force a possible 3-group
  regime
- none of them survive the late learner-test window
- none reaches `3` groups

Updated immediate next step:

- stop doing local numeric sweeps on the same `3|4|5|6 @ gnb_2` corridor
- the next move should be structural:
  - change source family
  - or redesign a regime where the split depends on richer temporal / relational
    structure, not just a simple snapshot axis
- in particular, prioritize finding:
  - natural `3-group` families
  - bridge-like ambiguous families
  - or temporal crossover families that simple `kmeans_embedding` cannot
    already solve

### P3.6q-1: source family mining says the current repo is nearly exhausted

Formal write-ups:

- `P3_6Q_1_SOURCE_FAMILY_MINING_ZH.md`
- `P3_6Q_2_NEXT_DATASET_CRITERIA_ZH.md`

New artifacts:

- `mine_source_family_candidates.py`
- `p3_6_source_family_mining/`

Key result:

- the repo currently has only a very small set of true positive families
- after normalizing by each family's best source audit, the main families are:
  - `3|4|5|6 @ gnb_2`
  - `0|1|2|3 @ gnb_2`
  - `0|1|2|3|4 @ gnb_2`
  - `0|1|15|2|3|4|5 @ gnb_1`
  - `1|2|3|4|5|6 @ gnb_2`

Interpretation:

- `3|4|5|6 @ gnb_2` remains the richest family, but same-family local sweeps are
  already near their limit
- `0|1|2|3 @ gnb_2` already served its role as a protocol-level supervision
  proof
- `0|1|2|3|4 @ gnb_2` is a useful bridge case, but is already deeply explored
- `0|1|15|2|3|4|5 @ gnb_1` remains the hard benchmark, but its positive support
  is too short to expect a natural large-gap expansion
- `1|2|3|4|5|6 @ gnb_2` is real, but still too easy once turned into a focused
  learner holdout

Additional check:

- `p3_6m_family_bank_filtered/` was re-checked
- its high-ranking near-miss families such as:
  - `1|2|4|5 @ gnb_2`
  - `0|1|15|2|3|4 @ gnb_1`
  - `31|4|5|6|7 @ gnb_2`
  do not produce strict positive segments under focused mining

Bottom line:

- there is currently no clean, underexplored positive family in-repo that looks
  likely to create a substantially larger teacher / learner / baseline gap via
  one more local tweak round

Updated immediate next step:

- stop treating the next move as "find one more hidden family in the current
  repo"
- the next meaningful step should be new data generation / new source-family
  construction with explicit criteria:
  - longer positive windows
  - natural `3-group` or `2-vs-3-group` structure
  - temporal crossover
  - history-sensitive decoys
  - preserved cross-traffic interaction

### P3.6q-3: first structural three-group ladder prototype still collapses

Formal write-up:

- `P3_6Q_3_THREE_GROUP_LADDER_FAILURE_ZH.md`

New artifacts:

- `build_p3_6q3_three_group_ladder_bundle.py`
- `p3_6q3_three_group_ladder_bundle/`
- `p3_6q3_teacher_audit/`

What was tried:

- start from `p3_6n10_late_state_hold_bundle`
- keep the same cross-traffic context
- impose a minimal:
  - strong / boundary / weak ladder
  - plus a late `ue5` / `ue6` temporal crossover

Goal:

- create the first natural `2-group / 3-group` boundary candidate inside the
  familiar `3|4|5|6 @ gnb_2` family

Result:

- on the true late target window `27.9s ~ 28.8s`:
  - `multi_group_count = 0`
  - `positive_gain_count = 0`
  - `max_teacher_group_count = 1`
- no `3-group` case appears

Interpretation:

- manually arranging a local three-subgroup ladder inside the existing family is
  still not enough
- the teacher seems to depend on deeper resource-interaction structure than a
  target-family-only ladder can provide

Updated immediate next step:

- deprioritize more hand-crafted ladder sweeps on the same family
- move toward:
  - new raw source families
  - or a stronger data-generation pipeline that explicitly rebuilds the
    cross-traffic / contention structure required for multi-group gain

### P3.6q-4 ~ q-8: declarative structural bridge line produced a real teacher-side extension

Formal write-up:

- `P3_6Q_4_TO_Q8_STRUCTURAL_BRIDGE_PROGRESS_ZH.md`

New artifacts:

- `build_family_window_transform_bundle.py`
- `p3_6q6_family_transform_spec_template.json`
- `p3_6q6_three_phase_ladder_spec.json`
- `p3_6q7_extend_mid_split_spec.json`
- `p3_6q8_bridge_window_nudge_spec.json`
- `p3_6q6_three_phase_ladder_bundle/`
- `p3_6q7_extend_mid_split_bundle/`
- `p3_6q8_bridge_window_nudge_bundle/`
- `p3_6q6_teacher_audit/`
- `p3_6q7_teacher_audit/`
- `p3_6q8_teacher_audit/`
- `p3_6q8_kmeans_learner/`
- `p3_6q8_hybrid_learner/`

What changed:

- instead of one-off local bundle builders, `q6+` introduced a reusable
  declarative family-window transform scaffold
- the target family is still `3|4|5|6 @ gnb_2`
- but the design goal changed from "force a 3-group ladder immediately" to:
  - first stabilize a longer positive temporal bridge
  - then test whether that bridge is learner-hard or only teacher-stable

Key teacher-side results:

- `q6` produced the first real two-phase positive family on `3|4|5|6 @ gnb_2`
  - `25.8, 26.2`: `[[0,1,3],[2]]` => isolate `ue5`
  - `27.1 ~ 27.3`: `[[0,2,3],[1]]` => isolate `ue4`
  - this proved the same family can support temporal weak-identity crossover

- `q7` showed that naive extension does not move the `27.4+` cliff

- `q8` is the first real bridge-window success
  - it preserved the early `ue5` positive phase
  - and extended the later `ue4`-isolation phase from:
    - `27.1 ~ 27.3`
    to
    - `27.1 ~ 27.6`
  - teacher gains stay:
    - `0.09440267226723498` for the `ue5` phase
    - `0.044402672267235155` for the `ue4` phase

Interpretation:

- this is the clearest proof so far that teacher-positive survival can be
  extended by localized structural bridge design
- however, teacher-side survival and learner-side hardness are still different
  questions

Focused learner result on `q8`:

- focused regime:
  - family `3|4|5|6`
  - train end = `27.3`
  - test = `27.4 ~ 27.6`

- both:
  - `p3_6q8_kmeans_learner/`
  - `p3_6q8_hybrid_learner/`
  end with the same outcome:
  - `No grouping` = `0.6471841780840183`
  - `CQI k-means` = `0.6767859595955085`
  - `Resource-cost k-means` = `0.6915868503512534`
  - `Multi-feature k-means` = `0.6915868503512534`
  - `Offline teacher` = `0.6915868503512534`
  - `LE-GRA MVP` = `0.6915868503512534`
  - pairwise / ARI / NMI = `1.0`

Bottom line:

- `q8` is a real teacher-side extension breakthrough
- but it is still learner-easy
- so "make the positive window longer" is not enough by itself to enlarge the
  teacher / learner / baseline gap

Updated immediate next step:

- move to a `q9`-style decoy bridge design
- keep the teacher-positive `ue4`-isolation alive if possible
- but introduce stronger conflicting cues on `ue5/ue6` so that:
  - the teacher still prefers the true weak split
  - while snapshot-driven baselines are more likely to follow the wrong weak
    identity or boundary

### P3.6q-9: lightweight decoy bridge extension is a clean stop-loss

Formal write-up:

- `P3_6Q_9_DECOY_BRIDGE_EXTENSION_FAILURE_ZH.md`

New artifacts:

- `p3_6q9_decoy_bridge_extension_spec.json`
- `p3_6q9_decoy_bridge_extension_bundle/`
- `p3_6q9_teacher_audit/`
- `p3_6q9_focus_mining/`
- `p3_6q9_kmeans_learner/`
- `p3_6q9_hybrid_learner/`

What was tried:

- keep the successful `q8` bridge
- then modify `27.7+` into a decoy regime:
  - `ue4` remains the intended true weak side via low `previous_quality`
  - `ue5` is made more decoy-like with stronger snapshot weakness but stronger
    history
  - `ue6` stays moderately weak

Goal:

- either extend the `ue4`-isolation positive corridor beyond `27.6`
- or make the surviving `27.4 ~ 27.6` bridge more learner-hard

Teacher result:

- no improvement over `q8`
- positive snapshots remain exactly:
  - `25.8, 26.2`: `[[0,1,3],[2]]` => isolate `ue5`
  - `27.1 ~ 27.6`: `[[0,2,3],[1]]` => isolate `ue4`
- nothing survives at `27.7+`

Focused learner result:

- same focused regime as `q8`:
  - family `3|4|5|6`
  - train end = `27.3`
  - test = `27.4 ~ 27.6`

- both:
  - `p3_6q9_kmeans_learner/`
  - `p3_6q9_hybrid_learner/`
  still fully match the teacher:
  - `Resource-cost k-means` = `0.6915868503512534`
  - `Multi-feature k-means` = `0.6915868503512534`
  - `Offline teacher` = `0.6915868503512534`
  - `LE-GRA MVP` = `0.6915868503512534`
  - pairwise / ARI / NMI = `1.0`

Interpretation:

- lightweight local decoys on this family are now a clean stop-loss
- they neither:
  - extend the teacher-positive cliff
  - nor create learner-hard ambiguity

Bottom line:

- do not continue same-family small decoy sweeps on `3|4|5|6 @ gnb_2`
- the next meaningful step should be a stronger structure-level redesign or a
  new source family, not another mild local `ue4/ue5/ue6` adjustment

### P3.6q-10: six-user transition pivot is the first real bridge-needed breakthrough in this line

Formal write-up:

- `P3_6Q_10_SIX_USER_TRANSITION_BREAKTHROUGH_ZH.md`

New artifacts:

- `p3_6q10_six_user_transition_extension_spec.json`
- `p3_6q10_six_user_transition_extension_bundle/`
- `p3_6q10_teacher_audit/`
- `p3_6q10_focus_mining/`
- `p3_6q10_kmeans_learner/`
- `p3_6q10_hybrid_learner/`
- `p3_6q10_membership_order_learner/`

Why this pivot was made:

- after `q8/q9`, the `3|4|5|6 @ gnb_2` family was clearly teacher-extendable
  but still learner-easy
- `1|2|3|4|5|6 @ gnb_2` under `rb_028` already contained a natural:
  - `ue2` singleton weak phase
  - followed by `{ue2, ue6}` dual-weak phase
- that made it a better candidate for a true bridge-needed regime

Teacher-side result:

- `q10` successfully extends the positive dual-weak corridor:
  - `27.3`: `[[0,2,3,4,5],[1]]` => isolate `ue2`
    - gain = `0.060380914957876564`
  - `27.4 ~ 27.6`: `[[0,2,3,4],[1,5]]` => weak group `{ue2, ue6}`
    - gain = `0.16083185759435376`
  - `27.7 ~ 28.2`: same `{ue2, ue6}` split remains positive
    - gain = `0.03190558516756159`

Interpretation:

- this is not just a longer positive window
- it is the first clear sustained dual-weak regime in this line that remains
  alive past the original collapse point

Focused learner result:

- focused setup:
  - family `1|2|3|4|5|6`
  - train end = `27.6`
  - test = `27.7 ~ 28.2`

- plain `kmeans_embedding` run:
  - `Offline teacher` = `0.6457564299182464`
  - `LE-GRA MVP` = `0.6244860398065387`
  - `Resource-cost k-means` = `0.6298036373344656`
  - `Multi-feature k-means` = `0.6138508447506849`

- `hybrid_membership_kmeans` run:
  - `Offline teacher` = `0.6457564299182464`
  - `LE-GRA MVP` = `0.6457564299182464`

- `membership_order` run:
  - `Offline teacher` = `0.6457564299182464`
  - `LE-GRA MVP` = `0.6457564299182464`

Key conclusion:

- this is the first focused regime in the recent `q` line where:
  - teacher clearly beats plain clustering baselines
  - plain LE-GRA also misses the teacher
  - but membership-aware bridge inference can recover the full teacher utility

This means:

- the bottleneck is no longer "can we make the teacher split?"
- and not merely "can we extend the positive window?"
- the key distinction is now:
  - snapshot / clustering path fails
  - membership-aware inference path succeeds

Updated immediate next step:

- stay on `q10`
- do focused mechanism study instead of family search:
  - inspect why `membership_order` already succeeds
  - compare it against the plain `kmeans_embedding` failure path
  - audit weak-group prediction / candidate ranking on the late `{ue2, ue6}`
    regime
  - then decide whether to scale `q10` into a larger ablation / robustness
    result

### P3.6q-11: q10 mechanism study shows the decisive factor is candidate routing, not extra k-means refinement

Formal write-up:

- `P3_6Q_11_Q10_MECHANISM_STUDY_ZH.md`

New artifact:

- `p3_6q10_test_window_candidate_path_comparison.csv`

Key finding 1:

- plain `kmeans_embedding` does not fail uniformly
- on the `27.7 ~ 28.2` test window it:
  - collapses to single-group for the first 4 snapshots
  - only matches the teacher on the last 2 snapshots
- that is why its final LE-GRA utility stays at:
  - `0.6244860398065387`
  instead of the teacher's:
  - `0.6457564299182464`

Key finding 2:

- the failure starts at candidate discovery, not only at final grouping
- for every test snapshot, the teacher candidate is:
  - `2|6`
- but plain `kmeans_embedding` predicts:
  - `3|1`
  - or `3|5`
- so it is following the wrong weak-candidate path before the final split stage

Key finding 3:

- both:
  - `membership_order`
  - `hybrid_membership_kmeans`
  predict the correct late candidate:
  - `2|6`
  on every test snapshot
- both also exactly match the teacher utility:
  - `0.6457564299182464`

Interpretation:

- the decisive mechanism in `q10` is membership-aware candidate routing
- not additional embedding k-means refinement
- on this regime, `hybrid` is effectively behaving like a successful
  membership-aware bridge path, rather than showing extra gains beyond
  `membership_order`

Updated immediate next step:

- keep `q10` as the main focused regime
- the best next research move is now:
  - localized supervision study for plain `kmeans_embedding`
  - to see whether train-side guidance can push it from the wrong
    `3|1 / 3|5` decoy path toward the true `2|6` path
- only after that should we consider a small robustness / reporting sweep

### P3.6q-12: localized supervision can recover q10 exactly, but robustness under a shifted boundary is still weak

Formal write-up:

- `P3_6Q_12_LOCALIZED_SUPERVISION_AND_BOUNDARY_ROBUSTNESS_ZH.md`

New artifacts:

- `p3_6q10_kmeans_candidate_bce/`
- `p3_6q10_kmeans_candidate_boundary/`
- `p3_6q10_kmeans_candidate_boundary_frontier/`
- `p3_6q10_kmeans_candidate_boundary_frontier_275/`

What was tried:

- keep the same focused `q10` regime:
  - family `1|2|3|4|5|6`
  - main train end = `27.6`
  - main test = `27.7 ~ 28.2`
- then progressively add localized supervision to plain
  `kmeans_embedding`:
  - candidate-membership BCE only
  - candidate BCE + teacher-boundary pairs
  - candidate BCE + teacher-boundary pairs + frontier contrast

Main result:

- candidate BCE only:
  - `LE-GRA MVP = 0.6244860398065387`
  - no improvement
- candidate BCE + boundary pairs:
  - `LE-GRA MVP = 0.6244860398065387`
  - still no improvement
- candidate BCE + boundary pairs + frontier contrast:
  - `Offline teacher = 0.6457564299182464`
  - `LE-GRA MVP = 0.6457564299182464`

Mechanism confirmation:

- on `p3_6q10_kmeans_candidate_boundary_frontier/`
  - `weak_group_prediction_audit.csv` shows:
    - `27.7 ~ 28.2` predicted top-k is `2|6` for all 6 test snapshots
  - `teacher_imitation_diagnostics.csv` shows:
    - pairwise / ARI / NMI = `1.0` for all 6 test snapshots

Interpretation:

- this is the first clean proof in the recent `q` line that:
  - plain `kmeans_embedding` can be repaired by train-side localized
    supervision
  - but only when three hooks are combined:
    - boundary-aware pair sampling
    - candidate-conditioned weak-group supervision
    - frontier hard-negative contrast
- candidate BCE alone and candidate+boundary alone are both insufficient

Robustness check:

- shifted the boundary one step earlier:
  - train end = `27.5`
  - test = `27.6 ~ 28.2`
- run:
  - `p3_6q10_kmeans_candidate_boundary_frontier_275/`
- result:
  - `Offline teacher = 0.6368533564947124`
  - `LE-GRA MVP = 0.6186215935418201`
  - teacher gap = `-0.0182317629528923`

Important nuance from diagnostics:

- the model still predicts the correct weak candidate:
  - `2|6` on all `27.6 ~ 28.2` test snapshots
- but final grouping is unstable:
  - exact teacher match at `27.6`
  - collapse to single-group for `27.7 ~ 28.0`
  - recovery again at `28.1 ~ 28.2`

Key updated conclusion:

- `q10` has now split the bottleneck into two layers:
  - candidate-path recovery
  - final grouping stabilization
- the first one is now solvable with localized joint supervision
- the second one is still not robust under a small boundary shift

Updated immediate next step:

- stay on `q10`
- do not go back to isolated micro-sweeps
- the best next move is now:
  - localized group-construction stabilization after the candidate is already
    correct
  - or boundary-neighborhood replay/support design around `27.6 ~ 28.0`
- this should be treated as a transfer / grouping-stability problem now, not
  a candidate-discovery problem

### P3.6q-13: candidate-anchored grouping fixes the remaining q10 boundary-shift failure

Formal write-up:

- `P3_6Q_13_CANDIDATE_ANCHORED_GROUPING_RECOVERY_ZH.md`

Code change:

- added a new inference-only grouping mode in `le_gra_mvp.py`:
  - `candidate_anchor_hybrid`
- new helpers:
  - `anchored_candidate_groups(...)`
  - `best_candidate_anchor_hybrid_groups(...)`

Why this was tried:

- `q12` showed that after frontier supervision:
  - the learner already predicts the correct weak candidate `2|6`
  - but final grouping still collapses under the shifted boundary
- so the remaining bottleneck was no longer candidate discovery
- it was candidate-to-grouping transfer

Idea:

- anchor the top weak-score candidates as one explicit group
- partition only the remaining users with embedding k-means
- union these anchored candidates with the plain k-means candidates
- let the same DP selector choose the best final grouping

Focused validation:

- run:
  - `p3_6q10_candidate_anchor_hybrid_275/`
- same train/test regime as the failing `q12` shifted-boundary run:
  - train end = `27.5`
  - test = `27.6 ~ 28.2`
- same supervision settings as `p3_6q10_kmeans_candidate_boundary_frontier_275/`
- only changed:
  - `grouping_mode = candidate_anchor_hybrid`

Result:

- `Offline teacher = 0.6368533564947124`
- `LE-GRA MVP = 0.6368533564947124`

Diagnostics:

- `teacher_imitation_diagnostics.csv`:
  - pairwise / ARI / NMI = `1.0` on all 7 test snapshots
- `weak_group_prediction_audit.csv`:
  - predicted top-k remains `2|6` on all test snapshots

Interpretation:

- this confirms the `q12` diagnosis exactly:
  - candidate recovery was already solved
  - the remaining issue was final grouping stabilization
- a small candidate-anchored grouping bridge is enough to remove the
  `27.7 ~ 28.0` collapse and restore full teacher match

New most accurate conclusion for `q10`:

- the main successful path is now clearly two-stage:
  - localized supervision repairs weak-candidate routing
  - candidate-anchored grouping repairs candidate-to-split transfer

Updated immediate next step:

- do not go back to random family search yet
- the most valuable follow-up is now:
  - test whether `candidate_anchor_hybrid` only works when the candidate path
    is already correct
  - or whether it can partially rescue weaker pre-frontier models too
- this should be framed as a clean ablation on the separation between:
  - candidate discovery
  - final group construction

### P3.6q-14: same-seed focused ablation shows the q10 gain is conditional, not universal

Formal write-up:

- `P3_6Q_14_Q10_FOCUSED_ABLATION_MATRIX_ZH.md`

Artifact:

- `p3_6q10_focused_ablation_matrix.csv`

Why this was necessary:

- the first `q13` reading was directionally right but still confounded by
  unrestricted restart selection
- plain `candidate_anchor_hybrid` had matched teacher in one unrestricted run
  because it selected restart seed `11`
- so we needed to compare plain/localized and kmeans/anchored grouping under
  the same restart seeds

Controlled result matrix:

- seed `9`
  - plain `kmeans_embedding`: fail (`0.6186`)
  - plain `candidate_anchor_hybrid`: fail (`0.6186`)
  - localized `kmeans_embedding`: fail (`0.6186`)
  - localized `candidate_anchor_hybrid`: success (`0.6369`)
- seed `11`
  - plain `kmeans_embedding`: success (`0.6369`)
  - plain `candidate_anchor_hybrid`: success (`0.6369`)
  - localized `kmeans_embedding`: success (`0.6369`)
  - localized `candidate_anchor_hybrid`: success (`0.6369`)

Most accurate interpretation now:

- `candidate_anchor_hybrid` is not a universal improvement
- it does **not** rescue the failing plain seed-9 path
- its real value is narrower and more precise:
  - it repairs the failing localized-supervision + seed-9 path after plain
    final grouping still collapses
- seed `11` is a naturally good basin where plain k-means already reaches the
  teacher

So the current `q10` bottleneck should now be described as two-layer:

1. basin / optimization sensitivity across restart seeds
2. final group-construction sensitivity inside a partially repaired basin

This means we should stop interpreting every gain as a generic grouping-mode
win. The cleaner research question is now:

- why does seed `11` already land in a teacher-aligned basin?
- why does seed `9` still need the candidate-anchored grouping bridge after
  localized supervision?

Updated immediate next step:

- do not expand to larger matrices yet
- first run `q10` basin diagnostics:
  - compare seed `9` vs seed `11`
  - inspect support-train and focus-test candidate paths, split evidence, and
    any embedding/grouping signatures that explain why one basin is easy and
    the other is not
- after that, if the mechanism stays consistent, do a small controlled
  robustness sweep around the shifted boundary with fixed seeds

### P3.6q-15: q10 basin diagnostics show the real selector bottleneck

Formal write-up:

- `P3_6Q_15_SEED_BASIN_DIAGNOSTICS_ZH.md`

Artifact:

- `p3_6q10_seed_basin_focus_test_comparison.csv`

Most important findings:

- the currently selected plain seed `9` is not the only viable basin
- forced plain seed `11` matches teacher on all 7 focus-test snapshots
- more importantly, the original selector chose seed `9` because it had the
  best support imitation metrics
- but seed `9` had the worst weak-margin and prototype-separation margins
- seed `11` had slightly lower support pairwise/ARI/NMI, yet generalized much
  better to the shifted boundary

This sharpened the diagnosis:

- the prototype does not only have learner/grouping bottlenecks
- it also has a restart-selection bottleneck

### P3.6q-16: minimal margin-aware restart selection recovers q10 without changing the learner

Formal write-up:

- `P3_6Q_16_MARGIN_AWARE_RESTART_SELECTION_ZH.md`

Code change:

- `run_p3_6g_temporal_learner.py`
  - added `--restart-selection-mode`
  - modes:
    - `support_imitation` (old default behavior)
    - `margin_aware` (experimental)

Experimental result A: plain q10 shifted-boundary

- artifact:
  - `p3_6q10_plain_baseline_275_margin_selector/`
- selected restart seed:
  - `11`
- result:
  - `LE-GRA MVP = Offline teacher = 0.6368533564947124`

Experimental result B: localized q10 shifted-boundary

- artifact:
  - `p3_6q10_kmeans_candidate_boundary_frontier_275_margin_selector/`
- selected restart seed:
  - `7`
- result:
  - `LE-GRA MVP = Offline teacher = 0.6368533564947124`

What this means:

- on `q10`, a large part of the apparent learner failure was actually selector
  failure
- we now have evidence that multiple teacher-matching basins exist
- the old selector was ranking them below a more imitation-looking but less
  robust basin

Updated best current interpretation of q10:

1. restart selector chooses the basin
2. learner/supervision shapes the representation inside that basin
3. grouping construction determines whether the final split transfers cleanly

Updated immediate next step:

- do **not** switch the whole project default to `margin_aware` yet
- first run a tiny transfer check on a few representative regimes:
  - `q10` (already positive)
  - `o8`
  - `m4b`
  - one easy regime such as `n3`
- the question is no longer "does margin-aware help q10?"
- it is:
  - does margin-aware systematically find better basins?
  - or is q10 a special case?

### P3.6q-17: margin-aware selector helps q10, stays neutral on n3, changes m4b, but does not fix o8

Formal write-up:

- `P3_6Q_17_MARGIN_SELECTOR_TRANSFER_CHECK_ZH.md`

Transfer-check artifacts:

- `p3_6q16_n3_margin_selector/`
- `p3_6q16_o8_margin_selector/`
- `p3_6q16_m4b_margin_selector/`

Representative transfer results:

- `n3` easy regime:
  - selected restart seed stays `7`
  - `LE-GRA MVP = Offline teacher = 0.4603881335630136`
  - interpretation:
    - no regression
    - margin-aware selector is at least neutral on an already-solvable regime
- `o8` bridge-needed short regime:
  - selected restart seed stays `7`
  - `LE-GRA MVP = 0.6071841780840183`
  - `Offline teacher = 0.6198214236671593`
  - interpretation:
    - selector does not move the basin
    - `o8` remains an inference/grouping-path bottleneck, not a selector bottleneck
- `m4b` hard dual-weak regime:
  - selected restart seed changes to `11`
  - `LE-GRA MVP = 0.5790831051936908`
  - `Offline teacher = 0.5796090488051922`
  - interpretation:
    - selector does change the basin
    - but changing the basin alone is still not enough to fully solve `m4b`
- `q10` shifted-boundary regime:
  - selected restart seed changes from `9` to `11`
  - `LE-GRA MVP = Offline teacher = 0.6368533564947124`
  - interpretation:
    - `q10` is a genuine selector-dominated failure mode

Updated regime taxonomy after `q17`:

1. selector-dominated failures
   - current best example: `q10`
   - hidden good basins already exist, but the old selector ranks them too low
2. partially selector-sensitive but still structural failures
   - current best example: `m4b`
   - better basin choice helps, but learner/grouping bottlenecks remain
3. non-selector failures
   - current best example: `o8`
   - changing the selector does not help because the failure is downstream

Most important interpretation change:

- `margin_aware` is a real research lever, but not a universal fix
- we should keep it as an experimental axis, not silently flip the project default
- future focused runs should explicitly compare:
  - `support_imitation`
  - `margin_aware`

Updated immediate next step:

- stop treating all hard regimes as one undifferentiated bucket
- first separate them into:
  - selector-sensitive regimes
  - post-selector structural regimes
- for the next focused experiment:
  - use `m4b` as the best post-selector structural target
  - keep `q10` as the selector-dominated reference case

### P3.6q-18: `m4b` is now clearly a post-selector structural failure, not a candidate-recovery failure

Formal write-up:

- `P3_6Q_18_M4B_POST_SELECTOR_PLATEAU_ZH.md`

Artifact:

- `p3_6q18_m4b_post_selector_summary.csv`

Most important findings:

- under `margin_aware`, `m4b` does switch to a better basin:
  - selected restart seed becomes `11`
- but the support-train imitation metrics are already saturated for all three seeds:
  - support pairwise accuracy = `1.0`
  - support ARI = `1.0`
  - support NMI = `1.0`
- the selector difference only comes from margin quality:
  - seed `11` has the best weak margins

Even more important:

- on the focus test window `43.7s ~ 43.9s`, the learner already recovers the
  correct weak candidate path:
  - teacher candidate signature = `15|4`
  - predicted top-k signature = `15|4`
  - teacher secondary UE `4` appears at predicted rank `2`

So the remaining failure is now precise:

- teacher grouping:
  - `0|1|2|3|5 / 15|4`
- predicted grouping:
  - `0|1|2|3|4|5 / 15`

Interpretation:

- `m4b` is no longer best described as a selector bottleneck
- it is also not a weak-candidate discovery bottleneck
- it is a **secondary weak UE extraction failure at the final grouping step**
- specifically:
  - `ue15` is extracted
  - `ue4` is still absorbed back into the strong group

Why this matters:

- `q10` and `m4b` now cleanly separate:
  - `q10`: selector-dominated failure
  - `m4b`: post-selector structural failure
- this means further progress on `m4b` should stop targeting:
  - selector-only tweaks
  - replay-only tweaks
  - top-k candidate calibration-only tweaks

Updated immediate next step:

- do a minimal post-selector structural probe for `m4b`
- the best target is not "recover the weak candidate"
- it is:
  - keep the secondary weak UE from being re-absorbed during final grouping
- in practice, this suggests:
  - secondary-anchor closure at inference/grouping time
  - or train-side boundary retention specifically for the secondary weak UE

### P3.6q-19: minimal secondary-anchor closure fully solves `m4b`

Formal write-up:

- `P3_6Q_19_M4B_SECONDARY_ANCHOR_CLOSURE_SUCCESS_ZH.md`

Artifact:

- `p3_6q19_m4b_anchor_closure_summary.csv`
- run directory:
  - `p3_6q19_m4b_candidate_anchor_margin_selector/`

Focused result:

- configuration:
  - `restart_selection_mode = margin_aware`
  - `grouping_mode = candidate_anchor_hybrid`
- selected restart seed:
  - `11`
- final utility:
  - `LE-GRA MVP = Offline teacher = 0.5796090488051922`

Most important diagnostics:

- on the focus test window `43.7s ~ 43.9s`, the weak candidate path remains:
  - teacher candidate signature = `15|4`
  - predicted top-k signature = `15|4`
- the decisive change is in the final grouping:
  - previous `margin_aware + kmeans_embedding`:
    - `0|1|2|3|4|5 / 15`
  - current `margin_aware + candidate_anchor_hybrid`:
    - `15|4 / 0|1|2|3|5`
  - which is teacher-equivalent

Why this matters:

- `P3.6q-18` diagnosed `m4b` as a secondary weak UE extraction failure
- `P3.6q-19` now directly validates that diagnosis
- once the candidate path is already correct, a minimal anchor-preserving
  grouping bridge is enough to close the final gap

Updated research interpretation:

- `q10` and `m4b` now form a clean two-stage story:
  1. `q10`:
     - selector-dominated failure
  2. `m4b`:
     - post-selector weak-closure failure
- this means the prototype now has evidence for two distinct but real levers:
  - selector quality
  - secondary-anchor-preserving grouping closure

Updated immediate next step:

- do not immediately assume `candidate_anchor_hybrid + margin_aware` is
  universal
- first do a small transfer check on a regime where candidate recovery is still
  not guaranteed, especially `o8`
- the key hypothesis to test is:
  - anchor closure helps when weak top-k is already correct
  - it should help much less when candidate discovery itself is still wrong

### P3.6q-20: `o8` is also recoverable by anchor-preserving closure, and the real failure was LE-GRA's grouping path

Formal write-up:

- `P3_6Q_20_O8_GROUPING_PATH_RECOVERY_ZH.md`

Artifact:

- `p3_6q20_o8_grouping_path_summary.csv`
- run directory:
  - `p3_6q20_o8_anchor_closure_margin_selector/`

Key comparison:

- old run:
  - `p3_6q16_o8_margin_selector/`
  - `restart_selection_mode = margin_aware`
  - `grouping_mode = kmeans_embedding`
  - selected restart seed = `7`
  - `Offline teacher = 0.6198214236671593`
  - `Multi-feature k-means = 0.6198214236671593`
  - `LE-GRA MVP = 0.6071841780840183`
- new run:
  - `p3_6q20_o8_anchor_closure_margin_selector/`
  - `restart_selection_mode = margin_aware`
  - `grouping_mode = candidate_anchor_hybrid`
  - selected restart seed still = `7`
  - `Offline teacher = 0.6198214236671593`
  - `LE-GRA MVP = 0.6198214236671593`

Most important diagnostics:

- this is not a basin-change story:
  - selected seed stays `7`
- it is not a representation-discovery story either:
  - even in the old run, `Multi-feature k-means` already matched teacher
- the failure was specifically in LE-GRA's own grouping path:
  - old LE-GRA grouping:
    - `0|1|2|3|4`
  - teacher grouping:
    - `0|1|2 / 3|4`
  - new anchor-preserving LE-GRA grouping:
    - `3|4 / 0|1|2`

This sharpens the interpretation of `o8`:

- `o8` is not selector-dominated
- `o8` is not learner-representation-dominated
- it is a **LE-GRA-specific grouping-path failure**

Updated cross-regime picture:

1. `q10`
   - selector-dominated failure
2. `m4b`
   - post-selector secondary weak-closure failure
3. `o8`
   - LE-GRA-specific grouping-path failure

Higher-level synthesis:

- both `m4b` and `o8` now support the same broader claim:
  - once the weak candidate path is already correct,
  - anchor-preserving grouping closure becomes a powerful last-mile fix

Updated immediate next step:

- stop assuming every remaining hard regime needs new learner-side supervision
- first build a small regime checklist / decision rule:
  - is the bottleneck selector?
  - is the weak candidate path already correct?
  - is the failure only in final grouping?
- then use that checklist to decide whether to try:
  - `margin_aware`
  - `candidate_anchor_hybrid`
  - or both

### P3.6q-21: hard-regime decision checklist is now explicit

Formal write-up:

- `P3_6Q_21_REGIME_DECISION_CHECKLIST_ZH.md`

Artifact:

- `p3_6q21_regime_decision_checklist.csv`

Purpose:

- stop treating every teacher gap as the same kind of failure
- reduce wasted sweeps by asking three questions first:
  1. is this selector-dominated?
  2. is the weak candidate path already recovered?
  3. is the remaining gap only in final grouping?

Current representative mapping:

- `q10`
  - selector-sensitive = yes
  - weak top-k recovered = yes
  - first probe = `margin_aware`
- `m4b`
  - selector-sensitive = yes
  - weak top-k recovered = yes
  - final gap = secondary weak closure
  - first probe = `margin_aware + candidate_anchor_hybrid`
- `o8`
  - selector-sensitive = no
  - weak top-k recovered = yes
  - multi-feature k-means already matches teacher
  - LE-GRA-only grouping path still fails
  - first probe = `candidate_anchor_hybrid`

Why this matters:

- this checklist now encodes the main research lesson from the latest round:
  - first diagnose whether the failure is basin selection, candidate recovery,
    or final grouping closure
  - then choose the smallest intervention that matches that failure mode

### P3.6q-22: hard-regime-only comparison matrix makes the real gaps visible

Artifacts:

- `p3_6q22_hard_regime_only_matrix.csv`
- `hard_regime_report_zh.html`

Purpose:

- answer the recurring concern that "the methods still do not look that far apart"
- stop averaging away the interesting parts by isolating only the most
  informative hard regimes:
  - `q10`
  - `m4b`
  - `o8`

Most important synthesis:

- on `q10`, the real gain is selector-side:
  - old LE-GRA path = `0.6186215935418201`
  - best LE-GRA = teacher match `0.6368533564947124`
  - interpretation:
    - the main improvement comes from choosing the right basin
- on `m4b`, the utility gap is numerically small but structurally important:
  - old LE-GRA path = `0.5790831051936908`
  - best LE-GRA = teacher match `0.5796090488051922`
  - interpretation:
    - the visible utility gap is tiny
    - but the grouping difference is exactly whether `ue4` stays with weak
      anchor `ue15`
- on `o8`, the main story is not representation quality but LE-GRA's own
  grouping path:
  - old LE-GRA path = `0.6071841780840183`
  - best LE-GRA = teacher match `0.6198214236671593`
  - interpretation:
    - plain multi-feature k-means was already correct
    - the old LE-GRA grouping path alone was the failure

Why this matrix matters:

- it makes clear that many of the real differences are concentrated in:
  - short transition windows
  - weak-pair recovery
  - final grouping closure
- therefore:
  - utility-only whole-dataset averages understate the current research gains
  - structural metrics and group signatures are now essential, not optional

Updated immediate next step:

- use the hard-regime-only matrix as the reporting backbone for the current
  research story
- then choose the next focused regime by applying the `q21` checklist first,
  instead of expanding generic sweeps

### P3.6q-23 / q-24: new dual-boundary temporal crossover regime found, and it is the best next benchmark candidate

Formal write-ups:

- `P3_6Q_23_NEXT_TARGETED_REGIME_ZH.md`
- `P3_6Q_24_DUAL_BOUNDARY_CROSSOVER_REGIME_ZH.md`

Artifacts:

- spec:
  - `p3_6q23_dual_boundary_crossover_spec.json`
- bundle:
  - `p3_6q23_dual_boundary_crossover_bundle/`
- teacher audit:
  - `p3_6q23_teacher_audit/`
- learner probes:
  - `p3_6q24_dual_boundary_crossover_temporal_probe/`
  - `p3_6q24_dual_boundary_crossover_anchor_probe/`
- summary:
  - `p3_6q24_dual_boundary_crossover_summary.csv`

What was built:

- new source family target:
  - `3|4|5|6 @ gnb_2`
- new regime structure:
  - persistent weak anchor `ue4`
  - early secondary weak candidate `ue5`
  - late secondary weak candidate `ue6`
  - strong anchor `ue3`
- design goal:
  - create a teacher-positive temporal crossover where the weak-side partner of
    `ue4` changes over time

Teacher-side result:

- positive gain count = `19`
- positive segment count = `2`
- segment 1:
  - `25.8s ~ 27.0s`
  - length `13`
  - teacher split = `3|6 / 4|5`
- segment 2:
  - `28.3s ~ 28.8s`
  - length `6`
  - teacher split = `3|5 / 4|6`

Why this matters:

- this is not a single-point bridge case
- it is also not just a fixed weak-pair regime
- it is the first new regime in the latest round that shows:
  - stable positive corridors
  - a true secondary weak-role switch
  - enough temporal support to serve as a stronger benchmark candidate

Focused learner probe:

- train:
  - `<= 27.0`
- test:
  - `28.3 ~ 28.8`
- plain probe artifact:
  - `p3_6q24_dual_boundary_crossover_temporal_probe/`

Most important result:

- `No grouping = 0.5721841780840183`
- `Multi-feature k-means = 0.5721841780840183`
- `Offline teacher = 0.5790955890522329`
- plain `LE-GRA MVP = 0.5779436872241971`

Interpretation:

- plain baselines fail cleanly:
  - `Multi-feature k-means` collapses to single-group on all 6 late test
    snapshots
- plain `LE-GRA` is already close:
  - it matches teacher on `28.4 ~ 28.8`
  - but still fails exactly at the earliest crossover boundary `28.3`

This is the key breakthrough:

- the new regime is not too easy
- it is not completely hopeless either
- it lands in a very valuable middle zone:
  - plain baselines fail hard
  - LE-GRA partially generalizes
  - one boundary snapshot still exposes the remaining weakness

Additional bridge check:

- artifact:
  - `p3_6q24_dual_boundary_crossover_anchor_probe/`
- settings:
  - `grouping_mode = candidate_anchor_hybrid`
  - `restart_selection_mode = margin_aware`
- result:
  - still `LE-GRA MVP = 0.5779436872241971`

Why this matters:

- unlike `o8` or `m4b`, the current minimal bridge does not immediately solve
  this regime
- that makes `q23/q24` a stronger next-step benchmark candidate rather than
  just another already-fixed case

Updated best next step:

- move the main breakthrough target to `q23/q24`
- do not expand broad matrices yet
- focus on the earliest late-phase crossover boundary:
  - `28.3s`
- the new working question should be:
  - how do we make LE-GRA generalize the secondary-weak switch one snapshot
    earlier?

Most promising next interventions on this regime:

1. localized boundary-aware supervision around `28.3`
2. temporal support replay from the early positive corridor into the late
   crossover onset
3. candidate-switch calibration specifically for the `ue5 -> ue6` transition

## P3.6q-25: once `28.3s` is included, the later crossover corridor is fully recoverable

Artifact:

- `P3_6Q_25_SINGLE_SUPPORT_CROSSOVER_TRANSFER_ZH.md`
- `p3_6q25_support283_test284_288_plain/`
- `p3_6q25_support283_test284_288_anchor_margin/`

Key result:

- if training/support already includes `28.3s`
- then both plain LE-GRA and anchor-margin variants recover
  `28.4s ~ 28.8s` completely

Interpretation:

- the late corridor itself is not the hard part
- the hard part is specifically the earliest onset at `28.3s`
- this is now best described as an earliest-onset crossover generalization
  failure

## P3.6q-26: replay cannot help before onset, and localized weighting still cannot move `28.3s`

Artifact:

- `P3_6Q_26_EARLIEST_ONSET_FAILURE_ZH.md`
- `p3_6q26_pre_onset_plain/`
- `p3_6q26_pre_onset_replay/`
- `p3_6q26_pre_onset_joint/`
- `p3_6q26_pre_onset_hard_negative/`

Focused test setup:

- train:
  - `<= 28.2s`
- test:
  - `28.3s` only

Most important results:

1. plain pre-onset transfer still fails
   - teacher:
     - `3|5 / 4|6`
   - LE-GRA:
     - `3|4|5|6`

2. replay cannot activate here
   - with:
     - `boundary_support_start = 27.9`
     - `boundary_support_positive_only = true`
   - result:
     - `boundary_support_selected_scenarios = 0`

3. learner-side localized supervision still does not move the onset
   - candidate-conditioned boundary weighting:
     - still fails
   - stronger frontier hard negatives:
     - still fails

Why this matters:

- `28.3s` is not a continuation of an already-positive corridor
- it is the first true split-onset point in this regime
- therefore replay-only logic has no positive examples to amplify before it
- the current failure is not just final grouping closure
- it is a failure to represent the earliest `ue5 -> ue6` secondary-weak switch
  early enough

Updated best next step:

1. stop doing replay-only or weight-only micro-tweaks on `28.3`
2. move to onset-aware structure or dataset-side onset shaping
3. best two candidates:
   - add temporal weak-candidate delta / rank-shift signals
   - redesign the regime so the first `ue5 -> ue6` handoff becomes a thin
     multi-snapshot onset corridor instead of a single-point cliff

## Additional interpretation: CQI granularity may be part of the bottleneck, but not the whole story

Current conclusion:

- the project is **not** currently using only raw CQI
- pure `CQI k-means` is only the weakest baseline
- the main learner already uses richer signals such as:
  - `cqi_history`
  - `rb_rates`-derived `cost_vec`
  - RB statistics (`mean/min/max/std`)
  - mobility/context features

Why this matters:

- the present `28.3s` onset failure cannot be explained simply as
  "CQI is quantized to `1..15`, so everything collapses"
- because even richer cost/context representations still fail at the first
  onset point

But the CQI concern is still useful:

- current exported coupled-radio schema already reserves
  `wideband_sinr_db`, `rsrp_dbm`, `rsrq_db`, and per-band `sinr_db`
- however the present exporter still leaves those fields empty

Updated research hypothesis:

- a meaningful next breakthrough path is to add continuous radio-quality
  measurements beyond CQI quantization
- best candidates:
  - `RSRP`
  - `RSRQ`
  - wideband `SINR`
  - per-band `SINR`

Why this is promising:

- these signals may expose the `ue5 -> ue6` weak-role handoff earlier than
  CQI / rate abstraction alone
- this is especially relevant for `q23/q26`, where the current failure is the
  earliest crossover onset rather than the later corridor

Recommended follow-up after resuming:

1. extend Simu5G export to populate radio-power / SINR fields
2. add a new focused feature ablation:
   - `history_cost_radio`
   - or `full_radio_context`
3. test only on `q23/q26` first before any larger matrix

## P3.6q-27: radio-aware learner path is ready, but the current coupled data still has 0% radio-signal coverage

Artifact:

- `P3_6Q_27_RADIO_SIGNAL_READINESS_ZH.md`
- `audit_radio_signal_coverage.py`
- `p3_6q27_q23_radio_coverage.csv`
- `p3_6q27_p35_radio_coverage.csv`

What was implemented:

1. end-to-end radio-aware feature support is now wired up
   - `simu5g_raw_radio_export.py`
   - `trace_io.py`
   - `run_p3_6_coupled_learner.py`
   - `le_gra_mvp.py`

2. new feature modes now exist
   - `history_cost_radio`
   - `full_radio_context`

3. raw-radio exporter is now backward-compatible
   - if optional raw fields exist, it preserves them
   - otherwise old raw traces still work

Most important readiness result:

- on the current main regime bundle:
  - `p3_6q23_dual_boundary_crossover_bundle`
- and on the earlier baseline bundle:
  - `p3_5_coupled_bundle`
- the optional radio fields still have `0%` coverage:
  - `wideband_sinr_db`
  - `rsrp_dbm`
  - `rsrq_db`
  - `mcs`
  - per-band `sinr_db`

Why this matters:

- the learner side is no longer the blocker for radio-aware experiments
- the current blocker is now data availability
- running `history_cost_radio` or `full_radio_context` on today's coupled
  bundles would only add zero-filled columns, not new information

Updated best next step:

1. do not start a radio-feature learner sweep yet
2. first extend the Simu5G recorder source so raw radio actually exports
   `SINR/RSRP/RSRQ/MCS`
3. rebuild a small coupled bundle and rerun `audit_radio_signal_coverage.py`
4. only after coverage becomes non-zero, run focused `q23/q26` onset tests

## P3.6q-28: source-hook audit shows the next real step is UE-PHY radio recorder expansion

Artifacts:

- `P3_6Q_28_SOURCE_HOOK_AUDIT_ZH.md`
- `p3_6q28_apply_radio_recorder_v2.sh`
- updated `p3_5_apply_recorders.sh`

What we confirmed:

1. current recorder is attached at the `LteMacEnb.cc` DL feedback path
2. `LteFeedback` already exposes:
   - `getBandCqi()`
   - `getWbCqi()`
3. `LteAmc` already exposes `getItbsPerCqi(cqi, dir)`
4. so the current recorder can be safely expanded immediately with:
   - `wideband_cqi`
   - `itbs`
5. the more important continuous signals are not imaginary:
   - `LteRealisticChannelModel` exposes `getSINR(...)`
   - `LteRealisticChannelModel` exposes `getRSRP(...)`
   - `LteFeedbackComputationRealistic` explicitly receives the per-band `snr` vector
   - `meanSnr(snr)` is already computed before wideband CQI mapping
6. `RSRQ` still does not have a clear low-cost hook in the current path

Why this matters:

- this is the first time we have pinned the radio-expansion blocker down to an exact source-layer issue
- the learner side is no longer the main unknown
- if we want to test the hypothesis that CQI quantization is hiding the real separability,
  the next meaningful experiment must come from a UE-PHY / feedback-computation recorder,
  not from another learner-only tweak

What was implemented this round:

1. `p3_5_apply_recorders.sh` now installs a richer v2 header on fresh environments:
   - `timestamp_s,ue_node_id,gnb_node_id,ue_module_path,band_index,cqi,tbs_bits_per_slot,total_bands,wideband_cqi,itbs`
2. `p3_6q28_apply_radio_recorder_v2.sh` upgrades an already-patched `LteMacEnb.cc`
   to the same v2 recorder without requiring a clean reinstall

Layered plan from here:

1. `Layer 1`:
   - apply recorder v2
   - rebuild Simu5G
   - rerun a small recorder smoke trace
   - verify raw CSV now contains `wideband_cqi,itbs`
2. `Layer 2`:
   - add UE-PHY / feedback-computation hook for:
     - `sinr_db`
     - `wideband_sinr_db`
     - `rsrp_dbm`
   - rerun `audit_radio_signal_coverage.py`
3. only after those continuous fields become non-zero, return to `q23/q26`
   focused learner validation

## P3.6r-8 breakthrough: resource-anchor candidate generation closes the new hard gap

Artifacts:

- `p3_6r8_q10_temporal_decoy_flicker_spec.json`
- `sweep_r8_learner_hooks.py`
- `_tmp_r8_hook_sweeps/leaderboard.csv`
- `_tmp_r8_hook_sweeps/resource_anchor_hybrid/teacher_imitation_diagnostics.csv`

Focused regime:

- bundle: `p3_6r8_q10_temporal_decoy_flicker_bundle/bundle`
- family: `1|2|3|4|5|6 @ gnb_2`
- split:
  - train: `27.7 ~ 28.0`
  - test: `28.1 ~ 28.2`

Key teacher pattern:

1. train includes both:
   - `27.7 ~ 27.9`: `1|3|4|5 / 2|6`
   - `28.0`: `1|3|4|5|6 / 2`
2. test also includes both:
   - `28.1`: `1|3|4|5 / 2|6`
   - `28.2`: `1|3|4|5|6 / 2`
3. so this is a real boundary regime, not a trivial always-pair or always-singleton case

What failed:

1. baseline LE-GRA on this split only reached `0.5552729409871294`
2. learner-only focused tweaks:
   - `scenario_focus`
   - `candidate_bce`
   - `frontier`
   - `prototype_membership`
   - `pair_warmup`
   all only recovered to `resource-cost` parity:
   - `0.5691723261457139`
3. the weak-score head itself remained misaligned:
   - it did not stably rank `ue2` as the top weak member
   - so candidate-membership / frontier losses were often reinforcing the wrong frontier

New insight:

1. the true blocker on `r8` was not "the learner cannot represent the structure"
2. the blocker was "the final candidate grouping set does not explicitly offer
   the top-cost anchor + plausible cost partner corridor"
3. for `28.1`, exact DP prefers `2|6`
4. for `28.2`, exact DP prefers singleton `2`
5. both decisions can be recovered if inference explicitly includes:
   - singleton top-cost-user candidate
   - top-cost-user + next-top-cost-partner candidates

What was implemented:

1. new grouping mode in `le_gra_mvp.py`:
   - `resource_anchor_hybrid`
2. this mode:
   - anchors the highest mean resource-cost user
   - explicitly enumerates:
     - singleton anchor vs rest
     - anchor + top-cost partner candidates
   - unions those candidates with the existing embedding k-means candidates
   - still uses exact DP utility selection to pick the final grouping

Result:

1. `resource_anchor_hybrid`:
   - teacher = `0.5776122002896149`
   - resource-cost = `0.5691723261457139`
   - LE-GRA = `0.5776122002896149`
2. `scenario_focus_resource_anchor` gives the same result
3. diagnostics confirm exact teacher imitation on both test points:
   - `28.1`: `2|6 / rest`
   - `28.2`: `2 / rest`

Interpretation:

1. this is a real post-plateau result:
   - we now have a second successful regime beyond `r4`
2. the improvement did **not** come from more learner-side loss tweaking
3. it came from a better structure-aware candidate space at inference time
4. this strongly suggests the next productive direction is:
   - localized candidate-space redesign
   - not more isolated BCE / frontier / warmup sweeps

Updated best comparison:

1. `r4` remains the strongest large-gap showcase:
   - teacher = LE-GRA = `0.5693854077668493`
   - resource-cost = `0.5425549335649255`
   - gap = `0.02683047420192386`
2. `r8` is now the best new hard-boundary success case:
   - teacher = LE-GRA = `0.5776122002896149`
   - resource-cost = `0.5691723261457139`
   - gap = `0.008439874143901016`

Recommended next step:

1. do not go back to learner-only local tweaks on `r8`
2. use `resource_anchor_hybrid` as the new structural baseline
3. next, search for additional families/regimes where:
   - top-cost anchor is stable
   - partner identity flickers across a narrow corridor
   - plain resource-cost k-means still misses at least one boundary point
4. if those regimes exist and `resource_anchor_hybrid` keeps winning,
   we can frame the contribution more clearly as:
   - "boundary-aware localized candidate generation"

## August 10 follow-up: `resource_anchor_hybrid` is a narrow but reproducible phase transition, not a one-off

Artifacts:

- `compare_resource_anchor_corridors.py`
- `_tmp_resource_anchor_corridor_compare/leaderboard.csv`
- `search_r8_boundary_variants.py`
- `r8_boundary_variant_search/leaderboard.csv`

What we tested:

1. first, we compared baseline LE-GRA vs `resource_anchor_hybrid` on four
   representative corridors:
   - `q10_main`
   - `r8_boundary`
   - `n3_long`
   - `i2_m4b`
2. then we ran a local 16-variant sweep around `r8` by only perturbing the
   boundary-relevant knobs:
   - `ue4` singleton-time decoy strength
   - `ue4` pair-time decoy strength
   - `ue6` pair-time support
   - `ue6` singleton-time support

Main result:

1. `resource_anchor_hybrid` is **not** a universal improvement
2. on easy / already-solved corridors:
   - `q10_main`
   - `n3_long`
   - `i2_m4b`
   it adds zero gain over baseline
3. on the hard `r8_boundary` corridor:
   - baseline LE-GRA = `0.5552729409871294`
   - resource-anchor LE-GRA = `0.5776122002896149`
   - exact gain = `+0.02233925930248548`
4. the local `r8` sweep shows a clean threshold:
   - when `ue4` singleton-time `rb_scale = 0.68`, baseline still fails and
     resource-anchor fully closes the gap
   - when `ue4` singleton-time `rb_scale = 0.72`, baseline already recovers
     teacher by itself, so resource-anchor adds nothing

Interpretation:

1. this is strong evidence that the new mechanism is solving a very specific
   regime:
   - strongest weak user is stable
   - the second weak partner is real but fragile
   - a boundary-time decoy can temporarily steal the cost ranking
2. so the contribution is becoming sharper:
   - not "a better general learner"
   - but "a better localized candidate generator for weak-partner flicker"
3. the search also tells us why progress felt slow earlier:
   - the informative band is narrow
   - many nearby variants collapse back into a trivially solved regime

Practical next move:

1. stop broad random sweeps again
2. if continuing this line, search specifically for more regimes with the same
   signature:
   - teacher-resource gap > 0
   - baseline LE-GRA gap > 0
   - top-cost anchor stable
   - second weak partner flickers across a narrow corridor
3. if we cannot find more than a small handful of such regimes, the honest
   paper framing should be:
   - a targeted mechanism for narrow boundary dual-weak corridors
   - not a broad all-regime learner improvement

## August 11 update: anti-CQI-hard mined regime finally re-opens a meaningful method gap

Artifacts:

- `run_anti_cqi_hard_regime.py`
- `anti_cqi_hard_regime_pilot/main_comparison.csv`
- `anti_cqi_hard_regime_pilot/scenario_audit.csv`
- `anti_cqi_hard_regime_pilot/scenario_summary.csv`
- `anti_cqi_hard_regime_pilot/teacher_imitation_diagnostics.csv`
- `analysis_method_metrics/method_metrics_report_zh.html`

What changed:

1. we added a new generator mode in `le_gra_mvp.py`:
   - `scenario_mode="anti_cqi_hard"`
2. this mode intentionally creates families where:
   - wideband CQI remains narrow
   - RB-level profile shape differs
   - temporal trend differs
   - previous-quality prior differs
   - RB budget is tighter
3. the goal is explicit:
   - make pure `CQI k-means` under-informative
   - while keeping richer `resource-cost` / `multi-feature` signals useful
4. we then built a mining script that does not accept arbitrary random cases;
   it filters for scenarios where:
   - `teacher_groups >= 2`
   - `cqi_span` is small
   - `teacher > no-grouping`
   - `teacher > CQI`
   - same-CQI users still show nontrivial cost dispersion

Pilot result (`anti_cqi_hard_regime_pilot`, train=`16`, test=`8`, epochs=`3`):

- `No grouping = 0.5555175114173516`
- `CQI k-means = 0.5631905221082654`
- `Resource-cost k-means = 0.5910372810788701`
- `Multi-feature k-means = 0.5880622570961298`
- `LE-GRA MVP = 0.5980196882224645`
- `Offline teacher = 0.6317218347486369`

ADR ordering in the same pilot:

- `No grouping = 3000.0`
- `CQI k-means = 3080.208333333333`
- `Multi-feature k-means = 3453.125`
- `LE-GRA MVP = 3700.0`
- `Resource-cost k-means = 3721.875`
- `Offline teacher = 4156.770833333334`

Why this matters:

1. this is the clearest recent evidence that the "all grouping-aware methods tie"
   problem was partly a benchmark-design problem
2. under the mined anti-CQI-hard corridor:
   - `CQI k-means` is only slightly above `No grouping`
   - `resource-cost` and `multi-feature` regain visible value
   - `Offline teacher` still keeps a real gap
3. this directly supports the reframed paper/mainline narrative:
   - `CQI-only grouping` is too coarse
   - `resource-cost` is a more allocation-aligned practical baseline
   - `multi-feature` is a richer representation baseline
   - `LE-GRA` is still exploratory unless it can consistently beat the stronger
     feature-based baselines

Current bottleneck:

1. the pilot proves gap creation is possible
2. but we still do **not** know whether the gap is stable after scaling to a
   more formal benchmark size
3. we also do not yet know whether `LE-GRA` can beat `resource-cost` reliably,
   or whether `resource-cost` remains the best practical method

Recommended next step:

1. do **not** go back to the old plateau families first
2. scale `anti_cqi_hard` into a formal benchmark run, for example:
   - train `96`
   - test `32`
   - epochs `10`
3. keep the generator fixed while scaling
4. evaluate whether the ordering remains:
   - `teacher > LE-GRA / resource-cost / multi-feature > CQI > no-grouping`
5. only after that, decide whether to:
   - refine LE-GRA further
   - or fully re-center the thesis/report around `resource-cost` and
     `multi-feature`

## August 21 update: interview-prep pivot, dispersion-stratified benchmark suite, and offline-teacher contiguity fix

This entry closes the gap between the August 11 log above and the current
state of the repo. It was written by Claude Code, not Codex; going forward,
prefer the memory store at
`C:\Users\Weber\.claude\projects\c--Users-Weber-Documents-LE-GRA-MVP\memory\`
(`MEMORY.md` there is the index) for anything after this date -- it is
updated more granularly than this file.

### Context: the actual goal is interview prep, and LE-GRA is the headline again

The user is preparing for a job interview that references their own
published paper (Huang & Liao, IEEE MSWiM 2025, CQI-based k-means MBS
grouping) as a resume topic. All work in this repo beyond the paper itself
is framed, honestly, as the user's own post-publication extension work --
never presented as part of the published paper. Sometime after the August 11
entries above (in sessions not captured in this file), the project narrative
reverted from "resource-cost/multi-feature mainline, LE-GRA secondary" back
to: **LE-GRA (learned embedding + k-means + a CQI-fallback ensemble) is the
headline extension; resource-cost k-means and multi-feature k-means are
closed ablation baselines under it.**

### What was built/found this session

1. **Paper-style dispersion-stratified benchmark**: `run_dispersion_metrics_breakdown.py`
   and `run_dispersion_metrics_breakdown_legra.py` (the latter adds LE-GRA,
   training one fresh model per dispersion level). Mirrors the paper's own
   Figure 4 -- fixed scenario conditions, only CQI dispersion (low/mid/high)
   varies, each method reported as % of the best method in that cell. This
   replaced an earlier pooled/randomized-dispersion comparison that diluted
   the real dispersion-dependent effects the user's paper shows.
2. **New `mid_v2` dispersion calibration** in `le_gra_mvp.py`'s
   `generate_scenario` (additive only -- the original `"mid"` branch is
   untouched): the original `"mid"` never pushed worst-case CQI below ~9,
   so "no grouping" barely lost to grouped methods at mid dispersion, unlike
   the paper's own mid-dispersed condition. `mid_v2` widens the distance
   range and steepens the CQI-distance slope to produce a real low-CQI tail,
   calibrated only against the resulting CQI histogram (not against any
   grouping-method outcome).
3. **User-count scaling confirmed** (n=24/50/150/300/500, see
   `dispersion_metrics_breakdown_n*_results/`): larger populations
   independently amplify the "no grouping" collapse at mid dispersion (ADR
   ratio 85%->43% from n=24 to n=500), because a bigger population is more
   likely to contain a catastrophically bad-CQI outlier. At n>=150 and high
   dispersion, "no grouping"'s absolute ADR floors at exactly the lowest
   video-bitrate tier and stops moving with n (a floor effect, not noise).
4. **Interview prep materials**: `INTERVIEW_PREP_GUIDE.md` +
   `interview_prep_guide.html` (rehearsal doc, published as a Claude
   artifact) and `metrics_slides.html` (a click-through slide deck of the
   dispersion-stratified comparison across all 5 metrics x 3 dispersions x
   6 methods, also published as an artifact).
5. **Found and fixed a real limitation in the "Offline teacher" baseline**:
   `offline_teacher_groups`/`offline_teacher_groups_fast` are, by their own
   docstring, only exact within contiguous-by-resource-cost partitions after
   sorting users -- not a true global optimum. This surfaced because the
   user noticed "Offline teacher" was not the utility-maximum at low
   dispersion in `dispersion_metrics_breakdown_legra_n150_results` (it
   should be, since utility is literally its own optimization objective).
   Root cause (confirmed via a concrete case study): at low CQI dispersion,
   CQI collapses to only ~3 distinct values, so many users tie on CQI while
   the continuous resource-cost sort key used for contiguity is near-noise
   among those ties -- the contiguous-by-cost DP then mixes different CQI
   values into the same group, while CQI k-means (which clusters directly
   on CQI) does not.
   - Added `offline_teacher_groups_multikey` (runs the same exact DP under 3
     sort keys -- resource cost, raw CQI, CQI-then-cost -- keeps whichever
     scores highest) and `offline_teacher_groups_bruteforce_exact` (true
     global optimum via full partition enumeration, small n only) to
     `le_gra_mvp.py`.
   - Validated at small scale (`validate_contiguity_assumption.py`, n=6/8/10/12,
     195 scenarios total): `multikey` matched the true brute-force global
     optimum in **100%** of all scenarios; plain `fast` lost to the true
     optimum in up to 100% of low-dispersion scenarios (worse as n grows).
   - Confirmed at the real n=150 scale used for the dispersion breakdown
     (`run_teacher_multikey_full_scale.py`, 600 scenarios/dispersion): the
     low-dispersion loss rate of plain `fast` (100% of 600 scenarios losing
     to the best heuristic on utility) drops to **0%** with `multikey`;
     mid/high dispersion (already near-100% correct) also tighten to 0%/0.2%.
   - `metrics_slides.html`'s utility slide now explains this limitation and
     the validated fix explicitly, instead of calling the teacher a
     "theoretical ceiling" (relabeled "近似最優解" / approximate-optimal
     everywhere in the deck).
   - First attempt at the small-scale validation used the wrong RB-budget
     ratio (copy-pasted from a different sibling script's local constant,
     1.0 instead of the project's actual medium-load convention of 0.25
     imported from `run_standard_matrix.LOAD_RATIOS`) -- caught by noticing
     the recomputed numbers didn't match the cached CSV, fixed, and rerun
     before being reported. See the `feedback-research-rigor` memory entry.
6. **Found, not yet applied**: `run_dispersion_metrics_breakdown_legra.py`
   wires "LE-GRA MVP" to plain `mvp.learned_grouping(...)`, not the
   already-implemented, already-validated `learned_grouping_with_cqi_fallback`
   (which takes whichever of {CQI k-means, LE-GRA} the exact-DP evaluator
   actually prefers per scenario, so it can never score below plain CQI
   k-means). This is very likely why LE-GRA loses to CQI k-means at high
   dispersion in the n=150 breakdown (83.7% vs 85.4% of best). User declined
   to spend the compute rerunning this as of 2026-08-21; see the
   `legra-cqi-fallback-unused` memory entry if revisiting.

### Repo state at this handoff

- `le_gra_mvp.py`: modified (added `mid_v2` dispersion branch,
  `offline_teacher_groups_multikey`, `_all_partitions_upto_k`,
  `offline_teacher_groups_bruteforce_exact`; nothing else touched).
- New scripts: `run_dispersion_metrics_breakdown.py`,
  `run_dispersion_metrics_breakdown_legra.py`,
  `validate_contiguity_assumption.py`, `run_teacher_multikey_full_scale.py`.
- New result directories (all committed):
  `dispersion_metrics_breakdown_results/`,
  `dispersion_metrics_breakdown_n150_results/`,
  `dispersion_metrics_breakdown_n150_full_results/`,
  `dispersion_metrics_breakdown_n300_results/`,
  `dispersion_metrics_breakdown_n500_results/`,
  `dispersion_metrics_breakdown_legra_n150_results/`,
  `contiguity_validation_results/`, `teacher_multikey_full_scale_results/`.
- New interview-prep artifacts: `INTERVIEW_PREP_GUIDE.md`,
  `interview_prep_guide.html`, `metrics_slides.html`.
- All of the above committed and pushed to `origin/main` at commit
  `df2a337` ("Add dispersion-stratified benchmark suite and offline-teacher
  contiguity fix"), 2026-08-21.

### Recommended next step (as of 2026-08-21)

1. If asked to widen LE-GRA's margin over CQI k-means legitimately: swap in
   `learned_grouping_with_cqi_fallback` for the n=150 breakdown (see item 6
   above) before trying anything else -- it is already built and validated,
   not a new design.
2. Do not try to make `multi-feature k-means` beat CQI k-means by a wide
   margin in "aligned" mode -- in that mode, RB rates are literally
   `CQI + noise`, so CQI is already close to a sufficient statistic and no
   clustering method has much room above it. Multi-feature's role is to show
   that raw feature richness alone (without learning) does not reliably beat
   CQI -- inflating its margin would undermine that ablation's point.
   `multi_feature_kmeans_grouping` already z-score-normalizes its feature
   matrix before k-means, so the common "unnormalized large-magnitude
   feature dominates the distance metric" failure mode is not the issue.
3. If extending the other 4 metrics (adr_kbps, served_ratio, average_quality,
   system_spectral_efficiency) to the `multikey` teacher for a fully updated
   slide dataset: only `utility` was recomputed so far; each additional
   metric needs its own re-evaluation pass over the same 1800 scenarios
   (~1.6h at n=150 for utility alone, so budget accordingly).
