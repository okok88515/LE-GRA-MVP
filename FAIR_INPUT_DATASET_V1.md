# Fair-input benchmark dataset v1

This dataset is the fixed input source for controlled, non-learned grouping
comparisons.  It separates physical/user state from the load applied during
allocation so every method receives the same observations and the same
allocator evaluates every proposed partition.

## Fixed dimensions

- users per snapshot: 150
- RBs per user: 100
- snapshots per dispersion/profile cell: 600 (30 seeds x 20 draws)
- CQI dispersions: `low`, `mid_v2`, `high`
- frequency profiles: `aligned`, `moderate`, `strong`
- load levels: `light=0.50`, `medium=0.25`, `heavy=0.10`

The physical arrays are stored once per `(dispersion, frequency_profile)` in
compressed NumPy shards.  `scenario_index.csv` expands each physical snapshot
to the three load levels without duplicating the large per-RB matrix.

## Common decision-time inputs

Every deployable method may use:

- five-step CQI history and current CQI;
- the complete per-RB achievable-rate profile;
- previous video-quality state;
- the current RB budget and total RB count.

Mobility fields are retained for auditing but are not part of the v1 common
feature set.  Optional RSRP/RSRQ/SINR/MCS fields are not fabricated.

## Previous-quality rule

`previous_quality` is an exogenous, deterministic application-state proxy
computed only from information available before the current decision:

1. map the previous CQI (`t-1`) to the six quality levels;
2. compute the CQI trend from `t-4` to `t-1`;
3. apply one-level hysteresis: a clearly improving trend keeps the prior
   quality one level lower, while a clearly degrading trend keeps it one
   level higher.

This deliberately replaces the legacy `current_cqi // 3` construction.  It
creates same-current-CQI users with different switching states without using
method outcomes or test utility.

The state is shared across the three load counterfactuals.  This is a
controlled snapshot study: changing load must not silently change the user or
channel state being compared.

## Frequency profiles

- `aligned`: per-RB CQI is current CQI plus low independent noise (standard
  deviation 0.25 CQI), representing an approximately flat RB response.
- `moderate`: smooth position/mobility-conditioned notches and ripples; CQI
  remains informative but incomplete.
- `strong`: left/right/flat/bursty frequency-selective shapes recentered to
  preserve approximately the same wideband CQI.

All three profiles share identical CQI histories, current CQI, mobility, and
previous-quality arrays within a dispersion.  Only the per-RB rate matrix
changes.

## Files

- `manifest.json`: protocol, source hashes, array schema, and shard checksums.
- `scenario_index.csv`: one row per physical snapshot x load counterfactual.
- `data_quality_summary.csv`: distribution and redundancy audit by cell.
- `shards/*.npz`: compressed source arrays.

The generated dataset directory is intentionally ignored by git because it is
large and exactly reproducible.  The builder, validator, and this protocol are
the version-controlled source of truth.

## Build and validate

```powershell
python build_fair_input_dataset.py
python validate_fair_input_dataset.py fair_input_dataset_v1
```

Use `--snapshots-per-seed` and `--seeds` for a smaller smoke build.  A smoke
build is not a substitute for the fixed full protocol above.
