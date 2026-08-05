# LE-GRA Research Session Handoff

Last updated: 2026-08-05

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

## Repository State at Handoff

Git contains all source patches, reproducible scripts, raw evidence, normalized
radio output, and the final P3.5 coupled bundle. It does not contain the WSL/Nix
simulator installations. On a new computer, first run the pure-Python
`run_p3_5_coupled_test.py` against committed evidence; only install the P3.5
runtime when a new coupled simulation must be generated. The current primary
research artifacts are `medium_matrix_results_v2_after_grad_fix/`,
`p3_4_actual_radio/`, and `p3_5_coupled_bundle/`.
