# LE-GRA MVP

This folder contains a minimal runnable prototype for:

**Learning-based Embedding Grouping and Resource Allocation (LE-GRA)**

The goal is to test whether learned user embeddings can improve 5G vehicular
MBS grouping beyond raw CQI-based grouping.

## What This First Version Does

1. Generates synthetic vehicular MBS scenarios.
2. Builds per-user features:
   - 5-step CQI history,
   - RB-level rate statistics,
   - mobility features,
   - resource-cost vector for video quality levels.
3. Uses an offline teacher to generate pseudo-labels:
   - sort users by resource-cost score,
   - exhaustively search boundary cuts up to `Kmax` groups,
   - for each candidate grouping, solve the group's video-quality assignment
     exactly under the RB budget with dynamic programming,
   - select the grouping with the highest QoE utility.
4. Trains an MLP encoder with pairwise contrastive loss.
5. Clusters learned embeddings with k-means.
6. Compares:
   - no grouping,
   - CQI k-means,
   - resource-cost k-means,
   - offline teacher,
   - LE-GRA.

## Run

```powershell
python .\le_gra_mvp.py
```

For a quicker run:

```powershell
python .\le_gra_mvp.py --train-scenarios 80 --test-scenarios 30 --epochs 5
```

To stress-test CQI-only grouping, run CQI-ambiguous scenarios:

```powershell
python .\le_gra_mvp.py --scenario-mode ambiguous
```

The standard matrix also exposes experimental pair sampling for learner-focused
studies. For a genuine hard-negative comparison with 24 users, use a pair cap
below the number of available negative pairs, for example:

```powershell
python .\run_standard_matrix.py --scenario-modes ambiguous --load-levels light medium `
  --kmax-values 3 --pair-sampling hard_negative --pairs-per-class 64
```

The formal default remains `random_balanced` with 160 pairs per class. See
`P2_HARD_NEGATIVE_STUDY_ZH.md` before changing that default.

To audit the synthetic inputs and teacher-label landscape without training the
learner, run:

```powershell
python -u .\run_data_audit.py
```

The current findings and interpretation are documented in
`P2_5_DATA_AUDIT_ZH.md`.

The bounded P2.6 mixed-load context comparison can be reproduced with:

```powershell
python -u .\run_context_study.py
```

See `P2_6_CONTEXT_STUDY_ZH.md`; the current leading feature candidate is
`history_cost_quality`.

## SUMO/Simu5G Trace Interface

The simulator boundary is defined in `TRACE_SCHEMA.md`. A trace bundle contains
`scenarios.csv`, `users.csv`, and `rb_rates.csv`; load it with `trace_io.py`.
Verify the interface and offline-teacher invariance with:

```powershell
python -u .\run_trace_roundtrip.py
```

See `P3_0_TRACE_INTERFACE_ZH.md` for the P3.0 acceptance results and remaining
Simu5G export risks.

Convert SUMO FCD mobility output into P3.1 staging tables with:

```powershell
python -u .\sumo_fcd_to_mobility.py `
  --fcd path\to\mobility.fcd.xml `
  --gnbs path\to\gnbs.csv `
  --min-users 24 --max-users 24 `
  --out-dir sumo_mobility_staging
```

The staging tables deliberately omit radio and QoE values until the P3.2
Simu5G join. See `SUMO_MOBILITY_SCHEMA.md` and verify the adapter with
`python -u .\run_sumo_mobility_test.py`.

Join normalized Simu5G radio exports with SUMO mobility and produce a complete
P3.0 bundle with:

```powershell
python -u .\join_sumo_simu5g.py `
  --mobility-dir sumo_mobility_staging `
  --radio-dir simu5g_radio_export `
  --min-users 24 --max-users 24 `
  --out-dir sumo_simu5g_trace_bundle
```

The required radio tables are defined in `SIMU5G_RADIO_SCHEMA.md`. Run
`python -u .\run_simu5g_join_test.py` for the P3.2 format-level acceptance test.

P3.3 has also run the official Simu5G NR `Single-UE` tutorial in a dedicated
`opp_env` WSL installation. See `P3_3_ENVIRONMENT_BRINGUP_ZH.md` and the
`p3_3_*.sh` scripts for the exact environment checks, tutorial run, and signal
audit. Native results expose CQI, SINR, served-block, HARQ, and throughput
signals; a custom recorder is still required for the complete per-UE/per-RB
counterfactual rate matrix used by the offline teacher.

P3.4 supplies that matrix with a versioned Simu5G patch and normalized
exporter. Apply/build the recorder with `p3_4_apply_and_build.sh`, run either
small scenario with `p3_4_run_recorder.sh` or
`p3_4_run_multi_ue_recorder.sh`, and validate the captured radio data with:

```powershell
python -u .\run_p3_4_export_test.py
python -u .\run_p3_4_multi_ue_validation.py
```

See `P3_4_SIMU5G_RADIO_EXPORTER_ZH.md`. P3.4 was a real-radio acceptance step,
not a complete SUMO+Simu5G training corpus. P3.5 resolves stable
cross-simulator IDs and shared timestamps; measured video quality remains
P3.6 work.

P3.5 now provides a one-clock SUMO+Veins+Simu5G smoke path. Install/check the
separate compatible environment with `p3_5_install_environment.sh` and
`p3_5_check_environment.sh`, apply the two recorders, run the official NR cars
case, and verify the final bundle with:

```powershell
python -u .\run_p3_5_coupled_test.py
```

See `P3_5_SUMO_SIMU5G_COUPLING_ZH.md`. This proves coupling and trace integrity;
the two-vehicle, all-CQI-15 smoke trace is deliberately not treated as a
learner-training corpus. Real video quality and a more informative channel/load
scenario remain the next data-quality milestone.

For cross-computer continuation, read `SESSION_HANDOFF.md`, then use the exact
prompt in `NEXT_SESSION_PROMPT.md`. `P3_6_NEXT_STEPS_ZH.md` defines the next
data-quality gates before any real-trace learner experiment is allowed.

Scenario modes:

- `aligned`: RB-level rates are strongly aligned with wideband CQI.
- `ambiguous`: users can share the same wideband CQI but have different
  RB-level profiles, mobility trends, and previous video quality.
- `mixed`: half aligned, half ambiguous.

## Resource Pressure and Spectral Efficiency

For a single run, set the available-RB ratio explicitly. For example, a heavy
load with 10% of the configured RBs available is:

```powershell
python .\le_gra_mvp.py --rb-budget-ratio 0.10
```

The standard matrix exposes three reproducible load levels:

- `light`: 50% of RBs available,
- `medium`: 25% of RBs available,
- `heavy`: 10% of RBs available.

```powershell
python .\run_standard_matrix.py --load-levels light medium heavy
```

Results include two multicast-aware spectral-efficiency metrics. Used-bandwidth
SE divides successfully delivered user bitrate by the bandwidth actually used;
system SE uses all currently available RB bandwidth as the denominator. The
latter is the primary metric for fixed-bandwidth comparisons. Interpret both
together with `served_ratio`, `unserved_ratio`, and `average_quality`, so a
method cannot appear strong merely by serving fewer users or lowering quality.

The clustering head uses deterministic multi-start k-means by default. Change
the number of initializations for focused studies with:

```powershell
python .\run_standard_matrix.py --kmeans-n-init 10
```

Main evaluation and teacher-imitation diagnostics reuse the same cached
groupings, so their reported utility and partition-agreement metrics refer to
the exact same clustering result.

## Notes

This is intentionally simple. It is meant to validate the research pipeline,
not to be the final simulator. The next step is to replace the synthetic
scenario generator with Simu5G/OMNeT++ traces and replace the simplified
allocation logic with your full k-GBRM phase-2 implementation.

`Kmax` defaults to 5. This is not just a rule of thumb: in MBS subgrouping,
too many groups reduce multicast gain, increase control/signaling overhead, and
make offline teacher search expensive. For a paper, report sensitivity results
for `Kmax = 3, 4, 5, 6` and show that performance saturates around the chosen
value.
