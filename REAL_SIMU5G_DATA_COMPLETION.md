# Real Simu5G data completion status

Last checked: 2026-08-25

## What is present

- Three committed mobility exports (`raw`, `mid`, `high`), but all three are
  byte-identical and therefore represent one mobility trajectory.
- `real_validation_results.csv`, containing 15 usable adjacent snapshots per
  dispersion/load cell.
- Power-setting configs and `run_p3_7.sh` documenting the original run.

## Recovery completed on 2026-08-24

The three files referenced by `parse_real_simu5g_data.py` were reconstructed
with OMNeT++ 6.3.0, INET 4.6.0, Simu5G 1.4.3, and Veins 5.3.1 and restored to
the Windows workspace:

- `real_simu5g_data/raw_radio.csv`
- `real_simu5g_data/mid_raw_radio.csv`
- `real_simu5g_data/high_raw_radio.csv`

The recovery rebuilt the P3.7 scenario from the committed P3.7 configs and
route, the P3.6 launch/SUMO config, and Simu5G's original NR cars SUMO network
assets.  Existing recorder hooks and compiled libraries were verified before
the runs.  Full hashes and row counts are recorded in
`real_simu5g_data/recovery_manifest.json`.

All three datasets parse to 15 complete scenarios with 24 users, 25 bands,
and five CQI history steps.  Re-running `run_real_data_validation.py` produced
the committed `real_validation_results.csv` exactly (no content diff).

## Multi-seed completion on 2026-08-25

`real_simu5g_multiseed_data/` now contains protocol-v3 outputs for:

- 10 independent seeds (`1..10`)
- 3 radio settings (`low`, `mid`, `high`)
- 30 separately preserved runs
- 15 complete scenarios per run
- 450 learner-facing scenarios total

Each seed has a different, explicitly generated mobility trajectory.  For a
given seed, low/mid/high use the same mobility input and differ only in radio
power.  Every run records the exact OMNeT++ and SUMO seed, generated per-car
speed factors, scenario files, raw CSV hashes, row counts, simulator versions,
timestamps, and duration.

`validate_real_simu5g_multiseed.py` verified all gzip hashes, all 30 parsable
runs, 10 unique mobility hashes across seeds, and one shared mobility hash
across the three dispersions for each seed.  The machine-readable results are:

- `real_simu5g_multiseed_data/aggregate_manifest.json`
- `real_simu5g_multiseed_data/multiseed_qa.csv`

Aggregate CQI mean / mean within-run standard deviation:

- low: `14.761 / 0.602`
- mid: `12.583 / 2.182`
- high: `9.188 / 3.010`

The 10-seed exploratory target is complete.  A 20-seed expansion remains the
target before making a confirmatory statistical claim.

## Remaining measurement limitations

1. Record native wideband CQI if available and actual previous application
   quality instead of forcing it to zero.
2. Record RSRP, RSRQ, SINR, and MCS if they are included in the final fair
   comparison variable set.
3. Split, bootstrap, and test at the seed/trajectory level; never treat the 15
   adjacent snapshots within a run as independent samples.
4. Low dispersion remains strongly saturated near CQI 15. Add a low-dispersion
   but non-saturated power setting before using that condition to argue broad
   generalization.

Changing transmit power affects both mean channel quality and its spread.
Accordingly, the eventual QA report must show CQI mean, standard deviation,
and quantiles; the labels low/mid/high cannot be accepted from config names
alone.

The missing-raw-data and minimum multi-seed blockers are resolved.  Application
state, optional native radio features, low-CQI saturation, and the 20-seed
confirmatory target remain limitations.
