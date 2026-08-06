# LE-GRA Research Session Handoff

Last updated: 2026-08-06

This document is the continuity note for resuming the LE-GRA discussion in a
new Codex task or on another computer. After pulling the repository, ask Codex
to read this file together with `medium_matrix_results/*.csv` before proposing
the next experiment.

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

## Repository State at Handoff

Git contains all source patches, reproducible scripts, raw evidence, normalized
radio output, and the final P3.5 coupled bundle. It does not contain the WSL/Nix
simulator installations. On a new computer, first run the pure-Python
`run_p3_5_coupled_test.py` against committed evidence; only install the P3.5
runtime when a new coupled simulation must be generated. The current primary
research artifacts are `medium_matrix_results_v2_after_grad_fix/`,
`p3_4_actual_radio/`, and `p3_5_coupled_bundle/`.
