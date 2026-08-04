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
